import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ProfileVersion(Base):
    """One record per CV upload — stores the raw extraction output."""

    __tablename__ = "profile_versions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # The profile snapshot created or updated by this upload
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="cv_upload")

    # Raw CV data
    cv_file_path: Mapped[str | None] = mapped_column(String(500))
    raw_text: Mapped[str | None] = mapped_column(Text)

    # Extracted contact fields
    full_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    email_extracted: Mapped[str | None] = mapped_column(String(255))
    location_raw: Mapped[str | None] = mapped_column(String(255))

    # Structured career data (JSONB lists)
    education: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    experience: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Skill arrays
    certifications: Mapped[list] = mapped_column(ARRAY(String), nullable=False, default=list)
    extracted_skills: Mapped[list] = mapped_column(ARRAY(String), nullable=False, default=list)
    inferred_skills: Mapped[list] = mapped_column(ARRAY(String), nullable=False, default=list)
    missing_fields: Mapped[list] = mapped_column(ARRAY(String), nullable=False, default=list)
    suggested_roles: Mapped[list] = mapped_column(ARRAY(String), nullable=False, default=list)

    extraction_confidence: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
