from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.db.models import User
from app.llm import get_provider
from app.schemas.cover_letter import CoverLetterGenerateRequest, CoverLetterRead
from app.services.cover_letter_service import generate_cover_letter, list_cover_letters

router = APIRouter()


@router.get("/", response_model=list[CoverLetterRead])
async def list_letters(
    job_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CoverLetterRead]:
    return await list_cover_letters(db, current_user.id, job_id=job_id)


@router.post("/generate", response_model=CoverLetterRead, status_code=status.HTTP_201_CREATED)
async def generate_letter(
    data: CoverLetterGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CoverLetterRead:
    provider = get_provider()
    try:
        return await generate_cover_letter(
            db,
            user_id=current_user.id,
            job_id=data.job_id,
            letter_type=data.type,
            language=data.language,
            provider=provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
