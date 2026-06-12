"""
Opportunity Discovery Agent — API endpoints.

Route order (literal routes MUST precede parameterized /{id}):
  POST /discover
  GET  /preferences
  PUT  /preferences
  GET  /          (list)
  POST /{id}/feedback
  GET  /{id}      (single)
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.db.models import User
from app.schemas.opportunity import (
    DiscoverParams,
    OpportunityFeedbackCreate,
    OpportunityFeedbackRead,
    OpportunityMatchDetail,
    OpportunityPreferencesCreate,
    OpportunityPreferencesRead,
    OpportunityRead,
    OpportunityScoreBreakdown,
    ScoredOpportunityRead,
)
from app.services import opportunity_discovery_service as opp_svc
from app.services import job_service
from app.services.opportunity_discovery_service import ScoredOpportunity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


# ── POST /discover — score and rank opportunities against user profile ─────────

@router.post("/discover", response_model=list[ScoredOpportunityRead])
async def discover_opportunities(
    params: DiscoverParams,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[ScoredOpportunityRead]:
    """
    Score and rank opportunities against the authenticated user's profile
    and learned preferences.

    Uses stored opportunity preferences as filter defaults when no params
    provided in the request body.

    Each result includes profile_score, preference_score, final_score,
    match details, and score breakdown.
    """
    profile = await job_service.get_profile_dict(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active profile found — create or upload a CV first",
        )

    # Merge request params with stored preferences as defaults
    stored_prefs = await opp_svc.get_opportunity_preferences(db, current_user.id)
    effective_types = params.opportunity_types or stored_prefs.get("preferred_opportunity_types", [])
    effective_locations = params.locations or stored_prefs.get("preferred_locations", [])
    effective_industries = params.industries or stored_prefs.get("preferred_industries", [])
    effective_ct = params.contract_types or stored_prefs.get("preferred_contract_types", [])

    scored = await opp_svc.discover_and_score(
        db,
        current_user.id,
        profile,
        opportunity_types=effective_types or None,
        locations=effective_locations or None,
        keywords=params.keywords or None,
        industries=effective_industries or None,
        contract_types=effective_ct or None,
        limit=params.limit,
        offset=params.offset,
        min_score=params.min_score,
        profile_weight=params.profile_weight,
        preference_weight=params.preference_weight,
        sort_by=params.sort_by,
    )

    return [_to_scored_read(s) for s in scored]


# ── GET /preferences — retrieve user's opportunity preferences ────────────────

@router.get("/preferences", response_model=OpportunityPreferencesRead)
async def get_opportunity_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> OpportunityPreferencesRead:
    """Return the current user's opportunity discovery preferences.

    Returns empty lists for all categories when no preferences have been set.
    """
    pref = await opp_svc.get_opportunity_preference_model(db, current_user.id)
    if pref is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No opportunity preferences configured — use PUT to create them",
        )
    return OpportunityPreferencesRead.model_validate(pref)


# ── PUT /preferences — create or update opportunity preferences ───────────────

@router.put(
    "/preferences",
    response_model=OpportunityPreferencesRead,
    status_code=status.HTTP_200_OK,
)
async def upsert_opportunity_preferences(
    data: OpportunityPreferencesCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> OpportunityPreferencesRead:
    """Create or update opportunity discovery preferences.

    Subsequent calls overwrite all categories. Idempotent.
    """
    pref = await opp_svc.upsert_opportunity_preferences(
        db, current_user.id, data.model_dump()
    )
    await db.commit()
    await db.refresh(pref)
    return OpportunityPreferencesRead.model_validate(pref)


# ── GET / — list opportunities with basic filtering ───────────────────────────

@router.get("", response_model=list[OpportunityRead])
async def list_opportunities(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    opportunity_type: str | None = Query(None, description="Filter by opportunity type"),
    industry: str | None = Query(None, description="Filter by industry"),
    contract_type: str | None = Query(None, description="Filter by contract type"),
    remote: str | None = Query(None, description="Filter by remote status: none, hybrid, full"),
    keyword: str | None = Query(None, description="Search in title and description"),
    sort_by: str = Query("scraped_at", description="Sort field: scraped_at, published_at, title"),
    sort_desc: bool = Query(True, description="Sort descending (default true)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[OpportunityRead]:
    """List opportunities with basic filtering and sorting.

    No scoring — for a ranked, profile-aware view use POST /discover.
    """
    opps = await opp_svc.list_opportunities(
        db,
        opportunity_types=[opportunity_type] if opportunity_type else None,
        industries=[industry] if industry else None,
        contract_types=[contract_type] if contract_type else None,
        keywords=[keyword] if keyword else None,
        remote=remote,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )
    return [_to_opp_read(o) for o in opps]


# ── POST /{id}/feedback — record opportunity interaction ──────────────────────

@router.post(
    "/{opportunity_id}/feedback",
    status_code=status.HTTP_201_CREATED,
    response_model=OpportunityFeedbackRead,
)
async def record_opportunity_feedback(
    opportunity_id: uuid.UUID,
    body: OpportunityFeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> OpportunityFeedbackRead:
    """Record a feedback event for an opportunity.

    Event types: viewed, saved, applied, interested, rejected.
    Feedback is integrated with the preference learning agent:
    positive events increase type/industry affinity, rejected decreases it.
    """
    opp = await opp_svc.get_opportunity(db, opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    fb = await opp_svc.record_opportunity_feedback(
        db, current_user.id, opportunity_id, body.event_type
    )
    await db.commit()
    await db.refresh(fb)

    return OpportunityFeedbackRead(
        id=fb.id,
        user_id=fb.user_id,
        opportunity_id=fb.opportunity_id,
        event_type=fb.outcome,
        created_at=fb.created_at,
    )


# ── GET /{id} — single opportunity ───────────────────────────────────────────

@router.get("/{opportunity_id}", response_model=OpportunityRead)
async def get_opportunity(
    opportunity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> OpportunityRead:
    opp = await opp_svc.get_opportunity(db, opportunity_id)
    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )
    return _to_opp_read(opp)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_opp_read(opp) -> OpportunityRead:
    return OpportunityRead(
        id=opp.id,
        source=opp.source,
        source_id=opp.source_id,
        url=opp.url,
        title=opp.title,
        company=opp.company,
        location=opp.location,
        remote=opp.remote,
        opportunity_type=opp.opportunity_type,
        industry=opp.industry,
        sector=opp.sector,
        contract_type=opp.contract_type,
        salary_min=opp.salary_min,
        salary_max=opp.salary_max,
        salary_currency=opp.salary_currency,
        required_skills=opp.required_skills or [],
        experience_level=opp.experience_level,
        language=opp.language,
        description=opp.description,
        metadata=opp.metadata_ or {},
        published_at=opp.published_at,
        scraped_at=opp.scraped_at,
        is_active=opp.is_active,
    )


def _to_scored_read(s: ScoredOpportunity) -> ScoredOpportunityRead:
    opp = s.opp
    mr = s.match
    bd = s.breakdown
    return ScoredOpportunityRead(
        id=opp.id,
        source=opp.source,
        source_id=opp.source_id,
        url=opp.url,
        title=opp.title,
        company=opp.company,
        location=opp.location,
        remote=opp.remote,
        opportunity_type=opp.opportunity_type,
        industry=opp.industry,
        sector=opp.sector,
        contract_type=opp.contract_type,
        salary_min=opp.salary_min,
        salary_max=opp.salary_max,
        salary_currency=opp.salary_currency,
        required_skills=opp.required_skills or [],
        experience_level=opp.experience_level,
        language=opp.language,
        description=opp.description,
        metadata=opp.metadata_ or {},
        published_at=opp.published_at,
        scraped_at=opp.scraped_at,
        is_active=opp.is_active,
        profile_score=s.profile_score,
        preference_score=s.preference_score,
        final_score=s.final_score,
        match=OpportunityMatchDetail(
            matched_skills=mr.matched_skills,
            missing_skills=mr.missing_skills,
            skill_match_percentage=mr.skill_match_percentage,
            role_match_percentage=mr.role_match_percentage,
            best_matching_role=mr.best_matching_role,
            location_match=mr.location_match,
            remote_match=mr.remote_match,
            contract_match=mr.contract_match,
            language_match=mr.language_match,
            salary_ok=mr.salary_ok,
            experience_gap=mr.experience_gap,
            overall_fit=mr.overall_fit,
        ),
        score=OpportunityScoreBreakdown(
            skill_match=bd.skill_match,
            experience_match=bd.experience_match,
            location_score=bd.location_score,
            salary_score=bd.salary_score,
            contract_score=bd.contract_score,
            company_score=bd.company_score,
            freshness_score=bd.freshness_score,
            total=bd.total,
        ),
    )
