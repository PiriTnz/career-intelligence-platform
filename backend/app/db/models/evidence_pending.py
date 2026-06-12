from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class EvidencePending(Base):
    """LLM-suggested skill evidence awaiting user confirmation or rejection."""

    __tablename__ = "evidence_pending"
    __table_args__ = (Index("ix_evidence_pending_user_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    skill: Mapped[str] = mapped_column(String(255), nullable=False)
    suggested_status: Mapped[str] = mapped_column(String(20), nullable=False)  # verified|learning|transferable
    agent_question: Mapped[str] = mapped_column(Text, nullable=False)
    agent_reasoning: Mapped[str | None] = mapped_column(Text)
    source_context: Mapped[str | None] = mapped_column(Text)  # job title / context that triggered this

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
