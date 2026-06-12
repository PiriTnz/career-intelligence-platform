from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class InterviewWorkspace(Base):
    """
    Per-job interview optimization workspace.
    Stores extended skill classification, recruiter concerns, mitigation strategies,
    optimized CV/cover letter drafts, and interview readiness.
    """

    __tablename__ = "interview_workspaces"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_iw_user_job"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Extended classification (4 categories)
    verified_matches: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    transferable_matches: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    learning_skills: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    real_gaps: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Recruiter intelligence
    recruiter_concerns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    mitigation_strategies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Generated content
    cv_draft: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cover_letter_draft: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Readiness
    readiness_label: Mapped[str] = mapped_column(String(20), nullable=False, default="weak")
    readiness_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    readiness_explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")

    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
