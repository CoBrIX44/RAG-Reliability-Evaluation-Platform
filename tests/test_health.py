from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from rag_api.main import create_app
from rag_core.database import DatabaseHealth, inspect_database
from rag_core.settings import Settings
from sqlalchemy.exc import OperationalError


def test_liveness_remains_available_without_database_and_secrets_are_not_exposed() -> None:
    down = DatabaseHealth(status="unavailable", code="database_unavailable", message="Unavailable")
    settings = Settings(_env_file=None, generation_api_key="private-token")
    with TestClient(create_app(settings, lambda: down)) as client:
        assert client.get("/api/v1/health/live").status_code == 200
        assert client.get("/api/v1/health/ready").status_code == 503
        workspace = client.get("/api/v1/workspace")
        assert workspace.status_code == 200
        assert workspace.json()["database"]["status"] == "unavailable"
        assert "private-token" not in workspace.text
        assert client.get("/api/v1/capabilities").json()["retrieval_strategies"] == [
            "postgresql_lexical",
            "pgvector_exact_dense",
            "hybrid_rrf",
            "hybrid_rrf_rerank",
        ]


def test_readiness_returns_200_only_when_schema_and_vector_are_ready() -> None:
    ready = DatabaseHealth(status="ready", code="ok", message="Ready")
    with TestClient(create_app(Settings(_env_file=None), lambda: ready)) as client:
        assert client.get("/api/v1/health/ready").status_code == 200


def test_database_exception_does_not_disclose_credentials() -> None:
    engine = MagicMock()
    engine.connect.side_effect = OperationalError("secret-password", {}, Exception("secret"))
    health = inspect_database(engine)
    assert health.code == "database_unavailable"
    assert "secret" not in health.model_dump_json()


def test_old_schema_blocks_readiness_before_other_queries() -> None:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.scalar.return_value = "alembic_version"
    connection.scalars.return_value = ["old_revision"]
    assert inspect_database(engine).code == "schema_mismatch"
    assert connection.scalar.call_count == 1


def test_absent_vector_extension_blocks_readiness() -> None:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.scalar.side_effect = ["alembic_version", False]
    connection.scalars.return_value = ["0008_answer_evaluations"]
    assert inspect_database(engine).code == "vector_unavailable"


@pytest.mark.parametrize("age, status", [(10, "ready"), (100, "stale"), (-100, "stale")])
def test_worker_readiness_requires_a_recent_nonfuture_heartbeat(age: int, status: str) -> None:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    heartbeat = datetime.now(UTC) - timedelta(seconds=age)
    connection.scalar.side_effect = ["alembic_version", True, heartbeat]
    connection.scalars.return_value = ["0008_answer_evaluations"]
    result = inspect_database(engine)
    assert result.status == "ready"
    assert result.worker_status == status
