from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CVVersion, Job, Profile
from app.llm.base import BaseLLMProvider

_STORAGE = Path("/app/storage/cvs")


def _cv_prompt(job: Job, profile: Profile, language: str) -> str:
    lang_instruction = "Write in French. Use formal French professional style." if language == "fr" \
        else "Write in English. Use a concise, professional tone."

    return f"""{lang_instruction}
Generate an ATS-optimized CV for this candidate tailored to the job below.
Use only real information provided — do not invent experience.

=== JOB ===
Title: {job.title}
Company: {job.company_name}
Location: {job.location} | Remote: {job.remote} | Contract: {job.contract_type}
Required skills: {', '.join(job.required_skills or [])}
Description excerpt: {(job.description or '')[:600]}

=== CANDIDATE PROFILE ===
Target roles: {', '.join(profile.target_roles)}
Skills: {', '.join(profile.skills)}
Experience level: {profile.experience_level}
Cities: {', '.join(profile.cities)}

=== OUTPUT FORMAT ===
## Professional Summary
[2-3 sentences. Highlight strongest skill matches for this specific job.]

## Technical Skills
[List skills most relevant to this job first. Group by category.]

## Professional Experience
[Use the candidate's actual experience level to structure this.
Focus on achievements using action verbs. Quantify where possible.]

## Education & Training
[Include relevant degrees, certifications, bootcamps.]

## Languages
[List the candidate's languages with proficiency level.]

ATS rules: use the exact skill names from the job posting. No tables, no columns."""


async def generate_cv(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    language: str,
    provider: BaseLLMProvider,
) -> CVVersion:
    # Load job and active profile
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

    prompt = _cv_prompt(job, profile, language)
    content = await provider.generate(prompt, max_tokens=1200)

    # Save to filesystem
    user_dir = _STORAGE / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    file_path = user_dir / f"{job_id}_{language}.txt"
    file_path.write_text(content, encoding="utf-8")

    # Rough ATS score: % of job skills present in CV text
    ats_score = 0
    if job.required_skills:
        matched = sum(1 for s in job.required_skills if s.lower() in content.lower())
        ats_score = round((matched / len(job.required_skills)) * 100)

    cv = CVVersion(
        user_id=user_id,
        job_id=job_id,
        file_path=str(file_path),
        language=language,
        ats_score=ats_score,
    )
    db.add(cv)
    await db.commit()
    await db.refresh(cv)
    return cv


async def list_cv_versions(
    db: AsyncSession, user_id: uuid.UUID
) -> list[CVVersion]:
    result = await db.execute(
        select(CVVersion)
        .where(CVVersion.user_id == user_id)
        .order_by(CVVersion.created_at.desc())
    )
    return list(result.scalars().all())


async def get_cv_content(cv: CVVersion) -> str:
    path = Path(cv.file_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")
