import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, HttpUrl


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    url: str
    title: str
    company_name: str
    location: str | None
    remote: Literal["none", "hybrid", "full"]
    contract_type: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str
    required_skills: list[str]
    experience_level: str | None
    language: str
    description: str | None
    published_at: datetime | None
    scraped_at: datetime


class JobListItem(BaseModel):
    """Compact job representation for list views — includes score total."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    company_name: str
    location: str | None
    remote: str
    contract_type: str | None
    salary_min: int | None
    salary_max: int | None
    required_skills: list[str]
    published_at: datetime | None
    # joined from scores table
    score_total: int | None = None
    score_id: uuid.UUID | None = None


class JobSyncResult(BaseModel):
    collected: int
    new_jobs: int
    scored: int
    sources: dict[str, int]
    errors: list[str] = []
