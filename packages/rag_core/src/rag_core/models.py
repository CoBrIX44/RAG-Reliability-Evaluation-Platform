"""Persistent document lineage. Schema changes belong in Alembic migrations."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Corpus(Base):
    __tablename__ = "corpora"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    draft_revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    corpus_id: Mapped[UUID] = mapped_column(ForeignKey("corpora.id"))
    filename: Mapped[str] = mapped_column(String(240))
    media_type: Mapped[str] = mapped_column(String(80))
    storage_key: Mapped[str] = mapped_column(String(160))
    checksum: Mapped[str] = mapped_column(String(64))
    byte_count: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(String(16), default="pending")
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentRevision(Base):
    __tablename__ = "document_revisions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), unique=True)
    extractor_version: Mapped[str] = mapped_column(String(80))
    checksum: Mapped[str] = mapped_column(String(64))
    section_count: Mapped[int] = mapped_column(Integer)
    character_count: Mapped[int] = mapped_column(BigInteger)
    sealed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceSection(Base):
    __tablename__ = "source_sections"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    revision_id: Mapped[UUID] = mapped_column(ForeignKey("document_revisions.id"))
    ordinal: Mapped[int] = mapped_column(Integer)
    heading_path: Mapped[list[str]] = mapped_column(JSONB)
    text: Mapped[str] = mapped_column(Text)
    start_offset: Mapped[int] = mapped_column(BigInteger)
    end_offset: Mapped[int] = mapped_column(BigInteger)
    source: Mapped[dict[str, object]] = mapped_column(JSONB)


class CorpusVersion(Base):
    __tablename__ = "corpus_versions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    corpus_id: Mapped[UUID] = mapped_column(ForeignKey("corpora.id"))
    version: Mapped[int] = mapped_column(Integer)
    draft_revision: Mapped[int] = mapped_column(Integer)
    manifest_hash: Mapped[str] = mapped_column(String(64))
    manifest: Mapped[dict[str, object]] = mapped_column(JSONB)
    document_count: Mapped[int] = mapped_column(Integer)
    sealed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CorpusVersionMember(Base):
    __tablename__ = "corpus_version_members"
    version_id: Mapped[UUID] = mapped_column(ForeignKey("corpus_versions.id"), primary_key=True)
    revision_id: Mapped[UUID] = mapped_column(ForeignKey("document_revisions.id"), primary_key=True)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), unique=True)
    kind: Mapped[str] = mapped_column(String(32), default="ingest")
    state: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    lease_token: Mapped[UUID | None] = mapped_column(nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checkpoint: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
