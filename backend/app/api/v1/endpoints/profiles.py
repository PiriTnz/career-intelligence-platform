from __future__ import annotations

import asyncio
import logging
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_user
from app.core.database import get_db
from app.db.models import User
from app.llm import get_provider
from app.schemas.feedback import AffinityItem, PreferenceProfileRead
from app.schemas.profile import (
    CVUploadResult,
    ProfileCreate,
    ProfileRead,
    ProfileUpdate,
    ProfileVersionRead,
)
from app.schemas.profile_assistant import (
    ApplyUpdatesRequest,
    AssistantMessageRequest,
    AssistantMessageResponse,
    ProfileCompletenessResponse,
)
from app.services import preference_service, profile_assistant_service, profile_service
from app.services.cv_parser import extract_text_from_pdf, parse_cv
from app.services.profile_service import (
    create_profile,
    get_active_profile,
    list_profile_versions,
    update_profile,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_UPLOAD_DIR = os.environ.get("CV_UPLOAD_DIR", "/tmp/career_intel_cvs")
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

    # --- deterministic extraction (no LLM) — run in thread to avoid blocking event loop ---
    raw_text = await asyncio.to_thread(extract_text_from_pdf, raw_bytes)
    extraction = await asyncio.to_thread(parse_cv, raw_text)

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


@router.post("/assistant/message", response_model=AssistantMessageResponse)
async def assistant_message(
    data: AssistantMessageRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AssistantMessageResponse:
    """Send a free-form message to the profile assistant.

    The assistant extracts career profile fields using LLM, validates them through
    Pydantic, and returns proposed updates. Nothing is written to the profile here.
    Use POST /assistant/apply-updates to confirm and persist the changes.
    """
    profile = await get_active_profile(db, current_user.id)
    current_profile_dict = (
        profile_assistant_service.profile_model_to_dict(profile) if profile else {}
    )

    provider = get_provider()
    extracted = await profile_assistant_service.extract_profile_updates(
        provider, data.message, current_profile_dict, data.language
    )

    # Merge extracted fields on top of current profile for completeness computation
    merged = dict(current_profile_dict)
    for k, v in extracted.items():
        if isinstance(v, list) and isinstance(merged.get(k), list):
            merged[k] = list(dict.fromkeys(merged[k] + v))
        elif v is not None:
            merged[k] = v

    result = profile_assistant_service.compute_profile_completeness(merged)
    assistant_msg = profile_assistant_service.build_assistant_message(
        data.language, extracted, result.missing_fields, result.completeness
    )
    next_q = profile_assistant_service.get_next_question(result.missing_fields, data.language)

    return AssistantMessageResponse(
        assistant_message=assistant_msg,
        updated_profile_fields=extracted,
        missing_fields=result.missing_fields,
        profile_completeness=result.completeness,
        next_question=next_q,
    )


@router.get("/completeness", response_model=ProfileCompletenessResponse)
async def get_completeness(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileCompletenessResponse:
    """Return the completeness score of the current user's active profile."""
    profile = await get_active_profile(db, current_user.id)
    profile_dict = (
        profile_assistant_service.profile_model_to_dict(profile) if profile else {}
    )
    result = profile_assistant_service.compute_profile_completeness(profile_dict)
    return ProfileCompletenessResponse(
        completeness=result.completeness,
        missing_fields=result.missing_fields,
        field_scores=result.field_scores,
        total_possible=result.total_possible,
    )


@router.post("/assistant/apply-updates", response_model=ProfileRead)
async def apply_updates(
    data: ApplyUpdatesRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileRead:
    """Persist profile updates previously proposed by POST /assistant/message.

    The updates dict is re-validated through Pydantic before any write occurs.
    List fields are merged with existing data; scalar fields are overwritten.
    """
    if not data.updates:
        profile = await get_active_profile(db, current_user.id)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active profile found and no updates provided",
            )
        return profile

    updated = await profile_assistant_service.apply_profile_updates(
        db, current_user.id, data.updates
    )
    return updated


@router.get("/preferences", response_model=PreferenceProfileRead)
async def get_preferences(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PreferenceProfileRead:
    """
    Return the computed preference profile derived from feedback events.

    Preferences are learned from feedback signals:
      interview (+3), applied (+2), saved (+1), viewed (0), rejected (−2)

    When no feedback events exist, all affinity lists are empty.
    """
    prefs = await preference_service.get_preference_profile(db, current_user.id)

    return PreferenceProfileRead(
        preferred_skills=[AffinityItem(name=n, affinity=a) for n, a in prefs.preferred_skills],
        preferred_locations=[AffinityItem(name=n, affinity=a) for n, a in prefs.preferred_locations],
        preferred_companies=[AffinityItem(name=n, affinity=a) for n, a in prefs.preferred_companies],
        preferred_contract_types=[AffinityItem(name=n, affinity=a) for n, a in prefs.preferred_contract_types],
        preferred_job_families=[AffinityItem(name=n, affinity=a) for n, a in prefs.preferred_job_families],
        total_events=prefs.total_events,
        signal_breakdown=prefs.signal_breakdown,
        has_preferences=prefs.has_preferences,
    )
