import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProfileCreate(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    avoid_roles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    experience_level: str | None = None   # junior, mid, senior
    salary_min: int | None = None
    salary_target: int | None = None
    remote_preference: bool = False
    countries: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    contract_types: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default=["fr", "en"])


class ProfileUpdate(BaseModel):
    target_roles: list[str] | None = None
    avoid_roles: list[str] | None = None
    skills: list[str] | None = None
    experience_level: str | None = None
    salary_min: int | None = None
    salary_target: int | None = None
    remote_preference: bool | None = None
    countries: list[str] | None = None
    cities: list[str] | None = None
    contract_types: list[str] | None = None
    languages: list[str] | None = None
    work_authorization: str | None = None


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    version: int
    target_roles: list[str]
    avoid_roles: list[str]
    skills: list[str]
    experience_level: str | None
    salary_min: int | None
    salary_target: int | None
    remote_preference: bool
    countries: list[str]
    cities: list[str]
    contract_types: list[str]
    languages: list[str]
    # CV-extracted enrichment (null when profile was created manually)
    phone: str | None = None
    certifications: list[str] = Field(default_factory=list)
    education: list[Any] = Field(default_factory=list)
    experience: list[Any] = Field(default_factory=list)
    cv_file_path: str | None = None
    raw_json: dict | None = None
    is_active: bool
    created_at: datetime


class ProfileVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: uuid.UUID
    profile_id: uuid.UUID | None
    version: int
    source: str
    cv_file_path: str | None
    full_name: str | None
    phone: str | None
    email_extracted: str | None
    location_raw: str | None
    education: list[Any]
    experience: list[Any]
    certifications: list[str]
    extracted_skills: list[str]
    inferred_skills: list[str]
    missing_fields: list[str]
    suggested_roles: list[str]
    extraction_confidence: int
    created_at: datetime


class CVUploadResult(BaseModel):
    """Returned immediately after a CV upload — no DB-level round-trip needed."""

    profile_version_id: int
    profile_id: uuid.UUID
    profile_version: int
    extraction_confidence: int
    full_name: str | None
    email_extracted: str | None
    phone: str | None
    location_raw: str | None
    extracted_skills: list[str]
    inferred_skills: list[str]
    suggested_roles: list[str]
    missing_fields: list[str]
    education_count: int
    experience_count: int
    certifications: list[str]
    message: str
