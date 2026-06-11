import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_source", "source"),
        Index("idx_jobs_scraped_at", "scraped_at"),
        Index("idx_jobs_contract_type", "contract_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # france_travail, adzuna
    source_id: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)

    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)

    location: Mapped[str | None] = mapped_column(String(255))
    remote: Mapped[str] = mapped_column(String(20), default="none")  # none, hybrid, full
    contract_type: Mapped[str | None] = mapped_column(String(50))  # cdi, cdd, stage, alternance, freelance

    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str] = mapped_column(String(10), default="EUR")

    required_skills: Mapped[list] = mapped_column(ARRAY(String), default=list)
    experience_level: Mapped[str | None] = mapped_column(String(50))  # junior, mid, senior
    language: Mapped[str] = mapped_column(String(10), default="fr")
    description: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[dict | None] = mapped_column(JSONB)

    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped["Company | None"] = relationship(back_populates="jobs")  # noqa: F821
    scores: Mapped[list["Score"]] = relationship(back_populates="job", cascade="all, delete-orphan")  # noqa: F821
    applications: Mapped[list["Application"]] = relationship(back_populates="job", cascade="all, delete-orphan")  # noqa: F821
