import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    user_id: uuid.UUID
    profile_version: int

    skill_match: int
    experience_match: int
    location_score: int
    salary_score: int
    contract_score: int
    company_score: int
    freshness_score: int
    total: int

    extraction_confidence: int
    needs_review: bool
    llm_explanation: str | None

    created_at: datetime


class ScoreWithJobRead(BaseModel):
    """Score plus the key job fields needed to display a ranked job list."""
    model_config = ConfigDict(from_attributes=False)

    # Score fields
    id: uuid.UUID
    job_id: uuid.UUID
    user_id: uuid.UUID
    profile_version: int
    skill_match: int
    experience_match: int
    location_score: int
    salary_score: int
    contract_score: int
    company_score: int
    freshness_score: int
    total: int
    extraction_confidence: int
    needs_review: bool
    llm_explanation: str | None
    created_at: datetime

    # Job fields
    job_title: str
    company_name: str
    location: str | None
    remote: str
    contract_type: str | None
    url: str


class BatchComputeResult(BaseModel):
    scored: int
    already_scored: int
    skipped: int
    profile_version: int


class GapAnalysisRead(BaseModel):
    """Result of LLM-generated skill gap analysis for a specific job."""
    job_id: uuid.UUID
    job_title: str
    company_name: str
    analysis: str
    missing_skills: list[str]
    experience_gap: int
    skill_match_percentage: float
