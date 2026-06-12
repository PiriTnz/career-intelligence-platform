"""
Score endpoints.

GET  /scores                      — list user's scores ordered by total desc, with job info
GET  /scores/{job_id}             — single score for one job
POST /scores/{job_id}/compute     — (re)compute deterministic score for one job
POST /scores/{job_id}/explain     — generate LLM explanation (score unchanged)
POST /scores/{job_id}/gap-analysis — generate LLM skill-gap advice (score unchanged)
POST /scores/batch-compute        — score every unscored job in one transaction
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.core.limiter import limiter
from app.db.models import Job, Score, User
from app.llm import get_provider
from app.llm.explanations import explain_match, gap_analysis
from app.schemas.score import BatchComputeResult, GapAnalysisRead, ScoreRead, ScoreWithJobRead
from app.services import job_service, matching_engine, scoring_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scores", tags=["scores"])


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ScoreWithJobRead])
async def list_scores(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    min_score: int = Query(default=0, ge=0, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[ScoreWithJobRead]:
    """Return all scores for the current user, joined with job info, highest score first."""
    rows = await db.execute(
        select(Score, Job)
        .join(Job, Score.job_id == Job.id)
        .where(Score.user_id == current_user.id, Score.total >= min_score)
        .order_by(Score.total.desc(), Score.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [
        ScoreWithJobRead(
            id=score.id,
            job_id=score.job_id,
            user_id=score.user_id,
            profile_version=score.profile_version,
            skill_match=score.skill_match,
            experience_match=score.experience_match,
            location_score=score.location_score,
            salary_score=score.salary_score,
            contract_score=score.contract_score,
            company_score=score.company_score,
            freshness_score=score.freshness_score,
            total=score.total,
            extraction_confidence=score.extraction_confidence,
            needs_review=score.needs_review,
            llm_explanation=score.llm_explanation,
            created_at=score.created_at,
            job_title=job.title,
            company_name=job.company_name,
            location=job.location,
            remote=job.remote,
            contract_type=job.contract_type,
            url=job.url,
        )
        for score, job in rows
    ]


# ── Single job score ──────────────────────────────────────────────────────────

@router.get("/{job_id}", response_model=ScoreRead)
async def get_score(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Score:
    result = await db.execute(
        select(Score).where(Score.job_id == job_id, Score.user_id == current_user.id)
    )
    score = result.scalar_one_or_none()
    if score is None:
        raise HTTPException(status_code=404, detail="Score not found — run POST /scores/batch-compute first")
    return score


# ── Single job compute ────────────────────────────────────────────────────────

@router.post("/{job_id}/compute", response_model=ScoreRead)
async def compute_score(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Score:
    """(Re)compute deterministic score for one job against the current profile."""
    job = await job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    profile = await job_service.get_profile_dict(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=400, detail="No active profile — create a profile first")

    job_dict = _job_to_dict(job)
    breakdown, confidence = scoring_service.score_job(job_dict, profile)
    score = await scoring_service.save_score(
        db,
        job_id=job.id,
        user_id=current_user.id,
        profile_version=profile.get("version", 1),
        breakdown=breakdown,
        confidence=confidence,
    )
    await db.commit()
    await db.refresh(score)
    return score


# ── Batch compute ─────────────────────────────────────────────────────────────

@router.post("/batch-compute", response_model=BatchComputeResult)
async def batch_compute_scores(
    limit: int = Query(
        default=500,
        ge=1,
        le=2000,
        description="Max number of unscored jobs to process in this call",
    ),
    rescore_all: bool = Query(
        default=False,
        description="When true, rescore jobs that already have a score",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> BatchComputeResult:
    """
    Score all unscored jobs (or all jobs if rescore_all=true) in a single
    database transaction. Much more efficient than calling /compute per job.
    """
    profile = await job_service.get_profile_dict(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=400, detail="No active profile — create a profile first")

    profile_version = profile.get("version", 1)

    if rescore_all:
        jobs_result = await db.execute(select(Job).limit(limit))
        jobs = list(jobs_result.scalars().all())
        already_scored = 0
    else:
        # Find jobs that have no score row for this user yet
        already_scored_count_result = await db.execute(
            select(Score).where(Score.user_id == current_user.id)
        )
        already_scored = len(already_scored_count_result.scalars().all())

        scored_subq = (
            select(Score.job_id)
            .where(Score.user_id == current_user.id)
            .scalar_subquery()
        )
        jobs_result = await db.execute(
            select(Job)
            .where(Job.id.not_in(scored_subq))
            .limit(limit)
        )
        jobs = list(jobs_result.scalars().all())

    scored = skipped = 0
    for job in jobs:
        try:
            job_dict = _job_to_dict(job)
            breakdown, confidence = scoring_service.score_job(job_dict, profile)
            await scoring_service.save_score(
                db,
                job_id=job.id,
                user_id=current_user.id,
                profile_version=profile_version,
                breakdown=breakdown,
                confidence=confidence,
            )
            scored += 1
        except Exception as exc:
            logger.error("Scoring failed for job %s: %s", job.id, exc)
            skipped += 1

    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.error("Batch score commit failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database commit failed — changes rolled back",
        ) from exc

    logger.info(
        "Batch score complete: scored=%d already_scored=%d skipped=%d profile_v%d",
        scored, already_scored, skipped, profile_version,
    )
    return BatchComputeResult(
        scored=scored,
        already_scored=already_scored,
        skipped=skipped,
        profile_version=profile_version,
    )


# ── LLM explanation (match-aware) ─────────────────────────────────────────────

@router.post("/{job_id}/explain", response_model=ScoreRead)
@limiter.limit("10/minute")
async def generate_explanation(
    request: Request,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Score:
    """
    Generate an LLM explanation for an existing score using both score and match data.
    The numeric score is never changed — only llm_explanation is updated.
    """
    result = await db.execute(
        select(Score).where(Score.job_id == job_id, Score.user_id == current_user.id)
    )
    score = result.scalar_one_or_none()
    if score is None:
        raise HTTPException(
            status_code=404,
            detail="No score found — call POST /scores/{job_id}/compute first",
        )

    job = await job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    profile = await job_service.get_profile_dict(db, current_user.id)

    breakdown = scoring_service.ScoreBreakdown(
        skill_match=score.skill_match,
        experience_match=score.experience_match,
        location_score=score.location_score,
        salary_score=score.salary_score,
        contract_score=score.contract_score,
        company_score=score.company_score,
        freshness_score=score.freshness_score,
    )

    job_dict = _job_to_dict(job)
    mr = matching_engine.match(job_dict, profile)

    provider = get_provider()
    explanation = await explain_match(
        provider,
        job_title=job.title,
        company_name=job.company_name,
        breakdown=breakdown,
        matched_skills=mr.matched_skills,
        missing_skills=mr.missing_skills,
        skill_match_percentage=mr.skill_match_percentage,
        role_match_percentage=mr.role_match_percentage,
        best_matching_role=mr.best_matching_role,
        location_match=mr.location_match,
        remote_match=mr.remote_match,
        contract_match=mr.contract_match,
        language_match=mr.language_match,
        salary_ok=mr.salary_ok,
        overall_fit=mr.overall_fit,
        candidate_experience_level=profile.get("experience_level"),
        confidence=score.extraction_confidence,
    )

    if explanation:
        score.llm_explanation = explanation
        await db.commit()
        await db.refresh(score)

    return score


# ── LLM gap analysis ──────────────────────────────────────────────────────────

@router.post("/{job_id}/gap-analysis", response_model=GapAnalysisRead)
@limiter.limit("10/minute")
async def generate_gap_analysis(
    request: Request,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> GapAnalysisRead:
    """
    Generate actionable skill-gap advice for a specific job.
    Does not require a pre-existing score. Score is never changed.
    """
    job = await job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    profile = await job_service.get_profile_dict(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=400, detail="No active profile — create a profile first")

    job_dict = _job_to_dict(job)
    mr = matching_engine.match(job_dict, profile)

    provider = get_provider()
    analysis_text = await gap_analysis(
        provider,
        job_title=job.title,
        company_name=job.company_name,
        required_skills=job.required_skills or [],
        matched_skills=mr.matched_skills,
        missing_skills=mr.missing_skills,
        skill_match_percentage=mr.skill_match_percentage,
        experience_gap=mr.experience_gap,
        candidate_skills=profile.get("skills", []),
        candidate_experience_level=profile.get("experience_level"),
        job_experience_level=job.experience_level,
    )

    return GapAnalysisRead(
        job_id=job_id,
        job_title=job.title,
        company_name=job.company_name,
        analysis=analysis_text,
        missing_skills=mr.missing_skills,
        experience_gap=mr.experience_gap,
        skill_match_percentage=mr.skill_match_percentage,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _job_to_dict(job: Job) -> dict:
    return {
        "title": job.title,
        "company_name": job.company_name,
        "required_skills": job.required_skills or [],
        "experience_level": job.experience_level,
        "location": job.location,
        "remote": job.remote,
        "contract_type": job.contract_type,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "published_at": job.published_at,
        "company_quality_score": 50,
        "language": getattr(job, "language", "fr"),
    }
