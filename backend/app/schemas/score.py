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
