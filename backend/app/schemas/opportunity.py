from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ── Base opportunity schema ───────────────────────────────────────────────────

class OpportunityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    source_id: str | None = None
    url: str
    title: str
    company: str | None = None
    location: str | None = None
    remote: str = "none"
    opportunity_type: str = "employment"
    industry: str | None = None
    sector: str | None = None
    contract_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = "EUR"
    required_skills: list[str] = []
    experience_level: str | None = None
    language: str = "en"
    description: str | None = None
    metadata: dict = {}
    published_at: datetime | None = None
    scraped_at: datetime
    is_active: bool


# ── Scored opportunity (POST /discover response) ──────────────────────────────

class OpportunityMatchDetail(BaseModel):
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    skill_match_percentage: float = 0.0
    role_match_percentage: float = 0.0
    best_matching_role: str | None = None
    location_match: bool = False
    remote_match: bool = False
    contract_match: bool = False
    language_match: bool = False
    salary_ok: bool = False
    experience_gap: int = 0
    overall_fit: float = 0.0


class OpportunityScoreBreakdown(BaseModel):
    skill_match: int = 0
    experience_match: int = 0
    location_score: int = 0
    salary_score: int = 0
    contract_score: int = 0
    company_score: int = 0
    freshness_score: int = 0
    total: int = 0


class ScoredOpportunityRead(BaseModel):
    # Core opportunity fields
    id: uuid.UUID
    source: str
    source_id: str | None = None
    url: str
    title: str
    company: str | None = None
    location: str | None = None
    remote: str = "none"
    opportunity_type: str = "employment"
    industry: str | None = None
    sector: str | None = None
    contract_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = "EUR"
    required_skills: list[str] = []
    experience_level: str | None = None
    language: str = "en"
    description: str | None = None
    metadata: dict = {}
    published_at: datetime | None = None
    scraped_at: datetime
    is_active: bool

    # Scoring
    profile_score: int
    preference_score: float
    final_score: int

    # Details
    match: OpportunityMatchDetail
    score: OpportunityScoreBreakdown


# ── Discovery request params ──────────────────────────────────────────────────

class DiscoverParams(BaseModel):
    opportunity_types: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    contract_types: list[str] = Field(default_factory=list)

    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)
    min_score: int = Field(0, ge=0, le=100)

    profile_weight: float = Field(0.70, ge=0.0, le=1.0)
    preference_weight: float = Field(0.30, ge=0.0, le=1.0)

    sort_by: Literal["final_score", "profile_score", "preference_score"] = "final_score"


# ── Opportunity preferences ───────────────────────────────────────────────────

class OpportunityPreferencesBase(BaseModel):
    preferred_opportunity_types: list[str] = Field(default_factory=list)
    preferred_industries: list[str] = Field(default_factory=list)
    preferred_sectors: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    preferred_contract_types: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class OpportunityPreferencesCreate(OpportunityPreferencesBase):
    pass


class OpportunityPreferencesRead(OpportunityPreferencesBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    has_preferences: bool = False

    @model_validator(mode="after")
    def _set_has_preferences(self) -> "OpportunityPreferencesRead":
        self.has_preferences = bool(
            self.preferred_opportunity_types
            or self.preferred_industries
            or self.preferred_sectors
            or self.preferred_locations
            or self.preferred_contract_types
            or self.keywords
        )
        return self


# ── Opportunity feedback ──────────────────────────────────────────────────────

OppEventType = Literal["viewed", "saved", "applied", "interested", "rejected"]


class OpportunityFeedbackCreate(BaseModel):
    event_type: OppEventType


class OpportunityFeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    opportunity_id: uuid.UUID
    event_type: str
    created_at: datetime
