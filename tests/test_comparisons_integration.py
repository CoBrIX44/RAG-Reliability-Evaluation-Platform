"""Disposable database only; all generated answers and reviews are software fixtures."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from rag_api.main import create_app
from rag_core.comparisons import ComparisonCreate, ComparisonQueue
from rag_core.errors import LostLease, PlatformError
from rag_core.runs import digest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from test_evaluations_integration import completed, review
from test_indexes_integration import setup as setup
from test_runs_integration import Workflow
from test_runs_integration import workflow as workflow

pytestmark = pytest.mark.integration


def fixture(workflow: Workflow) -> tuple[ComparisonQueue, ComparisonCreate]:
    runs, experiment, _ = workflow
    first = runs.submit(experiment.id, str(uuid4()))
    claim = runs.claim()
    assert claim
    runs.process(*claim, Event())
    second = runs.submit(experiment.id, str(uuid4()))
    claim = runs.claim()
    assert claim
    runs.process(*claim, Event())
    return ComparisonQueue(runs.engine, runs.settings), ComparisonCreate(
        name="Synthetic comparison",
        baseline_run_id=first.id,
        candidate_run_id=second.id,
        resamples=200,
    )


def test_saved_comparison_api_manifest_idempotency_and_immutability(workflow: Workflow) -> None:
    queue, value = fixture(workflow)
    key = str(uuid4())
    row = queue.create(value, key)
    assert queue.create(value, key).id == row.id
    with pytest.raises(PlatformError):
        queue.create(value.model_copy(update={"seed": 1}), key)
    frozen = queue.manifest(row.id)
    assert digest(frozen) == row.manifest_hash
    claim = queue.claim()
    assert claim
    queue.process(*claim, Event())
    saved = queue.get(row.id)
    assert saved.state == "completed" and saved.output
    assert saved.output["metrics"]["retrieval_recall"]["difference"] == 0
    assert saved.output["metrics"]["answer_correctness"]["difference"] is None
    assert saved.output["accounting"]["baseline"]["cost"]["value"] is None
    assert queue.manifest(row.id) == frozen
    with queue.engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text("UPDATE comparisons SET output='{}' WHERE id=:id"), {"id": row.id})
    with TestClient(create_app(queue.settings)) as client:
        assert client.get(f"/api/v1/comparisons/{row.id}").status_code == 200
        assert client.get(f"/api/v1/comparisons/{row.id}/manifest").json() == frozen
        assert client.get("/api/v1/comparisons").json()["items"][0]["output"] is None
        assert client.post(
            "/api/v1/comparisons",
            json=value.model_dump(mode="json"),
            headers={"Idempotency-Key": key},
        ).json()["id"] == str(row.id)


def test_concurrent_key_submission_and_exhausted_comparison_preserve_one_record(
    workflow: Workflow,
) -> None:
    queue, value = fixture(workflow)
    queue = ComparisonQueue(queue.engine, queue.settings.model_copy(update={"job_max_attempts": 1}))
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda _: queue.create(value, key), range(2)))
    assert rows[0].id == rows[1].id
    claim = queue.claim()
    assert claim
    with queue.engine.begin() as connection:
        connection.execute(
            text("UPDATE comparisons SET lease_expires_at=now()-interval '1 second' WHERE id=:id"),
            {"id": rows[0].id},
        )
    assert queue.claim() is None
    result = queue.get(rows[0].id)
    assert result.state == "failed" and result.output
    assert result.output["error_code"] == "attempts_exhausted"


def test_new_reviews_do_not_change_frozen_selection(workflow: Workflow) -> None:
    # Existing helper completes one synthetic run; create a second and explicit test review.
    evaluations, first_id, result_id = completed(workflow)
    runs, experiment, _ = workflow
    evaluations.create(first_id, result_id, str(uuid4()), review())
    second = runs.submit(experiment.id, str(uuid4()))
    claim = runs.claim()
    assert claim
    runs.process(*claim, Event())
    queue = ComparisonQueue(runs.engine, runs.settings)
    value = ComparisonCreate(
        name="Frozen synthetic reviews",
        baseline_run_id=first_id,
        candidate_run_id=second.id,
        resamples=200,
    )
    row = queue.create(value, str(uuid4()))
    before = queue.manifest(row.id)
    evaluations.create(
        first_id,
        result_id,
        str(uuid4()),
        review().model_copy(update={"reviewer": "New synthetic label"}),
    )
    assert queue.manifest(row.id) == before
    assert queue.create(value, str(uuid4())).manifest_hash != row.manifest_hash


def test_lease_reclaim_shutdown_runtime_mismatch_and_exhaustion(
    workflow: Workflow, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue, value = fixture(workflow)
    row = queue.create(value, str(uuid4()))
    first = queue.claim()
    assert first
    with queue.engine.begin() as connection:
        connection.execute(
            text("UPDATE comparisons SET lease_expires_at=now()-interval '1 second' WHERE id=:id"),
            {"id": row.id},
        )
    second = queue.claim()
    assert second and second != first
    with pytest.raises(LostLease):
        queue.complete(*first, {"error_code": "synthetic"})
    stop = Event()
    stop.set()
    queue.process(*second, stop)
    assert queue.get(row.id).state == "running"
    monkeypatch.setattr("rag_core.comparisons.execution_identity", lambda _: {})
    queue.process(*second, Event())
    saved = queue.get(row.id)
    assert saved.state == "failed" and saved.output
    assert saved.output["error_code"] == "comparison_runtime_mismatch"
