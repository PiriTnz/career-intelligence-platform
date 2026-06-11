import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.db.models import Score, User
from app.llm import get_provider
from app.llm.explanations import explain_score
from app.schemas.score import ScoreRead
from app.services import job_service, scoring_service

router = APIRouter(prefix="/scores", tags=["scores"])


@router.get("/{job_id}", response_model=ScoreRead)
async def get_score(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Score).where(Score.job_id == job_id, Score.user_id == current_user.id)
    )
    score = result.scalar_one_or_none()
    if score is None:
        raise HTTPException(status_code=404, detail="Score not found — run /jobs/sync first")
    return score


@router.post("/{job_id}/compute", response_model=ScoreRead)
async def compute_score(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """(Re)compute deterministic score for a job against the current profile."""
    job = await job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    profile = await job_service.get_profile_dict(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=400, detail="No active profile — create a profile first")

    job_dict = {
        "required_skills": job.required_skills,
        "experience_level": job.experience_level,
        "location": job.location,
        "remote": job.remote,
        "contract_type": job.contract_type,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "published_at": job.published_at,
        "company_quality_score": 50,
    }
    breakdown, confidence = scoring_service.score_job(job_dict, profile)
    score = await scoring_service.save_score(
        db,
        job_id=job.id,
        user_id=current_user.id,
        profile_version=profile.get("version", 1),
        breakdown=breakdown,
        confidence=confidence,
    )
    return score


@router.post("/{job_id}/explain", response_model=ScoreRead)
async def generate_explanation(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate an LLM explanation for an existing score.
    The score is not changed — only llm_explanation is updated.
    LLM is called here and only here; it never influences the numeric score.
    """
    # Load score
    result = await db.execute(
        select(Score).where(Score.job_id == job_id, Score.user_id == current_user.id)
    )
    score = result.scalar_one_or_none()
    if score is None:
        raise HTTPException(
            status_code=404,
            detail="No score found — call POST /scores/{job_id}/compute first",
        )

    # Load job
    job = await job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Load profile for context
    profile = await job_service.get_profile_dict(db, current_user.id)

    # Reconstruct breakdown from stored score (scores are immutable — do not re-compute)
    breakdown = scoring_service.ScoreBreakdown(
        skill_match=score.skill_match,
        experience_match=score.experience_match,
        location_score=score.location_score,
        salary_score=score.salary_score,
        contract_score=score.contract_score,
        company_score=score.company_score,
        freshness_score=score.freshness_score,
    )

    provider = get_provider()
    explanation = await explain_score(
        provider,
        job_title=job.title,
        company_name=job.company_name,
        location=job.location,
        remote=job.remote,
        contract_type=job.contract_type,
        required_skills=job.required_skills or [],
        breakdown=breakdown,
        confidence=score.extraction_confidence,
        candidate_skills=profile.get("skills", []),
        candidate_cities=profile.get("cities", []),
    )

    if explanation:
        score.llm_explanation = explanation
        await db.commit()
        await db.refresh(score)

    return score
