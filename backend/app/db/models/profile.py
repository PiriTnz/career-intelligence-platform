import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    target_roles: Mapped[list] = mapped_column(ARRAY(String), default=list, nullable=False)
    avoid_roles: Mapped[list] = mapped_column(ARRAY(String), default=list, nullable=False)
    skills: Mapped[list] = mapped_column(ARRAY(String), default=list, nullable=False)
    experience_level: Mapped[str | None] = mapped_column(String(50))  # junior, mid, senior

    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_target: Mapped[int | None] = mapped_column(Integer)

    remote_preference: Mapped[bool] = mapped_column(Boolean, default=False)
    countries: Mapped[list] = mapped_column(ARRAY(String), default=list, nullable=False)
    cities: Mapped[list] = mapped_column(ARRAY(String), default=list, nullable=False)
    contract_types: Mapped[list] = mapped_column(ARRAY(String), default=list, nullable=False)
    languages: Mapped[list] = mapped_column(ARRAY(String), default=lambda: ["fr", "en"], nullable=False)

    raw_json: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="profiles")  # noqa: F821
