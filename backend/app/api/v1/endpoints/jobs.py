import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.db.models import AgentLog, User
from app.schemas.job import JobListItem, JobRead, JobSyncResult
from app.services import job_service, normalizer, scoring_service
from app.services.sources import adzuna, france_travail

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

    # ── Collect from sources ──────────────────────────────────────────────────
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
                        # Score immediately if user has a profile
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

    # Log the sync event
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
