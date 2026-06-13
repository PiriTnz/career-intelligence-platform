import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

# Canonical lifecycle: recommended → preparing → ready_to_apply → applied
#                       → follow_up → interview → offer / rejected
ApplicationStatus = Literal[
    "recommended", "preparing", "ready_to_apply",
    "applied", "follow_up", "interview",
    "offer", "rejected",
]

# Valid forward transitions (and allowed same-level moves)
VALID_TRANSITIONS: dict[str, list[str]] = {
    "recommended":   ["preparing", "rejected"],
    "preparing":     ["ready_to_apply", "rejected"],
    "ready_to_apply":["applied", "rejected"],
    "applied":       ["follow_up", "interview", "rejected"],
    "follow_up":     ["interview", "rejected"],
    "interview":     ["offer", "rejected"],
    "offer":         [],      # terminal positive
    "rejected":      [],      # terminal negative
}


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID
    notes: str | None = None


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus
    notes: str | None = None


class ApplicationNotesUpdate(BaseModel):
    notes: str


class ApplicationTimelineItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    status: str
    notes: str | None
    created_at: datetime


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID
    status: str
    notes: str | None
    applied_at: datetime | None
    follow_up_at: datetime | None
    interview_at: datetime | None
    offer_at: datetime | None
    rejected_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApplicationWithTimeline(ApplicationRead):
    timeline: list[ApplicationTimelineItem] = []


class ApplicationTrackerItem(BaseModel):
    """Enriched row — Application joined with Job + optional InterviewWorkspace."""

    id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    company_name: str
    location: str | None
    remote: str
    status: str
    readiness_score: int | None
    readiness_label: str | None
    has_workspace: bool
    follow_up_due: bool          # True when follow_up_at is in the past
    applied_at: datetime | None
    follow_up_at: datetime | None
    interview_at: datetime | None
    offer_at: datetime | None
    rejected_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ApplicationMetrics(BaseModel):
    total: int
    recommended: int
    preparing: int
    ready_to_apply: int
    applied: int
    follow_up: int
    interview: int
    offer: int
    rejected: int
