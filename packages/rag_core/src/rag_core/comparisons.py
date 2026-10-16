"""Freeze explicit run/evaluation selections; compute analysis only in the durable worker."""

import contextlib
from datetime import datetime, timedelta
from threading import Event, Thread
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Engine, and_, func, or_, select
from sqlalchemy.orm import Session

from rag_core.comparison_analysis import ANALYSIS_VERSION, RunSample, analyze, timing_summary
from rag_core.comparison_models import Comparison
from rag_core.comparison_snapshot import snapshot_run
from rag_core.database import record_worker_heartbeat
from rag_core.errors import LostLease, PlatformError
from rag_core.run_models import Run
from rag_core.runs import digest, execution_identity
from rag_core.schemas import Page
from rag_core.settings import Settings


class ComparisonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=160)
    baseline_run_id: UUID
    candidate_run_id: UUID
    assessment_source: Literal["human", "model"] = "human"
    exploratory: bool = False
    seed: int = Field(default=0, ge=0, le=2**31 - 1)
    resamples: int = Field(default=1000, ge=200, le=5000)
    topics: list[str] = Field(default_factory=list, max_length=100)
    difficulties: list[Literal["easy", "medium", "hard"]] = Field(
        default_factory=list, max_length=3
    )

    @model_validator(mode="after")
    def distinct_runs(self) -> "ComparisonCreate":
        if any(not topic.strip() or len(topic) > 120 for topic in self.topics):
            raise ValueError("Choose nonempty topics of at most 120 characters.")
        self.topics = sorted(set(self.topics))
        self.difficulties = sorted(set(self.difficulties))
        if self.baseline_run_id == self.candidate_run_id:
            raise ValueError("Choose two different runs.")
        return self


class ComparisonView(BaseModel):
    id: UUID
    state: Literal["pending", "running", "completed", "failed"]
    manifest_hash: str
    manifest_summary: dict[str, Any]
    output: dict[str, Any] | None
    attempts: int
    created_at: datetime


