"""Real disposable PostgreSQL tests; all review/model labels are software fixtures."""

import hashlib
from threading import Event
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from rag_api.main import create_app
from rag_core.answer_evaluation import ClaimJudgment, Judgment
from rag_core.errors import LostLease, PlatformError
from rag_core.evaluations import EvaluationQueue, HumanReviewInput
from rag_core.judge import judge_contract
from rag_core.runs import digest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from test_indexes_integration import setup as setup
from test_runs_integration import Workflow
from test_runs_integration import workflow as workflow

pytestmark = pytest.mark.integration


def completed(workflow: Workflow) -> tuple[EvaluationQueue, UUID, UUID]:
    runs, experiment, _ = workflow
    run = runs.submit(experiment.id, str(uuid4()))
    claim = runs.claim()
    assert claim
    runs.process(*claim, Event())
    result = next(
        r for r in runs.results(run.id, 100, 0).items if r.answer_preview != "INSUFFICIENT_EVIDENCE"
    )
    settings = runs.settings.model_copy(update={"local_judge_enabled": True})
    return EvaluationQueue(runs.engine, settings), run.id, result.id


def review() -> HumanReviewInput:
    return HumanReviewInput(
        reviewer="Synthetic test reviewer (not a human research label)",
        judgment=Judgment(
            facts=["missing"],
            claims=[
                ClaimJudgment(
                    text="Synthetic answer",
                    support="unsupported",
                    citations=["P1"],
                    citations_supported=False,
                )
            ],
            no_factual_claims=False,
            rationale="Synthetic software fixture only.",
        ),
    )


def test_human_review_idempotency_immutability_and_unchanged_run(workflow: Workflow) -> None:
    queue, run_id, result_id = completed(workflow)
    runs = workflow[0]
    before = digest(runs.result(run_id, result_id).model_dump(mode="json"))
    key = str(uuid4())
    value = queue.create(run_id, result_id, key, review())
    assert value.state == "completed" and value.kind == "human"
    assert value.output and value.output["metrics"]["faithfulness"]["value"] == 0  # type: ignore[index]
    assert queue.create(run_id, result_id, key, review()).id == value.id
    with pytest.raises(PlatformError):
        queue.create(run_id, result_id, key, review().model_copy(update={"reviewer": "Another"}))
    with queue.engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(
            text("UPDATE answer_evaluations SET output='{}' WHERE id=:id"), {"id": value.id}
        )
    assert digest(runs.result(run_id, result_id).model_dump(mode="json")) == before
    assert queue.list(run_id, result_id).items[0].reviewer == review().reviewer


