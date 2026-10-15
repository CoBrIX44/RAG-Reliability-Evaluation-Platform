from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header
from pydantic import BaseModel, ConfigDict
from rag_core.answer_evaluation import RUBRIC
from rag_core.evaluations import EvaluationQueue, EvaluationView, HumanReviewInput
from rag_core.schemas import Page
from rag_core.settings import Settings
from sqlalchemy import Engine

from rag_api.documents import Cursor, Limit

Key = Annotated[str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]


class JudgeSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")


def evaluation_router(engine: Engine, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    store = EvaluationQueue(engine, settings)

    @router.get("/evaluation-rubric")
    def rubric() -> dict[str, object]:
        return {"rubric": RUBRIC, "local_judge_enabled": settings.local_judge_enabled}

    @router.get("/runs/{run_id}/evaluations")
    def summary(run_id: UUID) -> dict[str, object]:
        return store.summary(run_id)

    @router.get(
        "/runs/{run_id}/results/{result_id}/evaluations", response_model=Page[EvaluationView]
    )
    def evaluations(
        run_id: UUID, result_id: UUID, limit: Limit = 100, cursor: Cursor = 0
    ) -> Page[EvaluationView]:
        return store.list(run_id, result_id, limit, cursor)

    @router.post(
        "/runs/{run_id}/results/{result_id}/evaluations",
        response_model=EvaluationView,
        status_code=202,
    )
    def judge(
        run_id: UUID, result_id: UUID, value: JudgeSubmit, idempotency_key: Key
    ) -> EvaluationView:
        return store.create(run_id, result_id, idempotency_key)

    @router.post(
        "/runs/{run_id}/results/{result_id}/reviews", response_model=EvaluationView, status_code=201
    )
    def review(
        run_id: UUID, result_id: UUID, value: HumanReviewInput, idempotency_key: Key
    ) -> EvaluationView:
        return store.create(run_id, result_id, idempotency_key, value)

    return router
