import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.limiter import limiter
from app.db.models import User
from app.schemas.enrichment import (
    AnswerRequest,
    AnswerResponse,
    ConfirmRequest,
    ConfirmResponse,
    EnrichmentStatusResponse,
    SessionRead,
    StartSessionResponse,
)
from app.services import enrichment_service

router = APIRouter()


@router.post("/start/{job_id}", response_model=StartSessionResponse)
@limiter.limit("10/minute")
async def start_enrichment_session(
    request: Request,
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StartSessionResponse:
    """
    Analyse job requirements against the user's current profile/KB.
    Returns questions only for skills that are NOT already verified.
    """
    try:
        session, gaps = await enrichment_service.start_session(db, current_user.id, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    from app.schemas.enrichment import GapItem, QuestionItem

    gap_objects = [GapItem(**g) for g in session.detected_gaps]
    question_objects = [QuestionItem(**q) for q in session.generated_questions]

    verified = sum(1 for g in gap_objects if g.classification == "verified")

    # Load job title/company for response context
    from sqlalchemy import select
    from app.db.models import Job
    job_row = await db.execute(select(Job).where(Job.id == job_id))
    job = job_row.scalar_one_or_none()

    return StartSessionResponse(
        session_id=session.id,
        job_id=job_id,
        job_title=job.title if job else "Unknown",
        company_name=job.company_name if job else "Unknown",
        total_requirements=len(gap_objects),
        verified_count=verified,
        question_count=len(question_objects),
        questions=question_objects,
    )


@router.post("/answer", response_model=AnswerResponse)
@limiter.limit("30/minute")
async def submit_answer(
    request: Request,
    body: AnswerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnswerResponse:
    """
    Submit an answer to a single enrichment question.
    Classifies the answer and stores it — does NOT touch skill_evidence yet.
    """
    session = await enrichment_service.get_session(db, body.session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    try:
        item = await enrichment_service.record_answer(
            db, session, body.question_id, body.answer_text
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return AnswerResponse(
        question_id=item.question_id,
        requirement=item.requirement,
        answer_text=item.answer_text,
        evidence_type=item.evidence_type,
        suggested_status=item.suggested_status,
    )


@router.post("/confirm", response_model=ConfirmResponse)
@limiter.limit("10/minute")
async def confirm_enrichment(
    request: Request,
    body: ConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConfirmResponse:
    """
    Confirm or reject each classified answer.
    Confirmed items are added to skill_evidence with source=user_confirmed.
    Rejected items are silently skipped — never fabricated.
    """
    session = await enrichment_service.get_session(db, body.session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    enriched = await enrichment_service.confirm_enrichment(
        db, current_user.id, session, body.confirmations
    )

    return ConfirmResponse(
        enriched_count=len(enriched),
        enriched_skills=enriched,
        session_status=session.status,  # type: ignore[arg-type]
    )


@router.get("/session/{session_id}", response_model=SessionRead)
async def get_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    """Return full session state including gaps, questions, answers, and confirmations."""
    session = await enrichment_service.get_session(db, session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    from app.schemas.enrichment import AnswerItem, ConfirmationItem, GapItem, QuestionItem

    return SessionRead(
        id=session.id,
        user_id=session.user_id,
        job_id=session.job_id,
        status=session.status,  # type: ignore[arg-type]
        detected_gaps=[GapItem(**g) for g in (session.detected_gaps or [])],
        generated_questions=[QuestionItem(**q) for q in (session.generated_questions or [])],
        answers=[AnswerItem(**a) for a in (session.answers or [])],
        confirmations=[ConfirmationItem(**c) for c in (session.confirmations or [])],
        enriched_skills=list(session.enriched_skills or []),
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get("/status/{job_id}", response_model=EnrichmentStatusResponse)
async def get_status(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EnrichmentStatusResponse:
    """Return enrichment status for a job — used by the Application Workspace."""
    result = await enrichment_service.get_enrichment_status(db, current_user.id, job_id)
    return EnrichmentStatusResponse(
        job_id=job_id,
        has_open_session=result["has_open_session"],
        session_id=result["session_id"],
        session_status=result["session_status"],
        unanswered_questions=result["unanswered_questions"],
        enriched_skills=result["enriched_skills"],
    )
