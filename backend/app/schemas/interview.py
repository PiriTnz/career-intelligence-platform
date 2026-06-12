from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ── Evidence ──────────────────────────────────────────────────────────────────

EvidenceStatus = Literal["verified", "transferable", "learning", "rejected"]
EvidenceSource = Literal["profile", "cv_extracted", "user_confirmed", "agent_suggested"]
PendingStatus = Literal["verified", "learning", "transferable"]


class SkillEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    skill: str
    status: str
    source: str
    confidence: float
    evidence_notes: str | None
    created_at: datetime
    updated_at: datetime


class EvidencePendingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    skill: str
    suggested_status: str
    agent_question: str
    agent_reasoning: str | None
    source_context: str | None
    created_at: datetime


class ConfirmEvidenceRequest(BaseModel):
    pending_id: uuid.UUID
    override_status: PendingStatus | None = None
    evidence_notes: str | None = None


class RejectEvidenceRequest(BaseModel):
    pending_id: uuid.UUID


# ── Workspace ─────────────────────────────────────────────────────────────────

class TransferableMatch(BaseModel):
    skill: str
    via: str
    family: str
    rationale: str = ""


class RecruiterConcern(BaseModel):
    skill: str
    concern: str


class MitigationStrategy(BaseModel):
    skill: str
    strategy: str


class InterviewReadiness(BaseModel):
    label: Literal["excellent", "strong", "moderate", "weak"]
    score: int = Field(ge=0, le=100)
    explanation: str


class InterviewWorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    verified_matches: list[str]
    transferable_matches: list[dict]
    learning_skills: list[str]
    real_gaps: list[str]
    recruiter_concerns: list[dict]
    mitigation_strategies: list[dict]
    cv_draft: str
    cover_letter_draft: str
    readiness_label: str
    readiness_score: int
    readiness_explanation: str
    warnings: list[str]
    created_at: datetime
    updated_at: datetime


class PrepareWorkspaceResponse(BaseModel):
    job_id: uuid.UUID
    verified_matches: list[str]
    transferable_matches: list[TransferableMatch]
    learning_skills: list[str]
    real_gaps: list[str]
    recruiter_concerns: list[RecruiterConcern]
    mitigation_strategies: list[MitigationStrategy]
    cv_draft: str
    cover_letter_draft: str
    readiness: InterviewReadiness
    warnings: list[str]


# ── Pipeline ──────────────────────────────────────────────────────────────────

PipelineStage = Literal[
    "recommended", "ready_to_apply", "applied", "follow_up",
    "interview", "rejected", "offer"
]


class PipelineItem(BaseModel):
    job_id: uuid.UUID
    job_title: str
    company_name: str
    stage: str
    readiness_label: str | None
    readiness_score: int | None
    has_workspace: bool
    has_application: bool
    application_id: uuid.UUID | None
    application_status: str | None


class KnowledgeBaseResponse(BaseModel):
    verified: list[SkillEvidenceRead]
    transferable: list[SkillEvidenceRead]
    learning: list[SkillEvidenceRead]
    pending: list[EvidencePendingRead]
    total_skills: int
