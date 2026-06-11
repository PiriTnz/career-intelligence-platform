import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CoverLetter(Base):
    __tablename__ = "cover_letters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    application_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"))

    type: Mapped[str] = mapped_column(String(50), default="cover_letter")  # cover_letter, motivation, email_hr
    language: Mapped[str] = mapped_column(String(10), default="fr")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