class ComparisonQueue:
    def __init__(self, engine: Engine, settings: Settings) -> None:
        self.engine, self.settings = engine, settings

    def view(self, row: Comparison, detail: bool = True) -> ComparisonView:
        manifest: dict[str, Any] = row.manifest
        return ComparisonView(
            id=row.id,
            state=row.state,
            manifest_hash=row.manifest_hash,
            manifest_summary={
                "request": manifest["request"],
                "cutoff": manifest["cutoff"],
                "baseline": {
                    key: manifest["baseline"][key]
                    for key in ("id", "manifest_hash", "state", "purpose", "dataset_hash")
                },
                "candidate": {
                    key: manifest["candidate"][key]
                    for key in ("id", "manifest_hash", "state", "purpose", "dataset_hash")
                },
            },
            output=row.output if detail else None,
            attempts=row.attempts,
            created_at=row.created_at,
        )

    def create(self, value: ComparisonCreate, key: str) -> ComparisonView:
        request = value.model_dump(mode="json")
        with Session(self.engine) as session, session.begin():
            session.execute(select(func.pg_advisory_xact_lock(func.hashtext(key))))
            existing = session.scalar(select(Comparison).where(Comparison.request_key == key))
            if existing:
                if existing.manifest["request"] != request:
                    raise PlatformError(
                        "idempotency_conflict", "Key belongs to another comparison.", 409
                    )
                return self.view(existing)
            a, b = session.get(Run, value.baseline_run_id), session.get(Run, value.candidate_run_id)
            if a is None or b is None:
                raise PlatformError("run_not_found", "Choose two existing saved runs.", 404)
            if max(a.total_count, b.total_count) > 1000:
                raise PlatformError(
                    "comparison_capacity", "Comparisons support at most 1000 observations per run."
                )
            cutoff: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            baseline = snapshot_run(session, a, value.assessment_source, cutoff)
            candidate = snapshot_run(session, b, value.assessment_source, cutoff)
            for sample in (baseline, candidate):
                sample.questions = [
                    q
                    for q in sample.questions
                    if (not value.topics or q.topic in value.topics)
                    and (not value.difficulties or q.difficulty in value.difficulties)
                ]
                ids = {q.id for q in sample.questions}
                sample.observations = [row for row in sample.observations if row.question_id in ids]
                sample.accounting["subgroup_stage_timings"] = {
                    stage: timing_summary(
                        [row.timings[stage] for row in sample.observations if stage in row.timings],
                        len(sample.questions) * int(sample.config["repeats"]),
                    )
                    for stage in sample.accounting["stage_timings"]
                }
            if not baseline.questions and not candidate.questions:
                raise PlatformError(
                    "empty_comparison_filter", "No questions match these filters.", 422
                )
            manifest = {
                "version": ANALYSIS_VERSION,
                "request": request,
                "cutoff": cutoff.isoformat(),
                "baseline": baseline.model_dump(mode="json"),
                "candidate": candidate.model_dump(mode="json"),
                "execution": execution_identity(self.settings),
                "selection_policy": "frozen-latest-source-record-including-failures-v1",
            }
            row = Comparison(
                baseline_run_id=a.id,
                candidate_run_id=b.id,
                request_key=key,
                manifest=manifest,
                manifest_hash=digest(manifest),
                max_attempts=self.settings.job_max_attempts,
            )
            session.add(row)
            session.flush()
            return self.view(row)

    def facets(self, baseline_id: UUID, candidate_id: UUID) -> dict[str, list[str]]:
        with Session(self.engine) as session:
            runs = [session.get(Run, run_id) for run_id in (baseline_id, candidate_id)]
            if any(run is None for run in runs):
                raise PlatformError("run_not_found", "Run not found.", 404)
            questions: list[dict[str, Any]] = []
            for run in runs:
                if run is not None:
                    manifest: dict[str, Any] = run.manifest
                    questions.extend(q["content"] for q in manifest["questions"])
            return {
                "topics": sorted({q["topic"] for q in questions}),
                "difficulties": sorted({q["difficulty"] for q in questions}),
            }

    def get(self, comparison_id: UUID) -> ComparisonView:
        with Session(self.engine) as session:
            row = session.get(Comparison, comparison_id)
            if row is None:
                raise PlatformError("comparison_not_found", "Comparison not found.", 404)
            return self.view(row)

    def manifest(self, comparison_id: UUID) -> dict[str, object]:
        with Session(self.engine) as session:
            row = session.get(Comparison, comparison_id)
            if row is None:
                raise PlatformError("comparison_not_found", "Comparison not found.", 404)
            return row.manifest

    def list(self, limit: int, offset: int) -> Page[ComparisonView]:
        with Session(self.engine) as session:
            rows = list(
                session.scalars(
                    select(Comparison)
                    .order_by(Comparison.created_at.desc(), Comparison.id)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            return Page(
                items=[self.view(row, detail=False) for row in rows[:limit]],
                next_cursor=str(offset + limit) if len(rows) > limit else None,
            )

    def owned(self, session: Session, comparison_id: UUID, token: UUID) -> Comparison:
        row = session.scalar(
            select(Comparison)
            .where(
                Comparison.id == comparison_id,
                Comparison.state == "running",
                Comparison.lease_token == token,
                Comparison.lease_expires_at > func.clock_timestamp(),
            )
            .with_for_update()
        )
        if row is None:
            raise LostLease
        return row

    def claim(self) -> tuple[UUID, UUID] | None:
        with Session(self.engine) as session, session.begin():
            row = session.scalar(
                select(Comparison)
                .where(
                    or_(
                        Comparison.state == "pending",
                        and_(
                            Comparison.state == "running",
                            Comparison.lease_expires_at <= func.clock_timestamp(),
                        ),
                    )
                )
                .order_by(Comparison.created_at, Comparison.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if row is None:
                return None
            now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            row.state, row.lease_token = "running", uuid4()
            row.lease_expires_at = now + timedelta(seconds=self.settings.job_lease_seconds)
            if row.attempts >= row.max_attempts:
                session.flush()
                row.state, row.output = (
                    "failed",
                    {
                        "error_code": "attempts_exhausted",
                        "error_message": "Analysis retry budget exhausted; submit a new "
                        "comparison.",
                    },
                )
                row.lease_token = row.lease_expires_at = None
                return None
            row.attempts += 1
            return row.id, row.lease_token

    def heartbeat(self, comparison_id: UUID, token: UUID) -> None:
        with Session(self.engine) as session, session.begin():
            row = self.owned(session, comparison_id, token)
            now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            row.lease_expires_at = now + timedelta(seconds=self.settings.job_lease_seconds)
        record_worker_heartbeat(self.engine)

    def complete(self, comparison_id: UUID, token: UUID, output: dict[str, Any]) -> None:
        with Session(self.engine) as session, session.begin():
            row = self.owned(session, comparison_id, token)
            if "error_code" not in output and output.get("version") != ANALYSIS_VERSION:
                raise PlatformError("analysis_invalid", "Analysis output version differs.")
            row.output, row.state = output, "failed" if "error_code" in output else "completed"
            row.lease_token = row.lease_expires_at = None

    def process(self, comparison_id: UUID, token: UUID, stop: Event) -> None:
        lost, finished = Event(), Event()

        def keep_alive() -> None:
            while not finished.wait(self.settings.job_heartbeat_seconds):
                try:
                    self.heartbeat(comparison_id, token)
                except Exception:
                    lost.set()
                    return

        thread = Thread(target=keep_alive, daemon=True)
        thread.start()
        try:
            with Session(self.engine) as session:
                row = self.owned(session, comparison_id, token)
                manifest = row.manifest
                if digest(manifest) != row.manifest_hash or manifest[
                    "execution"
                ] != execution_identity(self.settings):
                    raise PlatformError(
                        "comparison_runtime_mismatch",
                        "Analysis code/locks/runtime differs from its frozen submission.",
                    )
                if manifest["version"] != ANALYSIS_VERSION:
                    raise PlatformError(
                        "comparison_policy_mismatch", "Frozen analysis version differs."
                    )
                request = ComparisonCreate.model_validate(manifest["request"])
            output = analyze(
                RunSample.model_validate(manifest["baseline"]),
                RunSample.model_validate(manifest["candidate"]),
                exploratory=request.exploratory,
                seed=request.seed,
                resamples=request.resamples,
                stop=stop,
                lost=lost,
            )
            if not stop.is_set() and not lost.is_set():
                self.complete(comparison_id, token, output)
        except LostLease:
            pass
        except Exception as error:
            if not stop.is_set() and not lost.is_set():
                safe = (
                    error
                    if isinstance(error, PlatformError)
                    else PlatformError(
                        "comparison_failed", "Analysis failed; no scores are inferred."
                    )
                )
                with contextlib.suppress(LostLease):
                    self.complete(
                        comparison_id,
                        token,
                        {"error_code": safe.code, "error_message": safe.message},
                    )
        finally:
            finished.set()
            thread.join(timeout=2)
