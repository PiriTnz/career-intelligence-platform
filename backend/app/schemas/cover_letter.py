import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

LetterType = Literal["cover_letter", "motivation", "email_hr"]


class CoverLetterGenerateRequest(BaseModel):
    job_id: uuid.UUID
    type: LetterType = "cover_letter"
    language: Literal["fr", "en"] = "fr"


class CoverLetterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID | None
    application_id: uuid.UUID | None
    type: str
    language: str
    content: str
    created_at: datetime
