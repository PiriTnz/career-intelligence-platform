"""CRUD operations for jobs, with upsert-based deduplication."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, Score


async def upsert_job(db: AsyncSession, data: dict[str, Any]) -> tuple[Job, bool]:
    """
    Insert job or update description/title on URL conflict.
    Returns (job, is_new).
    Deduplication: primary key is URL (unique index).
    """
    result = await db.execute(select(Job).where(Job.url == data["url"]))
    job = result.scalar_one_or_none()

    if job is None:
        job = Job(
            source=data["source"],
            source_id=data.get("source_id"),
            url=data["url"],
            title=data["title"],
            company_name=data["company_name"],
            location=data.get("location"),
            remote=data.get("remote", "none"),
            contract_type=data.get("contract_type"),
            salary_min=data.get("salary_min"),
            salary_max=data.get("salary_max"),
            salary_currency=data.get("salary_currency", "EUR"),
            required_skills=data.get("required_skills", []),
            experience_level=data.get("experience_level"),
            language=data.get("language", "fr"),
            description=data.get("description"),
            raw_json=data.get("raw_json"),
            published_at=_parse_dt(data.get("published_at")),
        )
        db.add(job)
        await db.flush()  # get the id before commit
        return job, True

    # Update mutable fields on duplicate
    job.title = data["title"]
    job.description = data.get("description") or job.description
    job.required_skills = data.get("required_skills") or job.required_skills
    job.salary_min = data.get("salary_min") or job.salary_min
    job.salary_max = data.get("salary_max") or job.salary_max
    return job, False


async def list_jobs(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    min_score: int = 0,
    contract_type: str | None = None,
    remote: str | None = None,
) -> list[dict]:
    """
    Return jobs ordered by score descending.
    Unscored jobs appear at the bottom (score treated as 0).
    """
    query = (
        select(
            Job.id,
            Job.title,
            Job.company_name,
            Job.location,
            Job.remote,
            Job.contract_type,
            Job.salary_min,
            Job.salary_max,
            Job.required_skills,
            Job.published_at,
            Score.id.label("score_id"),
            Score.total.label("score_total"),
        )
        .outerjoin(Score, and_(Score.job_id == Job.id, Score.user_id == user_id))
        .where(func.coalesce(Score.total, 0) >= min_score)
        .order_by(func.coalesce(Score.total, 0).desc(), Job.scraped_at.desc())
        .limit(limit)
        .offset(offset)
    )

    if contract_type:
        query = query.where(Job.contract_type == contract_type)
    if remote:
        query = query.where(Job.remote == remote)

    rows = await db.execute(query)
    return [row._asdict() for row in rows]


async def get_job(db: AsyncSession, job_id: uuid.UUID) -> Job | None:
    result = await db.execute(select(Job).where(Job.id == job_id))
    return result.scalar_one_or_none()


async def get_profile_dict(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Return user's active profile as a plain dict for scoring."""
    from app.db.models import Profile

    result = await db.execute(
        select(Profile)
        .where(Profile.user_id == user_id, Profile.is_active.is_(True))
        .order_by(Profile.version.desc())
        .limit(1)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        return {}
    return {
        "target_roles": profile.target_roles,
        "skills": profile.skills,
        "experience_level": profile.experience_level,
        "salary_min": profile.salary_min,
        "salary_target": profile.salary_target,
        "remote_preference": profile.remote_preference,
        "countries": profile.countries,
        "cities": profile.cities,
        "contract_types": profile.contract_types,
        "version": profile.version,
    }


def _parse_dt(value):
    if value is None:
        return None
    from datetime import datetime
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value)[:19])
    except (ValueError, TypeError):
        return None
