from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from rag_core.export_models import ExportJob
from rag_core.exports import ExportCreate, ExportQueue, ExportView
from rag_core.settings import Settings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

from rag_api.evaluations import Key


def export_router(engine: Engine, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1/exports")
    store = ExportQueue(engine, settings)

    @router.get("/latest", response_model=ExportView | None)
    def latest(source_kind: Literal["run", "comparison"], source_id: UUID) -> ExportView | None:
        with Session(engine) as session:
            column = ExportJob.run_id if source_kind == "run" else ExportJob.comparison_id
            row = session.scalar(
                select(ExportJob)
                .where(column == source_id)
                .order_by(ExportJob.created_at.desc(), ExportJob.id.desc())
                .limit(1)
            )
            return ExportView.model_validate(row) if row else None

    @router.post("", response_model=ExportView, status_code=202)
    def create(value: ExportCreate, idempotency_key: Key) -> ExportView:
        return store.create(value, idempotency_key)

    @router.get("/{export_id}", response_model=ExportView)
    def get(export_id: UUID) -> ExportView:
        return store.get(export_id)

    @router.get("/{export_id}/download")
    def download(export_id: UUID) -> FileResponse:
        path = store.artifact(export_id)
        return FileResponse(
            path,
            media_type="application/zip",
            filename=f"rag-evidence-{export_id}.zip",
            headers={"X-Content-Type-Options": "nosniff"},
        )

    return router
