import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Opportunity(Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        Index("ix_opp_source_id", "source", "source_id"),
        Index("ix_opp_type", "opportunity_type"),
        Index("ix_opp_is_active", "is_active"),
        Index("ix_opp_scraped_at", "scraped_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote: Mapped[str] = mapped_column(String(20), nullable=False, server_default="none")

    # Opportunity classification
    opportunity_type: Mapped[str] = mapped_column(String(100), nullable=False, server_default="employment")
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(255), nullable=True)

    contract_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(10), nullable=False, server_default="EUR")

    required_skills: Mapped[list[str]] = mapped_column(ARRAY(String()), nullable=False, server_default="{}")
    experience_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False, server_default="en")
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)

    # Source-specific extra data stored as JSONB; named metadata_ to avoid SQLAlchemy Base.metadata clash
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default="true")
