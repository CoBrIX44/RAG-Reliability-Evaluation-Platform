from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, ConfigDict
from rag_core.diagnostics import diagnostics
from rag_core.runs import (
    AttemptView,
    ExperimentCreate,
    ExperimentView,
    ResultSummary,
    ResultView,
    RunStore,
    RunView,
)
from rag_core.schemas import Page
from rag_core.settings import Settings
from sqlalchemy import Engine

from rag_api.documents import Cursor, Limit


class RunSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")


def run_router(engine: Engine, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    store = RunStore(engine, settings)

    @router.get("/runs/{run_id}/diagnostics")
    def inspect_failures(
        run_id: UUID,
        source: Literal["human", "model"] = "human",
        topic: Annotated[str, Query(max_length=120)] = "",
        difficulty: Literal["", "easy", "medium", "hard"] = "",
        issue: Annotated[str, Query(max_length=80)] = "",
        limit: Limit = 100,
        cursor: Cursor = 0,
    ) -> dict[str, object]:
        return diagnostics(
            engine,
            run_id,
            source=source,
            topic=topic,
            difficulty=difficulty,
            issue=issue,
            limit=limit,
            cursor=cursor,
        )

    @router.get("/experiments", response_model=Page[ExperimentView])
    def experiments(limit: Limit = 100, cursor: Cursor = 0) -> Page[ExperimentView]:
        return store.experiments(limit, cursor)

    @router.post("/experiments", response_model=ExperimentView, status_code=201)
    def create_experiment(value: ExperimentCreate) -> ExperimentView:
        return store.create_experiment(value)

    @router.post("/experiments/{experiment_id}/runs", response_model=RunView, status_code=202)
    def submit(
        experiment_id: UUID,
        value: RunSubmit,
        idempotency_key: Annotated[
            str,
            Header(
                min_length=1,
                max_length=128,
                pattern=r"^[A-Za-z0-9._:-]+$",
            ),
        ],
    ) -> RunView:
        return store.submit(experiment_id, idempotency_key)

    @router.get("/runs", response_model=Page[RunView])
    def runs(limit: Limit = 20, cursor: Cursor = 0) -> Page[RunView]:
        return store.list(limit, cursor)

    @router.get("/runs/{run_id}", response_model=RunView)
    def get(run_id: UUID) -> RunView:
        return store.get(run_id)

    @router.post("/runs/{run_id}/cancel", response_model=RunView)
    def cancel(run_id: UUID) -> RunView:
        return store.cancel(run_id)

    @router.get("/runs/{run_id}/manifest")
    def manifest(run_id: UUID) -> dict[str, object]:
        return store.manifest(run_id)

    @router.get("/runs/{run_id}/results", response_model=Page[ResultSummary])
    def results(run_id: UUID, limit: Limit = 100, cursor: Cursor = 0) -> Page[ResultSummary]:
        return store.results(run_id, limit, cursor)

    @router.get("/runs/{run_id}/results/{result_id}", response_model=ResultView)
    def result(run_id: UUID, result_id: UUID) -> ResultView:
        return store.result(run_id, result_id)

    @router.get("/runs/{run_id}/attempts", response_model=Page[AttemptView])
    def attempts(run_id: UUID, limit: Limit = 100, cursor: Cursor = 0) -> Page[AttemptView]:
        return store.attempts(run_id, limit, cursor)

    return router
