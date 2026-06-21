import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


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


# ── Job Discovery ─────────────────────────────────────────────────────────────

class JobDiscoverRequest(BaseModel):
    keywords: str = Field(default="software engineer", max_length=200)
    location: str = Field(default="France", max_length=100)
    max_results: int = Field(default=50, ge=1, le=200)
    contract_type: str | None = None
    remote_only: bool = False


class JobImportRequest(BaseModel):
    url: str = Field(..., min_length=10, max_length=2000)


class JobManualCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    company_name: str = Field(..., min_length=1, max_length=200)
    url: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=200)
    remote: Literal["none", "hybrid", "full"] = "none"
    contract_type: str | None = None
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=50_000)
    required_skills: list[str] = Field(default_factory=list)


class JobCreateResult(BaseModel):
    id: uuid.UUID
    title: str
    company_name: str
    location: str | None
    remote: str
    contract_type: str | None
    salary_min: int | None
    salary_max: int | None
    required_skills: list[str]
    url: str
    source: str
    description: str | None
    score_total: int | None
    is_new: bool


class JobDiscoverResult(BaseModel):
    jobs: list[JobCreateResult]
    keywords: str
    location: str
    new_count: int
    total_count: int
