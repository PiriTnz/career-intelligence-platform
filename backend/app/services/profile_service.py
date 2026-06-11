from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Profile
from app.db.models.profile_version import ProfileVersion
from app.schemas.profile import ProfileCreate, ProfileUpdate
from app.services.cv_parser import CVExtractionResult


async def get_active_profile(db: AsyncSession, user_id: uuid.UUID) -> Profile | None:
    result = await db.execute(
        select(Profile)
        .where(Profile.user_id == user_id, Profile.is_active.is_(True))
        .order_by(Profile.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_profile(
    db: AsyncSession, user_id: uuid.UUID, data: ProfileCreate
) -> Profile:
    # Deactivate any existing active profile
    existing = await get_active_profile(db, user_id)
    new_version = 1
    if existing:
        existing.is_active = False
        new_version = existing.version + 1

    profile = Profile(
        user_id=user_id,
        version=new_version,
        target_roles=data.target_roles,
        avoid_roles=data.avoid_roles,
        skills=data.skills,
        experience_level=data.experience_level,
        salary_min=data.salary_min,
        salary_target=data.salary_target,
        remote_preference=data.remote_preference,
        countries=data.countries,
        cities=data.cities,
        contract_types=data.contract_types,
        languages=data.languages,
        is_active=True,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def update_profile(
    db: AsyncSession, user_id: uuid.UUID, data: ProfileUpdate
) -> Profile | None:
    profile = await get_active_profile(db, user_id)
    if profile is None:
        return None

    update_data = data.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return profile


async def create_profile_from_dict(
    db: AsyncSession, user_id: uuid.UUID, data: dict
) -> Profile:
    """Used by Profile Agent after LLM extraction."""
    return await create_profile(db, user_id, ProfileCreate(**data))


async def create_profile_from_cv(
    db: AsyncSession,
    user_id: uuid.UUID,
    extraction: CVExtractionResult,
    cv_file_path: str,
    raw_text: str,
) -> tuple[Profile, ProfileVersion]:
    """
    Create a new profile version from deterministic CV extraction.

    Returns (profile, profile_version) — both are flushed but NOT committed.
    Caller must commit.
    """
    # Deactivate old active profile, determine version number
    existing = await get_active_profile(db, user_id)
    new_version = 1
    if existing:
        existing.is_active = False
        new_version = existing.version + 1

    # Build the profile from extracted data
    all_skills = list(dict.fromkeys(extraction.skills + extraction.inferred_skills))
    target_roles = extraction.suggested_roles or []

    # Infer location arrays from raw location string
    cities: list[str] = []
    countries: list[str] = []
    if extraction.location_raw:
        loc_lower = extraction.location_raw.lower()
        cities = [extraction.location_raw]
        # France detection — all French cities are in France
        from app.services.cv_parser import FRENCH_CITIES
        if any(c in loc_lower for c in FRENCH_CITIES):
            countries = ["france"]

    profile = Profile(
        user_id=user_id,
        version=new_version,
        target_roles=target_roles,
        avoid_roles=[],
        skills=all_skills,
        experience_level=extraction.experience_level,
        salary_min=None,
        salary_target=None,
        remote_preference=False,
        countries=countries,
        cities=[c.lower() for c in cities],
        contract_types=[],
        languages=extraction.languages or ["fr", "en"],
        phone=extraction.phone,
        certifications=extraction.certifications,
        education=extraction.education,
        experience=extraction.experience,
        cv_file_path=cv_file_path,
        is_active=True,
    )
    db.add(profile)
    await db.flush()  # get profile.id

    pv = ProfileVersion(
        user_id=user_id,
        profile_id=profile.id,
        version=new_version,
        source="cv_upload",
        cv_file_path=cv_file_path,
        raw_text=raw_text,
        full_name=extraction.full_name,
        phone=extraction.phone,
        email_extracted=extraction.email,
        location_raw=extraction.location_raw,
        education=extraction.education,
        experience=extraction.experience,
        certifications=extraction.certifications,
        extracted_skills=extraction.skills,
        inferred_skills=extraction.inferred_skills,
        missing_fields=extraction.missing_fields,
        suggested_roles=extraction.suggested_roles,
        extraction_confidence=extraction.extraction_confidence,
    )
    db.add(pv)
    await db.flush()

    return profile, pv


async def list_profile_versions(
    db: AsyncSession, user_id: uuid.UUID
) -> list[ProfileVersion]:
    result = await db.execute(
        select(ProfileVersion)
        .where(ProfileVersion.user_id == user_id)
        .order_by(ProfileVersion.created_at.desc())
    )
    return list(result.scalars().all())
