"""Durable dense query inference and exact retrieval; the API only queues and polls."""

import contextlib
import hashlib
from datetime import datetime, timedelta
from threading import Event, Thread
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine, and_, func, or_, select
from sqlalchemy.orm import Session

from rag_core.database import record_worker_heartbeat
from rag_core.embeddings import DENSE_STRATEGY, MAX_CONTENT_TOKENS, run_embeddings
from rag_core.errors import LostLease, PlatformError
from rag_core.index_models import DenseSearch, IndexVariant
from rag_core.indexes import IndexStore, SearchInput, SearchView
from rag_core.settings import Settings
from rag_core.tokenization import PinnedTokenizer


class DenseSearchView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    index_id: UUID
    state: Literal["pending", "running", "completed", "failed"]
    request: SearchInput
    result: SearchView | None
    attempts: int
    error_code: str | None
    error_message: str | None
    created_at: datetime


class DenseSearchQueue:
    def __init__(self, engine: Engine, settings: Settings) -> None:
        self.engine, self.settings = engine, settings

    def create(self, index_id: UUID, value: SearchInput) -> DenseSearchView:
        with Session(self.engine) as session, session.begin():
            index = session.scalar(
                select(IndexVariant).where(IndexVariant.id == index_id).with_for_update()
            )
            if index is None:
                raise PlatformError("index_not_found", "Index not found.", 404)
            if index.state != "ready" or index.config["retrieval"] != DENSE_STRATEGY:
                raise PlatformError("dense_index_required", "Choose a ready dense index.", 409)
            tokenizer = PinnedTokenizer.load(self.settings.model_cache_dir)
            if tokenizer.count(value.query) > MAX_CONTENT_TOKENS:
                raise PlatformError(
                    "embedding_input_too_long", "Dense queries must fit 254 content tokens."
                )
            digest = hashlib.sha256(value.model_dump_json().encode()).hexdigest()
            existing = session.scalar(
                select(DenseSearch).where(
                    DenseSearch.index_id == index_id,
                    DenseSearch.request_hash == digest,
                )
            )
            if existing:
                return DenseSearchView.model_validate(existing)
            row = DenseSearch(
                index_id=index_id,
                request_hash=digest,
                request=value.model_dump(),
                max_attempts=self.settings.job_max_attempts,
            )
            session.add(row)
            session.flush()
            return DenseSearchView.model_validate(row)

    def get(self, search_id: UUID) -> DenseSearchView:
        with Session(self.engine) as session:
            row = session.get(DenseSearch, search_id)
            if row is None:
                raise PlatformError("dense_search_not_found", "Dense search not found.", 404)
            return DenseSearchView.model_validate(row)

    def owned(self, session: Session, search_id: UUID, token: UUID) -> DenseSearch:
        row = session.scalar(
            select(DenseSearch)
            .where(
                DenseSearch.id == search_id,
                DenseSearch.state == "running",
                DenseSearch.lease_token == token,
                DenseSearch.lease_expires_at > func.clock_timestamp(),
            )
            .with_for_update()
        )
        if row is None:
            raise LostLease
        return row

    def claim(self) -> tuple[UUID, UUID] | None:
        with Session(self.engine) as session, session.begin():
            eligible = or_(
                and_(
                    DenseSearch.state == "pending",
                    DenseSearch.available_at <= func.clock_timestamp(),
                ),
                and_(
                    DenseSearch.state == "running",
                    DenseSearch.lease_expires_at <= func.clock_timestamp(),
                ),
            )
            while row := session.scalar(
                select(DenseSearch)
                .where(eligible)
                .order_by(DenseSearch.created_at, DenseSearch.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            ):
                if row.attempts >= row.max_attempts:
                    row.state, row.error_code = "failed", "attempts_exhausted"
                    row.error_message = "Dense search exhausted its retry budget."
                    row.lease_token = row.lease_expires_at = None
                    session.flush()
                    continue
                now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
                row.state, row.lease_token = "running", uuid4()
                row.attempts += 1
                row.lease_expires_at = now + timedelta(seconds=self.settings.job_lease_seconds)
                return row.id, row.lease_token
        return None

    def heartbeat(self, search_id: UUID, token: UUID) -> None:
        with Session(self.engine) as session, session.begin():
            row = self.owned(session, search_id, token)
            now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            row.lease_expires_at = now + timedelta(seconds=self.settings.job_lease_seconds)
        record_worker_heartbeat(self.engine)

    def complete(self, search_id: UUID, token: UUID, result: SearchView) -> None:
        with Session(self.engine) as session, session.begin():
            row = self.owned(session, search_id, token)
            request = SearchInput.model_validate(row.request)
            if (
                result.index_id != row.index_id
                or result.query != request.query
                or result.strategy != DENSE_STRATEGY
                or result.context.token_budget != request.context_tokens
            ):
                raise PlatformError("dense_result_mismatch", "Search result lineage is invalid.")
            row.result, row.state = result.model_dump(mode="json"), "completed"
            row.error_code = row.error_message = None
            row.lease_token = row.lease_expires_at = None

    def fail(self, search_id: UUID, token: UUID, error: PlatformError) -> None:
        with Session(self.engine) as session, session.begin():
            row = self.owned(session, search_id, token)
            row.state = (
                "pending" if error.retryable and row.attempts < row.max_attempts else "failed"
            )
            now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            row.available_at = now + timedelta(seconds=2**row.attempts)
            row.error_code, row.error_message = error.code, error.message
            row.lease_token = row.lease_expires_at = None

    def retry(self, search_id: UUID) -> DenseSearchView:
        with Session(self.engine) as session, session.begin():
            row = session.scalar(
                select(DenseSearch).where(DenseSearch.id == search_id).with_for_update()
            )
            if row is None:
                raise PlatformError("dense_search_not_found", "Dense search not found.", 404)
            if row.state != "failed":
                raise PlatformError(
                    "dense_search_not_failed", "Only failed searches can be retried.", 409
                )
            row.state, row.attempts = "pending", 0
            row.error_code = row.error_message = None
            row.available_at = session.execute(select(func.clock_timestamp())).scalar_one()
            return DenseSearchView.model_validate(row)

    def process(self, search_id: UUID, token: UUID, stop: Event) -> None:
        lost, finished = Event(), Event()

        def keep_alive() -> None:
            while not finished.wait(self.settings.job_heartbeat_seconds):
                try:
                    self.heartbeat(search_id, token)
                except Exception:
                    lost.set()
                    return

        thread = Thread(target=keep_alive, daemon=True)
        thread.start()
        try:
            with Session(self.engine) as session:
                row = self.owned(session, search_id, token)
                value, index_id = SearchInput.model_validate(row.request), row.index_id
            encoded = run_embeddings([value.query], self.settings, stop, lost)
            result = IndexStore(self.engine, self.settings).dense_result(index_id, value, encoded)
            if not stop.is_set() and not lost.is_set():
                self.complete(search_id, token, result)
        except LostLease:
            pass
        except Exception as error:
            if not stop.is_set() and not lost.is_set():
                with contextlib.suppress(LostLease):
                    self.fail(
                        search_id,
                        token,
                        error
                        if isinstance(error, PlatformError)
                        else PlatformError(
                            "dense_search_failed",
                            "Dense search failed. Inspect configuration and retry.",
                        ),
                    )
        finally:
            finished.set()
            thread.join(timeout=2)
