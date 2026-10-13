"""Frozen experiments, run submission, and bounded result/coverage inspection."""

import hashlib
import json
import platform
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from rag_core.dataset_models import DatasetVersion
from rag_core.dataset_schemas import QuestionInput
from rag_core.errors import PlatformError
from rag_core.generation import generation_contract
from rag_core.index_models import IndexVariant
from rag_core.retrieval_evaluation import EVIDENCE_SCORING_VERSION
from rag_core.run_models import Experiment, QuestionResult, Run, RunAttempt
from rag_core.schemas import Page
from rag_core.settings import Settings

TERMINAL = {"completed", "completed_with_errors", "failed", "cancelled"}


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def execution_identity(settings: Settings) -> dict[str, object]:
    # Ship hashes even when a container has no .git directory. Never guess a Git revision.
    root = Path(__file__).resolve().parents[4]
    paths = sorted(
        path
        for folder in ("packages", "services", "migrations")
        for path in (root / folder).rglob("*.py")
        if ".venv" not in path.parts
    )
    files = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }
    locks = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in ("uv.lock", "package-lock.json")
        if (root / name).exists()
    }
    return {
        "source_revision": settings.source_revision,
        "source_hash": digest(files),
        "source_files": files,
        "lock_hashes": locks,
        "python": platform.python_version(),
        "platform": platform.system(),
        "machine": platform.machine(),
        "generation_threads": settings.generation_threads,
        "generation_timeout_seconds": settings.generation_timeout_seconds,
    }


class ExperimentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=160)
    dataset_version_id: UUID
    index_id: UUID
    split: Literal["development", "test"] = "development"
    top_k: int = Field(default=5, ge=1, le=50)
    context_tokens: int = Field(default=1024, ge=0, le=1536)
    max_new_tokens: int = Field(default=128, ge=1, le=256)
    repeats: int = Field(default=1, ge=1, le=3)
    seed: int = Field(default=0, ge=0, le=2**31 - 4)


class ExperimentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    dataset_version_id: UUID
    index_id: UUID
    fingerprint: str
    config: dict[str, object]
    created_at: datetime


class RunView(BaseModel):
    id: UUID
    experiment_id: UUID
    state: Literal["queued", "running", "completed", "completed_with_errors", "failed", "cancelled"]
    cancel_requested: bool
    total_count: int
    completed_count: int
    failed_count: int
    cancelled_count: int
    attempts: int
    manifest_hash: str
    manifest_summary: dict[str, object]
    metrics: dict[str, object]
    cost: None = None
    cost_state: Literal["unavailable"] = "unavailable"
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ResultSummary(BaseModel):
    id: UUID
    question_id: UUID
    question_revision: int
    repeat: int
    state: Literal["succeeded", "failed"]
    question: str
    answer_preview: str | None
    error_code: str | None
    retrieval_scores: dict[str, object] | None
    context_scores: dict[str, object] | None


class AttemptView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    question_id: UUID
    repeat: int
    ordinal: int
    state: str
    trace: dict[str, object]
    error_code: str | None
    started_at: datetime
    finished_at: datetime | None


class ResultView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    run_id: UUID
    question_id: UUID
    question_revision: int
    repeat: int
    state: str
    trace: dict[str, object]
    created_at: datetime
    attempts: list[AttemptView] = Field(default_factory=list)


