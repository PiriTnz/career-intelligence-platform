from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.db.models import Application, User
from app.schemas.application import ApplicationCreate, ApplicationRead, ApplicationStatusUpdate

router = APIRouter()


@router.get("/", response_model=list[ApplicationRead])
async def list_applications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationRead]:
    result = await db.execute(
        select(Application)
        .where(Application.user_id == current_user.id)
        .order_by(Application.applied_at.desc())
    )
    return list(result.scalars().all())


@router.post("/", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
async def create_application(
    data: ApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationRead:
    app = Application(
        user_id=current_user.id,
        job_id=data.job_id,
        status="found",
        notes=data.notes,
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app


@router.get("/{application_id}", response_model=ApplicationRead)
async def get_application(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationRead:
    result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.user_id == current_user.id,
        )
    )
    app = result.scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


@router.patch("/{application_id}/status", response_model=ApplicationRead)
async def update_application_status(
    application_id: uuid.UUID,
    data: ApplicationStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationRead:
    result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.user_id == current_user.id,
        )
    )
    app = result.scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    app.status = data.status
    if data.notes is not None:
        app.notes = data.notes
    await db.commit()
    await db.refresh(app)
    return app


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_application(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.user_id == current_user.id,
        )
    )
    app = result.scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    await db.delete(app)
    await db.commit()
