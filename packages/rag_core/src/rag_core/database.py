"""Bounded database access and schema-aware readiness."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from rag_core.settings import Settings

SCHEMA_REVISION = "0008_answer_evaluations"
WORKER_FRESHNESS_SECONDS = 60


class DatabaseHealth(BaseModel):
    status: Literal["ready", "unavailable"]
    code: Literal["ok", "database_unavailable", "schema_mismatch", "vector_unavailable"]
    message: str
    worker_status: Literal["ready", "stale", "unavailable"] = "unavailable"


def create_database_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args={"connect_timeout": 2, "options": "-c statement_timeout=3000"},
    )


def inspect_database(engine: Engine) -> DatabaseHealth:
    """Report only sanitized status, never connection exceptions or credentials."""
    try:
        with engine.connect() as connection:
            has_version = connection.scalar(text("SELECT to_regclass('public.alembic_version')"))
            revisions = (
                list(connection.scalars(text("SELECT version_num FROM alembic_version")))
                if has_version
                else []
            )
            if revisions != [SCHEMA_REVISION]:
                return DatabaseHealth(
                    status="unavailable",
                    code="schema_mismatch",
                    message="Database migrations are required. Run uv run alembic upgrade head.",
                )
            vector = connection.scalar(
                text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            )
            if not vector:
                return DatabaseHealth(
                    status="unavailable",
                    code="vector_unavailable",
                    message="The database requires the pgvector extension.",
                )
            heartbeat = connection.scalar(
                text("SELECT last_seen_at FROM service_heartbeats WHERE service = 'worker'")
            )
            worker: Literal["ready", "stale", "unavailable"] = "unavailable"
            if isinstance(heartbeat, datetime):
                age = (datetime.now(UTC) - heartbeat).total_seconds()
                worker = "ready" if 0 <= age <= WORKER_FRESHNESS_SECONDS else "stale"
            return DatabaseHealth(
                status="ready",
                code="ok",
                message="Database and schema are ready.",
                worker_status=worker,
            )
    except SQLAlchemyError:
        return DatabaseHealth(
            status="unavailable",
            code="database_unavailable",
            message="PostgreSQL is unavailable. Start the database and check server configuration.",
        )


def record_worker_heartbeat(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO service_heartbeats (service, last_seen_at) "
                "VALUES ('worker', CURRENT_TIMESTAMP) "
                "ON CONFLICT (service) DO UPDATE SET last_seen_at = EXCLUDED.last_seen_at"
            )
        )
