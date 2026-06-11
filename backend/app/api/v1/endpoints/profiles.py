from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.db.models import User
from app.schemas.profile import ProfileCreate, ProfileRead, ProfileUpdate
from app.services.profile_service import create_profile, get_active_profile, update_profile

router = APIRouter()


@router.get("/me", response_model=ProfileRead)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileRead:
    profile = await get_active_profile(db, current_user.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active profile found")
    return profile


@router.post("/me", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
async def create_my_profile(
    data: ProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileRead:
    return await create_profile(db, current_user.id, data)


@router.put("/me", response_model=ProfileRead)
async def update_my_profile(
    data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileRead:
    profile = await update_profile(db, current_user.id, data)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active profile to update")
    return profile
