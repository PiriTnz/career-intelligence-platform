"""
Scoring engine — fully deterministic.
LLM is called AFTER scoring only to generate a text explanation.
"""
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ScoreBreakdown:
    skill_match: int       # max 30
    experience_match: int  # max 20
    location_score: int    # max 15
    salary_score: int      # max 15
    contract_score: int    # max 10
    company_score: int     # max 5
    freshness_score: int   # max 5

    @property
    def total(self) -> int:
        return (
            self.skill_match + self.experience_match +
            self.location_score + self.salary_score +
            self.contract_score + self.company_score +
            self.freshness_score
        )

    @property
    def needs_review(self) -> bool:
        """Flag if score is high but extraction was probably incomplete."""
        return self.total >= 60 and self.skill_match < 10


def score_job(job: dict, profile: dict) -> tuple[ScoreBreakdown, int]:
    """
    Returns (breakdown, extraction_confidence).
    extraction_confidence: 0-100, how well we parsed the job description.
    """
    breakdown = ScoreBreakdown(
        skill_match=_skill_match(job, profile),
        experience_match=_experience_match(job, profile),
        location_score=_location_score(job, profile),
        salary_score=_salary_score(job, profile),
        contract_score=_contract_score(job, profile),
        company_score=_company_score(job),
        freshness_score=_freshness_score(job),
    )
    confidence = _extraction_confidence(job)
    return breakdown, confidence


# ── Individual scorers ───────────────────────────────────────────────────────

def _skill_match(job: dict, profile: dict) -> int:
    required = set(s.lower() for s in job.get("required_skills", []))
    user_skills = set(s.lower() for s in profile.get("skills", []))
    if not required:
        return 15  # unknown requirements — give half points
    matched = len(required & user_skills)
    ratio = matched / len(required)
    return round(ratio * 30)


def _experience_match(job: dict, profile: dict) -> int:
    level_map = {"junior": 1, "mid": 2, "senior": 3}
    job_level = level_map.get(job.get("experience_level", "").lower())
    user_level = level_map.get(profile.get("experience_level", "junior").lower(), 1)
    if job_level is None:
        return 10  # unknown — half points
    diff = abs(job_level - user_level)
    return {0: 20, 1: 10, 2: 0}.get(diff, 0)


def _location_score(job: dict, profile: dict) -> int:
    remote = job.get("remote", "none").lower()
    if remote == "full" and profile.get("remote_preference"):
        return 15
    job_city = (job.get("location") or "").lower()
    preferred_cities = [c.lower() for c in profile.get("cities", [])]
    preferred_countries = [c.lower() for c in profile.get("countries", [])]
    if any(city in job_city for city in preferred_cities):
        return 15
    if any(country in job_city for country in preferred_countries):
        return 8
    if remote == "hybrid":
        return 6
    return 0


def _salary_score(job: dict, profile: dict) -> int:
    s_min = job.get("salary_min")
    s_max = job.get("salary_max")
    p_min = profile.get("salary_min")
    p_target = profile.get("salary_target")
    if not s_min and not s_max:
        return 7  # unknown — half points
    salary_mid = ((s_min or 0) + (s_max or s_min or 0)) / 2
    if p_target and salary_mid >= p_target:
        return 15
    if p_min and salary_mid >= p_min:
        return round(((salary_mid - p_min) / (p_target - p_min + 1)) * 15) if p_target else 10
    return 0


def _contract_score(job: dict, profile: dict) -> int:
    job_contract = (job.get("contract_type") or "").lower()
    preferred = [c.lower() for c in profile.get("contract_types", [])]
    if not preferred:
        return 5
    return 10 if job_contract in preferred else 0


def _company_score(job: dict) -> int:
    quality = job.get("company_quality_score", 50)
    return round((quality / 100) * 5)


def _freshness_score(job: dict) -> int:
    published = job.get("published_at")
    if not published:
        return 2
    if isinstance(published, str):
        try:
            published = datetime.fromisoformat(published)
        except Exception:
            return 2
    now = datetime.now(timezone.utc)
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    age_days = (now - published).days
    if age_days <= 2:
        return 5
    if age_days <= 7:
        return 3
    if age_days <= 14:
        return 1
    return 0


def _extraction_confidence(job: dict) -> int:
    """How complete is the parsed job data? Lower = less reliable score."""
    fields = ["required_skills", "experience_level", "salary_min", "location", "contract_type"]
    filled = sum(1 for f in fields if job.get(f))
    return round((filled / len(fields)) * 100)
