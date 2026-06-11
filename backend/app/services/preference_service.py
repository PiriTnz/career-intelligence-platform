"""
Feedback Learning Agent — preference service.

Reads FeedbackEvent rows, weights them by signal strength,
and derives preference affinities across skills, locations,
companies, contract types, and job families.

Design constraints:
  - Deterministic: same events always produce the same preference profile
  - LLM-free: pure frequency-weighted counts
  - Additive: positive events increase affinity, rejected events decrease it
  - Score never modified: preference_score only influences recommendation ranking
"""
from __future__ import annotations

import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FeedbackEvent, Job

# ── Signal weights ────────────────────────────────────────────────────────────

EVENT_WEIGHTS: dict[str, float] = {
    "interview": 3.0,   # strongest positive signal
    "applied": 2.0,     # candidate chose to apply
    "saved": 1.0,       # interested but not committed
    "viewed": 0.0,      # neutral — tracked but not used in affinities
    "rejected": -2.0,   # explicit disinterest
}

VALID_EVENT_TYPES: frozenset[str] = frozenset(EVENT_WEIGHTS)

# ── Job family extraction ─────────────────────────────────────────────────────

_SEP_RE = re.compile(r'[—–\-|/\\(,]')
_NOISE_WORDS = frozenset({
    "senior", "junior", "lead", "principal", "staff", "head",
    "stage", "alternance", "intern", "stagiaire",
    "confirmé", "confirme", "debutant", "débutant",
    "h/f", "f/h", "hf", "fh",
})


def _extract_family(title: str | None) -> str:
    """Normalize job title to a 1–3 word family token.

    Examples:
        "Senior ML Engineer — Paris" → "ml engineer"
        "Stage Data Scientist (6 mois)" → "data scientist"
    """
    if not title:
        return ""
    chunk = _SEP_RE.split(title.lower())[0].strip()
    words = [w for w in chunk.split() if w not in _NOISE_WORDS]
    return " ".join(words[:3])


