"""
Profile-aware job matching engine — pure functions, no I/O.

Compares a profile dict against a job dict and returns a MatchResult with
named, human-readable fields that go beyond the numeric ScoreBreakdown.

Entry point:  match(job, profile) -> MatchResult
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ── Result ─────────────────────────────────────────────────────────────────────

@dataclass
class MatchResult:
    # Skill-level analysis
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    skill_match_percentage: float = 0.0     # 0.0-100.0

    # Role-title alignment
    role_match_percentage: float = 0.0      # 0.0-100.0 (best match across target_roles)
    best_matching_role: str | None = None   # which target role matched best

    # Boolean flags
    location_match: bool = False            # exact city or country match
    remote_match: bool = False              # job remote matches profile preference
    contract_match: bool = False            # job contract in profile's preferred list
    language_match: bool = False            # job language in profile's languages
    salary_ok: bool = False                 # job salary midpoint >= profile salary_min

    # Experience gap: 0 = exact, >0 = overqualified, <0 = underqualified
    experience_gap: int = 0

    # Composite
    overall_fit: float = 0.0               # weighted 0-100


# ── Main entry point ──────────────────────────────────────────────────────────

def match(job: dict, profile: dict) -> MatchResult:
    """
    Compare a job against a profile.
    Pure function — no I/O, no side effects.

    Both dicts use the same keys as the scoring engine:
      job     → required_skills, experience_level, location, remote,
                contract_type, salary_min, salary_max, language (default "fr")
      profile → skills, target_roles, experience_level, cities, countries,
                remote_preference, contract_types, salary_min, languages
    """
    result = MatchResult()

    _compute_skill_match(result, job, profile)
    _compute_role_match(result, job, profile)
    _compute_location_match(result, job, profile)
    _compute_remote_match(result, job, profile)
    _compute_contract_match(result, job, profile)
    _compute_language_match(result, job, profile)
    _compute_experience_gap(result, job, profile)
    _compute_salary_ok(result, job, profile)
    _compute_overall_fit(result)

    return result


# ── Individual matchers ───────────────────────────────────────────────────────

def _compute_skill_match(result: MatchResult, job: dict, profile: dict) -> None:
    required = [s.lower() for s in job.get("required_skills", [])]
    user = {s.lower() for s in profile.get("skills", [])}

    if not required:
        # No skill requirements listed → neutral
        result.skill_match_percentage = 50.0
        return

    required_set = set(required)
    matched = sorted(required_set & user)
    missing = sorted(required_set - user)

    result.matched_skills = matched
    result.missing_skills = missing
    result.skill_match_percentage = round(len(matched) / len(required_set) * 100, 1)


def _compute_role_match(result: MatchResult, job: dict, profile: dict) -> None:
    title = job.get("title") or ""
    target_roles = [r for r in profile.get("target_roles", []) if r]

    if not target_roles:
        result.role_match_percentage = 50.0  # no preference → neutral
        return

    best_pct = 0.0
    best_role: str | None = None

    title_norm = _norm(title)

    for role in target_roles:
        role_norm = _norm(role)
        if not role_norm:
            continue

        # Substring: full role phrase in title → high confidence
        if role_norm in title_norm:
            pct = 90.0 + (10.0 * (len(role_norm) / max(len(title_norm), 1)))
            pct = min(pct, 100.0)
        else:
            title_words = set(title_norm.split())
            role_words = set(role_norm.split())
            overlap = len(title_words & role_words)
            union = len(title_words | role_words)
            pct = round(overlap / union * 100, 1) if union else 0.0

        if pct > best_pct:
            best_pct = pct
            best_role = role

    result.role_match_percentage = round(best_pct, 1)
    result.best_matching_role = best_role


def _compute_location_match(result: MatchResult, job: dict, profile: dict) -> None:
    job_loc = (job.get("location") or "").lower()
    cities = [c.lower() for c in profile.get("cities", [])]
    countries = [c.lower() for c in profile.get("countries", [])]

    result.location_match = (
        any(c in job_loc for c in cities if c)
        or any(c in job_loc for c in countries if c)
    )


def _compute_remote_match(result: MatchResult, job: dict, profile: dict) -> None:
    remote = (job.get("remote") or "none").lower()
    pref = profile.get("remote_preference", False)
    result.remote_match = (remote == "full" and pref) or (remote in ("hybrid", "none") and not pref)


def _compute_contract_match(result: MatchResult, job: dict, profile: dict) -> None:
    job_contract = (job.get("contract_type") or "").lower()
    preferred = [c.lower() for c in profile.get("contract_types", [])]
    if not preferred:
        result.contract_match = True  # no preference → any contract is fine
    else:
        result.contract_match = job_contract in preferred


def _compute_language_match(result: MatchResult, job: dict, profile: dict) -> None:
    """
    job.language is typically "fr" or "en".
    profile.languages may contain canonical names ("French", "English")
    or ISO codes ("fr", "en").
    """
    job_lang = (job.get("language") or "fr").lower()
    profile_langs = [l.lower() for l in profile.get("languages", [])]

    # Build a normalised set covering both ISO codes and English names
    normalised: set[str] = set()
    for lang in profile_langs:
        normalised.add(lang)
        # map common names → codes
        if lang in _LANG_TO_CODE:
            normalised.add(_LANG_TO_CODE[lang])
        # map codes → names
        if lang in _CODE_TO_LANG:
            normalised.add(_CODE_TO_LANG[lang])

    result.language_match = job_lang in normalised or not profile_langs


def _compute_experience_gap(result: MatchResult, job: dict, profile: dict) -> None:
    level_map = {"junior": 1, "mid": 2, "senior": 3}
    job_level = level_map.get((job.get("experience_level") or "").lower())
    user_level = level_map.get((profile.get("experience_level") or "mid").lower(), 2)

    if job_level is None:
        result.experience_gap = 0  # unknown → no gap
    else:
        # Positive = user is over-qualified, negative = under-qualified
        result.experience_gap = user_level - job_level


def _compute_salary_ok(result: MatchResult, job: dict, profile: dict) -> None:
    s_min = job.get("salary_min")
    s_max = job.get("salary_max")
    p_min = profile.get("salary_min")

    if not p_min:
        result.salary_ok = True  # no expectation → always ok
        return
    if not s_min and not s_max:
        result.salary_ok = False  # undisclosed salary → can't confirm
        return

    mid = ((s_min or 0) + (s_max or s_min or 0)) / 2
    result.salary_ok = mid >= p_min


def _compute_overall_fit(result: MatchResult) -> None:
    """
    Weighted overall fit score:
      skill_match_pct  40 %
      role_match_pct   20 %
      location         15 %  (bool → 0 or 100)
      salary           10 %  (bool → 0 or 100)
      contract         10 %  (bool → 0 or 100)
      language          5 %  (bool → 0 or 100)
    """
    loc = 100.0 if result.location_match or result.remote_match else 0.0
    sal = 100.0 if result.salary_ok else 0.0
    con = 100.0 if result.contract_match else 0.0
    lng = 100.0 if result.language_match else 0.0

    result.overall_fit = round(
        result.skill_match_percentage * 0.40
        + result.role_match_percentage * 0.20
        + loc * 0.15
        + sal * 0.10
        + con * 0.10
        + lng * 0.05,
        1,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

_LANG_TO_CODE: dict[str, str] = {
    "french": "fr", "français": "fr", "anglais": "en",
    "english": "en", "german": "de", "allemand": "de",
    "spanish": "es", "espagnol": "es", "italian": "it",
    "portuguese": "pt", "dutch": "nl", "chinese": "zh",
    "mandarin": "zh", "arabic": "ar", "japanese": "ja",
}

_CODE_TO_LANG: dict[str, str] = {v: k for k, v in _LANG_TO_CODE.items() if len(k) == 2}
# de→german, but de is not a 2-char value above, let's add manually
_CODE_TO_LANG.update({
    "fr": "french", "en": "english", "de": "german",
    "es": "spanish", "it": "italian", "pt": "portuguese",
    "nl": "dutch", "zh": "chinese", "ar": "arabic", "ja": "japanese",
})


def _norm(text: str) -> str:
    """Lowercase, strip punctuation/accents, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()
