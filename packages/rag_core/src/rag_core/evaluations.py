"""Answer evaluation storage, idempotent reviews, coverage and a durable judge queue."""

import contextlib
import hashlib
from datetime import datetime, timedelta
from threading import Event, Thread
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine, and_, func, or_, select, text
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from rag_core.answer_evaluation import RUBRIC, Judgment, score_judgment
from rag_core.database import record_worker_heartbeat
from rag_core.errors import LostLease, PlatformError
from rag_core.evaluation_models import AnswerEvaluation
from rag_core.judge import JudgeRequest, judge_contract, judge_output, run_judge_child
from rag_core.run_models import QuestionResult, Run
from rag_core.runs import digest, execution_identity
from rag_core.schemas import Page
from rag_core.settings import Settings


class HumanReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reviewer: str = Field(min_length=1, max_length=160)
    judgment: Judgment


class EvaluationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    result_id: UUID
    kind: Literal["model", "human"]
    reviewer: str | None
    manifest: dict[str, object]
    manifest_hash: str
    state: Literal["pending", "running", "completed", "failed"]
    output: dict[str, object] | None
    attempts: int
    created_at: datetime


def answer_inputs(result: QuestionResult) -> dict[str, object]:
    question = result.trace["question"]["content"]  # type: ignore[index]
    generation = result.trace["generation"]
    assert isinstance(question, dict) and isinstance(generation, dict)
    return {
        "question": question["text"],
        "answerable": question["answerable"],
        "reference_answer": question["reference_answer"],
        "required_facts": question["required_facts"],
        "answer": generation["answer"],
        "evidence": [
            {"citation": f"P{i}", "text": passage["text"]}
            for i, passage in enumerate(generation["context"]["passages"], 1)
        ],
    }


