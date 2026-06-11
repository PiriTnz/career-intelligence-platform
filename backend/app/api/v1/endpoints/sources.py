"""
POST /sources/france-travail/sync

Fetches raw jobs from France Travail, normalizes them, deduplicates by URL,
and saves to PostgreSQL. Returns counts of inserted / updated / skipped rows.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.db.models import User
from app.services.job_service import upsert_job
from app.services.normalizer import normalize
from app.services.sources import france_travail

logger = logging.getLogger(__name__)

router = APIRouter()


class SyncResult(BaseModel):
    source: str
    fetched: int = Field(description="Raw jobs returned by the API")
    inserted: int = Field(description="New jobs saved to DB")
    updated: int = Field(description="Existing jobs refreshed in DB")
    skipped: int = Field(description="Jobs skipped due to missing URL or errors")


@router.post(
    "/france-travail/sync",
    response_model=SyncResult,
    status_code=status.HTTP_200_OK,
    summary="Sync jobs from France Travail",
    description=(
        "Fetches job listings from France Travail API, normalizes them, "
        "deduplicates by URL, and upserts into PostgreSQL. "
        "Requires FRANCE_TRAVAIL_CLIENT_ID and FRANCE_TRAVAIL_CLIENT_SECRET "
        "to be set in the environment."
    ),
)
async def sync_france_travail(
    keywords: str = Query(
        default="AI Machine Learning MLOps",
        description="Keywords forwarded to France Travail motsCles param",
        max_length=200,
    ),
    department: str = Query(
        default="69",
        description="French department code (69 = Rhône/Lyon)",
        max_length=3,
        pattern=r"^\d{2,3}$",
    ),
    max_results: int = Query(
        default=300,
        ge=1,
        le=1000,
        description="Cap on how many raw jobs to fetch before stopping",
    ),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> SyncResult:
    raw_jobs = await france_travail.fetch_jobs(
        keywords=keywords,
        department=department,
        max_results=max_results,
    )

    if not raw_jobs:
        # fetch_jobs already logged why — could be no credentials or API error
        return SyncResult(
            source="france_travail",
            fetched=0,
            inserted=0,
            updated=0,
            skipped=0,
        )

    inserted = updated = skipped = 0

    for raw in raw_jobs:
        try:
            normalized = normalize(raw, "france_travail")
        except Exception as exc:
            logger.warning("Normalization failed for job %s: %s", raw.get("id"), exc)
            skipped += 1
            continue

        if not normalized.get("url"):
            skipped += 1
            continue

        # Store the full raw payload for debugging / reprocessing
        normalized["raw_json"] = raw

        try:
            _, is_new = await upsert_job(db, normalized)
            if is_new:
                inserted += 1
            else:
                updated += 1
        except Exception as exc:
            logger.error("DB upsert failed for url=%s: %s", normalized.get("url"), exc)
            skipped += 1

    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.error("France Travail sync commit failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database commit failed — changes rolled back",
        ) from exc

    logger.info(
        "France Travail sync complete: fetched=%d inserted=%d updated=%d skipped=%d",
        len(raw_jobs), inserted, updated, skipped,
    )
    return SyncResult(
        source="france_travail",
        fetched=len(raw_jobs),
        inserted=inserted,
        updated=updated,
        skipped=skipped,
    )
