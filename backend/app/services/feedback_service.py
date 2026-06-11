"""
Feedback Learning Service.
Analyses FeedbackEvent records to surface patterns and update profile
weights — no ML, pure heuristics based on outcome signals.
"""
from __future__ import annotations

import uuid
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Application, FeedbackEvent, Job, Profile


async def record_outcome(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    application_id: uuid.UUID,
    outcome: str,
    context: dict | None = None,
) -> FeedbackEvent:
    """
    Record a feedback signal.
    outcome: saved | rejected | applied | replied | interview | rejected_after_interview
    """
    # Resolve job_id from application
    app_result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    app = app_result.scalar_one_or_none()
    job_id = app.job_id if app else None

    event = FeedbackEvent(
        user_id=user_id,
        application_id=application_id,
        job_id=job_id,
        outcome=outcome,
        context=context or {},
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def compute_insights(
    db: AsyncSession, user_id: uuid.UUID
) -> dict:
    """
    Derive actionable patterns from feedback history.
    Returns a dict with suggested profile adjustments.
    """
    positive_outcomes = {"interview", "replied", "applied"}
    negative_outcomes = {"rejected", "rejected_after_interview"}

    events_res = await db.execute(
        select(FeedbackEvent).where(FeedbackEvent.user_id == user_id)
    )
    events = list(events_res.scalars().all())

    if not events:
        return {"insights": [], "skill_signals": {}, "total_events": 0}

    positive_job_ids = {e.job_id for e in events if e.outcome in positive_outcomes and e.job_id}
    negative_job_ids = {e.job_id for e in events if e.outcome in negative_outcomes and e.job_id}

    # Load job details for positive outcomes
    positive_skills: list[str] = []
    negative_skills: list[str] = []

    if positive_job_ids:
        jobs_res = await db.execute(
            select(Job.required_skills).where(Job.id.in_(positive_job_ids))
        )
        for (skills,) in jobs_res:
            positive_skills.extend(skills or [])

    if negative_job_ids:
        jobs_res = await db.execute(
            select(Job.required_skills).where(Job.id.in_(negative_job_ids))
        )
        for (skills,) in jobs_res:
            negative_skills.extend(skills or [])

    positive_counts = Counter(positive_skills)
    negative_counts = Counter(negative_skills)

    # Skills that appear in positive outcomes but not in profile → suggest adding
    profile_res = await db.execute(
        select(Profile)
        .where(Profile.user_id == user_id, Profile.is_active.is_(True))
        .order_by(Profile.version.desc())
        .limit(1)
    )
    profile = profile_res.scalar_one_or_none()
    current_skills = {s.lower() for s in (profile.skills if profile else [])}

    skills_to_add = [
        s for s, count in positive_counts.most_common(10)
        if s.lower() not in current_skills and count >= 2
    ]

    outcome_counts = Counter(e.outcome for e in events)

    return {
        "total_events": len(events),
        "outcome_distribution": dict(outcome_counts),
        "top_positive_skills": positive_counts.most_common(5),
        "skills_to_consider_adding": skills_to_add,
        "insights": _build_insights(outcome_counts, skills_to_add),
    }


def _build_insights(outcome_counts: Counter, skills_to_add: list[str]) -> list[str]:
    insights = []
    interviews = outcome_counts.get("interview", 0)
    rejections = outcome_counts.get("rejected", 0) + outcome_counts.get("rejected_after_interview", 0)

    if interviews > 0:
        insights.append(f"You received {interviews} interview invitation(s) — analyse those jobs for patterns.")
    if rejections > interviews and rejections > 2:
        insights.append("High rejection rate — consider widening target roles or adjusting salary expectations.")
    if skills_to_add:
        insights.append(f"Skills appearing in successful jobs not in your profile: {', '.join(skills_to_add[:5])}.")

    return insights
