"""Durable per-question execution; model work never holds database transactions."""

import contextlib
import time
from datetime import datetime, timedelta
from threading import Event, Thread
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from rag_core.database import record_worker_heartbeat
from rag_core.dataset_schemas import QuestionInput
from rag_core.embeddings import DENSE_STRATEGY, run_embeddings
from rag_core.errors import LostLease, PlatformError
from rag_core.generation import GenerationInput, generate, generation_contract, prepare_generation
from rag_core.indexes import IndexStore, SearchInput, SearchView
from rag_core.retrieval_evaluation import score_retrieval
from rag_core.run_models import QuestionResult, Run, RunAttempt
from rag_core.runs import RunStore, execution_identity


class RunQueue(RunStore):
    def owned(self, session: Session, run_id: UUID, token: UUID) -> Run:
        row = session.scalar(
            select(Run)
            .where(
                Run.id == run_id,
                Run.state == "running",
                Run.lease_token == token,
                Run.lease_expires_at > func.clock_timestamp(),
            )
            .with_for_update()
        )
        if row is None:
            raise LostLease
        return row

    def claim(self) -> tuple[UUID, UUID] | None:
        with Session(self.engine) as session, session.begin():
            eligible = or_(
                and_(Run.state == "queued", Run.available_at <= func.clock_timestamp()),
                and_(Run.state == "running", Run.lease_expires_at <= func.clock_timestamp()),
            )
            while row := session.scalar(
                select(Run)
                .where(eligible)
                .order_by(Run.created_at, Run.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            ):
                exhausted = row.attempts >= row.max_attempts
                now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
                row.state, row.lease_token = "running", uuid4()
                row.lease_expires_at = now + timedelta(seconds=self.settings.job_lease_seconds)
                row.started_at = row.started_at or now
                if not exhausted:
                    row.attempts += 1
                session.flush()
                unfinished = session.scalars(
                    select(RunAttempt).where(
                        RunAttempt.run_id == row.id, RunAttempt.state == "started"
                    )
                )
                for attempt in unfinished:
                    attempt.state, attempt.finished_at = (
                        ("cancelled" if row.cancel_requested else "interrupted"),
                        now,
                    )
                    attempt.error_code = (
                        "cancel_requested" if row.cancel_requested else "ownership_reassigned"
                    )
                session.flush()
                if row.cancel_requested:
                    row.state, row.finished_at = "cancelled", now
                    row.lease_token = row.lease_expires_at = None
                    session.flush()
                    continue
                if exhausted:
                    row.state, row.error_code = "failed", "attempts_exhausted"
                    row.error_message = (
                        "Run exhausted its recovery budget. Completed results remain available."
                    )
                    row.finished_at = now
                    row.lease_token = row.lease_expires_at = None
                    session.flush()
                    continue
                return row.id, row.lease_token
        return None

    def heartbeat(self, run_id: UUID, token: UUID) -> bool:
        with Session(self.engine) as session, session.begin():
            row = self.owned(session, run_id, token)
            now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            row.lease_expires_at = now + timedelta(seconds=self.settings.job_lease_seconds)
            cancelled = row.cancel_requested
        record_worker_heartbeat(self.engine)
        return cancelled

    def start_question(self, run_id: UUID, token: UUID, question_id: UUID, repeat: int) -> UUID:
        with Session(self.engine) as session, session.begin():
            row = self.owned(session, run_id, token)
            if row.cancel_requested:
                raise LostLease
            ordinal = (
                session.scalar(
                    select(func.max(RunAttempt.ordinal)).where(
                        RunAttempt.run_id == run_id,
                        RunAttempt.question_id == question_id,
                        RunAttempt.repeat == repeat,
                    )
                )
                or 0
            ) + 1
            attempt = RunAttempt(
                run_id=run_id,
                question_id=question_id,
                repeat=repeat,
                ordinal=ordinal,
                lease_token=token,
            )
            session.add(attempt)
            session.flush()
            return attempt.id

    def checkpoint(
        self, run_id: UUID, token: UUID, attempt_id: UUID, trace: dict[str, object]
    ) -> None:
        with Session(self.engine) as session, session.begin():
            row = self.owned(session, run_id, token)
            if row.cancel_requested:
                raise LostLease
            attempt = session.get(RunAttempt, attempt_id)
            if (
                attempt is None
                or attempt.run_id != run_id
                or attempt.lease_token != token
                or attempt.state != "started"
            ):
                raise LostLease
            attempt.trace = trace.copy()

    def save_result(
        self,
        run_id: UUID,
        token: UUID,
        attempt_id: UUID,
        revision: int,
        state: str,
        trace: dict[str, object],
    ) -> None:
        with Session(self.engine) as session, session.begin():
            row = self.owned(session, run_id, token)
            if row.cancel_requested:
                raise LostLease
            attempt = session.get(RunAttempt, attempt_id)
            if (
                attempt is None
                or attempt.run_id != run_id
                or attempt.lease_token != token
                or attempt.state != "started"
            ):
                raise LostLease
            now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            session.add(
                QuestionResult(
                    run_id=run_id,
                    question_id=attempt.question_id,
                    question_revision=revision,
                    repeat=attempt.repeat,
                    state=state,
                    trace=trace.copy(),
                )
            )
            attempt.trace, attempt.state = (
                trace.copy(),
                "completed" if state == "succeeded" else "failed",
            )
            error = trace.get("error")
            attempt.error_code = str(error["code"]) if isinstance(error, dict) else None
            attempt.finished_at = now

    def finish(self, run_id: UUID, token: UUID, error: PlatformError | None = None) -> None:
        with Session(self.engine) as session, session.begin():
            row = self.owned(session, run_id, token)
            now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            if row.cancel_requested or error:
                for attempt in session.scalars(
                    select(RunAttempt).where(
                        RunAttempt.run_id == run_id, RunAttempt.state == "started"
                    )
                ):
                    attempt.state = "cancelled" if row.cancel_requested else "interrupted"
                    attempt.error_code = (
                        "cancel_requested"
                        if row.cancel_requested
                        else error.code
                        if error
                        else None
                    )
                    attempt.finished_at = now
                session.flush()
            if row.cancel_requested:
                row.state = "cancelled"
            elif error:
                row.state, row.error_code, row.error_message = "failed", error.code, error.message
            else:
                count = session.scalar(
                    select(func.count())
                    .select_from(QuestionResult)
                    .where(QuestionResult.run_id == run_id)
                )
                if count != row.total_count:
                    raise PlatformError("run_incomplete", "Run has unprocessed questions.")
                failures = session.scalar(
                    select(func.count())
                    .select_from(QuestionResult)
                    .where(QuestionResult.run_id == run_id, QuestionResult.state == "failed")
                )
                row.state = "completed_with_errors" if failures else "completed"
            row.finished_at = now
            row.lease_token = row.lease_expires_at = None

    def retrieve(
        self, index_id: UUID, query: str, top_k: int, stop: Event, lost: Event
    ) -> SearchView:
        store = IndexStore(self.engine, self.settings)
        value = SearchInput(query=query, top_k=top_k, context_tokens=0)
        if store.get(index_id).config["retrieval"] == DENSE_STRATEGY:
            encoded = run_embeddings([query], self.settings, stop, lost)
            return store.dense_result(index_id, value, encoded)
        return store.search(index_id, value)

    def process(self, run_id: UUID, token: UUID, stop: Event) -> None:
        lost, abort, cancelled, finished = Event(), Event(), Event(), Event()

        def keep_alive() -> None:
            while not finished.wait(min(2, self.settings.job_heartbeat_seconds)):
                try:
                    if self.heartbeat(run_id, token):
                        cancelled.set()
                        abort.set()
                except Exception:
                    lost.set()
                    abort.set()
                    return

        thread = Thread(target=keep_alive, daemon=True)
        thread.start()
        try:
            with Session(self.engine) as session:
                row = self.owned(session, run_id, token)
                manifest = row.manifest
                cancelled_at_start = row.cancel_requested
                completed = set(
                    session.execute(
                        select(QuestionResult.question_id, QuestionResult.repeat).where(
                            QuestionResult.run_id == run_id
                        )
                    )
                )
            if cancelled_at_start:
                cancelled.set()
                raise LostLease
            if not self.settings.local_generation_enabled:
                raise PlatformError(
                    "generation_not_configured", "Local CPU generation is disabled."
                )
            config = manifest["config"]
            assert isinstance(config, dict)
            if config["generation"] != generation_contract() or manifest[
                "execution"
            ] != execution_identity(self.settings):
                raise PlatformError(
                    "run_runtime_mismatch",
                    "Worker code, locks, or runtime differs from the frozen run.",
                )
            prepare_generation(self.settings, stop, abort)
            index_id = UUID(str(manifest["index_id"]))
            questions = manifest["questions"]
            assert isinstance(questions, list)
            for snapshot in questions:
                question_id = UUID(snapshot["id"])
                question = QuestionInput.model_validate(snapshot["content"])
                for repeat in range(int(config["repeats"])):
                    if (question_id, repeat) in completed:
                        continue
                    if stop.is_set() or lost.is_set() or cancelled.is_set():
                        raise LostLease
                    try:
                        attempt_id = self.start_question(run_id, token, question_id, repeat)
                    except LostLease:
                        if self.get(run_id).cancel_requested:
                            cancelled.set()
                        raise
                    trace: dict[str, object] = {
                        "question": snapshot,
                        "repeat": repeat,
                        "timings": {},
                        "generation": None,
                        "answer_metrics": {
                            name: {"state": "unavailable", "value": None}
                            for name in (
                                "correctness",
                                "faithfulness",
                                "citation_support",
                                "abstention_quality",
                            )
                        },
                        "cost": None,
                        "cost_state": "unavailable",
                    }
                    started = time.monotonic()
                    stage = "retrieval"
                    state = "succeeded"
                    try:
                        retrieval = self.retrieve(
                            index_id, question.text, int(config["top_k"]), stop, abort
                        )
                        trace["retrieval"] = retrieval.model_dump(mode="json", exclude={"context"})
                        trace["retrieval_scores"] = score_retrieval(
                            question, [hit.chunk for hit in retrieval.hits]
                        ).model_dump(mode="json")
                        trace["timings"] = {
                            "retrieval_wall_ms": (time.monotonic() - started) * 1000
                        }
                        self.checkpoint(run_id, token, attempt_id, trace)
                        stage, generation_started = "generation", time.monotonic()
                        answer = generate(
                            GenerationInput(
                                question=question.text,
                                passages=[hit.chunk for hit in retrieval.hits],
                                context_tokens=int(config["context_tokens"]),
                                max_new_tokens=int(config["max_new_tokens"]),
                                seed=int(config["seed"]) + repeat,
                                threads=self.settings.generation_threads,
                            ),
                            self.settings,
                            stop,
                            abort,
                        )
                        trace["generation"] = answer.model_dump(mode="json")
                        trace["context_scores"] = score_retrieval(
                            question, answer.context.passages
                        ).model_dump(mode="json")
                        trace["timings"] = {
                            **cast(dict[str, float], trace["timings"]),
                            "generation_wall_ms": (time.monotonic() - generation_started) * 1000,
                            "question_wall_ms": (time.monotonic() - started) * 1000,
                        }
                    except LostLease:
                        raise
                    except Exception as error:
                        safe = (
                            error
                            if isinstance(error, PlatformError)
                            else PlatformError(
                                "question_execution_failed",
                                "Question execution failed; inspect configuration.",
                            )
                        )
                        trace["error"] = {
                            "stage": stage,
                            "code": safe.code,
                            "message": safe.message,
                        }
                        trace["timings"] = {
                            **cast(dict[str, float], trace["timings"]),
                            "question_wall_ms": (time.monotonic() - started) * 1000,
                        }
                        state = "failed"
                    if stop.is_set() or lost.is_set() or cancelled.is_set():
                        raise LostLease
                    self.save_result(
                        run_id, token, attempt_id, int(snapshot["revision"]), state, trace
                    )
            self.finish(run_id, token)
        except LostLease:
            if (
                not stop.is_set()
                and not lost.is_set()
                and (cancelled.is_set() or self.get(run_id).cancel_requested)
            ):
                with contextlib.suppress(LostLease):
                    self.finish(run_id, token)
        except Exception as error:
            if not stop.is_set() and not lost.is_set():
                with contextlib.suppress(LostLease):
                    self.finish(
                        run_id,
                        token,
                        error
                        if isinstance(error, PlatformError)
                        else PlatformError(
                            "run_failed",
                            "Run failed before completion. Existing results remain available.",
                        ),
                    )
        finally:
            finished.set()
            thread.join(timeout=3)
