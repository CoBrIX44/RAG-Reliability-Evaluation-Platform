"""Real SQL ranking/lineage/leases with explicitly synthetic inference and review labels."""

from threading import Event
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from rag_api.main import create_app
from rag_core.chunking import ChunkConfig
from rag_core.embeddings import DENSE_STRATEGY
from rag_core.errors import LostLease, PlatformError
from rag_core.indexes import IndexCreate, IndexQueue
from rag_core.reranking import RerankInput, RerankOutput, reranker_contract
from rag_core.runs import ExperimentCreate
from sqlalchemy import text
from test_embeddings import encoded
from test_indexes_integration import setup as setup
from test_runs_integration import Workflow, expire
from test_runs_integration import workflow as workflow

pytestmark = pytest.mark.integration


def prepare(
    workflow: Workflow, monkeypatch: pytest.MonkeyPatch, strategy: str = "hybrid_rerank"
) -> UUID:
    queue, previous, _ = workflow
    corpus_id = queue.engine.connect()
    with corpus_id as connection:
        corpus: UUID = connection.execute(
            text("SELECT corpus_version_id FROM dataset_versions WHERE id=:id"),
            {"id": previous.dataset_version_id},
        ).scalar_one()
    indexes = IndexQueue(queue.engine, queue.settings)
    monkeypatch.setattr(
        "rag_core.indexes.run_embeddings",
        lambda *args, **kwargs: encoded([[1.0] + [0.0] * 383, [0.6, 0.8] + [0.0] * 382]),
    )
    index = indexes.create(
        IndexCreate(
            corpus_version_id=corpus,
            retrieval="dense",
            chunking=ChunkConfig(strategy="section", max_tokens=254, overlap_tokens=0),
        )
    )
    claim = indexes.claim()
    assert claim
    indexes.process(*claim, Event())
    assert indexes.get(index.id).state == "ready"
    monkeypatch.setattr(
        "rag_core.hybrid.run_embeddings", lambda *args: encoded([[1.0] + [0.0] * 383])
    )
    monkeypatch.setattr("rag_core.run_worker.prepare_reranker", lambda *args: None)

    def synthetic_rerank(value: RerankInput, *args: object) -> RerankOutput:
        return RerankOutput(
            passage_ids=[chunk.id for chunk in value.passages],
            scores=[-3.0, 9.0][: len(value.passages)],
            pair_tokens=[20] * len(value.passages),
            metadata={"contract": reranker_contract(), "runtime": {"software_fixture": True}},
        )

    monkeypatch.setattr("rag_core.hybrid.rerank", synthetic_rerank)
    return queue.create_experiment(
        ExperimentCreate.model_validate(
            {
                "name": f"Synthetic {strategy} {uuid4()}",
                "dataset_version_id": previous.dataset_version_id,
                "index_id": index.id,
                "retrieval_strategy": strategy,
                "top_k": 1,
                "candidate_k": 2,
                "context_tokens": 256,
            }
        )
    ).id


@pytest.mark.parametrize("strategy", ["hybrid", "hybrid_rerank"])
def test_saved_hybrid_candidates_final_ranks_and_independent_gold_scoring(
    workflow: Workflow, monkeypatch: pytest.MonkeyPatch, strategy: str
) -> None:
    queue, _, _ = workflow
    experiment_id = prepare(workflow, monkeypatch, strategy)
    run = queue.submit(experiment_id, str(uuid4()))
    claim = queue.claim()
    assert claim
    queue.process(*claim, Event())
    assert queue.get(run.id).state == "completed"
    result = next(
        row for row in queue.results(run.id, 20, 0).items if row.question == "transaction"
    )
    trace = queue.result(run.id, result.id).model_dump()["trace"]
    pipeline = trace["retrieval"]["pipeline"]
    assert len(pipeline["lexical"]) == 1 and len(pipeline["dense"]) == 2
    assert pipeline["fused"][0]["score"] == pytest.approx(2 / 61)
    assert trace["retrieval"]["strategy"] == (
        "hybrid-rrf-v1" if strategy == "hybrid" else "hybrid-rrf-cross-encoder-v1"
    )
    assert trace["retrieval_scores"]["recall"] == (1 if strategy == "hybrid" else 0)
    assert (
        trace["generation"]["context"]["passages"][0]["id"]
        == trace["retrieval"]["hits"][0]["chunk"]["id"]
    )
    assert (pipeline["reranker"] is not None) == (strategy == "hybrid_rerank")
    if strategy == "hybrid_rerank":
        assert trace["retrieval"]["hits"][0]["score"] == 9.0
        assert len(trace["retrieval_candidates"]["hits"]) == 2
    # The same index's lexical projection is worker-only; the public dense preview stays queued.
    index_id = queue.manifest(run.id)["index_id"]
    with TestClient(create_app(queue.settings)) as client:
        assert (
            client.post(
                f"/api/v1/indexes/{index_id}/search", json={"query": "transaction"}
            ).status_code
            == 409
        )
    assert (
        IndexQueue(queue.engine, queue.settings).get(UUID(str(index_id))).config["retrieval"]
        == DENSE_STRATEGY
    )


def test_reranker_failure_retains_candidates_without_inventing_final_scores(
    workflow: Workflow, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue, _, _ = workflow
    experiment_id = prepare(workflow, monkeypatch)

    def fail(*args: object) -> RerankOutput:
        raise PlatformError("reranker_timeout", "Synthetic timeout")

    monkeypatch.setattr("rag_core.hybrid.rerank", fail)
    run = queue.submit(experiment_id, str(uuid4()))
    claim = queue.claim()
    assert claim
    queue.process(*claim, Event())
    assert queue.get(run.id).state == "completed_with_errors"
    result = queue.results(run.id, 20, 0).items[0]
    trace = queue.result(run.id, result.id).model_dump()["trace"]
    assert trace["error"]["stage"] == "reranking"
    assert len(trace["retrieval_candidates"]["hits"]) == 2
    assert "retrieval_scores" not in trace and trace["generation"] is None
    assert queue.get(run.id).model_dump()["metrics"]["retrieval_recall"]["mean"] is None


def test_interruption_during_reranking_preserves_candidate_checkpoint_and_recovers(
    workflow: Workflow, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue, _, _ = workflow
    experiment_id = prepare(workflow, monkeypatch)
    run = queue.submit(experiment_id, str(uuid4()))
    stop = Event()

    def interrupt(*args: object) -> RerankOutput:
        stop.set()
        raise LostLease

    with monkeypatch.context() as interrupted:
        interrupted.setattr("rag_core.hybrid.rerank", interrupt)
        old = queue.claim()
        assert old
        queue.process(*old, stop)
    assert queue.get(run.id).state == "running"
    assert "retrieval_candidates" in queue.attempts(run.id, 20, 0).items[0].trace
    expire(queue, run.id)
    new = queue.claim()
    assert new and new[1] != old[1]
    queue.process(*new, Event())
    assert queue.get(run.id).state == "completed"
    assert len(queue.results(run.id, 20, 0).items) == 2
    assert queue.attempts(run.id, 20, 0).items[0].state == "interrupted"


def test_hybrid_rejects_lexical_index(workflow: Workflow) -> None:
    queue, previous, _ = workflow
    with pytest.raises(PlatformError, match="ready dense index"):
        queue.create_experiment(
            ExperimentCreate(
                name="Synthetic incompatible hybrid",
                dataset_version_id=previous.dataset_version_id,
                index_id=previous.index_id,
                retrieval_strategy="hybrid",
            )
        )
