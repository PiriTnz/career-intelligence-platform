import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255))
    size: Mapped[str | None] = mapped_column(String(50))  # startup, sme, large, enterprise
    quality_score: Mapped[int] = mapped_column(SmallInteger, default=50)  # 0-100
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    jobs: Mapped[list["Job"]] = relationship(back_populates="company")  # noqa: F821
