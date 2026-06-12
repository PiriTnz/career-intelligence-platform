from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base

# status values: verified | transferable | learning | rejected
# source values: profile | cv_extracted | user_confirmed | agent_suggested


class SkillEvidence(Base):
    __tablename__ = "skill_evidence"
    __table_args__ = (
        UniqueConstraint("user_id", "skill", name="uq_skill_evidence_user_skill"),
        Index("ix_skill_evidence_user_id", "user_id"),
        Index("ix_skill_evidence_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    skill: Mapped[str] = mapped_column(String(255), nullable=False)  # lowercased
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # verified|transferable|learning|rejected
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # profile|cv_extracted|user_confirmed|agent_suggested
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    evidence_notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
