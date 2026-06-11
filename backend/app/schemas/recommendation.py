"""Schemas for the job recommendations endpoint."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScoreBreakdownRead(BaseModel):
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


class MatchDetailRead(BaseModel):
    matched_skills: list[str]
    missing_skills: list[str]
    skill_match_percentage: float
    role_match_percentage: float
    best_matching_role: str | None
    location_match: bool
    remote_match: bool
    contract_match: bool
    language_match: bool
    salary_ok: bool
    experience_gap: int
    overall_fit: float


class JobRecommendation(BaseModel):
    """A job with its full score breakdown, match detail, and preference ranking."""
    model_config = ConfigDict(from_attributes=False)

    # Job identity
    job_id: uuid.UUID
    title: str
    company_name: str
    location: str | None
    remote: str
    contract_type: str | None
    salary_min: int | None
    salary_max: int | None
    required_skills: list[str]
    url: str
    published_at: datetime | None

    # Deterministic profile score breakdown
    score: ScoreBreakdownRead

    # Profile-aware match detail
    match: MatchDetailRead

    # Preference-aware ranking (from feedback learning)
    preference_score: float = 50.0   # 0-100 affinity from past feedback; 50 = neutral
    final_score: int = 0             # blended ranking score used for ordering


class RecommendationSummary(BaseModel):
    """Header returned alongside the recommendation list."""
    total_jobs_evaluated: int
    jobs_returned: int
    profile_version: int
    filters_applied: dict[str, str | int | bool]
