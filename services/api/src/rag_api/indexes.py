from uuid import UUID

from fastapi import APIRouter
from rag_core.dense_searches import DenseSearchQueue, DenseSearchView
from rag_core.indexes import IndexCreate, IndexStore, IndexView, SearchInput, SearchView
from rag_core.schemas import Page
from rag_core.settings import Settings
from sqlalchemy import Engine

from rag_api.documents import Cursor, Limit


def index_router(engine: Engine, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    store = IndexStore(engine, settings)
    previews = DenseSearchQueue(engine, settings)

    @router.post("/indexes", response_model=IndexView, status_code=202)
    def create(value: IndexCreate) -> IndexView:
        return store.create(value)

    @router.get("/indexes", response_model=Page[IndexView])
    def list_indexes(limit: Limit = 100, cursor: Cursor = 0) -> Page[IndexView]:
        return store.list(limit, cursor)

    @router.get("/indexes/{index_id}", response_model=IndexView)
    def get(index_id: UUID) -> IndexView:
        return store.get(index_id)

    @router.post("/indexes/{index_id}/retry", response_model=IndexView, status_code=202)
    def retry(index_id: UUID) -> IndexView:
        return store.retry(index_id)

    @router.post("/indexes/{index_id}/search", response_model=SearchView)
    def search(index_id: UUID, value: SearchInput) -> SearchView:
        return store.search(index_id, value)

    @router.post(
        "/indexes/{index_id}/dense-searches", response_model=DenseSearchView, status_code=202
    )
    def queue_dense(index_id: UUID, value: SearchInput) -> DenseSearchView:
        return previews.create(index_id, value)

    @router.get("/dense-searches/{search_id}", response_model=DenseSearchView)
    def dense_status(search_id: UUID) -> DenseSearchView:
        return previews.get(search_id)

    @router.post(
        "/dense-searches/{search_id}/retry", response_model=DenseSearchView, status_code=202
    )
    def dense_retry(search_id: UUID) -> DenseSearchView:
        return previews.retry(search_id)

    return router
