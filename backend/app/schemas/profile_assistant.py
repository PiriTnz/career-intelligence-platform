"""
Schemas for the LLM Profile Assistant.

Flow:
  POST /assistant/message  → AssistantMessageResponse (proposed updates, NOT applied)
  POST /assistant/apply-updates → ProfileRead (actually applies confirmed updates)
  GET  /completeness       → ProfileCompletenessResponse
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


# ── Request schemas ───────────────────────────────────────────────────────────

InputMode = Literal["text", "voice_transcript"]
SupportedLanguage = Literal["en", "fr", "fa"]


class AssistantMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    language: SupportedLanguage = "en"
    # voice_transcript is treated identically to text in v1 (voice-ready structure)
    input_mode: InputMode = "text"


class ApplyUpdatesRequest(BaseModel):
    """Apply updates previously proposed by /assistant/message."""
    updates: dict = Field(default_factory=dict)


# ── Response schemas ──────────────────────────────────────────────────────────

class AssistantMessageResponse(BaseModel):
    assistant_message: str
    # Validated extracted fields (proposed — not yet applied to profile)
    updated_profile_fields: dict
    missing_fields: list[str]
    profile_completeness: int  # 0-100
    next_question: str


class ProfileCompletenessResponse(BaseModel):
    completeness: int           # 0-100
    missing_fields: list[str]
    field_scores: dict[str, int]
    total_possible: int = 100


# ── Internal validation schema (LLM output → clean dict) ─────────────────────

class ExtractedProfileUpdate(BaseModel):
    """
    Pydantic schema that validates raw JSON from LLM extraction.

    Invalid values are silently dropped (None / empty) so the LLM's
    mistakes never reach the profile. Extra fields are ignored.
    """

    model_config = ConfigDict(extra="ignore")

    target_roles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    experience_level: str | None = None
    years_experience: int | None = None   # converted to experience_level, not stored
    salary_min: int | None = None
    salary_target: int | None = None
    remote_preference: bool | None = None
    countries: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    contract_types: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)

    # Extra fields stored in profile.raw_json (no DB column)
    industries: list[str] = Field(default_factory=list)
    opportunity_types: list[str] = Field(default_factory=list)
    visa_work_auth: str | None = None

    @field_validator("experience_level", mode="before")
    @classmethod
    def validate_experience_level(cls, v):
        if v is None:
            return None
        cleaned = str(v).lower().strip()
        return cleaned if cleaned in {"junior", "mid", "senior"} else None

    @field_validator("salary_min", "salary_target", mode="before")
    @classmethod
    def validate_salary(cls, v):
        if v is None:
            return None
        try:
            n = int(v)
        except (TypeError, ValueError):
            return None
        return n if 0 <= n <= 1_000_000 else None

    @field_validator("years_experience", mode="before")
    @classmethod
    def validate_years(cls, v):
        if v is None:
            return None
        try:
            n = int(v)
        except (TypeError, ValueError):
            return None
        return n if 0 <= n <= 60 else None

    @field_validator(
        "skills", "contract_types", mode="before"
    )
    @classmethod
    def normalize_lowercase_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [s.strip().lower() for s in v.split(",") if s.strip()]
        if isinstance(v, list):
            return [str(s).strip().lower() for s in v if s]
        return []

    @field_validator(
        "target_roles", "countries", "cities", "languages",
        "certifications", "industries", "opportunity_types",
        mode="before",
    )
    @classmethod
    def normalize_string_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        if isinstance(v, list):
            return [str(s).strip() for s in v if s]
        return []

    @model_validator(mode="after")
    def infer_experience_level_from_years(self) -> "ExtractedProfileUpdate":
        """If LLM provided years_experience but no experience_level, derive it."""
        if self.years_experience is not None and self.experience_level is None:
            if self.years_experience <= 2:
                self.experience_level = "junior"
            elif self.years_experience <= 5:
                self.experience_level = "mid"
            else:
                self.experience_level = "senior"
        return self

    def to_clean_dict(self) -> dict:
        """Return only non-None, non-empty-list fields (excludes years_experience)."""
        d = self.model_dump(exclude={"years_experience"})
        return {k: v for k, v in d.items() if v is not None and v != []}
