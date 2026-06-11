import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class CVGenerateRequest(BaseModel):
    job_id: uuid.UUID
    language: Literal["fr", "en"] = "fr"


class CVVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID | None
    application_id: uuid.UUID | None
    file_path: str
    language: str
    ats_score: int | None
    created_at: datetime
