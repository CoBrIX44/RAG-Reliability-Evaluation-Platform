"""Real PostgreSQL locking/search and tokenizer-library fixtures; disposable rag_test only."""

import hashlib
import json
import os
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from rag_api.main import create_app
from rag_core.chunking import CanonicalSection, ChunkConfig, build_chunks
from rag_core.database import create_database_engine
from rag_core.documents import DocumentStore
from rag_core.errors import LostLease
from rag_core.indexes import IndexCreate, IndexQueue
from rag_core.jobs import IngestionQueue
from rag_core.schemas import CorpusCreate
from rag_core.settings import Settings
from rag_core.tokenization import BASELINE_TOKENIZER_REVISION, PinnedTokenizer
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace

pytestmark = pytest.mark.integration


@pytest.fixture
def setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Settings, UUID, PinnedTokenizer]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to disposable PostgreSQL/pgvector rag_test")
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    settings = Settings(_env_file=None, artifact_root=tmp_path)
    tokenizer = Tokenizer(WordLevel({"[UNK]": 0}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = Whitespace()
    token_path = tmp_path / "fixture-tokenizer.json"
    tokenizer.save(str(token_path))
    pinned = PinnedTokenizer(token_path, "software-fixture", BASELINE_TOKENIZER_REVISION)
    monkeypatch.setattr(PinnedTokenizer, "load", lambda *args, **kwargs: pinned)
    engine = create_database_engine(settings)
    try:
        store = DocumentStore(engine)
        corpus = store.create_corpus(CorpusCreate(name=f"Index software fixture {uuid4()}"))
        raw = (
            b"# Transactions\nA transaction is an atomic unit.\n"
            b"# Indexes\nIndexes speed up queries.\n"
        )
        key = f"originals/{uuid4()}.md"
        (tmp_path / key).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / key).write_bytes(raw)
        store.upload(
            corpus.id,
            "software-fixture.md",
            key,
            hashlib.sha256(raw).hexdigest(),
            len(raw),
            "text/markdown",
            3,
        )
        queue = IngestionQueue(engine, settings)
        claim = queue.claim()
        assert claim
        queue.process(*claim, Event())
        return settings, store.publish(corpus.id).id, pinned
    finally:
        engine.dispose()


def test_durable_index_search_lineage_idempotency_and_immutability(
    setup: tuple[Settings, UUID, PinnedTokenizer],
) -> None:
    settings, corpus_id, _ = setup
    engine = create_database_engine(settings)
    queue = IndexQueue(engine, settings)
    try:
        with TestClient(create_app(settings)) as client:
            payload = {
                "corpus_version_id": str(corpus_id),
                "chunking": {"strategy": "section", "max_tokens": 256, "overlap_tokens": 0},
            }
            response = client.post("/api/v1/indexes", json=payload)
            assert response.status_code == 202, response.text
            index_id = response.json()["id"]
            assert client.post("/api/v1/indexes", json=payload).json()["id"] == index_id
            assert (
                client.post(
                    f"/api/v1/indexes/{index_id}/search", json={"query": "transaction"}
                ).status_code
                == 409
            )
            claim = queue.claim()
            assert claim and str(claim[0]) == index_id
            queue.process(*claim, Event())
            row = client.get(f"/api/v1/indexes/{index_id}").json()
            assert row["state"] == "ready", row
            assert row["chunk_count"] == 2 and row["manifest"]["chunk_hash"]
            result = client.post(
                f"/api/v1/indexes/{index_id}/search",
                json={"query": "transaction", "context_tokens": 3},
            ).json()
            assert result["returned_count"] == 1
            assert "transaction" in result["hits"][0]["chunk"]["text"]
            assert result["context"]["token_count"] <= 3
            assert result["context"]["truncated_chunk_ids"]
            assert (
                result["context"]["passages"][0]["spans"][0]["end_offset"]
                < result["hits"][0]["chunk"]["spans"][0]["end_offset"]
            )
            empty = client.post(
                f"/api/v1/indexes/{index_id}/search", json={"query": "zzzzmissing"}
            ).json()
            assert empty["returned_count"] == 0 and empty["context"]["text"] == ""
            assert client.post(f"/api/v1/indexes/{index_id}/retry").status_code == 409
        for sql in [
            "UPDATE index_variants SET config='{}' WHERE id=:id",
            "UPDATE index_chunks SET text='changed' WHERE index_id=:id",
            "DELETE FROM index_chunks WHERE index_id=:id",
        ]:
            with pytest.raises(IntegrityError), engine.begin() as connection:
                connection.execute(text(sql), {"id": UUID(index_id)})
    finally:
        engine.dispose()


def test_index_reclaim_rejects_stale_owner_and_attempt_exhaustion(
    setup: tuple[Settings, UUID, PinnedTokenizer],
) -> None:
    settings, corpus_id, pinned = setup
    engine = create_database_engine(settings)
    queue = IndexQueue(engine, settings)
    try:
        index = queue.create(IndexCreate(corpus_version_id=corpus_id))
        first = queue.claim()
        assert first and first[0] == index.id
        # A locked claimed row is skipped, even if deliberately expired.
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE index_variants SET lease_expires_at=now()-interval '1 second' "
                    "WHERE id=:id"
                ),
                {"id": index.id},
            )
            assert queue.claim() is None
        second = queue.claim()
        assert second and second[0] == first[0] and second[1] != first[1]
        with pytest.raises(LostLease):
            queue.complete(*first, [], pinned)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE index_variants SET attempts=max_attempts,"
                    "lease_expires_at=now()-interval '1 second' WHERE id=:id"
                ),
                {"id": index.id},
            )
        assert queue.claim() is None
        assert queue.get(index.id).state == "failed"
        assert queue.get(index.id).error_code == "attempts_exhausted"
        assert queue.retry(index.id).state == "pending"
        claim = queue.claim()
        assert claim
        queue.process(*claim, Event())
        assert queue.get(index.id).state == "ready"
    finally:
        engine.dispose()


