"""Disposable PostgreSQL tests. Answers/reviews below are synthetic software fixtures."""

import hashlib
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from rag_api.main import create_app
from rag_core.chunking import ChunkConfig
from rag_core.context import pack_context
from rag_core.database import create_database_engine
from rag_core.dataset_schemas import DatasetCreate, QuestionInput, QuestionUpdate
from rag_core.datasets import DatasetStore
from rag_core.errors import LostLease, PlatformError
from rag_core.generation import GenerationInput, GenerationOutput, generation_contract
from rag_core.indexes import IndexCreate, IndexQueue
from rag_core.run_worker import RunQueue
from rag_core.runs import ExperimentCreate, ExperimentView
from rag_core.settings import Settings
from rag_core.tokenization import PinnedTokenizer
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from test_indexes_integration import setup as setup

pytestmark = pytest.mark.integration
Workflow = tuple[RunQueue, ExperimentView, Callable[..., GenerationOutput]]


@pytest.fixture
def workflow(
    setup: tuple[Settings, UUID, PinnedTokenizer], monkeypatch: pytest.MonkeyPatch
) -> Iterator[Workflow]:
    settings, corpus_id, tokenizer = setup
    assert settings.database_url.get_secret_value().split("/")[-1] == "rag_test"
    cleanup = create_database_engine(settings)
    with cleanup.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE export_jobs,comparisons,answer_evaluations,run_attempts,"
                "question_results,runs,experiments"
            )
        )
    cleanup.dispose()
    settings = settings.model_copy(update={"local_generation_enabled": True})
    engine = create_database_engine(settings)
    with engine.connect() as connection:
        section = connection.execute(
            text(
                "SELECT s.id,s.text FROM source_sections s JOIN corpus_version_members m "
                "ON m.revision_id=s.revision_id "
                "WHERE m.version_id=:id AND s.text LIKE '%atomic%'"
            ),
            {"id": corpus_id},
        ).one()
    datasets = DatasetStore(engine)
    dataset = datasets.create(
        DatasetCreate(
            name=f"Synthetic run fixture {uuid4()}",
            corpus_version_id=corpus_id,
            purpose="development_fixture",
        )
    )
    question = QuestionInput(
        text="transaction",
        reference_answer="A transaction is an atomic unit.",
        required_facts=["A transaction is an atomic unit."],
        topic="transactions",
        split="development",
        split_group="synthetic-transactions",
        review_status="reviewed",
        reviewer="Software test fixture (synthetic)",
        evidence_groups=[
            {
                "fact_index": 0,
                "alternatives": [
                    {
                        "spans": [
                            {
                                "section_id": str(section.id),
                                "start_offset": 0,
                                "end_offset": len(section.text),
                            }
                        ]
                    }
                ],
            }
        ],
    )
    datasets.add(dataset.id, [question])
    datasets.add(
        dataset.id,
        [
            QuestionInput(
                text="unknown",
                answerable=False,
                reference_answer="Not in this software fixture.",
                topic="missing",
                split="development",
                split_group="synthetic-missing",
                review_status="reviewed",
                reviewer="Software test fixture (synthetic)",
            )
        ],
    )
    version = datasets.publish(dataset.id)
    indexes = IndexQueue(engine, settings)
    index = indexes.create(
        IndexCreate(
            corpus_version_id=corpus_id,
            chunking=ChunkConfig(strategy="section", max_tokens=256, overlap_tokens=0),
        )
    )
    claim = indexes.claim()
    assert claim and claim[0] == index.id
    indexes.process(*claim, Event())
    queue = RunQueue(engine, settings)
    experiment = queue.create_experiment(
        ExperimentCreate(
            name=f"Synthetic experiment {uuid4()}",
            dataset_version_id=version.id,
            index_id=index.id,
            context_tokens=256,
        )
    )

    def synthetic_answer(value: GenerationInput, *args: object) -> GenerationOutput:
        context = pack_context(value.passages, tokenizer, value.context_tokens)
        prompt = "Software fixture; no model inference was performed."
        return GenerationOutput(
            answer="Synthetic answer [P1]" if context.passages else "INSUFFICIENT_EVIDENCE",
            context=context,
            prompt=prompt,
            prompt_hash=hashlib.sha256(prompt.encode()).hexdigest(),
            input_tokens=12,
            output_tokens=4,
            finish_reason="eos",
            abstained=not context.passages,
            citations=["P1"] if context.passages else [],
            unknown_citations=[],
            metadata={"contract": generation_contract(), "runtime": {"software_fixture": True}},
        )

    monkeypatch.setattr("rag_core.run_worker.prepare_generation", lambda *args: None)
    monkeypatch.setattr("rag_core.run_worker.generate", synthetic_answer)
    try:
        yield queue, experiment, synthetic_answer
    finally:
        engine.dispose()


