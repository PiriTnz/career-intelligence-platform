"""
Opportunity Discovery Agent — discovery, scoring, and preference management.

Scores opportunities against the authenticated user's profile (deterministic)
and preference signals (feedback-learned + explicit settings).

Architecture constraints:
  - No hardcoded user data, roles, locations, or skills.
  - All scoring driven by the authenticated user's profile and preferences.
  - score_job() and match() are reused directly from existing engines.
  - Deterministic weighted scoring only; no LLM in this service.
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Opportunity, OpportunityFeedback, OpportunityPreference
from app.services import preference_service
from app.services.matching_engine import MatchResult, match
from app.services.preference_service import PreferenceProfile, compute_preference_score
from app.services.scoring_service import ScoreBreakdown, score_job

logger = logging.getLogger(__name__)

# ── Opportunity feedback signal weights ───────────────────────────────────────
# "interested" is specific to opportunities (no job equivalent)

OPP_EVENT_WEIGHTS: dict[str, float] = {
    "interview": 3.0,
    "applied": 2.0,
    "interested": 1.5,
    "saved": 1.0,
    "viewed": 0.0,
    "rejected": -2.0,
}

VALID_OPP_EVENT_TYPES: frozenset[str] = frozenset(OPP_EVENT_WEIGHTS)

# Fields present in the normalized schema — extras go into metadata
_STANDARD_FIELDS: frozenset[str] = frozenset({
    "source", "source_id", "url", "title", "company", "company_name",
    "location", "remote", "opportunity_type", "industry", "sector",
    "contract_type", "salary_min", "salary_max", "salary_currency",
    "required_skills", "experience_level", "language", "description",
    "published_at",
})


# ── Scored result container ───────────────────────────────────────────────────

@dataclass
class ScoredOpportunity:
    """Opportunity annotated with profile score, preference score, and final rank."""

    opp: Opportunity
    profile_score: int
    preference_score: float
    final_score: int
    match: MatchResult
    breakdown: ScoreBreakdown


# ── Normalization ─────────────────────────────────────────────────────────────

def normalize_opportunity(raw: dict, source: str) -> dict:
    """Normalize a raw opportunity dict from any source into the standard schema.

    Any keys not in the standard schema are collected into metadata_.
    Returns a dict ready to pass to upsert_opportunity().
    """
    contract = raw.get("contract_type")
    return {
        "source": source,
        "source_id": raw.get("source_id") or raw.get("id"),
        "url": raw.get("url", ""),
        "title": raw.get("title", ""),
        "company": raw.get("company") or raw.get("company_name"),
        "location": raw.get("location"),
        "remote": (raw.get("remote") or "none").lower(),
        "opportunity_type": (raw.get("opportunity_type") or "employment").lower(),
        "industry": raw.get("industry"),
        "sector": raw.get("sector"),
        "contract_type": contract.lower() if contract else None,
        "salary_min": raw.get("salary_min"),
        "salary_max": raw.get("salary_max"),
        "salary_currency": raw.get("salary_currency", "EUR"),
        "required_skills": [s.lower() for s in raw.get("required_skills", [])],
        "experience_level": raw.get("experience_level"),
        "language": raw.get("language", "en"),
        "description": raw.get("description"),
        "metadata_": {k: v for k, v in raw.items() if k not in _STANDARD_FIELDS},
        "published_at": raw.get("published_at"),
    }


# ── Preference scoring ────────────────────────────────────────────────────────

def _compute_explicit_pref_score(opp_dict: dict, opp_prefs: dict) -> float:
    """Score 0–100 how well an opportunity matches explicit user preferences.

    Weights: opportunity_type 40 pts, industry 30 pts, sector 30 pts.
    Returns 50.0 (neutral) when a category has no preferences configured.
    """
    score = 0.0

    # Opportunity type — 40 pts (20 neutral)
    preferred_types = {t.lower() for t in opp_prefs.get("preferred_opportunity_types", [])}
    opp_type = (opp_dict.get("opportunity_type") or "").lower()
    if not preferred_types:
        score += 20.0
    elif opp_type in preferred_types:
        score += 40.0

    # Industry — 30 pts (15 neutral)
    preferred_industries = {i.lower() for i in opp_prefs.get("preferred_industries", [])}
    opp_industry = (opp_dict.get("industry") or "").lower()
    if not preferred_industries:
        score += 15.0
    elif opp_industry in preferred_industries:
        score += 30.0

    # Sector — 30 pts (15 neutral)
    preferred_sectors = {s.lower() for s in opp_prefs.get("preferred_sectors", [])}
    opp_sector = (opp_dict.get("sector") or "").lower()
    if not preferred_sectors:
        score += 15.0
    elif opp_sector in preferred_sectors:
        score += 30.0

    return score


def _compute_type_feedback_score(opp_dict: dict, type_affinities: dict[str, float]) -> float:
    """Score 0–100 based on learned affinities from past opportunity feedback.

    Uses the opportunity_type dimension only (type, not industry/sector,
    since those are handled by explicit preferences).
    Returns 50.0 when no feedback exists.
    """
    if not type_affinities:
        return 50.0

    opp_type = (opp_dict.get("opportunity_type") or "").lower()
    if opp_type not in type_affinities:
        return 50.0

    max_abs = max(abs(v) for v in type_affinities.values()) or 1.0
    aff = type_affinities[opp_type]
    # Map [-max_abs, +max_abs] → [0, 100] centered at 50
    return round(max(0.0, min(100.0, (aff / max_abs) * 50 + 50)), 1)


def compute_opportunity_preference_score(
    opp_dict: dict,
    job_feedback_prefs: PreferenceProfile,
    opp_prefs: dict,
    type_affinities: dict[str, float],
) -> float:
    """Blend three preference signals into one 0–100 score.

    Weights:
        60%  skill/location/company affinities (from job feedback via preference_service)
        25%  explicit opportunity type/industry/sector preferences
        15%  learned opportunity-type affinities (from opportunity feedback)

    Returns 50.0 (neutral) when all three signals are absent.
    """
    skill_loc_score = compute_preference_score(opp_dict, job_feedback_prefs)
    explicit_score = _compute_explicit_pref_score(opp_dict, opp_prefs)
    type_fb_score = _compute_type_feedback_score(opp_dict, type_affinities)

    return round(0.60 * skill_loc_score + 0.25 * explicit_score + 0.15 * type_fb_score, 1)


def blend_opportunity_scores(
    profile_score: int,
    preference_score: float,
    *,
    profile_weight: float = 0.70,
    preference_weight: float = 0.30,
    has_preferences: bool,
) -> int:
    """Blend profile and preference scores with configurable weights.

    Weights are normalized so they always sum to 1.0.
    Falls back to pure profile_score when has_preferences is False.
    """
    if not has_preferences:
        return profile_score
    total = profile_weight + preference_weight or 1.0
    pw = profile_weight / total
    prw = preference_weight / total
    return round(pw * profile_score + prw * preference_score)


# ── DB helpers ────────────────────────────────────────────────────────────────

def _model_to_score_dict(opp: Opportunity) -> dict:
    """Map Opportunity model to the dict format expected by score_job() and match()."""
    return {
        "title": opp.title,
        "company_name": opp.company or "",
        "required_skills": opp.required_skills or [],
        "experience_level": opp.experience_level,
        "location": opp.location,
        "remote": opp.remote,
        "contract_type": opp.contract_type,
        "salary_min": opp.salary_min,
        "salary_max": opp.salary_max,
        "published_at": opp.published_at,
        "company_quality_score": 50,
        "language": opp.language or "en",
        "opportunity_type": opp.opportunity_type,
        "industry": opp.industry,
        "sector": opp.sector,
    }


async def get_opportunity(db: AsyncSession, opportunity_id: uuid.UUID) -> Opportunity | None:
    result = await db.execute(select(Opportunity).where(Opportunity.id == opportunity_id))
    return result.scalar_one_or_none()


async def list_opportunities(
    db: AsyncSession,
    *,
    opportunity_types: list[str] | None = None,
    locations: list[str] | None = None,
    keywords: list[str] | None = None,
    industries: list[str] | None = None,
    contract_types: list[str] | None = None,
    remote: str | None = None,
    is_active: bool = True,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "scraped_at",
    sort_desc: bool = True,
) -> list[Opportunity]:
    """Fetch opportunities from DB with optional filtering and sorting."""
    q = select(Opportunity).where(Opportunity.is_active == is_active)

    if opportunity_types:
        lower_types = [t.lower() for t in opportunity_types]
        q = q.where(func.lower(Opportunity.opportunity_type).in_(lower_types))

    if industries:
        lower_ind = [i.lower() for i in industries]
        q = q.where(func.lower(Opportunity.industry).in_(lower_ind))

    if contract_types:
        lower_ct = [c.lower() for c in contract_types]
        q = q.where(func.lower(Opportunity.contract_type).in_(lower_ct))

    if remote:
        q = q.where(Opportunity.remote == remote.lower())

    for loc in (locations or []):
        q = q.where(Opportunity.location.ilike(f"%{loc}%"))

    for kw in (keywords or []):
        q = q.where(
            Opportunity.title.ilike(f"%{kw}%") | Opportunity.description.ilike(f"%{kw}%")
        )

    col_map = {
        "scraped_at": Opportunity.scraped_at,
        "published_at": Opportunity.published_at,
        "title": Opportunity.title,
    }
    sort_col = col_map.get(sort_by, Opportunity.scraped_at)
    q = q.order_by(sort_col.desc() if sort_desc else sort_col.asc())
    q = q.offset(offset).limit(limit)

    result = await db.execute(q)
    return list(result.scalars().all())


async def upsert_opportunity(db: AsyncSession, data: dict) -> tuple[Opportunity, bool]:
    """Insert or update an opportunity. Deduplicates by (source, source_id) or URL.

    Returns (opportunity, is_new).
    Flushes but does NOT commit — caller owns the transaction.
    """
    source = data.get("source", "")
    source_id = data.get("source_id")

    opp: Opportunity | None = None
    if source_id:
        result = await db.execute(
            select(Opportunity).where(
                Opportunity.source == source,
                Opportunity.source_id == source_id,
            )
        )
        opp = result.scalar_one_or_none()

    if opp is None:
        url = data.get("url", "")
        if url:
            result = await db.execute(select(Opportunity).where(Opportunity.url == url))
            opp = result.scalar_one_or_none()

    is_new = opp is None
    if is_new:
        opp = Opportunity()
        db.add(opp)

    for attr, value in data.items():
        if hasattr(opp, attr):
            setattr(opp, attr, value)

    await db.flush()
    return opp, is_new


# ── Preference management ─────────────────────────────────────────────────────

async def get_opportunity_preferences(
    db: AsyncSession, user_id: uuid.UUID
) -> dict:
    """Return user's opportunity preferences as a plain dict.

    Returns an empty dict when no preferences have been configured.
    """
    result = await db.execute(
        select(OpportunityPreference).where(OpportunityPreference.user_id == user_id)
    )
    pref = result.scalar_one_or_none()
    if pref is None:
        return {}
    return {
        "preferred_opportunity_types": pref.preferred_opportunity_types or [],
        "preferred_industries": pref.preferred_industries or [],
        "preferred_sectors": pref.preferred_sectors or [],
        "preferred_locations": pref.preferred_locations or [],
        "preferred_contract_types": pref.preferred_contract_types or [],
        "keywords": pref.keywords or [],
    }


async def get_opportunity_preference_model(
    db: AsyncSession, user_id: uuid.UUID
) -> OpportunityPreference | None:
    """Return the raw OpportunityPreference ORM model (for serialization)."""
    result = await db.execute(
        select(OpportunityPreference).where(OpportunityPreference.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def upsert_opportunity_preferences(
    db: AsyncSession, user_id: uuid.UUID, data: dict
) -> OpportunityPreference:
    """Create or update opportunity preferences for a user.

    Flushes but does NOT commit — caller owns the transaction.
    """
    result = await db.execute(
        select(OpportunityPreference).where(OpportunityPreference.user_id == user_id)
    )
    pref = result.scalar_one_or_none()
    if pref is None:
        pref = OpportunityPreference(user_id=user_id)
        db.add(pref)

    for attr, value in data.items():
        if hasattr(pref, attr):
            setattr(pref, attr, value)

    await db.flush()
    return pref


# ── Opportunity feedback integration ──────────────────────────────────────────

async def get_opportunity_type_affinities(
    db: AsyncSession, user_id: uuid.UUID
) -> dict[str, float]:
    """Compute opportunity-type affinities from past feedback events.

    Integrates with the Feedback Learning Agent: positive interactions
    (applied, interested, interview) increase affinity; rejected decreases it.
    Returns empty dict when no feedback exists.
    """
    result = await db.execute(
        select(OpportunityFeedback.outcome, Opportunity.opportunity_type)
        .join(Opportunity, OpportunityFeedback.opportunity_id == Opportunity.id)
        .where(OpportunityFeedback.user_id == user_id)
    )
    rows = result.all()

    type_aff: dict[str, float] = defaultdict(float)
    for outcome, opp_type in rows:
        weight = OPP_EVENT_WEIGHTS.get(outcome, 0.0)
        if weight != 0.0 and opp_type:
            type_aff[opp_type.lower()] += weight

    return dict(type_aff)


async def record_opportunity_feedback(
    db: AsyncSession,
    user_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    event_type: str,
) -> OpportunityFeedback:
    """Persist an opportunity feedback event.

    Flushes but does NOT commit — caller owns the transaction.
    """
    fb = OpportunityFeedback(
        user_id=user_id,
        opportunity_id=opportunity_id,
        outcome=event_type,
    )
    db.add(fb)
    await db.flush()
    return fb


# ── Main discovery function ───────────────────────────────────────────────────

async def discover_and_score(
    db: AsyncSession,
    user_id: uuid.UUID,
    profile: dict,
    *,
    opportunity_types: list[str] | None = None,
    locations: list[str] | None = None,
    keywords: list[str] | None = None,
    industries: list[str] | None = None,
    contract_types: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
    min_score: int = 0,
    profile_weight: float = 0.70,
    preference_weight: float = 0.30,
    sort_by: str = "final_score",
) -> list[ScoredOpportunity]:
    """Score and rank opportunities against the user's profile and preferences.

    Fetches up to 500 candidates from DB, scores all in memory, then
    sorts by final_score (or profile_score/preference_score) and paginates.
    """
    opps = await list_opportunities(
        db,
        opportunity_types=opportunity_types,
        locations=locations,
        keywords=keywords,
        industries=industries,
        contract_types=contract_types,
        limit=500,
        offset=0,
    )

    if not opps:
        return []

    # Load all preference signals (one DB round-trip each)
    job_prefs = await preference_service.get_preference_profile(db, user_id)
    opp_prefs_dict = await get_opportunity_preferences(db, user_id)
    type_affinities = await get_opportunity_type_affinities(db, user_id)

    has_prefs = job_prefs.has_preferences or bool(opp_prefs_dict) or bool(type_affinities)

    results: list[ScoredOpportunity] = []
    for opp in opps:
        try:
            score_dict = _model_to_score_dict(opp)
            breakdown, _ = score_job(score_dict, profile)

            if breakdown.total < min_score:
                continue

            mr = match(score_dict, profile)
            pref_score = compute_opportunity_preference_score(
                score_dict, job_prefs, opp_prefs_dict, type_affinities
            )
            final = blend_opportunity_scores(
                breakdown.total,
                pref_score,
                profile_weight=profile_weight,
                preference_weight=preference_weight,
                has_preferences=has_prefs,
            )

            results.append(
                ScoredOpportunity(
                    opp=opp,
                    profile_score=breakdown.total,
                    preference_score=pref_score,
                    final_score=final,
                    match=mr,
                    breakdown=breakdown,
                )
            )
        except Exception as exc:
            logger.warning("Skipping opportunity %s in discovery: %s", opp.id, exc)

    # Sort in memory (final sort key after all scoring)
    sort_key_map = {
        "profile_score": lambda s: s.profile_score,
        "preference_score": lambda s: s.preference_score,
    }
    key_fn = sort_key_map.get(sort_by, lambda s: s.final_score)
    results.sort(key=key_fn, reverse=True)

    return results[offset: offset + limit]
