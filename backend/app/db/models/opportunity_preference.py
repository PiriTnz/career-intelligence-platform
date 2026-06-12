import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class OpportunityPreference(Base):
    """Per-user configurable opportunity discovery preferences.

    One row per user (UNIQUE on user_id). Upserted on PUT /opportunities/preferences.
    These are explicit user settings, distinct from the learned feedback affinities
    stored in opportunity_feedback_events.
    """

    __tablename__ = "opportunity_preferences"
    __table_args__ = (Index("ix_opp_pref_user", "user_id", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    preferred_opportunity_types: Mapped[list[str]] = mapped_column(
        ARRAY(String()), nullable=False, server_default="{}"
    )
    preferred_industries: Mapped[list[str]] = mapped_column(
        ARRAY(String()), nullable=False, server_default="{}"
    )
    preferred_sectors: Mapped[list[str]] = mapped_column(
        ARRAY(String()), nullable=False, server_default="{}"
    )
    preferred_locations: Mapped[list[str]] = mapped_column(
        ARRAY(String()), nullable=False, server_default="{}"
    )
    preferred_contract_types: Mapped[list[str]] = mapped_column(
        ARRAY(String()), nullable=False, server_default="{}"
    )
    keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String()), nullable=False, server_default="{}"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