def test_saved_results_metrics_manifest_and_api(workflow: Workflow) -> None:
    queue, experiment, _ = workflow
    run = queue.submit(experiment.id, str(uuid4()))
    assert queue.submit(experiment.id, queue_key(queue, run.id)).id == run.id
    manifest = queue.manifest(run.id)
    assert isinstance(manifest["questions"], list)
    assert len(manifest["questions"]) == 2
    claim = queue.claim()
    assert claim and claim[0] == run.id
    queue.process(*claim, Event())
    result = queue.get(run.id)
    assert result.state == "completed", result
    assert result.completed_count == 2 and result.failed_count == 0
    assert result.model_dump()["metrics"]["retrieval_recall"]["mean"] == 1
    assert result.model_dump()["metrics"]["retrieval_recall"]["applicable_count"] == 1
    assert result.model_dump()["metrics"]["faithfulness"]["mean"] is None and result.cost is None
    assert queue.manifest(run.id) == manifest
    rows = queue.results(run.id, 1, 0)
    assert len(rows.items) == 1 and rows.next_cursor == "1"
    trace = queue.result(run.id, rows.items[0].id)
    assert (
        trace.attempts[0].state == "completed"
        and "question_wall_ms" in trace.model_dump()["trace"]["timings"]
    )
    with TestClient(create_app(queue.settings)) as client:
        assert client.get(f"/api/v1/runs/{run.id}").status_code == 200
        assert (
            client.get(f"/api/v1/runs/{run.id}/results/{trace.id}").json()["trace"] == trace.trace
        )
        assert client.post(f"/api/v1/experiments/{experiment.id}/runs", json={}).status_code == 422
        assert client.post(
            f"/api/v1/experiments/{experiment.id}/runs",
            headers={"Idempotency-Key": queue_key(queue, run.id)},
            json={},
        ).json()["id"] == str(run.id)
        assert (
            client.post(
                f"/api/v1/experiments/{experiment.id}/runs",
                headers={"Idempotency-Key": "extra-field"},
                json={"seed": 1},
            ).status_code
            == 422
        )
    for sql in [
        "UPDATE experiments SET name='tamper' WHERE id=:id",
        "DELETE FROM experiments WHERE id=:id",
    ]:
        with pytest.raises(IntegrityError), queue.engine.begin() as connection:
            connection.execute(text(sql), {"id": experiment.id})
    for sql in [
        "UPDATE runs SET manifest='{}' WHERE id=:id",
        "UPDATE runs SET state='queued' WHERE id=:id",
    ]:
        with pytest.raises(IntegrityError), queue.engine.begin() as connection:
            connection.execute(text(sql), {"id": run.id})
    with pytest.raises(IntegrityError), queue.engine.begin() as connection:
        connection.execute(
            text("UPDATE question_results SET trace='{}' WHERE run_id=:id"), {"id": run.id}
        )


def queue_key(queue: RunQueue, run_id: UUID) -> str:
    with queue.engine.connect() as connection:
        return connection.execute(
            text("SELECT idempotency_key FROM runs WHERE id=:id"), {"id": run_id}
        ).scalar_one()


def expire(queue: RunQueue, run_id: UUID) -> None:
    with queue.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE runs SET lease_expires_at=clock_timestamp()-interval '1 second' "
                "WHERE id=:id"
            ),
            {"id": run_id},
        )


