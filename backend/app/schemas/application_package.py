from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TransferableSkill(BaseModel):
    skill: str   # required skill the user lacks
    via: str     # user's skill that bridges it
    family: str  # skill family name


class RequirementAnalysis(BaseModel):
    verified_match: list[str]
    transferable_match: list[TransferableSkill]
    real_gap: list[str]


class ApplicationPackageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID
    cv_draft: str
    cover_letter_draft: str
    requirement_analysis: dict
    warnings: list[str]
    ready_to_apply_score: int
    created_at: datetime
    updated_at: datetime


class PreparePackageResponse(BaseModel):
    job_id: uuid.UUID
    cv_draft: str
    cover_letter_draft: str
    requirement_analysis: RequirementAnalysis
    warnings: list[str]
    ready_to_apply_score: int
