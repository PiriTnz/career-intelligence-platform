from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Profile
from app.schemas.profile import ProfileCreate, ProfileUpdate


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