def metrics_summary(
    manifest: dict[str, object], results: list[QuestionResult]
) -> dict[str, object]:
    questions = manifest["questions"]
    config = manifest["config"]
    assert isinstance(questions, list) and isinstance(config, dict)
    applicable = sum(QuestionInput.model_validate(q["content"]).answerable for q in questions)
    applicable *= int(config["repeats"])
    summary: dict[str, object] = {}
    for name, source, field in (
        ("retrieval_precision", "retrieval_scores", "precision"),
        ("retrieval_recall", "retrieval_scores", "recall"),
        ("context_recall", "context_scores", "recall"),
    ):
        values: list[float] = []
        errors = 0
        for result in results:
            frozen = result.trace["question"]
            assert isinstance(frozen, dict)
            question = QuestionInput.model_validate(frozen["content"])
            if not question.answerable:
                continue
            scores = result.trace.get(source)
            if isinstance(scores, dict) and isinstance(scores.get(field), (float, int)):
                values.append(float(scores[field]))
            elif result.state == "failed":
                errors += 1
        summary[name] = {
            "state": "scored" if values else "unavailable" if applicable else "not_applicable",
            "mean": sum(values) / len(values) if values else None,
            "applicable_count": applicable,
            "scored_count": len(values),
            "error_count": errors,
            "unavailable_count": applicable - len(values) - errors,
            "policy": EVIDENCE_SCORING_VERSION,
        }
    for name in ("answer_correctness", "faithfulness", "citation_support", "abstention_quality"):
        summary[name] = {
            "state": "unavailable",
            "mean": None,
            "applicable_count": None,
            "scored_count": 0,
            "error_count": 0,
            "reason": "Answer evaluators arrive in M5; no score is inferred.",
        }
    return summary


