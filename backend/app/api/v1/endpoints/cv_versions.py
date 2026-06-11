from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.db.models import User
from app.llm import get_provider
from app.schemas.cv import CVGenerateRequest, CVVersionRead
from app.services.cv_service import generate_cv, get_cv_content, list_cv_versions

router = APIRouter()


@router.get("/", response_model=list[CVVersionRead])
async def list_cvs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CVVersionRead]:
    return await list_cv_versions(db, current_user.id)


@router.post("/generate", response_model=CVVersionRead, status_code=status.HTTP_201_CREATED)
async def generate_cv_endpoint(
    data: CVGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CVVersionRead:
    provider = get_provider()
    try:
        return await generate_cv(
            db,
            user_id=current_user.id,
            job_id=data.job_id,
            language=data.language,
            provider=provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{cv_id}/content")
async def get_cv_text(
    cv_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    cvs = await list_cv_versions(db, current_user.id)
    cv = next((c for c in cvs if c.id == cv_id), None)
    if cv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found")
    content = await get_cv_content(cv)
    return {"cv_id": str(cv_id), "content": content, "language": cv.language}
