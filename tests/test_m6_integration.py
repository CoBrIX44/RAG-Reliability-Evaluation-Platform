"""M6 evidence/diagnostic software fixtures on disposable PostgreSQL; no model inference."""

import hashlib
import json
from threading import Event
from typing import Any
from uuid import uuid4
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from rag_api.main import create_app
from rag_core.diagnostics import diagnostics
from rag_core.errors import LostLease, PlatformError
from rag_core.exports import ExportCreate, ExportQueue
from rag_core.runs import digest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from test_comparisons_integration import fixture as comparison_fixture
from test_evaluations_integration import completed, review
from test_indexes_integration import setup as setup
from test_runs_integration import Workflow
from test_runs_integration import workflow as workflow

pytestmark = pytest.mark.integration


def test_export_complete_evidence_checksums_download_and_immutable_sources(
    workflow: Workflow,
) -> None:
    evaluations, run_id, result_id = completed(workflow)
    review_row = evaluations.create(run_id, result_id, str(uuid4()), review())
    runs = workflow[0]
    before = digest(runs.result(run_id, result_id).model_dump(mode="json"))
    queue = ExportQueue(runs.engine, runs.settings)
    value = ExportCreate(source_kind="run", source_id=run_id)
    key = str(uuid4())
    job = queue.create(value, key)
    assert queue.create(value, key).id == job.id
    claim = queue.claim()
    assert claim
    queue.process(*claim, Event())
    saved = queue.get(job.id)
    assert saved.state == "completed", saved.output
    assert saved.output
    path = queue.artifact(job.id)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == saved.output["sha256"]
    with ZipFile(path) as archive:
        checksums = json.loads(archive.read("checksums.json"))
        assert set(archive.namelist()) == set(checksums) | {"checksums.json"}
        for filename, sha in checksums.items():
            assert hashlib.sha256(archive.read(filename)).hexdigest() == sha
        raw = json.loads(archive.read(f"runs/{run_id}/run.json"))
        assert raw["manifest"] == runs.manifest(run_id)
        assert (
            json.loads(archive.read(f"runs/{run_id}/evaluations/{review_row.id}.json"))["reviewer"]
            == review().reviewer
        )
        assert any(name.endswith("chunks.jsonl") for name in checksums)
        assert any(name.startswith("sources/sections/") for name in checksums)
    assert digest(runs.result(run_id, result_id).model_dump(mode="json")) == before
    with queue.engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text("UPDATE export_jobs SET output='{}' WHERE id=:id"), {"id": job.id})
    with TestClient(create_app(queue.settings)) as client:
        response = client.get(f"/api/v1/exports/{job.id}/download")
        assert response.status_code == 200 and response.headers["content-type"] == "application/zip"
        assert hashlib.sha256(response.content).hexdigest() == saved.output["sha256"]
        assert client.get(f"/api/v1/exports/latest?source_kind=run&source_id={run_id}").json()[
            "id"
        ] == str(job.id)


def test_pending_judge_not_backfilled_and_export_snapshot_rejects_key_conflict(
    workflow: Workflow,
) -> None:
    evaluations, run_id, result_id = completed(workflow)
    pending = evaluations.create(run_id, result_id, str(uuid4()))
    queue = ExportQueue(evaluations.engine, evaluations.settings)
    key = str(uuid4())
    job = queue.create(ExportCreate(source_kind="run", source_id=run_id), key)
    with pytest.raises(PlatformError):
        queue.create(ExportCreate(source_kind="comparison", source_id=run_id), key)
    claim = evaluations.claim()
    assert claim
    evaluations.complete(*claim, {"error_code": "synthetic_failure"})
    claim = queue.claim()
    assert claim
    queue.process(*claim, Event())
    assert queue.get(job.id).state == "completed"
    with ZipFile(queue.artifact(job.id)) as archive:
        frozen = json.loads(archive.read(f"runs/{run_id}/evaluations/{pending.id}.json"))
        assert frozen["state"] == "pending" and frozen["output"] is None


