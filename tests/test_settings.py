from pathlib import Path

import pytest
from pydantic import ValidationError
from rag_core.settings import Settings


def test_sample_environment_file_loads_string_concurrency(tmp_path: Path) -> None:
    environment = tmp_path / ".env"
    environment.write_text("WORKER_CONCURRENCY=1\nJOB_MAX_ATTEMPTS=3\n", encoding="utf-8")
    assert Settings(_env_file=environment).worker_concurrency == 1


def test_secrets_are_redacted_and_not_model_dumped_in_plaintext() -> None:
    settings = Settings(_env_file=None, generation_api_key="private-token")
    assert "private-token" not in repr(settings)
    assert "private-token" not in settings.model_dump_json()


@pytest.mark.parametrize("heartbeat", [60, 120])
def test_heartbeat_must_leave_time_for_lease_recovery(heartbeat: int) -> None:
    with pytest.raises(ValidationError, match="less than half"):
        Settings(_env_file=None, job_heartbeat_seconds=heartbeat, job_lease_seconds=120)


@pytest.mark.parametrize("url", ["sqlite:///test.db", "postgresql://localhost/rag", "not-a-url"])
def test_database_driver_is_explicit_and_postgresql_only(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=url)


def test_cors_accepts_comma_separated_explicit_origins() -> None:
    settings = Settings(_env_file=None, cors_origins="http://localhost:3000/, https://example.test")
    assert settings.cors_origins == ["http://localhost:3000", "https://example.test"]


@pytest.mark.parametrize("origins", ["*", "", "file://local"])
def test_wildcard_and_invalid_origins_are_rejected(origins: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=origins)
