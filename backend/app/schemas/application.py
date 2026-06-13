import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ApplicationStatus = Literal[
    "found", "shortlisted", "cv_generated", "approved",
    "applied", "viewed", "replied", "interview", "rejected", "archived",
]


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID
    notes: str | None = None


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus
    notes: str | None = None


class ApplicationNotesUpdate(BaseModel):
    notes: str


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID
    status: str
    applied_at: datetime | None
    approved_at: datetime | None
    replied_at: datetime | None
    interview_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ApplicationTrackerItem(BaseModel):
    """Enriched application row — Application + Job + optional Workspace data."""

    id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    company_name: str
    location: str | None
    remote: str  # none | hybrid | full
    status: str
    readiness_score: int | None
    readiness_label: str | None
    has_workspace: bool
    applied_at: datetime | None
    approved_at: datetime | None
    replied_at: datetime | None
    interview_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