def _word_overlap(a: str, b: str) -> float:
    wa = set(a.split())
    wb = set(b.split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


# ── PreferenceProfile dataclass ───────────────────────────────────────────────

@dataclass
class PreferenceProfile:
    """Computed from feedback events. Affinities are strictly positive (negatives filtered)."""

    preferred_skills: list[tuple[str, float]] = field(default_factory=list)
    preferred_locations: list[tuple[str, float]] = field(default_factory=list)
    preferred_companies: list[tuple[str, float]] = field(default_factory=list)
    preferred_contract_types: list[tuple[str, float]] = field(default_factory=list)
    preferred_job_families: list[tuple[str, float]] = field(default_factory=list)
    total_events: int = 0
    signal_breakdown: dict[str, int] = field(default_factory=dict)

    @property
    def has_preferences(self) -> bool:
        """True when at least one category has positive affinity data."""
        return bool(
            self.preferred_skills
            or self.preferred_locations
            or self.preferred_companies
            or self.preferred_contract_types
            or self.preferred_job_families
        )


# ── Preference computation ────────────────────────────────────────────────────

async def get_preference_profile(
    db: AsyncSession, user_id: uuid.UUID
) -> PreferenceProfile:
    """
    Compute preference profile for a user from all their feedback events.
    Returns an empty PreferenceProfile when no events exist.
    """
    events_result = await db.execute(
        select(FeedbackEvent).where(FeedbackEvent.user_id == user_id)
    )
    events = events_result.scalars().all()

    if not events:
        return PreferenceProfile(total_events=0)

    # Signal breakdown
    signal_breakdown: dict[str, int] = defaultdict(int)
    for ev in events:
        signal_breakdown[ev.outcome] += 1

    # Collect job IDs that carry signal weight
    job_ids = {
        ev.job_id
        for ev in events
        if ev.job_id and EVENT_WEIGHTS.get(ev.outcome, 0.0) != 0.0
    }

    if not job_ids:
        return PreferenceProfile(
            total_events=len(events),
            signal_breakdown=dict(signal_breakdown),
        )

    # Batch-load jobs
    jobs_result = await db.execute(select(Job).where(Job.id.in_(job_ids)))
    jobs: dict[uuid.UUID, Job] = {j.id: j for j in jobs_result.scalars()}

    # Accumulate weighted affinities
    skill_aff: dict[str, float] = defaultdict(float)
    location_aff: dict[str, float] = defaultdict(float)
    company_aff: dict[str, float] = defaultdict(float)
    contract_aff: dict[str, float] = defaultdict(float)
    family_aff: dict[str, float] = defaultdict(float)

    for ev in events:
        weight = EVENT_WEIGHTS.get(ev.outcome, 0.0)
        if weight == 0.0 or not ev.job_id:
            continue
        job = jobs.get(ev.job_id)
        if job is None:
            continue

        for skill in (job.required_skills or []):
            skill_aff[skill.lower()] += weight

        if job.location:
            city = job.location.split(",")[0].strip().lower()
            if city:
                location_aff[city] += weight

        if job.company_name:
            company_aff[job.company_name.lower()] += weight

        if job.contract_type:
            contract_aff[job.contract_type.lower()] += weight

        family = _extract_family(job.title)
        if family:
            family_aff[family] += weight

    def _top(aff_dict: dict, n: int) -> list[tuple[str, float]]:
        return sorted(
            ((k, round(v, 2)) for k, v in aff_dict.items() if v > 0),
            key=lambda x: x[1],
            reverse=True,
        )[:n]

    return PreferenceProfile(
        preferred_skills=_top(skill_aff, 20),
        preferred_locations=_top(location_aff, 10),
        preferred_companies=_top(company_aff, 10),
        preferred_contract_types=_top(contract_aff, 5),
        preferred_job_families=_top(family_aff, 10),
        total_events=len(events),
        signal_breakdown=dict(signal_breakdown),
    )


# ── Preference scoring ────────────────────────────────────────────────────────

def compute_preference_score(job_dict: dict, prefs: PreferenceProfile) -> float:
    """
    Compute a 0–100 preference affinity score for a job.

    Weights:
        skills      40 pts
        location    25 pts
        contract    15 pts
        company     10 pts
        job family  10 pts

    Returns 50.0 (neutral) when no preferences have been learned.
    Neutral per-category baseline ensures no relative ranking change
    until users provide at least one non-viewed signal.
    """
    if not prefs.has_preferences:
        return 50.0

    score = 0.0

    # ── Skills (40 pts) ──────────────────────────────────────────────────────
    if prefs.preferred_skills:
        max_aff = max(aff for _, aff in prefs.preferred_skills)
        skill_lookup = {s: aff for s, aff in prefs.preferred_skills}
        job_skills = [s.lower() for s in job_dict.get("required_skills", [])]
        n = len(job_skills) or 1
        raw = sum(skill_lookup.get(s, 0.0) for s in job_skills)
        score += min(raw / (max_aff * n), 1.0) * 40
    else:
        score += 20.0  # neutral 50% of 40

    # ── Location (25 pts) ────────────────────────────────────────────────────
    if prefs.preferred_locations:
        loc = (job_dict.get("location") or "").lower()
        max_aff = max(aff for _, aff in prefs.preferred_locations)
        if job_dict.get("remote") == "full":
            score += 12.5  # remote jobs are location-neutral
        else:
            best = max(
                (aff for pref_loc, aff in prefs.preferred_locations
                 if pref_loc in loc or loc.startswith(pref_loc)),
                default=0.0,
            )
            score += (best / max_aff) * 25
    else:
        score += 12.5  # neutral

    # ── Contract type (15 pts) ───────────────────────────────────────────────
    if prefs.preferred_contract_types:
        contract = (job_dict.get("contract_type") or "").lower()
        max_aff = max(aff for _, aff in prefs.preferred_contract_types)
        match_aff = next(
            (aff for pref_c, aff in prefs.preferred_contract_types if pref_c == contract),
            0.0,
        )
        score += (match_aff / max_aff) * 15
    else:
        score += 7.5  # neutral

    # ── Company (10 pts) ─────────────────────────────────────────────────────
    if prefs.preferred_companies:
        company = (job_dict.get("company_name") or "").lower()
        max_aff = max(aff for _, aff in prefs.preferred_companies)
        best = max(
            (aff for pref_comp, aff in prefs.preferred_companies
             if pref_comp in company or company in pref_comp),
            default=0.0,
        )
        score += (best / max_aff) * 10
    else:
        score += 5.0  # neutral

    # ── Job family (10 pts) ──────────────────────────────────────────────────
    if prefs.preferred_job_families:
        title_fam = _extract_family(job_dict.get("title"))
        max_aff = max(aff for _, aff in prefs.preferred_job_families)
        best = max(
            (aff for pref_fam, aff in prefs.preferred_job_families
             if (pref_fam in title_fam or title_fam in pref_fam or
                 _word_overlap(pref_fam, title_fam) >= 0.33)),
            default=0.0,
        )
        score += (best / max_aff) * 10
    else:
        score += 5.0  # neutral

    return round(score, 1)


def blend_scores(
    profile_score: int,
    preference_score: float,
    *,
    has_preferences: bool,
) -> int:
    """
    Blend profile score and preference score into final ranking score.

    Formula: 0.70 × profile_score + 0.30 × preference_score

    Falls back to pure profile_score when no preferences have been learned,
    preserving the original ranking for new users.
    """
    if not has_preferences:
        return profile_score
    return round(0.70 * profile_score + 0.30 * preference_score)
