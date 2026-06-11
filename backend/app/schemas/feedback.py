"""Schemas for feedback events and computed preference profiles."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


VALID_EVENT_TYPES = Literal["viewed", "saved", "applied", "interview", "rejected"]


class FeedbackCreate(BaseModel):
    event_type: VALID_EVENT_TYPES = Field(
        description="Type of interaction with this job"
    )


class FeedbackEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID | None
    event_type: str  # mapped from outcome in the endpoint
    created_at: datetime


class AffinityItem(BaseModel):
    name: str
    affinity: float = Field(ge=0.0, description="Cumulative weighted affinity score")


class PreferenceProfileRead(BaseModel):
    """Computed preference profile derived from feedback events."""
    preferred_skills: list[AffinityItem]
    preferred_locations: list[AffinityItem]
    preferred_companies: list[AffinityItem]
    preferred_contract_types: list[AffinityItem]
    preferred_job_families: list[AffinityItem]
    total_events: int
    signal_breakdown: dict[str, int]
    has_preferences: bool
