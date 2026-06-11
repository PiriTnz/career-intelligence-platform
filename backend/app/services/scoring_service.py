"""
Deterministic weighted scoring engine.
Rule: scores are computed from data only — LLM is only called for explanation text,
never to influence the numeric outcome.

Weights: skill_match/30, experience/20, location/15, salary/15,
         contract/10, company/5, freshness/5  → total max 100
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Score


@dataclass
class ScoreBreakdown:
    skill_match: int = 0       # max 30
    experience_match: int = 0  # max 20
    location_score: int = 0    # max 15
    salary_score: int = 0      # max 15
    contract_score: int = 0    # max 10
    company_score: int = 0     # max 5
    freshness_score: int = 0   # max 5

    @property
    def total(self) -> int:
        return (
            self.skill_match + self.experience_match + self.location_score
            + self.salary_score + self.contract_score + self.company_score
            + self.freshness_score
        )

    @property
    def needs_review(self) -> bool:
        """High score but poor skill extraction → flag for manual review."""
        return self.total >= 60 and self.skill_match < 10


def score_job(job: dict[str, Any], profile: dict[str, Any]) -> tuple[ScoreBreakdown, int]:
    """
    Pure function — no I/O.
    Returns (breakdown, extraction_confidence 0-100).
    """
    breakdown = ScoreBreakdown(
        skill_match=_skill_match(job, profile),
        experience_match=_experience_match(job, profile),
        location_score=_location_score(job, profile),
        salary_score=_salary_score(job, profile),
        contract_score=_contract_score(job, profile),
        company_score=_company_score(job),
        freshness_score=_freshness_score(job),
    )
    return breakdown, _extraction_confidence(job)


async def save_score(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    user_id: uuid.UUID,
    profile_version: int,
    breakdown: ScoreBreakdown,
    confidence: int,
    explanation: str | None = None,
) -> Score:
    """Upsert score for (job_id, user_id) pair.

    Flushes but does NOT commit — the caller owns the transaction.
    This allows batch callers to commit once after processing many jobs.
    """
    result = await db.execute(
        select(Score).where(Score.job_id == job_id, Score.user_id == user_id)
    )
    score = result.scalar_one_or_none()

    if score is None:
        score = Score(job_id=job_id, user_id=user_id)
        db.add(score)

    score.profile_version = profile_version
    score.skill_match = breakdown.skill_match
    score.experience_match = breakdown.experience_match
    score.location_score = breakdown.location_score
    score.salary_score = breakdown.salary_score
    score.contract_score = breakdown.contract_score
    score.company_score = breakdown.company_score
    score.freshness_score = breakdown.freshness_score
    score.total = breakdown.total
    score.extraction_confidence = confidence
    score.needs_review = breakdown.needs_review
    if explanation is not None:
        score.llm_explanation = explanation

    await db.flush()
    return score


# ── Individual dimension scorers ──────────────────────────────────────────────

def _skill_match(job: dict, profile: dict) -> int:
    required = {s.lower() for s in job.get("required_skills", [])}
    user_skills = {s.lower() for s in profile.get("skills", [])}
    if not required:
        return 15  # unknown requirements → half credit
    ratio = len(required & user_skills) / len(required)
    return round(ratio * 30)


def _experience_match(job: dict, profile: dict) -> int:
    level_map = {"junior": 1, "mid": 2, "senior": 3}
    job_level = level_map.get((job.get("experience_level") or "").lower())
    user_level = level_map.get((profile.get("experience_level") or "junior").lower(), 1)
    if job_level is None:
        return 10  # unknown → half credit
    return {0: 20, 1: 10, 2: 0}.get(abs(job_level - user_level), 0)


def _location_score(job: dict, profile: dict) -> int:
    remote = (job.get("remote") or "none").lower()
    if remote == "full" and profile.get("remote_preference"):
        return 15
    job_city = (job.get("location") or "").lower()
    if any(c.lower() in job_city for c in profile.get("cities", [])):
        return 15
    if any(c.lower() in job_city for c in profile.get("countries", [])):
        return 8
    if remote == "hybrid":
        return 6
    return 0


def _salary_score(job: dict, profile: dict) -> int:
    s_min = job.get("salary_min")
    s_max = job.get("salary_max")
    p_min = profile.get("salary_min")
    p_target = profile.get("salary_target")
    if not s_min and not s_max:
        return 7  # unknown → half credit
    mid = ((s_min or 0) + (s_max or s_min or 0)) / 2
    if p_target and mid >= p_target:
        return 15
    if p_min and mid >= p_min:
        if p_target and p_target > p_min:
            return round(((mid - p_min) / (p_target - p_min)) * 15)
        return 10
    return 0


def _contract_score(job: dict, profile: dict) -> int:
    job_contract = (job.get("contract_type") or "").lower()
    preferred = [c.lower() for c in profile.get("contract_types", [])]
    if not preferred:
        return 5  # no preference → half credit
    return 10 if job_contract in preferred else 0


def _company_score(job: dict) -> int:
    quality = job.get("company_quality_score", 50)
    return round((quality / 100) * 5)


def _freshness_score(job: dict) -> int:
    published = job.get("published_at")
    if not published:
        return 2
    if isinstance(published, str):
        try:
            published = datetime.fromisoformat(published)
        except ValueError:
            return 2
    now = datetime.now(timezone.utc)
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    age = (now - published).days
    if age <= 2:
        return 5
    if age <= 7:
        return 3
    if age <= 14:
        return 1
    return 0


def _extraction_confidence(job: dict) -> int:
    fields = ["required_skills", "experience_level", "salary_min", "location", "contract_type"]
    filled = sum(1 for f in fields if job.get(f))
    return round((filled / len(fields)) * 100)
