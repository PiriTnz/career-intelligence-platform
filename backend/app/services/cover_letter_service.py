from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CoverLetter, Job, Profile
from app.llm.base import BaseLLMProvider

_TYPE_INSTRUCTIONS = {
    "cover_letter": "Write a professional cover letter (lettre de motivation formelle). Use 3-4 paragraphs. Max 400 words.",
    "motivation": "Write a motivation letter focused on personal drive, passion for AI/ML, and cultural fit. 3 paragraphs. Max 350 words.",
    "email_hr": "Write a short, direct email to HR. Introduce the candidate and their top 3 matching skills. Max 150 words. Subject line included.",
}


def _letter_prompt(job: Job, profile: Profile, letter_type: str, language: str) -> str:
    instruction = _TYPE_INSTRUCTIONS.get(letter_type, _TYPE_INSTRUCTIONS["cover_letter"])
    lang_line = "Write in French (formal tu/vous — use vous)." if language == "fr" else "Write in English."

    return f"""{instruction}
{lang_line}

=== POSITION ===
Title: {job.title}
Company: {job.company_name}
Location: {job.location} | Contract: {job.contract_type}
Required skills: {', '.join(job.required_skills or [])}
Job description excerpt: {(job.description or '')[:600]}

=== CANDIDATE ===
Skills: {', '.join(profile.skills)}
Target roles: {', '.join(profile.target_roles)}
Experience level: {profile.experience_level}
Cities: {', '.join(profile.cities)}

Rules:
- Be specific — mention actual matching skills by name.
- No generic phrases like "I am passionate about technology".
- Highlight the strongest 2-3 skill matches for this specific job.
- Do not invent experience. Use only what is given."""


async def generate_cover_letter(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    letter_type: str,
    language: str,
    provider: BaseLLMProvider,
) -> CoverLetter:
    from sqlalchemy import select as sel

    job_res = await db.execute(sel(Job).where(Job.id == job_id))
    job = job_res.scalar_one_or_none()
    if job is None:
        raise ValueError(f"Job {job_id} not found")

    profile_res = await db.execute(
        sel(Profile)
        .where(Profile.user_id == user_id, Profile.is_active.is_(True))
        .order_by(Profile.version.desc())
        .limit(1)
    )
    profile = profile_res.scalar_one_or_none()
    if profile is None:
        raise ValueError("No active profile — create a profile first")

    prompt = _letter_prompt(job, profile, letter_type, language)
    content = await provider.generate(prompt, max_tokens=800)

    letter = CoverLetter(
        user_id=user_id,
        job_id=job_id,
        type=letter_type,
        language=language,
        content=content or f"[Generation failed — check LLM availability]",
    )
    db.add(letter)
    await db.commit()
    await db.refresh(letter)
    return letter


async def list_cover_letters(
    db: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID | None = None
) -> list[CoverLetter]:
    query = select(CoverLetter).where(CoverLetter.user_id == user_id)
    if job_id:
        query = query.where(CoverLetter.job_id == job_id)
    query = query.order_by(CoverLetter.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())
