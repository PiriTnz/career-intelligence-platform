import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.limiter import limiter
from app.db.models import Application, InterviewWorkspace, Job, User
from app.llm import get_provider
from app.schemas.application import (
    ApplicationCreate,
    ApplicationNotesUpdate,
    ApplicationRead,
    ApplicationStatusUpdate,
    ApplicationTrackerItem,
)
from app.schemas.application_package import PreparePackageResponse, RequirementAnalysis, TransferableSkill
from app.services import application_package_service

router = APIRouter()

# Statuses that set specific timestamps when transitioned into
_TIMESTAMP_MAP = {
    "approved":  "approved_at",
    "applied":   "applied_at",
    "replied":   "replied_at",
    "interview": "interview_at",
}


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


@router.get("/tracker", response_model=list[ApplicationTrackerItem])
async def list_tracker_applications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationTrackerItem]:
    """
    Return enriched applications joined with Job and optional InterviewWorkspace.
    Used by the Application Tracker pipeline UI.
    """
    stmt = (
        select(Application, Job, InterviewWorkspace)
        .join(Job, Application.job_id == Job.id)
        .outerjoin(
            InterviewWorkspace,
            (InterviewWorkspace.job_id == Application.job_id)
            & (InterviewWorkspace.user_id == Application.user_id),
        )
        .where(Application.user_id == current_user.id)
        .order_by(Application.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()

    return [
        ApplicationTrackerItem(
            id=app.id,
            job_id=app.job_id,
            job_title=job.title,
            company_name=job.company_name,
            location=job.location,
            remote=job.remote,
            status=app.status,
            readiness_score=ws.readiness_score if ws else None,
            readiness_label=ws.readiness_label if ws else None,
            has_workspace=ws is not None,
            applied_at=app.applied_at,
            approved_at=app.approved_at,
            replied_at=app.replied_at,
            interview_at=app.interview_at,
            notes=app.notes,
            created_at=app.created_at,
            updated_at=app.updated_at,
        )
        for app, job, ws in rows
    ]


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

    # Set timestamps the first time each milestone is reached
    ts_field = _TIMESTAMP_MAP.get(data.status)
    if ts_field and getattr(app, ts_field) is None:
        setattr(app, ts_field, datetime.now(timezone.utc))

    await db.commit()
    await db.refresh(app)
    return app


@router.patch("/{application_id}/notes", response_model=ApplicationRead)
async def update_application_notes(
    application_id: uuid.UUID,
    data: ApplicationNotesUpdate,
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


# ── Application Package endpoints ─────────────────────────────────────────────

def _build_analysis_response(data: dict) -> RequirementAnalysis:
    return RequirementAnalysis(
        verified_match=data.get("verified_match", []),
        transferable_match=[
            TransferableSkill(**t) for t in data.get("transferable_match", [])
        ],
        real_gap=data.get("real_gap", []),
    )


@router.post("/{job_id}/prepare", response_model=PreparePackageResponse)
@limiter.limit("5/minute")
async def prepare_application_package(
    request: Request,
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PreparePackageResponse:
    """
    Generate an evidence-based application package (CV draft + cover letter)
    for the given job. Saves the result; re-running updates the existing package.
    """
    provider = get_provider()
    try:
        pkg = await application_package_service.prepare_application_package(
            db, current_user.id, job_id, provider
        )
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    return PreparePackageResponse(
        job_id=job_id,
        cv_draft=pkg.cv_draft,
        cover_letter_draft=pkg.cover_letter_draft,
        requirement_analysis=_build_analysis_response(pkg.requirement_analysis),
        warnings=pkg.warnings,
        ready_to_apply_score=pkg.ready_to_apply_score,
    )


@router.get("/{job_id}/package", response_model=PreparePackageResponse)
async def get_application_package(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PreparePackageResponse:
    """Retrieve a previously generated application package for the given job."""
    pkg = await application_package_service.get_application_package(
        db, current_user.id, job_id
    )
    if pkg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No package found for this job. Call POST /{job_id}/prepare first.",
        )

    return PreparePackageResponse(
        job_id=job_id,
        cv_draft=pkg.cv_draft,
        cover_letter_draft=pkg.cover_letter_draft,
        requirement_analysis=_build_analysis_response(pkg.requirement_analysis),
        warnings=pkg.warnings,
        ready_to_apply_score=pkg.ready_to_apply_score,
    )
