"""Real PostgreSQL guarantees; TEST_DATABASE_URL must be a disposable database."""

import hashlib
import os
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from rag_api.main import create_app
from rag_core.database import create_database_engine
from rag_core.documents import DocumentStore
from rag_core.errors import LostLease
from rag_core.extraction import extract
from rag_core.jobs import IngestionQueue
from rag_core.models import CorpusVersion, Job, SourceSection
from rag_core.schemas import CorpusCreate
from rag_core.settings import Settings
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL/pgvector database")
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    return Settings(_env_file=None, artifact_root=tmp_path, worker_poll_seconds=1)


def test_upload_worker_publication_and_immutable_evidence(config: Settings) -> None:
    engine = create_database_engine(config)
    queue = IngestionQueue(engine, config)
    try:
        with TestClient(create_app(config)) as client:
            corpus = client.post("/api/v1/corpora", json={"name": f"Test {uuid4()}"}).json()
            path = f"/api/v1/corpora/{corpus['id']}"
            upload = client.post(
                f"{path}/documents",
                files={"file": ("guide.md", b"# SQL\n\nSELECT 1;", "text/markdown")},
            )
            assert upload.status_code == 202, upload.text
            document = upload.json()
            duplicate = client.post(
                f"{path}/documents",
                files={"file": ("renamed.md", b"# SQL\n\nSELECT 1;", "text/markdown")},
            ).json()
            assert duplicate["id"] == document["id"] and duplicate["job_id"] == document["job_id"]
            assert client.post(f"{path}/versions").status_code == 409
            claim = queue.claim()
            assert claim and str(claim[0]) == document["job_id"]
            queue.process(*claim, Event())
            ready = client.get(f"/api/v1/documents/{document['id']}").json()
            assert ready["state"] == "ready", ready
            sections = client.get(f"/api/v1/documents/{document['id']}/sections").json()["items"]
            assert sections[0]["source"]["start_line"] == 1
            assert sections[0]["end_offset"] - sections[0]["start_offset"] == len(
                sections[0]["text"]
            )
            version = client.post(f"{path}/versions").json()
            assert client.post(f"{path}/versions").json()["id"] == version["id"]
            with engine.begin() as connection, pytest.raises(IntegrityError):
                connection.execute(
                    text("UPDATE source_sections SET text='tampered' WHERE id=:id"),
                    {"id": sections[0]["id"]},
                )
            with engine.begin() as connection, pytest.raises(IntegrityError):
                connection.execute(
                    text("UPDATE corpus_versions SET manifest_hash='tampered' WHERE id=:id"),
                    {"id": version["id"]},
                )
            second = client.post(
                f"{path}/documents", files={"file": ("extra.txt", b"More evidence.", "text/plain")}
            )
            assert second.status_code == 202
            claim = queue.claim()
            assert claim
            queue.process(*claim, Event())
            new_version = client.post(f"{path}/versions").json()
            assert new_version["version"] == 2 and new_version["document_count"] == 2
            stored = client.get(f"{path}/versions").json()["items"]
            assert stored[0]["manifest"] == version["manifest"]
            assert len(list(config.artifact_root.glob("originals/*"))) == 2
            assert client.get(f"/api/v1/jobs/{document['job_id']}").json()["state"] == "succeeded"
    finally:
        engine.dispose()


def test_claim_skips_locked_jobs_and_exhausted_attempts_are_terminal(config: Settings) -> None:
    engine = create_database_engine(config)
    store, queue = DocumentStore(engine), IngestionQueue(engine, config)
    try:
        corpus = store.create_corpus(CorpusCreate(name=f"Leases {uuid4()}"))
        first, _ = store.upload(
            corpus.id, "first.txt", "originals/first.txt", "1" * 64, 1, "text/plain", 1
        )
        second, _ = store.upload(
            corpus.id, "second.txt", "originals/second.txt", "2" * 64, 1, "text/plain", 1
        )
        with Session(engine) as session, session.begin():
            session.scalar(select(Job).where(Job.id == first.job_id).with_for_update())
            claim = queue.claim()
            assert claim and claim[0] == second.job_id
        next_claim = queue.claim()
        assert next_claim and next_claim[0] == first.job_id
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE jobs SET lease_expires_at=clock_timestamp() "
                    "-interval '1 second' WHERE id IN (:first,:second)"
                ),
                {"first": first.job_id, "second": second.job_id},
            )
        assert queue.claim() is None
        assert store.job(first.job_id).state == "failed"
        assert store.job(first.job_id).error_code == "attempts_exhausted"
        assert store.document(second.id).state == "failed"
        store.retry(first.id)
        assert store.job(first.job_id).attempts == 0
        claim = queue.claim()
        assert claim and claim[0] == first.job_id
        queue.process(*claim, Event())
        assert store.job(first.job_id).state == "failed"  # Missing original is explicit.
    finally:
        engine.dispose()


def test_expired_owner_is_fenced_and_checkpoint_survives_reclaim(config: Settings) -> None:
    engine = create_database_engine(config)
    store, queue = DocumentStore(engine), IngestionQueue(engine, config)
    try:
        corpus = store.create_corpus(CorpusCreate(name=f"Recovery {uuid4()}"))
        raw = b"Canonical evidence."
        key = "originals/recovery.txt"
        path = queue.blobs.path(key)
        path.parent.mkdir(parents=True)
        path.write_bytes(raw)
        checksum = hashlib.sha256(raw).hexdigest()
        document, _ = store.upload(
            corpus.id, "recovery.txt", key, checksum, len(raw), "text/plain", 3
        )
        claim = queue.claim()
        assert claim and claim[0] == document.job_id
        extracted = extract(path, "recovery.txt", checksum, 10000, 20)
        checkpoint = "checkpoints/recovery.json"
        target = queue.blobs.path(checkpoint)
        target.parent.mkdir(parents=True)
        target.write_text('{"extraction":' + extracted.model_dump_json() + "}", encoding="utf-8")
        queue.checkpoint(*claim, checkpoint)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE jobs SET lease_expires_at=clock_timestamp() "
                    "-interval '1 second' WHERE id=:id"
                ),
                {"id": claim[0]},
            )
        reclaimed = queue.claim()
        assert reclaimed and reclaimed[0] == claim[0] and reclaimed[1] != claim[1]
        with pytest.raises(LostLease):
            queue.complete(*claim, extracted)
        # Removing the original proves the persisted extraction checkpoint is used.
        path.unlink()
        queue.process(*reclaimed, Event())
        assert store.document(document.id).state == "ready"
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(SourceSection))
            job = session.get(Job, document.job_id)
            assert job and job.attempts == 2
            assert session.get(CorpusVersion, UUID(int=0)) is None
    finally:
        engine.dispose()
