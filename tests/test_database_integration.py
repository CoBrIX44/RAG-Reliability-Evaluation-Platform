"""Use only a disposable test database: this test upgrades and downgrades its schema."""

import os

import pytest
from alembic import command
from alembic.config import Config
from rag_core.database import create_database_engine, inspect_database, record_worker_heartbeat
from rag_core.settings import Settings
from sqlalchemy import text


@pytest.mark.integration
def test_migration_round_trip_and_real_worker_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL/pgvector database")
    monkeypatch.setenv("DATABASE_URL", url)
    settings = Settings(_env_file=None)
    config = Config("alembic.ini")
    engine = create_database_engine(settings)
    try:
        command.upgrade(config, "head")
        health = inspect_database(engine)
        assert health.status == "ready"
        record_worker_heartbeat(engine)
        assert inspect_database(engine).worker_status == "ready"
        command.downgrade(config, "base")
        assert inspect_database(engine).code == "schema_mismatch"
        # Downgrade must leave the shared extension alone.
        with engine.connect() as connection:
            assert connection.scalar(
                text("SELECT extname FROM pg_extension WHERE extname='vector'")
            )
        command.upgrade(config, "head")
        assert inspect_database(engine).status == "ready"
    finally:
        engine.dispose()
