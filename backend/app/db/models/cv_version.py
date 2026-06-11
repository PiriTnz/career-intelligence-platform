import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CVVersion(Base):
    __tablename__ = "cv_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    application_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"))

    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="fr")
    ats_score: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
