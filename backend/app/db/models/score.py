import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint("job_id", "user_id", name="uq_score_job_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Deterministic breakdown (max values shown in comments)
    skill_match: Mapped[int] = mapped_column(SmallInteger, default=0)       # max 30
    experience_match: Mapped[int] = mapped_column(SmallInteger, default=0)  # max 20
    location_score: Mapped[int] = mapped_column(SmallInteger, default=0)    # max 15
    salary_score: Mapped[int] = mapped_column(SmallInteger, default=0)      # max 15
    contract_score: Mapped[int] = mapped_column(SmallInteger, default=0)    # max 10
    company_score: Mapped[int] = mapped_column(SmallInteger, default=0)     # max 5
    freshness_score: Mapped[int] = mapped_column(SmallInteger, default=0)   # max 5
    total: Mapped[int] = mapped_column(SmallInteger, default=0)             # sum = max 100

    extraction_confidence: Mapped[int] = mapped_column(SmallInteger, default=100)  # 0-100
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    llm_explanation: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped["Job"] = relationship(back_populates="scores")  # noqa: F821
