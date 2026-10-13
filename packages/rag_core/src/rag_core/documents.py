"""Transactional corpus drafts and immutable publication."""

import hashlib
import json
from uuid import UUID

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from rag_core.errors import PlatformError
from rag_core.models import (
    Corpus,
    CorpusVersion,
    CorpusVersionMember,
    Document,
    DocumentRevision,
    Job,
    SourceSection,
)
from rag_core.schemas import (
    CorpusCreate,
    CorpusView,
    DocumentView,
    JobView,
    Page,
    SectionView,
    VersionView,
)


def require_corpus(session: Session, corpus_id: UUID, lock: bool = False) -> Corpus:
    query = select(Corpus).where(Corpus.id == corpus_id)
    corpus = session.scalar(query.with_for_update() if lock else query)
    if corpus is None:
        raise PlatformError("not_found", "The corpus was not found.", 404)
    return corpus


def document_view(session: Session, document: Document) -> DocumentView:
    job = session.scalar(select(Job).where(Job.document_id == document.id))
    revision = session.scalar(
        select(DocumentRevision).where(DocumentRevision.document_id == document.id)
    )
    assert job is not None
    values = {
        field: getattr(document, field)
        for field in DocumentView.model_fields
        if hasattr(document, field)
    }
    return DocumentView(
        **values,
        job_id=job.id,
        section_count=revision.section_count if revision else 0,
        revision_id=revision.id if revision else None,
    )


class DocumentStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create_corpus(self, value: CorpusCreate) -> CorpusView:
        with Session(self.engine) as session, session.begin():
            corpus = Corpus(**value.model_dump())
            session.add(corpus)
            session.flush()
            return CorpusView.model_validate(corpus)

    def corpora(self, limit: int, offset: int) -> Page[CorpusView]:
        with Session(self.engine) as session:
            rows = list(
                session.scalars(
                    select(Corpus)
                    .order_by(Corpus.created_at, Corpus.id)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            return Page(
                items=[CorpusView.model_validate(row) for row in rows[:limit]],
                next_cursor=str(offset + limit) if len(rows) > limit else None,
            )

    def corpus(self, corpus_id: UUID) -> CorpusView:
        with Session(self.engine) as session:
            return CorpusView.model_validate(require_corpus(session, corpus_id))

    def upload(
        self,
        corpus_id: UUID,
        filename: str,
        key: str,
        checksum: str,
        size: int,
        media_type: str,
        max_attempts: int,
    ) -> tuple[DocumentView, bool]:
        with Session(self.engine) as session, session.begin():
            corpus = require_corpus(session, corpus_id, lock=True)
            existing = session.scalar(
                select(Document).where(
                    Document.corpus_id == corpus_id, Document.checksum == checksum
                )
            )
            if existing:
                return document_view(session, existing), False
            document = Document(
                corpus_id=corpus_id,
                filename=filename,
                storage_key=key,
                checksum=checksum,
                byte_count=size,
                media_type=media_type,
            )
            session.add(document)
            session.flush()
            session.add(Job(document_id=document.id, max_attempts=max_attempts))
            corpus.draft_revision += 1
            session.flush()
            return document_view(session, document), True

    def documents(self, corpus_id: UUID, limit: int, offset: int) -> Page[DocumentView]:
        with Session(self.engine) as session:
            require_corpus(session, corpus_id)
            rows = list(
                session.scalars(
                    select(Document)
                    .where(Document.corpus_id == corpus_id)
                    .order_by(Document.created_at, Document.id)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            return Page(
                items=[document_view(session, row) for row in rows[:limit]],
                next_cursor=str(offset + limit) if len(rows) > limit else None,
            )

    def document(self, document_id: UUID) -> DocumentView:
        with Session(self.engine) as session:
            document = session.get(Document, document_id)
            if document is None:
                raise PlatformError("not_found", "The document was not found.", 404)
            return document_view(session, document)

    def sections(self, document_id: UUID, limit: int, offset: int) -> Page[SectionView]:
        with Session(self.engine) as session:
            if session.get(Document, document_id) is None:
                raise PlatformError("not_found", "The document was not found.", 404)
            revision = session.scalar(
                select(DocumentRevision).where(DocumentRevision.document_id == document_id)
            )
            if revision is None:
                raise PlatformError("document_not_ready", "Extraction has not completed.", 409)
            rows = list(
                session.scalars(
                    select(SourceSection)
                    .where(SourceSection.revision_id == revision.id)
                    .order_by(SourceSection.ordinal)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            return Page(
                items=[SectionView.model_validate(row) for row in rows[:limit]],
                next_cursor=str(offset + limit) if len(rows) > limit else None,
            )

    def job(self, job_id: UUID) -> JobView:
        with Session(self.engine) as session:
            job = session.get(Job, job_id)
            if job is None:
                raise PlatformError("not_found", "The job was not found.", 404)
            value = JobView.model_validate(job)
            value.checkpoint_stage = "extracted" if job.checkpoint else None
            return value

    def retry(self, document_id: UUID) -> DocumentView:
        with Session(self.engine) as session, session.begin():
            job = session.scalar(
                select(Job).where(Job.document_id == document_id).with_for_update()
            )
            if job is None:
                raise PlatformError("not_found", "The document was not found.", 404)
            if job.state != "failed":
                raise PlatformError(
                    "retry_not_available", "Only failed documents can be retried.", 409
                )
            document = session.get(Document, document_id)
            assert document is not None
            job.state, job.attempts = "pending", 0
            job.available_at = session.execute(select(func.clock_timestamp())).scalar_one()
            job.error_code = job.error_message = None
            document.state = "pending"
            document.error_code = document.error_message = None
            session.flush()
            return document_view(session, document)

    def publish(self, corpus_id: UUID) -> VersionView:
        with Session(self.engine) as session, session.begin():
            corpus = require_corpus(session, corpus_id, lock=True)
            previous = session.scalar(
                select(CorpusVersion).where(
                    CorpusVersion.corpus_id == corpus_id,
                    CorpusVersion.draft_revision == corpus.draft_revision,
                )
            )
            if previous:
                return VersionView.model_validate(previous)
            documents = list(
                session.scalars(
                    select(Document)
                    .where(Document.corpus_id == corpus_id)
                    .order_by(Document.id)
                    .with_for_update()
                )
            )
            if not documents or any(doc.state != "ready" for doc in documents):
                raise PlatformError(
                    "corpus_not_ready",
                    "Every document must finish extraction before publishing.",
                    409,
                )
            revisions = list(
                session.scalars(
                    select(DocumentRevision)
                    .join(Document)
                    .where(Document.corpus_id == corpus_id, DocumentRevision.sealed)
                    .order_by(DocumentRevision.id)
                )
            )
            if len(revisions) != len(documents):
                raise PlatformError("corpus_not_ready", "Document evidence is incomplete.", 409)
            by_id = {doc.id: doc for doc in documents}
            manifest: dict[str, object] = {
                "schema": "corpus-v1",
                "corpus_id": str(corpus_id),
                "documents": [
                    {
                        "document_id": str(r.document_id),
                        "revision_id": str(r.id),
                        "filename": by_id[r.document_id].filename,
                        "original_checksum": by_id[r.document_id].checksum,
                        "text_checksum": r.checksum,
                        "extractor_version": r.extractor_version,
                        "section_count": r.section_count,
                    }
                    for r in revisions
                ],
            }
            digest = hashlib.sha256(
                json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            latest = (
                session.scalar(
                    select(func.max(CorpusVersion.version)).where(
                        CorpusVersion.corpus_id == corpus_id
                    )
                )
                or 0
            )
            version = CorpusVersion(
                corpus_id=corpus_id,
                version=latest + 1,
                draft_revision=corpus.draft_revision,
                manifest=manifest,
                manifest_hash=digest,
                document_count=len(documents),
            )
            session.add(version)
            session.flush()
            session.add_all(
                [CorpusVersionMember(version_id=version.id, revision_id=r.id) for r in revisions]
            )
            session.flush()
            version.sealed = True
            session.flush()
            return VersionView.model_validate(version)

    def versions(self, corpus_id: UUID, limit: int, offset: int) -> Page[VersionView]:
        with Session(self.engine) as session:
            require_corpus(session, corpus_id)
            rows = list(
                session.scalars(
                    select(CorpusVersion)
                    .where(CorpusVersion.corpus_id == corpus_id)
                    .order_by(CorpusVersion.version)
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            return Page(
                items=[VersionView.model_validate(row) for row in rows[:limit]],
                next_cursor=str(offset + limit) if len(rows) > limit else None,
            )