def test_export_capacity_shutdown_stale_ownership_and_missing_artifact(workflow: Workflow) -> None:
    evaluations, run_id, _ = completed(workflow)
    settings = evaluations.settings.model_copy(update={"max_export_bytes": 1024})
    queue = ExportQueue(evaluations.engine, settings)
    job = queue.create(ExportCreate(source_kind="run", source_id=run_id), str(uuid4()))
    first = queue.claim()
    assert first
    stop = Event()
    stop.set()
    queue.process(*first, stop)
    assert queue.get(job.id).state == "running"
    with queue.engine.begin() as connection:
        connection.execute(
            text("UPDATE export_jobs SET lease_expires_at=now()-interval '1 second' WHERE id=:id"),
            {"id": job.id},
        )
    second = queue.claim()
    assert second and second != first
    with pytest.raises(LostLease):
        queue.complete(*first, {"error_code": "stale"})
    queue.process(*second, Event())
    result = queue.get(job.id)
    assert result.state == "failed" and result.output
    assert result.output["error_code"] == "export_capacity"
    with pytest.raises(PlatformError):
        queue.artifact(job.id)


def test_comparison_filters_freeze_selected_questions_and_export_report(workflow: Workflow) -> None:
    comparisons, request = comparison_fixture(workflow)
    request = request.model_copy(update={"topics": ["transactions"], "difficulties": ["medium"]})
    # The fixture uses medium by default; derive its frozen difficulty instead of inventing labels.
    manifest: dict[str, Any] = workflow[0].manifest(request.baseline_run_id)
    question = next(q for q in manifest["questions"] if q["content"]["topic"] == "transactions")
    request = request.model_copy(update={"difficulties": [question["content"]["difficulty"]]})
    job = comparisons.create(request, str(uuid4()))
    frozen: dict[str, Any] = comparisons.manifest(job.id)
    assert len(frozen["baseline"]["questions"]) == 1
    assert (
        frozen["baseline"]["accounting"]["subgroup_stage_timings"]["question_wall_ms"][
            "scored_count"
        ]
        == 1
    )
    claim = comparisons.claim()
    assert claim
    comparisons.process(*claim, Event())
    exports = ExportQueue(comparisons.engine, comparisons.settings)
    export = exports.create(ExportCreate(source_kind="comparison", source_id=job.id), str(uuid4()))
    claim = exports.claim()
    assert claim
    exports.process(*claim, Event())
    assert exports.get(export.id).state == "completed", exports.get(export.id).output
    with ZipFile(exports.artifact(export.id)) as archive:
        assert json.loads(archive.read("comparison.json"))["manifest"] == frozen
    with pytest.raises(PlatformError) as error:
        comparisons.create(request.model_copy(update={"topics": ["does-not-exist"]}), str(uuid4()))
    assert error.value.code == "empty_comparison_filter"
    assert comparisons.facets(request.baseline_run_id, request.candidate_run_id)["topics"] == [
        "missing",
        "transactions",
    ]


def test_diagnostics_filter_and_exact_result_lineage(workflow: Workflow) -> None:
    evaluations, run_id, result_id = completed(workflow)
    evaluations.create(run_id, result_id, str(uuid4()), review())
    data = diagnostics(
        evaluations.engine, run_id, source="human", topic="transactions", issue="quality_issue"
    )
    assert data["filtered_count"] == 1 and data["total_count"] == 2
    assert data["items"][0]["result_id"] == str(result_id)
    assert "quality_issue" in data["items"][0]["issues"]
    with TestClient(create_app(evaluations.settings)) as client:
        assert (
            client.get(f"/api/v1/runs/{run_id}/diagnostics?topic=transactions&limit=1").status_code
            == 200
        )
        assert (
            client.get(f"/api/v1/runs/{run_id}/diagnostics?issue=not-a-signal").status_code == 422
        )


def test_active_run_export_rejected_missing_results_are_not_zero(workflow: Workflow) -> None:
    runs, experiment, _ = workflow
    run = runs.submit(experiment.id, str(uuid4()))
    queue = ExportQueue(runs.engine, runs.settings)
    with pytest.raises(PlatformError) as error:
        queue.create(ExportCreate(source_kind="run", source_id=run.id), str(uuid4()))
    assert error.value.code == "export_source_active"
    data = diagnostics(runs.engine, run.id, issue="missing_observation")
    assert data["filtered_count"] == 2 and all(row["result_id"] is None for row in data["items"])
