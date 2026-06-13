import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.limiter import limiter
from app.db.models import Application, ApplicationTimeline, InterviewWorkspace, Job, User
from app.llm import get_provider
from app.schemas.application import (
    ApplicationCreate,
    ApplicationMetrics,
    ApplicationNotesUpdate,
    ApplicationRead,
    ApplicationStatusUpdate,
    ApplicationTimelineItem,
    ApplicationTrackerItem,
    ApplicationWithTimeline,
    VALID_TRANSITIONS,
)
from app.schemas.application_package import PreparePackageResponse, RequirementAnalysis, TransferableSkill
from app.services import application_package_service

router = APIRouter()

# Timestamp field to set (once) when first entering a status
_TIMESTAMP_MAP: dict[str, str] = {
    "applied":    "applied_at",
    "follow_up":  "follow_up_at",
    "interview":  "interview_at",
    "offer":      "offer_at",
    "rejected":   "rejected_at",
}


# ── helpers ───────────────────────────────────────────────────────────────────

async def _get_own_application(
    db: AsyncSession, application_id: uuid.UUID, user_id: uuid.UUID
) -> Application:
    result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.user_id == user_id,
        )
    )
    app = result.scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


async def _get_own_application_by_job(
    db: AsyncSession, job_id: uuid.UUID, user_id: uuid.UUID
) -> Application:
    result = await db.execute(
        select(Application).where(
            Application.job_id == job_id,
            Application.user_id == user_id,
        )
    )
    app = result.scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


async def _fetch_timeline(db: AsyncSession, application_id: uuid.UUID) -> list[ApplicationTimeline]:
    result = await db.execute(
        select(ApplicationTimeline)
        .where(ApplicationTimeline.application_id == application_id)
        .order_by(ApplicationTimeline.created_at)
    )
    return list(result.scalars().all())


def _apply_status_transition(app: Application, new_status: str) -> None:
    """Mutate app in-place: set status + first-time timestamp. Validates transition."""
    if new_status == app.status:
        return
    allowed = VALID_TRANSITIONS.get(app.status, [])
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition from '{app.status}' to '{new_status}'. Allowed: {allowed or ['none (terminal state)']}",
        )
    app.status = new_status
    ts_field = _TIMESTAMP_MAP.get(new_status)
    if ts_field and getattr(app, ts_field) is None:
        setattr(app, ts_field, datetime.now(timezone.utc))


async def _record_timeline(
    db: AsyncSession, application_id: uuid.UUID, new_status: str, notes: str | None
) -> None:
    db.add(ApplicationTimeline(
        id=uuid.uuid4(),
        application_id=application_id,
        status=new_status,
        notes=notes,
    ))


def _build_tracker_item(app: Application, job: Job, ws: InterviewWorkspace | None) -> ApplicationTrackerItem:
    now = datetime.now(timezone.utc)
    return ApplicationTrackerItem(
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
        follow_up_due=app.follow_up_at is not None and app.follow_up_at < now,
        applied_at=app.applied_at,
        follow_up_at=app.follow_up_at,
        interview_at=app.interview_at,
        offer_at=app.offer_at,
        rejected_at=app.rejected_at,
        notes=app.notes,
        created_at=app.created_at,
        updated_at=app.updated_at,
    )


# ── List / create ─────────────────────────────────────────────────────────────

@router.get("/", response_model=list[ApplicationRead])
async def list_applications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationRead]:
    result = await db.execute(
        select(Application)
        .where(Application.user_id == current_user.id)
        .order_by(Application.created_at.desc())
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
        status="recommended",
        notes=data.notes,
    )
    db.add(app)
    await db.flush()
    await _record_timeline(db, app.id, "recommended", None)
    await db.commit()
    await db.refresh(app)
    return app


# ── Tracker / queue / metrics (fixed routes before parameterized) ─────────────

@router.get("/tracker", response_model=list[ApplicationTrackerItem])
async def list_tracker_applications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationTrackerItem]:
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
    return [_build_tracker_item(app, job, ws) for app, job, ws in rows]


