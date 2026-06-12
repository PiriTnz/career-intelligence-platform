import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class OpportunityFeedback(Base):
    """Feedback events on opportunities (viewed, saved, applied, interested, rejected).

    Distinct from FeedbackEvent (job feedback) so opportunity-specific outcome
    weights (e.g. 'interested') don't bleed into job preference scoring.
    Integrated with the Feedback Learning Agent via get_opportunity_type_affinities().
    """

    __tablename__ = "opportunity_feedback_events"
    __table_args__ = (
        Index("ix_opp_fb_user", "user_id"),
        Index("ix_opp_fb_opportunity", "opportunity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("opportunities.id", ondelete="CASCADE"),
        nullable=False,
    )

    # viewed, saved, applied, interested, rejected
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)

    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
