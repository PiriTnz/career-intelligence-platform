import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_application_user_job"),
        Index("idx_applications_status", "status"),
        Index("idx_applications_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)

    # found → shortlisted → cv_generated → approved → applied
    # → viewed → replied → interview / rejected / archived
    status: Mapped[str] = mapped_column(String(50), default="found", nullable=False)

    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    interview_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="applications")  # noqa: F821
    job: Mapped["Job"] = relationship(back_populates="applications")  # noqa: F821
