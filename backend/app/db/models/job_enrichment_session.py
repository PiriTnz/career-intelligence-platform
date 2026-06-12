from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class JobEnrichmentSession(Base):
    """
    Tracks a single enrichment run: the questions generated for a job,
    the user's answers, their confirmations, and which skills were enriched.

    Status lifecycle:  pending → answering → confirmed → enriched
    """

    __tablename__ = "job_enrichment_sessions"
    __table_args__ = (
        Index("ix_jes_user_id", "user_id"),
        Index("ix_jes_job_id", "job_id"),
        Index("ix_jes_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    # Analysis output
    detected_gaps: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    generated_questions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # User interaction
    answers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confirmations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Result
    enriched_skills: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
