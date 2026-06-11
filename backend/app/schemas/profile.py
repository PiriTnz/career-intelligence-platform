import uuid
from datetime import datetime

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
    is_active: bool
    created_at: datetime
