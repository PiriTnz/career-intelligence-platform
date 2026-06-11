from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.db.models import User
from app.schemas.profile import (
    CVUploadResult,
    ProfileCreate,
    ProfileRead,
    ProfileUpdate,
    ProfileVersionRead,
)
from app.services import profile_service
from app.services.cv_parser import extract_text_from_pdf, parse_cv
from app.services.profile_service import (
    create_profile,
    get_active_profile,
    list_profile_versions,
    update_profile,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_UPLOAD_DIR = os.environ.get("CV_UPLOAD_DIR", "/tmp/job_hunter_cvs")
_MAX_CV_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


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


@router.post(
    "/upload-cv",
    response_model=CVUploadResult,
    status_code=status.HTTP_201_CREATED,
)
async def upload_cv(
    file: UploadFile = File(..., description="PDF resume / CV"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CVUploadResult:
    """
    Upload a PDF CV.  Text is extracted deterministically (no LLM).
    A new profile version is created from the extracted data.
    """
    # --- validate content type ---
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only PDF files are accepted (content-type: application/pdf)",
        )

    raw_bytes = await file.read()

    # --- validate magic bytes (%PDF) ---
    if not raw_bytes.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File does not appear to be a valid PDF",
        )

    if len(raw_bytes) > _MAX_CV_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"PDF exceeds maximum allowed size of {_MAX_CV_SIZE_BYTES // 1024 // 1024} MB",
        )

    # --- save to disk ---
    user_dir = os.path.join(_UPLOAD_DIR, str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}.pdf"
    cv_path = os.path.join(user_dir, safe_name)
    with open(cv_path, "wb") as fh:
        fh.write(raw_bytes)

    # --- deterministic extraction (no LLM) ---
    raw_text = extract_text_from_pdf(raw_bytes)
    extraction = parse_cv(raw_text)

    logger.info(
        "CV uploaded for user %s — confidence=%d missing=%s",
        current_user.id,
        extraction.extraction_confidence,
        extraction.missing_fields,
    )

    # --- persist: new profile + new profile_version ---
    try:
        profile, pv = await profile_service.create_profile_from_cv(
            db,
            user_id=current_user.id,
            extraction=extraction,
            cv_file_path=cv_path,
            raw_text=raw_text,
        )
        await db.commit()
        await db.refresh(profile)
        await db.refresh(pv)
    except Exception as exc:
        await db.rollback()
        logger.error("CV profile creation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save extracted profile — please try again",
        ) from exc

    missing_count = len(extraction.missing_fields)
    if missing_count == 0:
        msg = "CV parsed successfully — all fields extracted."
    else:
        msg = (
            f"CV parsed with {extraction.extraction_confidence}% confidence. "
            f"Missing fields: {', '.join(extraction.missing_fields)}. "
            "You can fill these in via PUT /profiles/me."
        )

    return CVUploadResult(
        profile_version_id=pv.id,
        profile_id=profile.id,
        profile_version=profile.version,
        extraction_confidence=extraction.extraction_confidence,
        full_name=extraction.full_name,
        email_extracted=extraction.email,
        phone=extraction.phone,
        location_raw=extraction.location_raw,
        extracted_skills=extraction.skills,
        inferred_skills=extraction.inferred_skills,
        suggested_roles=extraction.suggested_roles,
        missing_fields=extraction.missing_fields,
        education_count=len(extraction.education),
        experience_count=len(extraction.experience),
        certifications=extraction.certifications,
        message=msg,
    )


@router.get("/versions", response_model=list[ProfileVersionRead])
async def get_profile_versions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProfileVersionRead]:
    """Return all CV upload history for the current user, newest first."""
    return await list_profile_versions(db, current_user.id)
