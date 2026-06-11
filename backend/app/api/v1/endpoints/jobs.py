import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.db.models import AgentLog, FeedbackEvent, User
from app.schemas.feedback import FeedbackCreate, FeedbackEventRead
from app.schemas.job import JobListItem, JobRead, JobSyncResult
from app.schemas.recommendation import JobRecommendation, MatchDetailRead, ScoreBreakdownRead
from app.services import job_service, matching_engine, normalizer, scoring_service
from app.services import preference_service
from app.services.sources import adzuna, france_travail

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobListItem])
async def list_jobs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    min_score: int = Query(0, ge=0, le=100),
    contract_type: str | None = None,
    remote: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[dict]:
    return await job_service.list_jobs(
        db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        min_score=min_score,
        contract_type=contract_type,
        remote=remote,
    )


# ── Recommendations — MUST be registered before /{job_id} ────────────────────

@router.get("/recommendations", response_model=list[JobRecommendation])
async def get_recommendations(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    min_score: int = Query(default=0, ge=0, le=100, description="Minimum total score (0-100)"),
    location: str | None = Query(default=None, max_length=100, description="Filter by location keyword"),
    remote_only: bool = Query(default=False, description="Return only fully remote jobs"),
    contract_type: str | None = Query(default=None, description="Filter by contract type (cdi, cdd, stage…)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[JobRecommendation]:
    """
    Return jobs ranked by blended score (profile + preference feedback).

    Each result includes:
    - Full score breakdown (skill_match, experience, location, salary, contract, company, freshness)
    - Match detail (matched_skills, missing_skills, role_match_percentage, etc.)
    - preference_score: learned affinity from past feedback events (50 = neutral/no data)
    - final_score: blended ranking score (0.7×profile + 0.3×preference); falls back to
      profile score when no feedback events exist

    Jobs are scored in-memory — up to 500 candidates are evaluated, then
    the top results after filtering are returned.
    """
    profile = await job_service.get_profile_dict(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="No active profile found — create or upload a CV first",
        )

    # Load preference profile once (single DB round-trip for all events)
    prefs = await preference_service.get_preference_profile(db, current_user.id)

    jobs = await job_service.get_jobs_for_matching(
        db,
        location=location,
        remote_only=remote_only,
        contract_type=contract_type,
        limit=500,
    )

    if not jobs:
        return []

    results: list[tuple[int, JobRecommendation]] = []

    for job in jobs:
        try:
            job_dict = _job_to_dict(job)
            breakdown, confidence = scoring_service.score_job(job_dict, profile)
            mr = matching_engine.match(job_dict, profile)
            pref_score = preference_service.compute_preference_score(job_dict, prefs)
            final = preference_service.blend_scores(
                breakdown.total, pref_score, has_preferences=prefs.has_preferences
            )

            if breakdown.total < min_score:
                continue

            rec = JobRecommendation(
                job_id=job.id,
                title=job.title,
                company_name=job.company_name,
                location=job.location,
                remote=job.remote,
                contract_type=job.contract_type,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                required_skills=job.required_skills or [],
                url=job.url,
                published_at=job.published_at,
                score=ScoreBreakdownRead(
                    skill_match=breakdown.skill_match,
                    experience_match=breakdown.experience_match,
                    location_score=breakdown.location_score,
                    salary_score=breakdown.salary_score,
                    contract_score=breakdown.contract_score,
                    company_score=breakdown.company_score,
                    freshness_score=breakdown.freshness_score,
                    total=breakdown.total,
                    extraction_confidence=confidence,
                    needs_review=breakdown.needs_review,
                ),
                match=MatchDetailRead(
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
                    experience_gap=mr.experience_gap,
                    overall_fit=mr.overall_fit,
                ),
                preference_score=pref_score,
                final_score=final,
            )
            results.append((final, rec))
        except Exception as exc:
            logger.warning("Skipping job %s in recommendations: %s", job.id, exc)

    # Sort by final_score descending (preference-aware), then paginate
    results.sort(key=lambda x: x[0], reverse=True)
    return [rec for _, rec in results[offset: offset + limit]]


# ── Feedback recording — before /{job_id} to avoid route conflict ─────────────

@router.post("/{job_id}/feedback", status_code=status.HTTP_201_CREATED, response_model=FeedbackEventRead)
async def record_feedback(
    job_id: uuid.UUID,
    body: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> FeedbackEventRead:
    """
    Record a feedback event for a job (viewed, saved, applied, interview, rejected).
    Multiple events of the same type are allowed; each is stored individually.
    The preference learning agent aggregates them on next recommendation request.
    """
    job = await job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    event = FeedbackEvent(
        user_id=current_user.id,
        job_id=job_id,
        outcome=body.event_type,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    return FeedbackEventRead(
        id=event.id,
        user_id=event.user_id,
        job_id=event.job_id,
        event_type=event.outcome,
        created_at=event.created_at,
    )


# ── Single job (after literal routes) ────────────────────────────────────────

@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    job = await job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/sync", response_model=JobSyncResult)
async def sync_jobs(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    Fetch jobs from all configured sources, normalise, deduplicate,
    score against the user's active profile, and persist to DB.
    """
    profile = await job_service.get_profile_dict(db, current_user.id)
    profile_version = profile.get("version", 1)

    collected = 0
    new_jobs = 0
    scored = 0
    errors: list[str] = []
    source_counts: dict[str, int] = {}

    sources = [
        ("france_travail", france_travail.fetch_jobs),
        ("adzuna", adzuna.fetch_jobs),
    ]

    for source_name, fetch_fn in sources:
        try:
            raw_jobs = await fetch_fn()
            source_counts[source_name] = len(raw_jobs)
            collected += len(raw_jobs)

            for raw in raw_jobs:
                try:
                    data = normalizer.normalize(raw, source_name)
                    if not data.get("url") or not data.get("title"):
                        continue

                    job, is_new = await job_service.upsert_job(db, data)

                    if is_new:
                        new_jobs += 1
                        if profile:
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
                            await scoring_service.save_score(
                                db,
                                job_id=job.id,
                                user_id=current_user.id,
                                profile_version=profile_version,
                                breakdown=breakdown,
                                confidence=confidence,
                            )
                            scored += 1
                except Exception as e:
                    errors.append(f"{source_name}: {str(e)[:80]}")

        except Exception as e:
            errors.append(f"{source_name} fetch failed: {str(e)[:80]}")
            source_counts[source_name] = 0

    await db.commit()

    db.add(AgentLog(
        user_id=current_user.id,
        agent="job_collection",
        action="sync",
        payload={"collected": collected, "new": new_jobs, "scored": scored, "sources": source_counts},
        status="ok" if not errors else "partial",
    ))
    await db.commit()

    return {
        "collected": collected,
        "new_jobs": new_jobs,
        "scored": scored,
        "sources": source_counts,
        "errors": errors[:10],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _job_to_dict(job) -> dict:
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