def test_invalid_chunk_lineage_rolls_back_atomic_build(
    setup: tuple[Settings, UUID, PinnedTokenizer],
) -> None:
    settings, corpus_id, pinned = setup
    engine = create_database_engine(settings)
    queue = IndexQueue(engine, settings)
    try:
        index = queue.create(
            IndexCreate(corpus_version_id=corpus_id, chunking=ChunkConfig(strategy="fixed"))
        )
        claim = queue.claim()
        assert claim
        foreign = build_chunks(
            [CanonicalSection(uuid4(), uuid4(), 0, "not in corpus")],
            ChunkConfig(),
            pinned,
            index.id,
        )
        with pytest.raises(IntegrityError):
            queue.complete(*claim, foreign, pinned)
        with engine.connect() as connection:
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM index_chunks WHERE index_id=:id"), {"id": index.id}
                )
                == 0
            )
        queue.process(*claim, Event())
        assert queue.get(index.id).state == "ready"
    finally:
        engine.dispose()


def test_shutdown_leaves_reclaimable_build_and_no_partial_chunks(
    setup: tuple[Settings, UUID, PinnedTokenizer],
) -> None:
    settings, corpus_id, _ = setup
    engine = create_database_engine(settings)
    queue = IndexQueue(engine, settings)
    try:
        index = queue.create(IndexCreate(corpus_version_id=corpus_id))
        first = queue.claim()
        assert first
        stopped = Event()
        stopped.set()
        queue.process(*first, stopped)
        assert queue.get(index.id).state == "running"
        with engine.begin() as connection:
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM index_chunks WHERE index_id=:id"), {"id": index.id}
                )
                == 0
            )
            connection.execute(
                text(
                    "UPDATE index_variants SET lease_expires_at=now()-interval '1 second' "
                    "WHERE id=:id"
                ),
                {"id": index.id},
            )
        recovered = queue.claim()
        assert recovered and recovered[1] != first[1]
        queue.process(*recovered, Event())
        assert queue.get(index.id).state == "ready"
        assert queue.get(index.id).attempts == 2
    finally:
        engine.dispose()


@pytest.mark.parametrize("offset", [None, 0.5, "0"])
def test_sql_rejects_null_fractional_and_string_offsets(
    setup: tuple[Settings, UUID, PinnedTokenizer],
    offset: object,
) -> None:
    settings, corpus_id, _ = setup
    engine = create_database_engine(settings)
    queue = IndexQueue(engine, settings)
    try:
        index = queue.create(IndexCreate(corpus_version_id=corpus_id))
        claim = queue.claim()
        assert claim
        with engine.connect() as connection:
            source = connection.execute(
                text(
                    "SELECT s.id,s.text FROM source_sections s "
                    "JOIN corpus_version_members m ON m.revision_id=s.revision_id "
                    "WHERE m.version_id=:id ORDER BY s.ordinal LIMIT 1"
                ),
                {"id": corpus_id},
            ).one()
        spans = [
            {
                "section_id": str(source.id),
                "start_offset": offset,
                "end_offset": 3,
                "text_start": 0,
                "text_end": 3,
            }
        ]
        with (
            pytest.raises(IntegrityError, match="nonnegative integers"),
            engine.begin() as connection,
        ):
            connection.execute(
                text(
                    "INSERT INTO index_chunks(id,index_id,ordinal,text,token_count,spans) "
                    "VALUES(:id,:index,0,:text,1,CAST(:spans AS jsonb))"
                ),
                {
                    "id": uuid4(),
                    "index": index.id,
                    "text": source.text[:3],
                    "spans": json.dumps(spans),
                },
            )
        queue.process(*claim, Event())
        assert queue.get(index.id).state == "ready"
    finally:
        engine.dispose()
