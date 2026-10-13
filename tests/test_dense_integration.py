"""Real exact pgvector ranking and durable query leases with software-only embeddings."""

from threading import Event
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from rag_api.main import create_app
from rag_core.chunking import ChunkConfig
from rag_core.database import create_database_engine
from rag_core.dense_searches import DenseSearchQueue
from rag_core.errors import LostLease, PlatformError
from rag_core.indexes import IndexCreate, IndexQueue, SearchInput
from rag_core.settings import Settings
from rag_core.tokenization import PinnedTokenizer
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError
from test_embeddings import encoded
from test_indexes_integration import setup as setup  # shared isolated corpus/tokenizer fixture

pytestmark = pytest.mark.integration


def prepare(
    setup: tuple[Settings, UUID, PinnedTokenizer], monkeypatch: pytest.MonkeyPatch
) -> tuple[Engine, IndexQueue, UUID]:
    settings, corpus, _ = setup
    engine = create_database_engine(settings)
    queue = IndexQueue(engine, settings)
    vectors = encoded([[1.0] + [0.0] * 383, [0.6, 0.8] + [0.0] * 382])
    monkeypatch.setattr("rag_core.indexes.run_embeddings", lambda *args, **kwargs: vectors)
    index = queue.create(
        IndexCreate(
            corpus_version_id=corpus,
            retrieval="dense",
            chunking=ChunkConfig(strategy="section", max_tokens=254),
        )
    )
    claim = queue.claim()
    assert claim and claim[0] == index.id
    queue.process(*claim, Event())
    assert queue.get(index.id).state == "ready", queue.get(index.id)
    return engine, queue, index.id


def test_exact_cosine_lineage_idempotent_preview_and_sql_immutability(
    setup: tuple[Settings, UUID, PinnedTokenizer],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, store, index_id = prepare(setup, monkeypatch)
    settings, _, _ = setup
    queries = DenseSearchQueue(engine, settings)
    query = encoded([[1.0] + [0.0] * 383])
    monkeypatch.setattr("rag_core.dense_searches.run_embeddings", lambda *args, **kwargs: query)
    try:
        with TestClient(create_app(settings)) as client:
            payload = {"query": "transaction", "context_tokens": 3}
            response = client.post(f"/api/v1/indexes/{index_id}/dense-searches", json=payload)
            assert response.status_code == 202, response.text
            search_id = UUID(response.json()["id"])
            assert client.post(f"/api/v1/indexes/{index_id}/dense-searches", json=payload).json()[
                "id"
            ] == str(search_id)
            assert (
                client.post(f"/api/v1/indexes/{index_id}/search", json=payload).status_code == 409
            )
            claim = queries.claim()
            assert claim and claim[0] == search_id
            queries.process(*claim, Event())
            row = client.get(f"/api/v1/dense-searches/{search_id}").json()
            assert row["state"] == "completed", row
            result = row["result"]
            assert [hit["chunk"]["ordinal"] for hit in result["hits"]] == [0, 1]
            assert [hit["score"] for hit in result["hits"]] == pytest.approx([1.0, 0.6])
            assert result["context"]["token_count"] <= 3
            assert result["context"]["truncated_chunk_ids"]
            assert result["hits"][0]["chunk"]["spans"][0]["section_id"]
            assert client.post(f"/api/v1/dense-searches/{search_id}/retry").status_code == 409
            assert (
                client.post(
                    f"/api/v1/indexes/{index_id}/dense-searches", json={"query": "word " * 255}
                ).status_code
                == 422
            )
        for sql, value in [
            (
                "UPDATE chunk_embeddings SET compatibility_key='changed' WHERE index_id=:id",
                index_id,
            ),
            ("DELETE FROM chunk_embeddings WHERE index_id=:id", index_id),
            ("UPDATE dense_searches SET request='{}' WHERE id=:id", search_id),
            ("UPDATE dense_searches SET state='pending',result=NULL WHERE id=:id", search_id),
        ]:
            with pytest.raises(IntegrityError), engine.begin() as connection:
                connection.execute(text(sql), {"id": value})
        changed = query.model_copy(deep=True)
        changed.metadata["artifact_hashes"] = {"different": "0" * 64}
        with pytest.raises(PlatformError, match="artifacts"):
            store.dense_result(index_id, SearchInput(query="transaction"), changed)
    finally:
        engine.dispose()


def test_dense_shutdown_reclaim_stale_owner_failure_and_retry(
    setup: tuple[Settings, UUID, PinnedTokenizer],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, _, index_id = prepare(setup, monkeypatch)
    settings, _, _ = setup
    queue = DenseSearchQueue(engine, settings)
    try:
        preview = queue.create(index_id, SearchInput(query="transactions"))
        first = queue.claim()
        assert first
        stopped = Event()
        stopped.set()
        monkeypatch.setattr(
            "rag_core.dense_searches.run_embeddings", lambda *args: encoded([[1.0] + [0.0] * 383])
        )
        queue.process(*first, stopped)
        assert queue.get(preview.id).state == "running" and queue.get(preview.id).result is None
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE dense_searches SET lease_expires_at=now()-interval '1 second' "
                    "WHERE id=:id"
                ),
                {"id": preview.id},
            )
            assert queue.claim() is None
        second = queue.claim()
        assert second and second[1] != first[1]
        with pytest.raises(LostLease):
            queue.heartbeat(*first)
        queue.fail(*second, PlatformError("embedding_timeout", "Software timeout fixture"))
        assert queue.get(preview.id).state == "failed"
        queue.retry(preview.id)
        third = queue.claim()
        assert third
        queue.process(*third, Event())
        assert queue.get(preview.id).state == "completed"
    finally:
        engine.dispose()


def test_incomplete_embeddings_roll_back_every_chunk(
    setup: tuple[Settings, UUID, PinnedTokenizer],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, corpus, _ = setup
    engine = create_database_engine(settings)
    queue = IndexQueue(engine, settings)
    monkeypatch.setattr(
        "rag_core.indexes.run_embeddings", lambda *args, **kwargs: encoded([[1.0] + [0.0] * 383])
    )
    try:
        index = queue.create(
            IndexCreate(
                corpus_version_id=corpus,
                retrieval="dense",
                chunking=ChunkConfig(strategy="section", max_tokens=254),
            )
        )
        claim = queue.claim()
        assert claim
        queue.process(*claim, Event())
        assert queue.get(index.id).state == "failed"
        assert queue.get(index.id).error_code == "embedding_mismatch"
        with engine.connect() as connection:
            for table in ("index_chunks", "chunk_embeddings"):
                assert (
                    connection.scalar(
                        text(f"SELECT count(*) FROM {table} WHERE index_id=:id"), {"id": index.id}
                    )
                    == 0
                )
    finally:
        engine.dispose()
