import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"
    __table_args__ = (
        Index("idx_feedback_user", "user_id"),
        Index("idx_feedback_outcome", "outcome"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    application_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"))

    # Outcome signals the feedback learning agent uses
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    # saved, rejected, applied, replied, interview, rejected_after_interview

    context: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
