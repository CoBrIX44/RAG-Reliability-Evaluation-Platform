"""Validated server-side configuration. Nothing here is a browser configuration API."""

from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    app_env: Literal["development", "test", "production"] = "development"
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://rag:rag_local_only@127.0.0.1:5432/rag"
    )
    artifact_root: Path = Path("data/artifacts")
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    max_upload_bytes: int = Field(default=52_428_800, gt=0, le=1_073_741_824)
    extraction_timeout_seconds: int = Field(default=60, ge=1, le=600)
    max_extracted_characters: int = Field(default=2_000_000, ge=100, le=20_000_000)
    max_pdf_pages: int = Field(default=1000, ge=1, le=10_000)
    max_run_questions: int = Field(default=1000, gt=0, le=10_000)
    max_jsonl_bytes: int = Field(default=10_485_760, gt=0, le=52_428_800)
    worker_concurrency: Literal[1] = 1
    worker_poll_seconds: int = Field(default=15, ge=1, le=60)
    job_lease_seconds: int = Field(default=120, ge=10, le=3600)
    job_heartbeat_seconds: int = Field(default=20, ge=1, le=300)
    job_max_attempts: int = Field(default=3, ge=1, le=10)
    model_timeout_seconds: int = Field(default=120, ge=1, le=1800)
    model_cache_dir: Path = Path("data/models")
    generation_timeout_seconds: int = Field(default=300, ge=1, le=1800)
    generation_threads: int = Field(default=2, ge=1, le=8)
    local_generation_enabled: bool = False
    source_revision: str = "unrecorded"
    embedding_threads: int = Field(default=2, ge=1, le=8)
    embedding_batch_size: int = Field(default=16, ge=1, le=64)
    max_dense_chunks: int = Field(default=10_000, ge=1, le=10_000)
    embedding_model_id: str = ""
    embedding_model_revision: str = ""
    reranker_model_id: str = ""
    reranker_model_revision: str = ""
    generation_provider: str = ""
    generation_model_id: str = ""
    generation_api_key: SecretStr = SecretStr("")
    judge_provider: str = ""
    judge_model_id: str = ""
    judge_api_key: SecretStr = SecretStr("")

    @field_validator("worker_concurrency", mode="before")
    @classmethod
    def parse_worker_concurrency(cls, value: str | int) -> str | int:
        if isinstance(value, bool):
            raise ValueError("WORKER_CONCURRENCY must be 1")
        return 1 if value == "1" else value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            if url.drivername != "postgresql+psycopg" or not url.host or not url.database:
                raise ValueError
        except (ValueError, TypeError, ArgumentError) as error:
            raise ValueError("Use a PostgreSQL URL with the postgresql+psycopg driver") from error
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        origins = value.split(",") if isinstance(value, str) else value
        cleaned = [origin.strip().rstrip("/") for origin in origins if origin.strip()]
        if not cleaned or any(
            not origin.startswith(("http://", "https://")) or "*" in origin for origin in cleaned
        ):
            raise ValueError("Specify explicit HTTP(S) origins; wildcard CORS is unsupported")
        return cleaned

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if self.job_heartbeat_seconds >= self.job_lease_seconds / 2:
            raise ValueError("JOB_HEARTBEAT_SECONDS must be less than half JOB_LEASE_SECONDS")
        return self
