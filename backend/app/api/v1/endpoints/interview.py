import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.limiter import limiter
from app.db.models import User
from app.llm import get_provider
from app.schemas.interview import (
    ConfirmEvidenceRequest,
    EvidencePendingRead,
    InterviewReadiness,
    KnowledgeBaseResponse,
    MitigationStrategy,
    PipelineItem,
    PrepareWorkspaceResponse,
    RecruiterConcern,
    RejectEvidenceRequest,
    SkillEvidenceRead,
    TransferableMatch,
)
from app.services import career_interview_service, interview_optimization_service

router = APIRouter()


# ── Workspace endpoints ───────────────────────────────────────────────────────

@router.post("/prepare/{job_id}", response_model=PrepareWorkspaceResponse)
@limiter.limit("5/minute")
async def prepare_workspace(
    request: Request,
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PrepareWorkspaceResponse:
    """
    Generate a complete interview optimization workspace for the given job.
    Performs: knowledge-base seeding → extended classification → readiness →
    recruiter concerns → mitigation strategies → CV/cover letter via LLM.
    Re-running updates the existing workspace.
    """
    provider = get_provider()
    try:
        ws = await interview_optimization_service.prepare_workspace(
            db, current_user.id, job_id, provider
        )
    except ValueError as exc:
        detail = str(exc)
        code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=detail)

    return _ws_to_response(ws, job_id)


@router.get("/workspace/{job_id}", response_model=PrepareWorkspaceResponse)
async def get_workspace(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PrepareWorkspaceResponse:
    """Retrieve a previously generated interview workspace."""
    ws = await interview_optimization_service.get_workspace(db, current_user.id, job_id)
    if ws is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workspace found for this job. Call POST /prepare/{job_id} first.",
        )
    return _ws_to_response(ws, job_id)


# ── Evidence management ───────────────────────────────────────────────────────

@router.post("/confirm-evidence", response_model=SkillEvidenceRead)
async def confirm_evidence(
    data: ConfirmEvidenceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SkillEvidenceRead:
    """
    Confirm a pending skill evidence suggestion.
    Moves it into the verified knowledge base with the confirmed status.
    """
    evidence = await career_interview_service.confirm_evidence(
        db,
        current_user.id,
        data.pending_id,
        override_status=data.override_status,
        evidence_notes=data.evidence_notes,
    )
    if evidence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending evidence not found.",
        )
    return evidence


@router.post("/reject-evidence", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def reject_evidence(
    data: RejectEvidenceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a pending suggestion without adding it to the knowledge base."""
    found = await career_interview_service.reject_evidence(
        db, current_user.id, data.pending_id
    )
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending evidence not found.",
        )


# ── Knowledge base & pipeline ─────────────────────────────────────────────────

@router.get("/knowledge-base", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBaseResponse:
    """Return the user's full evidence knowledge base grouped by status."""
    kb = await career_interview_service.get_knowledge_base(db, current_user.id)
    pending = await career_interview_service.get_pending_evidence(db, current_user.id)

    verified = [e for e in kb if e.status == "verified"]
    transferable = [e for e in kb if e.status == "transferable"]
    learning = [e for e in kb if e.status == "learning"]

    return KnowledgeBaseResponse(
        verified=[SkillEvidenceRead.model_validate(e) for e in verified],
        transferable=[SkillEvidenceRead.model_validate(e) for e in transferable],
        learning=[SkillEvidenceRead.model_validate(e) for e in learning],
        pending=[EvidencePendingRead.model_validate(p) for p in pending],
        total_skills=len(kb),
    )


@router.get("/application-pipeline", response_model=list[PipelineItem])
async def get_application_pipeline(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PipelineItem]:
    """
    Return all jobs in the user's application pipeline, ordered by readiness score.
    Merges InterviewWorkspaces and Applications into a unified view.
    """
    items = await interview_optimization_service.get_application_pipeline(
        db, current_user.id
    )
    return [PipelineItem(**item) for item in items]


# ── Response builder ──────────────────────────────────────────────────────────

def _ws_to_response(ws, job_id: uuid.UUID) -> PrepareWorkspaceResponse:
    transferable = [
        TransferableMatch(
            skill=t["skill"],
            via=t["via"],
            family=t["family"],
            rationale=t.get("rationale", ""),
        )
        for t in (ws.transferable_matches or [])
    ]
    concerns = [
        RecruiterConcern(skill=c["skill"], concern=c["concern"])
        for c in (ws.recruiter_concerns or [])
    ]
    mitigations = [
        MitigationStrategy(skill=m["skill"], strategy=m["strategy"])
        for m in (ws.mitigation_strategies or [])
    ]
    readiness = InterviewReadiness(
        label=ws.readiness_label,
        score=ws.readiness_score,
        explanation=ws.readiness_explanation,
    )
    return PrepareWorkspaceResponse(
        job_id=job_id,
        verified_matches=ws.verified_matches or [],
        transferable_matches=transferable,
        learning_skills=ws.learning_skills or [],
        real_gaps=ws.real_gaps or [],
        recruiter_concerns=concerns,
        mitigation_strategies=mitigations,
        cv_draft=ws.cv_draft,
        cover_letter_draft=ws.cover_letter_draft,
        readiness=readiness,
        warnings=ws.warnings or [],
        prepared_at=ws.updated_at,
    )
