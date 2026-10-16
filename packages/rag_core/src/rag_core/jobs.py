"""Leased ingestion, recoverable checkpoints, and fenced evidence commits."""

import contextlib
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from threading import Event, Thread
from uuid import UUID, uuid4, uuid5

from sqlalchemy import Engine, and_, func, or_, select
from sqlalchemy.orm import Session

from rag_core.database import record_worker_heartbeat
from rag_core.errors import LostLease, PlatformError
from rag_core.extraction import EXTRACTOR_VERSION
from rag_core.models import Document, DocumentRevision, Job, SourceSection
from rag_core.processes import hidden_window_flags
from rag_core.schemas import Extraction
from rag_core.settings import Settings
from rag_core.storage import BlobStore


class IngestionQueue:
    def __init__(self, engine: Engine, settings: Settings) -> None:
        self.engine, self.settings = engine, settings
        self.blobs = BlobStore(settings.artifact_root)

    def claim(self) -> tuple[UUID, UUID] | None:
        with Session(self.engine) as session, session.begin():
            eligible = or_(
                and_(Job.state == "pending", Job.available_at <= func.clock_timestamp()),
                and_(Job.state == "running", Job.lease_expires_at <= func.clock_timestamp()),
            )
            while job := session.scalar(
                select(Job)
                .where(eligible)
                .order_by(Job.created_at, Job.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            ):
                if job.attempts >= job.max_attempts:
                    document = session.get(Document, job.document_id)
                    assert document is not None
                    self._failure(
                        job, document, "attempts_exhausted", "Ingestion exhausted its retry budget."
                    )
                    session.flush()
                    continue
                now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
                token = uuid4()
                job.state, job.lease_token = "running", token
                job.attempts += 1
                job.heartbeat_at = now
                job.lease_expires_at = now + timedelta(seconds=self.settings.job_lease_seconds)
                document = session.get(Document, job.document_id)
                assert document is not None
                document.state = "processing"
                return job.id, token
        return None

    def _owned(self, session: Session, job_id: UUID, token: UUID) -> Job:
        job = session.scalar(
            select(Job)
            .where(
                Job.id == job_id,
                Job.lease_token == token,
                Job.state == "running",
                Job.lease_expires_at > func.clock_timestamp(),
            )
            .with_for_update()
        )
        if job is None:
            raise LostLease
        return job

    def heartbeat(self, job_id: UUID, token: UUID) -> None:
        with Session(self.engine) as session, session.begin():
            job = self._owned(session, job_id, token)
            now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            job.heartbeat_at = now
            job.lease_expires_at = now + timedelta(seconds=self.settings.job_lease_seconds)
        record_worker_heartbeat(self.engine)

    @staticmethod
    def _failure(job: Job, document: Document, code: str, message: str) -> None:
        job.state, document.state = "failed", "failed"
        job.error_code = document.error_code = code
        job.error_message = document.error_message = message
        job.lease_token = job.lease_expires_at = None

    def fail(self, job_id: UUID, token: UUID, error: PlatformError) -> None:
        with Session(self.engine) as session, session.begin():
            job = self._owned(session, job_id, token)
            document = session.get(Document, job.document_id)
            assert document is not None
            if error.retryable and job.attempts < job.max_attempts:
                job.state = document.state = "pending"
                now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
                job.available_at = now + timedelta(seconds=2**job.attempts)
                job.lease_token = job.lease_expires_at = None
            else:
                self._failure(job, document, error.code, error.message)

    def checkpoint(self, job_id: UUID, token: UUID, key: str) -> None:
        with Session(self.engine) as session, session.begin():
            self._owned(session, job_id, token).checkpoint = {
                "key": key,
                "extractor": EXTRACTOR_VERSION,
            }

    def complete(self, job_id: UUID, token: UUID, extraction: Extraction) -> None:
        with Session(self.engine) as session, session.begin():
            job = self._owned(session, job_id, token)
            document = session.get(Document, job.document_id)
            assert document is not None
            if (
                extraction.input_checksum != document.checksum
                or extraction.extractor_version != EXTRACTOR_VERSION
            ):
                raise PlatformError(
                    "checkpoint_mismatch", "Extraction evidence does not match its original."
                )
            revision = DocumentRevision(
                id=uuid5(document.id, EXTRACTOR_VERSION),
                document_id=document.id,
                extractor_version=extraction.extractor_version,
                checksum=extraction.checksum,
                section_count=len(extraction.sections),
                character_count=extraction.character_count,
            )
            session.add(revision)
            session.flush()
            offset = 0
            for ordinal, section in enumerate(extraction.sections):
                session.add(
                    SourceSection(
                        id=uuid5(revision.id, str(ordinal)),
                        revision_id=revision.id,
                        ordinal=ordinal,
                        heading_path=section.heading_path,
                        text=section.text,
                        start_offset=offset,
                        end_offset=offset + len(section.text),
                        source=section.source.model_dump(exclude_none=True),
                    )
                )
                offset += len(section.text) + 2
            session.flush()
            now: datetime = session.execute(select(func.clock_timestamp())).scalar_one()
            if job.lease_expires_at is None or job.lease_expires_at <= now:
                raise LostLease
            revision.sealed = True
            document.state, job.state = "ready", "succeeded"
            document.error_code = document.error_message = job.error_code = job.error_message = None
            job.lease_token = job.lease_expires_at = None

    def process(self, job_id: UUID, token: UUID, stop: Event) -> None:
        lost, finished = Event(), Event()

        def keep_alive() -> None:
            while not finished.wait(self.settings.job_heartbeat_seconds):
                try:
                    self.heartbeat(job_id, token)
                except Exception:
                    lost.set()
                    return

        thread = Thread(target=keep_alive, daemon=True)
        thread.start()
        try:
            with Session(self.engine) as session:
                job = self._owned(session, job_id, token)
                document = session.get(Document, job.document_id)
                assert document is not None
                filename, checksum, original = (
                    document.filename,
                    document.checksum,
                    document.storage_key,
                )
                checkpoint = job.checkpoint
            extraction: Extraction | None = None
            if checkpoint and checkpoint.get("extractor") == EXTRACTOR_VERSION:
                try:
                    cached = json.loads(
                        self.blobs.path(str(checkpoint["key"])).read_text(encoding="utf-8")
                    )
                    candidate = Extraction.model_validate(cached["extraction"])
                    if candidate.input_checksum == checksum:
                        extraction = candidate
                except (OSError, ValueError, KeyError):
                    pass
            if extraction is None:
                key = f"checkpoints/{job_id}/{token}.json"
                output = self.blobs.path(key)
                output.parent.mkdir(parents=True, exist_ok=True)
                command = [
                    sys.executable,
                    "-m",
                    "rag_core.extract_child",
                    str(self.blobs.path(original)),
                    str(output),
                    filename,
                    checksum,
                    str(self.settings.max_extracted_characters),
                    str(self.settings.max_pdf_pages),
                ]
                child = subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=hidden_window_flags(),
                )
                deadline = time.monotonic() + self.settings.extraction_timeout_seconds
                try:
                    while child.poll() is None:
                        if lost.is_set() or stop.is_set():
                            raise LostLease
                        if time.monotonic() >= deadline:
                            raise PlatformError(
                                "extraction_timeout", "Extraction exceeded its time limit."
                            )
                        finished.wait(0.1)
                    if child.returncode != 0 or not output.exists():
                        raise PlatformError(
                            "extraction_failed", "The extraction process failed.", retryable=True
                        )
                    result = json.loads(output.read_text(encoding="utf-8"))
                    if "error" in result:
                        raise PlatformError(result["error"]["code"], result["error"]["message"])
                    extraction = Extraction.model_validate(result["extraction"])
                    self.checkpoint(job_id, token, key)
                finally:
                    if child.poll() is None:
                        child.kill()
                    child.wait()
            if lost.is_set() or stop.is_set():
                raise LostLease
            self.complete(job_id, token, extraction)
        except LostLease:
            pass  # Expiry makes interrupted work eligible for another owner.
        except PlatformError as error:
            with contextlib.suppress(LostLease):
                self.fail(job_id, token, error)
        except Exception:
            with contextlib.suppress(LostLease):
                self.fail(
                    job_id,
                    token,
                    PlatformError(
                        "ingestion_failed", "Ingestion failed; it can be retried.", retryable=True
                    ),
                )
        finally:
            finished.set()
            thread.join(timeout=5)
