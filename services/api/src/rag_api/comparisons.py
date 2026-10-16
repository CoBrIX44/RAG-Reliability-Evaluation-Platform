from uuid import UUID

from fastapi import APIRouter
from rag_core.comparisons import ComparisonCreate, ComparisonQueue, ComparisonView
from rag_core.schemas import Page
from rag_core.settings import Settings
from sqlalchemy import Engine

from rag_api.documents import Cursor, Limit
from rag_api.evaluations import Key


def comparison_router(engine: Engine, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1/comparisons")
    store = ComparisonQueue(engine, settings)

    @router.get("/facets")
    def facets(baseline_run_id: UUID, candidate_run_id: UUID) -> dict[str, list[str]]:
        return store.facets(baseline_run_id, candidate_run_id)

    @router.post("", response_model=ComparisonView, status_code=202)
    def create(value: ComparisonCreate, idempotency_key: Key) -> ComparisonView:
        return store.create(value, idempotency_key)

    @router.get("", response_model=Page[ComparisonView])
    def list_comparisons(limit: Limit = 20, cursor: Cursor = 0) -> Page[ComparisonView]:
        return store.list(limit, cursor)

    @router.get("/{comparison_id}", response_model=ComparisonView)
    def get(comparison_id: UUID) -> ComparisonView:
        return store.get(comparison_id)

    @router.get("/{comparison_id}/manifest")
    def manifest(comparison_id: UUID) -> dict[str, object]:
        return store.manifest(comparison_id)

    return router