def test_partial_failure_preserves_retrieval_scores(
    workflow: Workflow, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue, experiment, answer = workflow

    def fail_one(value: GenerationInput, *args: object) -> GenerationOutput:
        if value.question == "transaction":
            raise PlatformError("generation_timeout", "Synthetic timeout")
        return answer(value)

    monkeypatch.setattr("rag_core.run_worker.generate", fail_one)
    run = queue.submit(experiment.id, str(uuid4()))
    claim = queue.claim()
    assert claim
    queue.process(*claim, Event())
    result = queue.get(run.id)
    assert result.state == "completed_with_errors" and result.failed_count == 1
    assert result.model_dump()["metrics"]["retrieval_recall"]["mean"] == 1
    assert result.model_dump()["metrics"]["context_recall"]["mean"] is None
    assert result.model_dump()["metrics"]["context_recall"]["error_count"] == 1


def test_cooperative_cancellation_keeps_completed_results(
    workflow: Workflow, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue, experiment, answer = workflow
    queued = queue.submit(experiment.id, str(uuid4()))
    assert queue.cancel(queued.id).state == "cancelled"
    run = queue.submit(experiment.id, str(uuid4()))
    calls = 0

    def cancel_second(value: GenerationInput, *args: object) -> GenerationOutput:
        nonlocal calls
        calls += 1
        if calls == 2:
            queue.cancel(run.id)
            raise LostLease
        return answer(value)

    monkeypatch.setattr("rag_core.run_worker.generate", cancel_second)
    claim = queue.claim()
    assert claim
    queue.process(*claim, Event())
    result = queue.get(run.id)
    assert (
        result.state == "cancelled" and result.completed_count == 1 and result.cancelled_count == 1
    )
    attempts = queue.attempts(run.id, 20, 0).items
    assert [a.state for a in attempts] == ["completed", "cancelled"]
    assert "retrieval" in attempts[1].trace


def test_shutdown_recovery_skips_saved_results_and_fences_old_owner(
    workflow: Workflow, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue, experiment, answer = workflow
    run = queue.submit(experiment.id, str(uuid4()))
    stop = Event()
    calls = 0

    def interrupt_second(value: GenerationInput, *args: object) -> GenerationOutput:
        nonlocal calls
        calls += 1
        if calls == 2:
            stop.set()
            raise LostLease
        return answer(value)

    monkeypatch.setattr("rag_core.run_worker.generate", interrupt_second)
    old = queue.claim()
    assert old
    queue.process(*old, stop)
    assert queue.get(run.id).state == "running" and queue.get(run.id).completed_count == 1
    expire(queue, run.id)
    new = queue.claim()
    assert new and new[1] != old[1]
    with pytest.raises(LostLease):
        queue.heartbeat(*old)
    monkeypatch.setattr("rag_core.run_worker.generate", answer)
    queue.process(*new, Event())
    assert queue.get(run.id).state == "completed" and queue.get(run.id).completed_count == 2
    attempts = queue.attempts(run.id, 20, 0).items
    assert [a.state for a in attempts] == ["completed", "interrupted", "completed"]
    assert "retrieval" in attempts[1].trace
    assert len(queue.results(run.id, 20, 0).items) == 2


def test_runtime_mismatch_exhaustion_and_idempotency_conflict(workflow: Workflow) -> None:
    queue, experiment, _ = workflow
    key = str(uuid4())
    run = queue.submit(experiment.id, key)
    other = queue.create_experiment(
        ExperimentCreate(
            name=f"Other {uuid4()}",
            dataset_version_id=experiment.dataset_version_id,
            index_id=experiment.index_id,
        )
    )
    with pytest.raises(PlatformError, match="another experiment"):
        queue.submit(other.id, key)
    claim = queue.claim()
    assert claim
    queue.settings = queue.settings.model_copy(
        update={"source_revision": "different-software-revision"}
    )
    queue.process(*claim, Event())
    assert queue.get(run.id).error_code == "run_runtime_mismatch"
    queued = queue.submit(other.id, str(uuid4()))
    for _ in range(queue.settings.job_max_attempts):
        assert queue.claim()
        expire(queue, queued.id)
    assert queue.claim() is None
    assert queue.get(queued.id).error_code == "attempts_exhausted"


def test_manifest_and_result_lineage_are_enforced_in_sql(workflow: Workflow) -> None:
    queue, experiment, _ = workflow
    run = queue.submit(experiment.id, str(uuid4()))
    claim = queue.claim()
    assert claim
    questions = queue.manifest(run.id)["questions"]
    assert isinstance(questions, list)
    planned = questions[0]
    with pytest.raises(IntegrityError), queue.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO question_results "
                "(id,run_id,question_id,question_revision,repeat,state,trace) "
                "VALUES (:id,:run,:question,:revision,0,'succeeded','{}')"
            ),
            {
                "id": uuid4(),
                "run": run.id,
                "question": planned["id"],
                "revision": planned["revision"],
            },
        )
    queue.cancel(run.id)
    queue.finish(*claim)


def test_submission_retry_survives_disabled_generation_and_empty_split_is_rejected(
    workflow: Workflow,
) -> None:
    queue, experiment, _ = workflow
    key = str(uuid4())
    run = queue.submit(experiment.id, key)
    queue.settings = queue.settings.model_copy(update={"local_generation_enabled": False})
    assert queue.submit(experiment.id, key).id == run.id
    with pytest.raises(PlatformError, match="Enable the local"):
        queue.submit(experiment.id, str(uuid4()))
    with pytest.raises(PlatformError, match="nonempty split"):
        queue.create_experiment(
            ExperimentCreate(
                name="Empty software test split",
                dataset_version_id=experiment.dataset_version_id,
                index_id=experiment.index_id,
                split="test",
            )
        )
    queue.cancel(run.id)


def test_expired_cancel_request_finishes_without_recovery_inference(workflow: Workflow) -> None:
    queue, experiment, _ = workflow
    run = queue.submit(experiment.id, str(uuid4()))
    claim = queue.claim()
    assert claim
    questions = queue.manifest(run.id)["questions"]
    assert isinstance(questions, list)
    attempt = queue.start_question(*claim, UUID(questions[0]["id"]), 0)
    queue.checkpoint(*claim, attempt, {"software_fixture": True})
    queue.cancel(run.id)
    expire(queue, run.id)
    assert queue.claim() is None
    assert queue.get(run.id).state == "cancelled"
    assert queue.attempts(run.id, 20, 0).items[0].state == "cancelled"
    assert queue.attempts(run.id, 20, 0).items[0].trace == {"software_fixture": True}


def test_later_draft_edits_cannot_change_executed_question_revision(workflow: Workflow) -> None:
    queue, experiment, _ = workflow
    run = queue.submit(experiment.id, str(uuid4()))
    frozen = queue.manifest(run.id)
    with queue.engine.connect() as connection:
        dataset_id: UUID = connection.execute(
            text("SELECT dataset_id FROM dataset_versions WHERE id=:id"),
            {"id": experiment.dataset_version_id},
        ).scalar_one()
    store = DatasetStore(queue.engine)
    draft = store.questions(dataset_id, 20, 0).items[0]
    changed = draft.content.model_copy(
        update={
            "text": "Changed synthetic draft question",
            "review_status": "candidate",
            "reviewer": "",
        }
    )
    store.update(
        dataset_id, draft.id, QuestionUpdate(expected_revision=draft.revision, content=changed)
    )
    claim = queue.claim()
    assert claim
    queue.process(*claim, Event())
    assert queue.get(run.id).state == "completed"
    assert queue.manifest(run.id) == frozen
    results = queue.results(run.id, 20, 0).items
    assert all(result.question != changed.text for result in results)
    assert (
        next(result for result in results if result.question_id == draft.id).question_revision
        == draft.revision
    )


def test_concurrent_submission_and_locked_run_skip(workflow: Workflow) -> None:
    queue, experiment, _ = workflow
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        runs = list(pool.map(lambda _: queue.submit(experiment.id, key), range(2)))
    assert runs[0].id == runs[1].id
    second = queue.submit(experiment.id, str(uuid4()))
    with queue.engine.begin() as connection:
        connection.execute(text("SELECT id FROM runs WHERE id=:id FOR UPDATE"), {"id": runs[0].id})
        claim = queue.claim()
        assert claim and claim[0] == second.id
    queue.cancel(runs[0].id)
    queue.cancel(second.id)
    queue.finish(*claim)
