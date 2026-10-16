"""Frozen analysis inputs, durable worker ownership and immutable reports."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from rag_core.models import Base


class Comparison(Base):
    __tablename__ = "comparisons"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    baseline_run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"))
    candidate_run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"))
    request_key: Mapped[str] = mapped_column(String(128), unique=True)
    manifest: Mapped[dict[str, object]] = mapped_column(JSONB)
    manifest_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16), default="pending")
    output: Mapped[dict[str, object] | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer)
    lease_token: Mapped[UUID | None] = mapped_column(nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
