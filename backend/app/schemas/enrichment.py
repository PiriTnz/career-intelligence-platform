from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

# ── Gap classification ─────────────────────────────────────────────────────────

GapClassification = Literal["verified", "partially_verified", "unknown"]

EvidenceType = Literal["professional", "project", "academic", "learning", "verified", "rejected"]

SuggestedStatus = Literal["verified", "learning", "rejected"]

QuestionType = Literal[
    "skill_evidence",
    "project_evidence",
    "leadership_evidence",
    "cloud_experience",
    "devops_experience",
    "research_experience",
    "startup_experience",
    "language_proficiency",
    "certification_evidence",
]

SessionStatus = Literal["pending", "answering", "confirmed", "enriched"]


# ── Nested items stored in JSONB ───────────────────────────────────────────────

class GapItem(BaseModel):
    requirement: str
    classification: GapClassification
    rationale: str
    via_skill: str | None = None
    via_family: str | None = None


class QuestionItem(BaseModel):
    id: str  # "q-0", "q-1", …
    requirement: str
    question: str
    question_type: QuestionType
    classification: GapClassification


class AnswerItem(BaseModel):
    question_id: str
    requirement: str
    answer_text: str
    evidence_type: EvidenceType
    suggested_status: SuggestedStatus
    answered_at: str  # ISO datetime string


class ConfirmationItem(BaseModel):
    question_id: str
    requirement: str
    confirmed: bool
    evidence_note: str | None = None
    suggested_status: SuggestedStatus


# ── Request / Response bodies ──────────────────────────────────────────────────

class StartSessionResponse(BaseModel):
    session_id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    company_name: str
    total_requirements: int
    verified_count: int
    question_count: int
    questions: list[QuestionItem]


class AnswerRequest(BaseModel):
    session_id: uuid.UUID
    question_id: str
    answer_text: str


class AnswerResponse(BaseModel):
    question_id: str
    requirement: str
    answer_text: str
    evidence_type: EvidenceType
    suggested_status: SuggestedStatus


class ConfirmRequest(BaseModel):
    session_id: uuid.UUID
    confirmations: list[ConfirmationItem]


class ConfirmResponse(BaseModel):
    enriched_count: int
    enriched_skills: list[str]
    session_status: SessionStatus


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID
    status: SessionStatus
    detected_gaps: list[GapItem]
    generated_questions: list[QuestionItem]
    answers: list[AnswerItem]
    confirmations: list[ConfirmationItem]
    enriched_skills: list[str]
    created_at: datetime
    updated_at: datetime


class EnrichmentStatusResponse(BaseModel):
    job_id: uuid.UUID
    has_open_session: bool
    session_id: uuid.UUID | None = None
    session_status: SessionStatus | None = None
    unanswered_questions: int
    enriched_skills: list[str]
