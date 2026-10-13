from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, UploadFile
from rag_core.dataset_schemas import (
    DatasetCreate,
    DatasetVersionView,
    DatasetView,
    ImportResult,
    QuestionInput,
    QuestionUpdate,
    QuestionView,
)
from rag_core.datasets import DatasetStore
from rag_core.errors import PlatformError
from rag_core.schemas import Page, SectionView
from rag_core.settings import Settings
from sqlalchemy import Engine
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from rag_api.documents import Cursor, Limit


def dataset_router(engine: Engine, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    store = DatasetStore(engine, settings.max_run_questions)

    @router.post("/datasets", response_model=DatasetView, status_code=201)
    def create(value: DatasetCreate) -> DatasetView:
        return store.create(value)

    @router.get("/datasets", response_model=Page[DatasetView])
    def datasets(limit: Limit = 100, cursor: Cursor = 0) -> Page[DatasetView]:
        return store.datasets(limit, cursor)

    @router.get("/datasets/{dataset_id}", response_model=DatasetView)
    def dataset(dataset_id: UUID) -> DatasetView:
        return store.get(dataset_id)

    @router.get("/datasets/{dataset_id}/questions", response_model=Page[QuestionView])
    def questions(dataset_id: UUID, limit: Limit = 100, cursor: Cursor = 0) -> Page[QuestionView]:
        return store.questions(dataset_id, limit, cursor)

    @router.post("/datasets/{dataset_id}/questions", response_model=QuestionView, status_code=201)
    def add(dataset_id: UUID, value: QuestionInput) -> QuestionView:
        return store.add(dataset_id, [value])[0]

    @router.patch("/datasets/{dataset_id}/questions/{question_id}", response_model=QuestionView)
    def update(dataset_id: UUID, question_id: UUID, value: QuestionUpdate) -> QuestionView:
        return store.update(dataset_id, question_id, value)

    @router.post("/datasets/{dataset_id}/import", response_model=ImportResult)
    async def import_jsonl(dataset_id: UUID, file: Annotated[UploadFile, File()]) -> ImportResult:
        try:
            raw = await file.read(settings.max_jsonl_bytes + 1)
            if len(raw) > settings.max_jsonl_bytes:
                raise PlatformError(
                    "import_too_large", "The JSONL file exceeds the import limit.", 413
                )
            return await run_in_threadpool(store.import_jsonl, dataset_id, raw)
        finally:
            await file.close()

    @router.post(
        "/datasets/{dataset_id}/versions", response_model=DatasetVersionView, status_code=201
    )
    def publish(dataset_id: UUID) -> DatasetVersionView:
        return store.publish(dataset_id)

    @router.get("/datasets/{dataset_id}/versions", response_model=Page[DatasetVersionView])
    def versions(
        dataset_id: UUID, limit: Limit = 100, cursor: Cursor = 0
    ) -> Page[DatasetVersionView]:
        return store.versions(dataset_id, limit, cursor)

    @router.get("/dataset-versions/{version_id}/export")
    def export(version_id: UUID) -> Response:
        return Response(
            store.export(version_id),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="dataset-{version_id}.jsonl"'},
        )

    @router.get("/corpus-versions/{version_id}/sections", response_model=Page[SectionView])
    def sections(version_id: UUID, limit: Limit = 20, cursor: Cursor = 0) -> Page[SectionView]:
        return store.source_sections(version_id, limit, cursor)

    @router.get("/corpus-versions/{version_id}/sections/{section_id}", response_model=SectionView)
    def section(version_id: UUID, section_id: UUID) -> SectionView:
        return store.source_section(version_id, section_id)

    return router