@router.get("/ready", response_model=list[ApplicationTrackerItem])
async def list_ready_to_apply(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationTrackerItem]:
    """Applications that are ready to apply — user has prepared and is waiting to submit."""
    stmt = (
        select(Application, Job, InterviewWorkspace)
        .join(Job, Application.job_id == Job.id)
        .outerjoin(
            InterviewWorkspace,
            (InterviewWorkspace.job_id == Application.job_id)
            & (InterviewWorkspace.user_id == Application.user_id),
        )
        .where(
            Application.user_id == current_user.id,
            Application.status == "ready_to_apply",
        )
        .order_by(Application.updated_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [_build_tracker_item(app, job, ws) for app, job, ws in rows]


@router.get("/metrics", response_model=ApplicationMetrics)
async def get_application_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationMetrics:
    result = await db.execute(
        select(Application.status, func.count(Application.id))
        .where(Application.user_id == current_user.id)
        .group_by(Application.status)
    )
    counts: dict[str, int] = {row[0]: row[1] for row in result.all()}
    total = sum(counts.values())
    return ApplicationMetrics(
        total=total,
        recommended=counts.get("recommended", 0),
        preparing=counts.get("preparing", 0),
        ready_to_apply=counts.get("ready_to_apply", 0),
        applied=counts.get("applied", 0),
        follow_up=counts.get("follow_up", 0),
        interview=counts.get("interview", 0),
        offer=counts.get("offer", 0),
        rejected=counts.get("rejected", 0),
    )


# ── Job-id-scoped endpoints (used from WorkspaceTab) ─────────────────────────

@router.get("/job/{job_id}", response_model=ApplicationWithTimeline)
async def get_application_by_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationWithTimeline:
    app = await _get_own_application_by_job(db, job_id, current_user.id)
    timeline = await _fetch_timeline(db, app.id)
    return ApplicationWithTimeline(
        **ApplicationRead.model_validate(app).model_dump(),
        timeline=[ApplicationTimelineItem.model_validate(t) for t in timeline],
    )


@router.post("/job/{job_id}/status", response_model=ApplicationWithTimeline)
async def update_status_by_job(
    job_id: uuid.UUID,
    data: ApplicationStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationWithTimeline:
    app = await _get_own_application_by_job(db, job_id, current_user.id)
    _apply_status_transition(app, data.status)
    if data.notes is not None:
        app.notes = data.notes
    await _record_timeline(db, app.id, data.status, data.notes)
    await db.commit()
    await db.refresh(app)
    timeline = await _fetch_timeline(db, app.id)
    return ApplicationWithTimeline(
        **ApplicationRead.model_validate(app).model_dump(),
        timeline=[ApplicationTimelineItem.model_validate(t) for t in timeline],
    )


@router.post("/job/{job_id}/notes", response_model=ApplicationRead)
async def update_notes_by_job(
    job_id: uuid.UUID,
    data: ApplicationNotesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationRead:
    app = await _get_own_application_by_job(db, job_id, current_user.id)
    app.notes = data.notes
    await db.commit()
    await db.refresh(app)
    return app


# ── Application-id-scoped endpoints ──────────────────────────────────────────

@router.get("/{application_id}", response_model=ApplicationRead)
async def get_application(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationRead:
    return await _get_own_application(db, application_id, current_user.id)


@router.patch("/{application_id}/status", response_model=ApplicationRead)
async def update_application_status(
    application_id: uuid.UUID,
    data: ApplicationStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationRead:
    app = await _get_own_application(db, application_id, current_user.id)
    _apply_status_transition(app, data.status)
    if data.notes is not None:
        app.notes = data.notes
    await _record_timeline(db, app.id, data.status, data.notes)
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
    app = await _get_own_application(db, application_id, current_user.id)
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
    app = await _get_own_application(db, application_id, current_user.id)
    await db.delete(app)
    await db.commit()


# ── Application Package (LLM-powered — rate-limited) ─────────────────────────

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
