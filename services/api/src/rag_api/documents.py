"""Document ingestion routes; parsing remains in the durable worker."""

from pathlib import PureWindowsPath
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Query, UploadFile
from rag_core.documents import DocumentStore
from rag_core.errors import PlatformError
from rag_core.schemas import (
    CorpusCreate,
    CorpusView,
    DocumentView,
    JobView,
    Page,
    SectionView,
    VersionView,
)
from rag_core.settings import Settings
from rag_core.storage import BlobStore
from sqlalchemy import Engine
from starlette.concurrency import run_in_threadpool

Limit = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[int, Query(ge=0)]


def document_router(engine: Engine, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    store, blobs = DocumentStore(engine), BlobStore(settings.artifact_root)

    @router.post("/corpora", response_model=CorpusView, status_code=201)
    def create_corpus(value: CorpusCreate) -> CorpusView:
        return store.create_corpus(value)

    @router.get("/corpora", response_model=Page[CorpusView])
    def corpora(limit: Limit = 100, cursor: Cursor = 0) -> Page[CorpusView]:
        return store.corpora(limit, cursor)

    @router.get("/corpora/{corpus_id}", response_model=CorpusView)
    def corpus(corpus_id: UUID) -> CorpusView:
        return store.corpus(corpus_id)

    @router.get("/corpora/{corpus_id}/documents", response_model=Page[DocumentView])
    def documents(corpus_id: UUID, limit: Limit = 100, cursor: Cursor = 0) -> Page[DocumentView]:
        return store.documents(corpus_id, limit, cursor)

    @router.post("/corpora/{corpus_id}/documents", response_model=DocumentView, status_code=202)
    async def upload(corpus_id: UUID, file: Annotated[UploadFile, File()]) -> DocumentView:
        filename = PureWindowsPath(file.filename or "").name
        if not filename or len(filename) > 240 or any(ord(c) < 32 for c in filename):
            raise PlatformError("invalid_filename", "Provide a filename of at most 240 characters.")
        await run_in_threadpool(store.corpus, corpus_id)
        key, checksum, size, mime = await blobs.upload(
            filename, file.read, settings.max_upload_bytes
        )
        try:
            document, created = await run_in_threadpool(
                store.upload,
                corpus_id,
                filename,
                key,
                checksum,
                size,
                mime,
                settings.job_max_attempts,
            )
            if not created:
                blobs.path(key).unlink(missing_ok=True)
            return document
        finally:
            # Retain the original if a connection/cancellation makes the commit outcome unknown.
            # Removing it could corrupt a document that committed successfully.
            await file.close()

    @router.get("/documents/{document_id}", response_model=DocumentView)
    def document(document_id: UUID) -> DocumentView:
        return store.document(document_id)

    @router.get("/documents/{document_id}/sections", response_model=Page[SectionView])
    def sections(document_id: UUID, limit: Limit = 20, cursor: Cursor = 0) -> Page[SectionView]:
        return store.sections(document_id, limit, cursor)

    @router.post("/documents/{document_id}/retry", response_model=DocumentView, status_code=202)
    def retry(document_id: UUID) -> DocumentView:
        return store.retry(document_id)

    @router.get("/jobs/{job_id}", response_model=JobView)
    def job(job_id: UUID) -> JobView:
        return store.job(job_id)

    @router.post("/corpora/{corpus_id}/versions", response_model=VersionView, status_code=201)
    def publish(corpus_id: UUID) -> VersionView:
        return store.publish(corpus_id)

    @router.get("/corpora/{corpus_id}/versions", response_model=Page[VersionView])
    def versions(corpus_id: UUID, limit: Limit = 100, cursor: Cursor = 0) -> Page[VersionView]:
        return store.versions(corpus_id, limit, cursor)

    return router
