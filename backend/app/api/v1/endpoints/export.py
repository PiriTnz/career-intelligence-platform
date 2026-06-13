import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.db.models import Job, User
from app.db.models.application_package import ApplicationPackage
from app.db.models.profile import Profile
from app.services import export_service

router = APIRouter()

# ── helpers ───────────────────────────────────────────────────────────────────

async def _get_package(
    db: AsyncSession, job_id: uuid.UUID, user_id: uuid.UUID
) -> ApplicationPackage:
    result = await db.execute(
        select(ApplicationPackage).where(
            ApplicationPackage.job_id == job_id,
            ApplicationPackage.user_id == user_id,
        )
    )
    pkg = result.scalar_one_or_none()
    if pkg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No application package found. Call POST /applications/{job_id}/prepare first.",
        )
    return pkg


async def _get_job(db: AsyncSession, job_id: uuid.UUID) -> Job:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


async def _get_candidate_name(db: AsyncSession, user_id: uuid.UUID) -> str:
    result = await db.execute(select(Profile).where(Profile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if profile and isinstance(profile.personal_info, dict):
        name = profile.personal_info.get("name") or profile.personal_info.get("full_name")
        if name:
            return str(name)
    return "Candidate"


# ── CV export ─────────────────────────────────────────────────────────────────

@router.get("/{job_id}/cv.docx")
async def download_cv_docx(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    pkg = await _get_package(db, job_id, current_user.id)
    if not pkg.cv_draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV draft is empty")

    payload = export_service.build_cv_docx(pkg.cv_draft)

    # Record export timestamp (first time only)
    if pkg.exported_cv_at is None:
        pkg.exported_cv_at = datetime.now(timezone.utc)
        await db.commit()

    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="cv.docx"'},
    )


@router.get("/{job_id}/cv.pdf")
async def download_cv_pdf(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    pkg = await _get_package(db, job_id, current_user.id)
    if not pkg.cv_draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV draft is empty")

    payload = export_service.build_cv_pdf(pkg.cv_draft)

    if pkg.exported_cv_at is None:
        pkg.exported_cv_at = datetime.now(timezone.utc)
        await db.commit()

    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="cv.pdf"'},
    )


# ── Cover letter export ───────────────────────────────────────────────────────

@router.get("/{job_id}/letter.docx")
async def download_letter_docx(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    pkg = await _get_package(db, job_id, current_user.id)
    if not pkg.cover_letter_draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cover letter is empty")

    payload = export_service.build_cover_letter_docx(pkg.cover_letter_draft)

    if pkg.exported_cover_letter_at is None:
        pkg.exported_cover_letter_at = datetime.now(timezone.utc)
        await db.commit()

    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="cover_letter.docx"'},
    )


@router.get("/{job_id}/letter.pdf")
async def download_letter_pdf(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    pkg = await _get_package(db, job_id, current_user.id)
    if not pkg.cover_letter_draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cover letter is empty")

    payload = export_service.build_cover_letter_pdf(pkg.cover_letter_draft)

    if pkg.exported_cover_letter_at is None:
        pkg.exported_cover_letter_at = datetime.now(timezone.utc)
        await db.commit()

    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="cover_letter.pdf"'},
    )


# ── Copy-ready messages ───────────────────────────────────────────────────────

class MessagesResponse(BaseModel):
    hr_email: str
    linkedin_message: str


@router.get("/{job_id}/messages", response_model=MessagesResponse)
async def get_copy_messages(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessagesResponse:
    pkg = await _get_package(db, job_id, current_user.id)
    job = await _get_job(db, job_id)
    candidate_name = await _get_candidate_name(db, current_user.id)

    cover_letter = pkg.cover_letter_draft or pkg.cv_draft or ""

    return MessagesResponse(
        hr_email=export_service.build_hr_email(
            job_title=job.title,
            company_name=job.company_name,
            candidate_name=candidate_name,
            cover_letter=cover_letter,
        ),
        linkedin_message=export_service.build_linkedin_message(
            job_title=job.title,
            company_name=job.company_name,
            candidate_name=candidate_name,
            cover_letter=cover_letter,
        ),
    )
