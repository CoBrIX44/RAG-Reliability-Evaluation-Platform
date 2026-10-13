"""Index queue and immutable ready chunks; separate from document ingestion payloads."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from rag_core.models import Base


class IndexVariant(Base):
    __tablename__ = "index_variants"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    corpus_version_id: Mapped[UUID] = mapped_column(ForeignKey("corpus_versions.id"))
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    config: Mapped[dict[str, object]] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(16), default="pending")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    manifest: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    lease_token: Mapped[UUID | None] = mapped_column(nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IndexChunk(Base):
    __tablename__ = "index_chunks"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    index_id: Mapped[UUID] = mapped_column(ForeignKey("index_variants.id"))
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    spans: Mapped[list[dict[str, object]]] = mapped_column(JSONB)


class DenseSearch(Base):
    __tablename__ = "dense_searches"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    index_id: Mapped[UUID] = mapped_column(ForeignKey("index_variants.id"))
    request_hash: Mapped[str] = mapped_column(String(64))
    request: Mapped[dict[str, object]] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(16), default="pending")
    result: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    lease_token: Mapped[UUID | None] = mapped_column(nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