class EvaluationQueue:
    def __init__(self, engine: Engine, settings: Settings) -> None:
        self.engine, self.settings = engine, settings

    def create(
        self, run_id: UUID, result_id: UUID, key: str, review: HumanReviewInput | None = None
    ) -> EvaluationView:
        if (
            not key
            or len(key) > 128
            or any(
                c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:-"
                for c in key
            )
        ):
            raise PlatformError("invalid_request_key", "Use an ASCII idempotency key.")
        kind = "human" if review else "model"
        with Session(self.engine) as session, session.begin():
            # Global key serialization handles ambiguous network retries and concurrent submissions.
            lock = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
            session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
            existing = session.scalar(
                select(AnswerEvaluation).where(AnswerEvaluation.request_key == key)
            )
            result = session.get(QuestionResult, result_id)
            if result is None or result.run_id != run_id:
                raise PlatformError("result_not_found", "Saved result not found.", 404)
            if existing:
                expected = review.model_dump(mode="json") if review else None
                if (
                    existing.result_id != result_id
                    or existing.kind != kind
                    or existing.manifest.get("review_submission") != expected
                ):
                    raise PlatformError(
                        "idempotency_conflict", "This key belongs to another submission.", 409
                    )
                return EvaluationView.model_validate(existing)
            if result.state != "succeeded" or not result.trace.get("generation"):
                raise PlatformError(
                    "answer_required", "Only a saved successful answer can be evaluated.", 409
                )
            if review is None and not self.settings.local_judge_enabled:
                raise PlatformError(
                    "judge_unavailable",
                    "Local experimental judge is disabled; human review is available.",
                    409,
                )
            run = session.get(Run, run_id)
            assert run
            inputs = answer_inputs(result)
            manifest = {
                "version": "answer-evaluation-v1",
                "result_id": str(result_id),
                "run_manifest_hash": run.manifest_hash,
                "result_trace_hash": digest(result.trace),
                "inputs": inputs,
                "rubric": RUBRIC,
                "review_submission": review.model_dump(mode="json") if review else None,
                "judge": judge_contract() if review is None else None,
                "execution": execution_identity(self.settings) if review is None else None,
            }
            output = (
                None
                if review is None
                else {
                    "judgment": review.judgment.model_dump(mode="json"),
                    "metrics": score_judgment(review.judgment, inputs),
                }
            )
            row = AnswerEvaluation(
                result_id=result_id,
                kind=kind,
                request_key=key,
                reviewer=review.reviewer if review else None,
                manifest=manifest,
                manifest_hash=digest(manifest),
                state="completed" if review else "pending",
                output=output,
                max_attempts=self.settings.job_max_attempts,
            )
            session.add(row)
            session.flush()
            return EvaluationView.model_validate(row)

    def list(
        self, run_id: UUID, result_id: UUID, limit: int = 100, cursor: int = 0
    ) -> Page[EvaluationView]:
        with Session(self.engine) as session:
            result = session.get(QuestionResult, result_id)
            if not result or result.run_id != run_id:
                raise PlatformError("result_not_found", "Saved result not found.", 404)
            rows = list(
                session.scalars(
                    select(AnswerEvaluation)
                    .where(AnswerEvaluation.result_id == result_id)
                    .order_by(AnswerEvaluation.created_at.desc(), AnswerEvaluation.id.desc())
                    .offset(cursor)
                    .limit(limit + 1)
                )
            )
            return Page(
                items=[EvaluationView.model_validate(row) for row in rows[:limit]],
                next_cursor=cursor + limit if len(rows) > limit else None,
            )

    def owned(self, session: Session, evaluation_id: UUID, token: UUID) -> AnswerEvaluation:
        row = session.scalar(
            select(AnswerEvaluation)
            .where(
                AnswerEvaluation.id == evaluation_id,
                AnswerEvaluation.state == "running",
                AnswerEvaluation.lease_token == token,
                AnswerEvaluation.lease_expires_at > func.clock_timestamp(),
            )
            .with_for_update()
        )
        if row is None:
            raise LostLease
        return row

    def summary(self, run_id: UUID) -> dict[str, object]:
        """Latest record per answer/source, projected without loading prompts or raw responses."""
        with Session(self.engine) as session:
            run = session.get(Run, run_id)
            if run is None:
                raise PlatformError("run_not_found", "Run not found.", 404)
            answers: dict[UUID, bool] = dict(
                session.execute(
                    select(
                        QuestionResult.id,
                        QuestionResult.trace["question"]["content"]["answerable"].as_boolean(),
                    ).where(QuestionResult.run_id == run_id, QuestionResult.state == "succeeded")
                ).all()
            )
            rows = session.execute(
                select(
                    AnswerEvaluation.result_id,
                    AnswerEvaluation.kind,
                    AnswerEvaluation.state,
                    AnswerEvaluation.output["metrics"].label("metrics"),
                )
                .join(QuestionResult, QuestionResult.id == AnswerEvaluation.result_id)
                .where(QuestionResult.run_id == run_id)
                .ext(distinct_on(AnswerEvaluation.result_id, AnswerEvaluation.kind))
                .order_by(
                    AnswerEvaluation.result_id,
                    AnswerEvaluation.kind,
                    AnswerEvaluation.created_at.desc(),
                    AnswerEvaluation.id.desc(),
                )
            ).all()
        sources: dict[str, object] = {}
        metrics = ("answer_correctness", "faithfulness", "citation_support", "abstention_quality")
        for kind in ("human", "model"):
            source = {row.result_id: row for row in rows if row.kind == kind}
            summary: dict[str, object] = {}
            for metric in metrics:
                applicable = (
                    sum(answers.values())
                    if metric == "answer_correctness"
                    else len(answers)
                    if metric == "abstention_quality"
                    else None
                )
                known_applicable = 0
                values: list[float] = []
                errors = 0
                completed = 0
                for result_id, answerable in answers.items():
                    row = source.get(result_id)
                    if metric == "answer_correctness" and not answerable:
                        continue
                    if row is None:
                        continue
                    if row.state == "failed":
                        errors += 1
                    if row.state == "completed":
                        completed += 1
                        score = (row.metrics or {}).get(metric, {})
                        if score.get("value") is not None:
                            values.append(float(score["value"]))
                            known_applicable += 1
                if applicable is None and completed == len(answers):
                    applicable = known_applicable
                summary[metric] = {
                    "mean": sum(values) / len(values) if values else None,
                    "state": "scored" if values else "unavailable",
                    "applicable_count": applicable,
                    "known_applicable_count": known_applicable,
                    "scored_count": len(values),
                    "error_count": errors,
                    "unavailable_count": len(answers) - len(values) - errors,
                }
            sources[kind] = summary
        pairs = {
            kind: {
                row.result_id: row for row in rows if row.kind == kind and row.state == "completed"
            }
            for kind in ("model", "human")
        }
        disagreement: dict[str, object] = {}
        for metric in metrics:
            differences = []
            for result_id in pairs["model"].keys() & pairs["human"].keys():
                a = (pairs["model"][result_id].metrics or {}).get(metric, {}).get("value")
                b = (pairs["human"][result_id].metrics or {}).get(metric, {}).get("value")
                if a is not None and b is not None:
                    differences.append(abs(float(a) - float(b)))
            disagreement[metric] = {
                "paired_count": len(differences),
                "excluded_count": len(answers) - len(differences),
                "mean_absolute_difference": sum(differences) / len(differences)
                if differences
                else None,
            }
        return {
            "selection": "latest-record-per-result-and-source-v1",
            "rubric": RUBRIC["version"],
            "total_observations": run.total_count,
            "eligible_answers": len(answers),
            "without_saved_answer": run.total_count - len(answers),
            "sources": sources,
            "disagreement": disagreement,
        }

    def claim(self) -> tuple[UUID, UUID] | None:
        with Session(self.engine) as session, session.begin():
            row = session.scalar(
                select(AnswerEvaluation)
                .where(
                    or_(
                        AnswerEvaluation.state == "pending",
                        and_(
                            AnswerEvaluation.state == "running",
                            AnswerEvaluation.lease_expires_at <= func.clock_timestamp(),
                        ),
                    )
                )
                .order_by(AnswerEvaluation.created_at, AnswerEvaluation.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if not row:
                return None
            now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            row.state, row.lease_token = "running", uuid4()
            row.lease_expires_at = now + timedelta(seconds=self.settings.job_lease_seconds)
            # Exhaustion is published under this new live ownership, never a stale lease.
            if row.attempts >= row.max_attempts:
                session.flush()
                row.state, row.output = (
                    "failed",
                    {
                        "error_code": "attempts_exhausted",
                        "error_message": "Judge retry budget exhausted; scores unavailable.",
                    },
                )
                row.lease_token = row.lease_expires_at = None
                return None
            row.attempts += 1
            return row.id, row.lease_token

    def heartbeat(self, evaluation_id: UUID, token: UUID) -> None:
        with Session(self.engine) as session, session.begin():
            row = self.owned(session, evaluation_id, token)
            now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            row.lease_expires_at = now + timedelta(seconds=self.settings.job_lease_seconds)
        record_worker_heartbeat(self.engine)

    def complete(self, evaluation_id: UUID, token: UUID, output: dict[str, object]) -> None:
        with Session(self.engine) as session, session.begin():
            row = self.owned(session, evaluation_id, token)
            inputs = row.manifest["inputs"]
            assert isinstance(inputs, dict)
            if "error_code" not in output and "judgment" not in output:
                raise PlatformError(
                    "invalid_judgment", "Successful evaluations require a judgment."
                )
            if "judgment" in output:
                judgment = Judgment.model_validate(output["judgment"])
                output = output | {"metrics": score_judgment(judgment, inputs)}
            row.output = output
            row.state = "failed" if "error_code" in output else "completed"
            row.lease_token = row.lease_expires_at = None

    def process(self, evaluation_id: UUID, token: UUID, stop: Event) -> None:
        lost, finished = Event(), Event()

        def keep_alive() -> None:
            while not finished.wait(self.settings.job_heartbeat_seconds):
                try:
                    self.heartbeat(evaluation_id, token)
                except Exception:
                    lost.set()
                    return

        thread = Thread(target=keep_alive, daemon=True)
        thread.start()
        try:
            with Session(self.engine) as session:
                row = self.owned(session, evaluation_id, token)
                manifest = row.manifest
                if digest(manifest) != row.manifest_hash or manifest[
                    "execution"
                ] != execution_identity(self.settings):
                    raise PlatformError(
                        "evaluation_runtime_mismatch",
                        "Judge source/runtime differs from its frozen submission.",
                    )
                if manifest["judge"] != judge_contract() or not self.settings.local_judge_enabled:
                    raise PlatformError(
                        "judge_unavailable", "Pinned local judge is unavailable or disabled."
                    )
                inputs = manifest["inputs"]
                assert isinstance(inputs, dict)
            raw = run_judge_child(
                JudgeRequest(inputs=inputs, threads=self.settings.generation_threads),
                self.settings,
                stop,
                lost,
            )
            if not stop.is_set() and not lost.is_set():
                self.complete(evaluation_id, token, judge_output(raw, inputs))
        except LostLease:
            pass
        except Exception as error:
            if not stop.is_set() and not lost.is_set():
                safe = (
                    error
                    if isinstance(error, PlatformError)
                    else PlatformError("judge_failed", "Judge failed; scores unavailable.")
                )
                with contextlib.suppress(LostLease):
                    self.complete(
                        evaluation_id,
                        token,
                        {"error_code": safe.code, "error_message": safe.message},
                    )
        finally:
            finished.set()
            thread.join(timeout=2)
