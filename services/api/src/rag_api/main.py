"""Foundation API: explicit readiness and truthful workspace capabilities."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rag_core.database import DatabaseHealth, create_database_engine, inspect_database
from rag_core.errors import PlatformError
from rag_core.settings import Settings
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from rag_api.datasets import dataset_router
from rag_api.documents import document_router
from rag_api.evaluations import evaluation_router
from rag_api.indexes import index_router
from rag_api.limits import BodyLimit
from rag_api.runs import run_router


class WorkspaceStatus(BaseModel):
    stage: Literal["baselines"] = "baselines"
    api: Literal["ready"] = "ready"
    database: DatabaseHealth
    capabilities: list[str] = [
        "health",
        "workspace_status",
        "document_ingestion",
        "corpus_versions",
        "dataset_curation",
        "lexical_indexing",
        "dense_indexing",
        "experiment_runs",
        "hybrid_retrieval",
        "cross_encoder_reranking",
        "answer_evaluation",
    ]
    generation_configured: bool
    judge_configured: bool


def create_app(
    settings: Settings | None = None,
    health_checker: Callable[[], DatabaseHealth] | None = None,
) -> FastAPI:
    config = settings or Settings()
    engine = create_database_engine(config)
    check = health_checker or (lambda: inspect_database(engine))

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    application = FastAPI(
        title="RAG Reliability Platform",
        version="0.1.0",
        description=(
            "Frozen experiments, local generation, and source-based retrieval evaluation."
        ),
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "Idempotency-Key"],
    )
    application.add_middleware(BodyLimit, limit=config.max_upload_bytes + 1_048_576)
    application.include_router(document_router(engine, config))
    application.include_router(dataset_router(engine, config))
    application.include_router(index_router(engine, config))
    application.include_router(run_router(engine, config))
    application.include_router(evaluation_router(engine, config))

    @application.get("/api/v1/health/live")
    def live() -> dict[str, str]:
        return {"status": "alive", "version": "0.1.0"}

    @application.get("/api/v1/health/ready", response_model=None)
    def ready() -> JSONResponse:
        health = check()
        return JSONResponse(
            health.model_dump(), status_code=200 if health.status == "ready" else 503
        )

    @application.get("/api/v1/workspace", response_model=WorkspaceStatus)
    def workspace() -> WorkspaceStatus:
        # Provider configuration is visible; provider secrets and names are not returned.
        return WorkspaceStatus(
            database=check(),
            generation_configured=config.local_generation_enabled,
            judge_configured=config.local_judge_enabled,
        )

    @application.get("/api/v1/capabilities")
    def capabilities() -> dict[str, object]:
        return {
            "stage": "baselines",
            "implemented": [
                "health",
                "workspace_status",
                "document_ingestion",
                "corpus_versions",
                "dataset_curation",
                "lexical_indexing",
                "dense_indexing",
                "experiment_runs",
                "hybrid_retrieval",
                "cross_encoder_reranking",
                "answer_evaluation",
            ],
            "retrieval_strategies": [
                "postgresql_lexical",
                "pgvector_exact_dense",
                "hybrid_rrf",
                "hybrid_rrf_rerank",
            ],
            "metrics": ["retrieval_precision", "retrieval_recall", "context_recall"],
            "document_types": ["pdf", "html", "markdown", "text"],
        }

    @application.exception_handler(PlatformError)
    async def platform_error(_: Request, error: PlatformError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status,
            content={
                "code": error.code,
                "message": error.message,
                "retryable": error.retryable,
                "request_id": str(uuid4()),
                "field_errors": getattr(error, "field_errors", []),
            },
        )

    @application.exception_handler(HTTPException)
    async def http_error(_: Request, error: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "code": "upload_too_large" if error.status_code == 413 else "request_failed",
                "message": str(error.detail),
                "field_errors": [],
                "retryable": False,
                "request_id": str(uuid4()),
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "invalid_request",
                "message": "Check the request fields and try again.",
                "retryable": False,
                "request_id": str(uuid4()),
                "field_errors": [
                    {"field": ".".join(str(part) for part in item["loc"]), "message": item["msg"]}
                    for item in error.errors()
                ],
            },
        )

    @application.exception_handler(SQLAlchemyError)
    async def database_error(_: Request, __: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "code": "database_unavailable",
                "message": "The database is unavailable. Check PostgreSQL and migrations.",
                "retryable": True,
                "request_id": str(uuid4()),
                "field_errors": [],
            },
        )

    @application.exception_handler(Exception)
    async def unexpected_error(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": "The request could not be completed.",
                "field_errors": [],
                "request_id": str(uuid4()),
                "retryable": False,
            },
        )

    return application


app = create_app()