class RunStore:
    def __init__(self, engine: Engine, settings: Settings) -> None:
        self.engine, self.settings = engine, settings

    def create_experiment(self, value: ExperimentCreate) -> ExperimentView:
        with Session(self.engine) as session, session.begin():
            dataset = session.scalar(
                select(DatasetVersion)
                .where(
                    DatasetVersion.id == value.dataset_version_id, DatasetVersion.sealed.is_(True)
                )
                .with_for_update()
            )
            index = session.get(IndexVariant, value.index_id)
            if dataset is None or index is None:
                raise PlatformError(
                    "experiment_inputs_missing", "Choose a published dataset and index.", 404
                )
            if index.state != "ready" or index.corpus_version_id != dataset.corpus_version_id:
                raise PlatformError(
                    "experiment_lineage_mismatch",
                    "Dataset and ready index must share a corpus version.",
                    409,
                )
            snapshots = dataset.manifest["questions"]
            assert isinstance(snapshots, list)
            selected = [q for q in snapshots if q["content"]["split"] == value.split]
            if not selected or len(selected) * value.repeats > self.settings.max_run_questions:
                raise PlatformError(
                    "run_capacity", "Choose a nonempty split within the run question limit.", 422
                )
            config = value.model_dump(
                mode="json", exclude={"name", "dataset_version_id", "index_id"}
            )
            config.update(
                generation=generation_contract(),
                retrieval=index.config,
                evidence_scoring=EVIDENCE_SCORING_VERSION,
            )
            fingerprint = digest({"request": value.model_dump(mode="json"), "config": config})
            previous = session.scalar(
                select(Experiment).where(Experiment.fingerprint == fingerprint)
            )
            if previous:
                return ExperimentView.model_validate(previous)
            row = Experiment(
                name=value.name,
                dataset_version_id=dataset.id,
                index_id=index.id,
                fingerprint=fingerprint,
                config=config,
            )
            session.add(row)
            session.flush()
            return ExperimentView.model_validate(row)

    def experiments(self, limit: int, offset: int) -> Page[ExperimentView]:
        with Session(self.engine) as session:
            rows = list(
                session.scalars(
                    select(Experiment)
                    .order_by(Experiment.created_at.desc(), Experiment.id)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            return Page(
                items=[ExperimentView.model_validate(row) for row in rows[:limit]],
                next_cursor=str(offset + limit) if len(rows) > limit else None,
            )

    def submit(self, experiment_id: UUID, key: str) -> RunView:
        with Session(self.engine) as session, session.begin():
            # Global key serialization covers requests for different experiment definitions.
            session.execute(select(func.pg_advisory_xact_lock(func.hashtext(key))))
            existing = session.scalar(select(Run).where(Run.idempotency_key == key))
            if existing:
                if existing.experiment_id != experiment_id:
                    raise PlatformError(
                        "idempotency_conflict",
                        "This submission key belongs to another experiment.",
                        409,
                    )
                return self._view(session, existing)
            if not self.settings.local_generation_enabled:
                raise PlatformError(
                    "generation_not_configured",
                    "Enable the local CPU answer model in workspace settings.",
                    409,
                )
            experiment = session.get(Experiment, experiment_id)
            if experiment is None:
                raise PlatformError("experiment_not_found", "Experiment not found.", 404)
            if experiment.config["generation"] != generation_contract():
                raise PlatformError(
                    "generation_contract_changed",
                    "Create an experiment for the current answer runtime.",
                    409,
                )
            dataset = session.get(DatasetVersion, experiment.dataset_version_id)
            index = session.get(IndexVariant, experiment.index_id)
            assert dataset and index
            snapshots = dataset.manifest["questions"]
            assert isinstance(snapshots, list)
            questions = [
                q for q in snapshots if q["content"]["split"] == experiment.config["split"]
            ]
            total = len(questions) * int(str(experiment.config["repeats"]))
            if total > self.settings.max_run_questions:
                raise PlatformError("run_capacity", "Run exceeds the configured question limit.")
            manifest = {
                "schema": "rag-run-v1",
                "experiment_id": str(experiment.id),
                "corpus_version_id": str(dataset.corpus_version_id),
                "dataset_version_id": str(dataset.id),
                "dataset_hash": dataset.manifest_hash,
                "purpose": dataset.manifest["purpose"],
                "index_id": str(index.id),
                "index_manifest": index.manifest,
                "config": experiment.config,
                "questions": questions,
                "execution": execution_identity(self.settings),
            }
            row = Run(
                experiment_id=experiment_id,
                idempotency_key=key,
                manifest=manifest,
                manifest_hash=digest(manifest),
                total_count=total,
                max_attempts=self.settings.job_max_attempts,
            )
            session.add(row)
            session.flush()
            return self._view(session, row)

    def _view(self, session: Session, row: Run) -> RunView:
        # Polling projects only scoring inputs, never the potentially large prompts/evidence.
        rows = session.execute(
            select(
                QuestionResult.state,
                QuestionResult.trace["question"],
                QuestionResult.trace["retrieval_scores"],
                QuestionResult.trace["context_scores"],
            ).where(QuestionResult.run_id == row.id)
        )
        results = [
            QuestionResult(
                state=state,
                trace={
                    "question": question,
                    "retrieval_scores": retrieval,
                    "context_scores": context,
                },
            )
            for state, question, retrieval, context in rows
        ]
        completed = sum(result.state == "succeeded" for result in results)
        failed = len(results) - completed
        manifest = {key: value for key, value in row.manifest.items() if key != "questions"}
        return RunView(
            id=row.id,
            experiment_id=row.experiment_id,
            state=row.state,
            cancel_requested=row.cancel_requested,
            total_count=row.total_count,
            completed_count=completed,
            failed_count=failed,
            cancelled_count=row.total_count - len(results) if row.state == "cancelled" else 0,
            attempts=row.attempts,
            manifest_hash=row.manifest_hash,
            manifest_summary=manifest,
            metrics=metrics_summary(row.manifest, results),
            error_code=row.error_code,
            error_message=row.error_message,
            created_at=row.created_at,
            started_at=row.started_at,
            finished_at=row.finished_at,
        )

    def get(self, run_id: UUID) -> RunView:
        with Session(self.engine) as session:
            row = session.get(Run, run_id)
            if row is None:
                raise PlatformError("run_not_found", "Run not found.", 404)
            return self._view(session, row)

    def manifest(self, run_id: UUID) -> dict[str, object]:
        with Session(self.engine) as session:
            row = session.get(Run, run_id)
            if row is None:
                raise PlatformError("run_not_found", "Run not found.", 404)
            return row.manifest

    def list(self, limit: int, offset: int) -> Page[RunView]:
        with Session(self.engine) as session:
            rows = list(
                session.scalars(
                    select(Run)
                    .order_by(Run.created_at.desc(), Run.id)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            return Page(
                items=[self._view(session, row) for row in rows[:limit]],
                next_cursor=str(offset + limit) if len(rows) > limit else None,
            )

    def cancel(self, run_id: UUID) -> RunView:
        with Session(self.engine) as session, session.begin():
            row = session.scalar(select(Run).where(Run.id == run_id).with_for_update())
            if row is None:
                raise PlatformError("run_not_found", "Run not found.", 404)
            now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            if row.state not in TERMINAL:
                row.cancel_requested = True
                if row.state == "queued":
                    row.state = "cancelled"
                    row.finished_at = now
                session.flush()
            return self._view(session, row)

    def results(self, run_id: UUID, limit: int, offset: int) -> Page[ResultSummary]:
        with Session(self.engine) as session:
            if session.get(Run, run_id) is None:
                raise PlatformError("run_not_found", "Run not found.", 404)
            # Summaries stay small even when full evidence/prompt traces are large.
            rows = list(
                session.execute(
                    select(
                        QuestionResult.id,
                        QuestionResult.question_id,
                        QuestionResult.question_revision,
                        QuestionResult.repeat,
                        QuestionResult.state,
                        QuestionResult.trace["question"]["content"]["text"].as_string(),
                        func.left(QuestionResult.trace["generation"]["answer"].as_string(), 300),
                        QuestionResult.trace["error"]["code"].as_string(),
                        QuestionResult.trace["retrieval_scores"],
                        QuestionResult.trace["context_scores"],
                    )
                    .where(QuestionResult.run_id == run_id)
                    .order_by(QuestionResult.question_id, QuestionResult.repeat)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            items = [
                ResultSummary(
                    id=result_id,
                    question_id=question_id,
                    question_revision=revision,
                    repeat=repeat,
                    state=state,
                    question=question,
                    answer_preview=answer,
                    error_code=error_code,
                    retrieval_scores=retrieval,
                    context_scores=context,
                )
                for (
                    result_id,
                    question_id,
                    revision,
                    repeat,
                    state,
                    question,
                    answer,
                    error_code,
                    retrieval,
                    context,
                ) in rows[:limit]
            ]
            return Page(items=items, next_cursor=str(offset + limit) if len(rows) > limit else None)

    def result(self, run_id: UUID, result_id: UUID) -> ResultView:
        with Session(self.engine) as session:
            row = session.scalar(
                select(QuestionResult).where(
                    QuestionResult.id == result_id, QuestionResult.run_id == run_id
                )
            )
            if row is None:
                raise PlatformError("result_not_found", "Question result not found.", 404)
            attempts = list(
                session.scalars(
                    select(RunAttempt)
                    .where(
                        RunAttempt.run_id == run_id,
                        RunAttempt.question_id == row.question_id,
                        RunAttempt.repeat == row.repeat,
                    )
                    .order_by(RunAttempt.ordinal)
                )
            )
            return ResultView.model_validate(row).model_copy(
                update={"attempts": [AttemptView.model_validate(attempt) for attempt in attempts]}
            )

    def attempts(self, run_id: UUID, limit: int, offset: int) -> Page[AttemptView]:
        with Session(self.engine) as session:
            rows = list(
                session.scalars(
                    select(RunAttempt)
                    .where(RunAttempt.run_id == run_id)
                    .order_by(RunAttempt.started_at, RunAttempt.id)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            return Page(
                items=[AttemptView.model_validate(row) for row in rows[:limit]],
                next_cursor=str(offset + limit) if len(rows) > limit else None,
            )