def test_worker_validated_judgment_and_api(
    workflow: Workflow, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue, run_id, result_id = completed(workflow)
    prompt = "Synthetic software judge; no inference performed."
    monkeypatch.setattr(
        "rag_core.evaluations.run_judge_child",
        lambda *args: {
            "answer": review().judgment.model_dump_json(),
            "prompt": prompt,
            "prompt_hash": hashlib.sha256(prompt.encode()).hexdigest(),
            "finish_reason": "eos",
            "contract": judge_contract(),
            "input_tokens": 1,
            "output_tokens": 1,
            "software_fixture": True,
        },
    )
    with TestClient(create_app(queue.settings)) as client:
        path = f"/api/v1/runs/{run_id}/results/{result_id}"
        response = client.post(
            f"{path}/evaluations", json={}, headers={"Idempotency-Key": str(uuid4())}
        )
        assert response.status_code == 202
        claim = queue.claim()
        assert claim
        queue.process(*claim, Event())
        records = client.get(f"{path}/evaluations").json()["items"]
        assert records[0]["state"] == "completed"
        assert records[0]["reviewer"] is None
        assert records[0]["output"]["metrics"]["citation_support"]["value"] == 0
        assert client.get("/api/v1/evaluation-rubric").json()["local_judge_enabled"] is True
        assert (
            client.post(
                f"{path}/reviews",
                json=review().model_dump(),
                headers={"Idempotency-Key": str(uuid4())},
            ).status_code
            == 201
        )


def test_invalid_raw_output_kept_scores_missing_and_new_key_can_retry(
    workflow: Workflow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue, run_id, result_id = completed(workflow)
    monkeypatch.setattr(
        "rag_core.evaluations.run_judge_child",
        lambda *args: {
            "answer": "Not JSON",
            "contract": judge_contract(),
            "finish_reason": "eos",
            "input_tokens": 10,
            "output_tokens": 3,
        },
    )
    first = queue.create(run_id, result_id, str(uuid4()))
    claim = queue.claim()
    assert claim
    queue.process(*claim, Event())
    value = queue.list(run_id, result_id).items[0]
    assert value.id == first.id and value.state == "failed" and value.output
    assert value.output["error_code"] == "judge_invalid_output" and "metrics" not in value.output
    assert queue.create(run_id, result_id, str(uuid4())).id != first.id


def test_missing_judge_and_wrong_result_route_are_rejected(workflow: Workflow) -> None:
    queue, run_id, result_id = completed(workflow)
    disabled = EvaluationQueue(
        queue.engine, queue.settings.model_copy(update={"local_judge_enabled": False})
    )
    with pytest.raises(PlatformError) as error:
        disabled.create(run_id, result_id, str(uuid4()))
    assert error.value.code == "judge_unavailable"
    assert disabled.create(run_id, result_id, str(uuid4()), review()).kind == "human"
    with pytest.raises(PlatformError):
        queue.list(uuid4(), result_id)


def test_expired_lease_reclaim_blocks_stale_publication_and_shutdown_keeps_job(
    workflow: Workflow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue, run_id, result_id = completed(workflow)
    job = queue.create(run_id, result_id, str(uuid4()))
    first = queue.claim()
    assert first
    with queue.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE answer_evaluations SET lease_expires_at=now()-interval '1 second' "
                "WHERE id=:id"
            ),
            {"id": job.id},
        )
    second = queue.claim()
    assert second and second[0] == first[0] and second[1] != first[1]
    with pytest.raises(LostLease):
        queue.complete(*first, {"error_code": "synthetic"})
    monkeypatch.setattr(
        "rag_core.evaluations.run_judge_child", lambda *args: (_ for _ in ()).throw(LostLease())
    )
    stop = Event()
    stop.set()
    queue.process(*second, stop)
    assert queue.list(run_id, result_id).items[0].state == "running"
    queue.complete(*second, {"error_code": "synthetic_failure", "error_message": "Fixture"})
    with pytest.raises(LostLease):
        queue.complete(*second, {"error_code": "duplicate"})


def test_runtime_mismatch_fails_before_inference(
    workflow: Workflow, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue, run_id, result_id = completed(workflow)
    queue.create(run_id, result_id, str(uuid4()))
    claim = queue.claim()
    assert claim
    monkeypatch.setattr("rag_core.evaluations.execution_identity", lambda _: {})
    queue.process(*claim, Event())
    value = queue.list(run_id, result_id).items[0]
    assert value.state == "failed" and value.output
    assert value.output["error_code"] == "evaluation_runtime_mismatch"


def test_judge_attempt_exhaustion_and_idempotent_replay_when_disabled(workflow: Workflow) -> None:
    queue, run_id, result_id = completed(workflow)
    queue = EvaluationQueue(queue.engine, queue.settings.model_copy(update={"job_max_attempts": 1}))
    key = str(uuid4())
    first = queue.create(run_id, result_id, key)
    claim = queue.claim()
    assert claim
    with pytest.raises(PlatformError):
        queue.complete(*claim, {})
    with queue.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE answer_evaluations SET lease_expires_at=now()-interval '1 second' "
                "WHERE id=:id"
            ),
            {"id": first.id},
        )
    assert queue.claim() is None
    last = queue.list(run_id, result_id).items[0]
    assert last.state == "failed" and last.output
    assert last.output["error_code"] == "attempts_exhausted"
    disabled = EvaluationQueue(
        queue.engine, queue.settings.model_copy(update={"local_judge_enabled": False})
    )
    assert disabled.create(run_id, result_id, key).id == first.id


def test_sql_rejects_a_review_with_changed_answer_evidence(workflow: Workflow) -> None:
    queue, run_id, result_id = completed(workflow)
    value = queue.create(run_id, result_id, str(uuid4()), review())
    with queue.engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(
            text("""
          INSERT INTO answer_evaluations
            (id,result_id,kind,request_key,reviewer,manifest,manifest_hash,state,output,
             attempts,max_attempts)
          SELECT :new_id,result_id,kind,:key,reviewer,
            jsonb_set(manifest,'{inputs,evidence}','[]'),manifest_hash,state,output,0,max_attempts
          FROM answer_evaluations WHERE id=:id
        """),
            {"new_id": uuid4(), "key": str(uuid4()), "id": value.id},
        )


def test_coverage_uses_latest_source_record_and_exposes_unknown_applicability(
    workflow: Workflow,
) -> None:
    queue, run_id, result_id = completed(workflow)
    before = queue.summary(run_id)
    assert before["total_observations"] == before["eligible_answers"] == 2
    assert before["sources"]["model"]["faithfulness"]["applicable_count"] is None  # type: ignore[index]
    queue.create(run_id, result_id, str(uuid4()), review())
    queue.create(run_id, result_id, str(uuid4()))
    claim = queue.claim()
    assert claim
    queue.complete(*claim, {"judgment": review().judgment.model_dump()})
    paired = queue.summary(run_id)
    assert paired["sources"]["human"]["answer_correctness"]["scored_count"] == 1  # type: ignore[index]
    assert paired["disagreement"]["faithfulness"] == {  # type: ignore[index]
        "paired_count": 1,
        "excluded_count": 1,
        "mean_absolute_difference": 0.0,
    }
    queue.create(run_id, result_id, str(uuid4()))
    claim = queue.claim()
    assert claim
    queue.complete(*claim, {"error_code": "synthetic_failure"})
    after = queue.summary(run_id)
    assert after["sources"]["model"]["answer_correctness"]["scored_count"] == 0  # type: ignore[index]
    assert after["sources"]["model"]["answer_correctness"]["error_count"] == 1  # type: ignore[index]
    assert after["disagreement"]["faithfulness"]["paired_count"] == 0  # type: ignore[index]
