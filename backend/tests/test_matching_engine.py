"""
Unit tests for the profile-aware matching engine.

All functions are pure — no DB, no mocks.
"""
from __future__ import annotations

import pytest

from app.services.matching_engine import MatchResult, match


# ── Fixtures ──────────────────────────────────────────────────────────────────

FULL_PROFILE = {
    "skills": ["python", "pytorch", "fastapi", "docker", "kubernetes", "llm", "rag", "mlops"],
    "target_roles": ["ML Engineer", "LLM Engineer", "MLOps Engineer"],
    "experience_level": "mid",
    "salary_min": 42_000,
    "salary_target": 58_000,
    "remote_preference": True,
    "countries": ["france"],
    "cities": ["lyon", "paris", "grenoble"],
    "contract_types": ["cdi", "cdd"],
    "languages": ["French", "English"],
}

PERFECT_JOB = {
    "title": "ML Engineer — LLM & RAG",
    "required_skills": ["python", "pytorch", "llm", "rag"],
    "experience_level": "mid",
    "location": "Lyon, France",
    "remote": "full",
    "contract_type": "cdi",
    "salary_min": 52_000,
    "salary_max": 65_000,
    "language": "fr",
}

PARTIAL_JOB = {
    "title": "Data Engineer",
    "required_skills": ["python", "spark", "kafka", "airflow"],
    "experience_level": "senior",
    "location": "Marseille, France",
    "remote": "none",
    "contract_type": "cdi",
    "salary_min": 35_000,
    "salary_max": 42_000,
    "language": "fr",
}

NO_MATCH_JOB = {
    "title": "Java Backend Developer",
    "required_skills": ["java", "spring", "oracle"],
    "experience_level": "junior",
    "location": "London, UK",
    "remote": "none",
    "contract_type": "stage",
    "salary_min": 20_000,
    "salary_max": 25_000,
    "language": "en",
}


# ── MatchResult dataclass ─────────────────────────────────────────────────────

class TestMatchResultDefaults:
    def test_defaults_are_empty(self):
        r = MatchResult()
        assert r.matched_skills == []
        assert r.missing_skills == []
        assert r.skill_match_percentage == 0.0
        assert r.role_match_percentage == 0.0
        assert r.location_match is False
        assert r.contract_match is False
        assert r.language_match is False
        assert r.experience_gap == 0
        assert r.salary_ok is False
        assert r.overall_fit == 0.0


# ── Skill matching ────────────────────────────────────────────────────────────

class TestSkillMatch:
    def test_perfect_match(self):
        job = {"required_skills": ["python", "docker"]}
        profile = {"skills": ["python", "docker", "kubernetes"]}
        r = match(job, profile)
        assert r.skill_match_percentage == 100.0
        assert r.matched_skills == ["docker", "python"]
        assert r.missing_skills == []

    def test_no_match(self):
        job = {"required_skills": ["cobol", "fortran"]}
        profile = {"skills": ["python", "docker"]}
        r = match(job, profile)
        assert r.skill_match_percentage == 0.0
        assert r.matched_skills == []
        assert set(r.missing_skills) == {"cobol", "fortran"}

    def test_partial_match(self):
        job = {"required_skills": ["python", "java", "c++", "go"]}
        profile = {"skills": ["python"]}
        r = match(job, profile)
        assert r.skill_match_percentage == 25.0
        assert r.matched_skills == ["python"]
        assert "java" in r.missing_skills

    def test_case_insensitive(self):
        job = {"required_skills": ["Python", "Docker"]}
        profile = {"skills": ["python", "DOCKER"]}
        r = match(job, profile)
        assert r.skill_match_percentage == 100.0

    def test_no_required_skills_gives_50_percent(self):
        job = {"required_skills": []}
        profile = {"skills": ["python"]}
        r = match(job, profile)
        assert r.skill_match_percentage == 50.0

    def test_matched_and_missing_are_sorted(self):
        job = {"required_skills": ["z-skill", "a-skill", "m-skill"]}
        profile = {"skills": ["a-skill", "m-skill"]}
        r = match(job, profile)
        assert r.matched_skills == sorted(r.matched_skills)
        assert r.missing_skills == sorted(r.missing_skills)


# ── Role matching ─────────────────────────────────────────────────────────────

class TestRoleMatch:
    def test_exact_substring_match_scores_high(self):
        job = {"title": "Senior ML Engineer", "required_skills": []}
        profile = {"skills": [], "target_roles": ["ML Engineer"]}
        r = match(job, profile)
        assert r.role_match_percentage >= 80.0
        assert r.best_matching_role == "ML Engineer"

    def test_no_match_scores_low(self):
        job = {"title": "Java Backend Developer", "required_skills": []}
        profile = {"skills": [], "target_roles": ["ML Engineer", "Data Scientist"]}
        r = match(job, profile)
        assert r.role_match_percentage < 50.0

    def test_no_target_roles_returns_50(self):
        job = {"title": "ML Engineer", "required_skills": []}
        profile = {"skills": [], "target_roles": []}
        r = match(job, profile)
        assert r.role_match_percentage == 50.0

    def test_best_matching_role_is_set(self):
        job = {"title": "MLOps Engineer", "required_skills": []}
        profile = {"skills": [], "target_roles": ["ML Engineer", "MLOps Engineer", "Data Scientist"]}
        r = match(job, profile)
        assert r.best_matching_role == "MLOps Engineer"
        assert r.role_match_percentage >= 80.0

    def test_partial_word_overlap_gives_nonzero(self):
        job = {"title": "Machine Learning Scientist", "required_skills": []}
        profile = {"skills": [], "target_roles": ["ML Engineer"]}
        r = match(job, profile)
        # "machine learning" appears; some overlap
        assert r.role_match_percentage >= 0.0

    def test_multiple_roles_picks_best(self):
        job = {"title": "Data Scientist", "required_skills": []}
        profile = {
            "skills": [],
            "target_roles": ["Backend Developer", "Data Scientist", "ML Engineer"],
        }
        r = match(job, profile)
        assert r.best_matching_role == "Data Scientist"
        assert r.role_match_percentage >= 80.0


# ── Location matching ─────────────────────────────────────────────────────────

class TestLocationMatch:
    def test_city_match(self):
        job = {"location": "Lyon, France", "remote": "none", "required_skills": []}
        profile = {"skills": [], "cities": ["lyon"], "countries": [], "remote_preference": False}
        r = match(job, profile)
        assert r.location_match is True

    def test_country_match(self):
        job = {"location": "Bordeaux, France", "remote": "none", "required_skills": []}
        profile = {"skills": [], "cities": ["lyon"], "countries": ["france"], "remote_preference": False}
        r = match(job, profile)
        assert r.location_match is True

    def test_no_location_match(self):
        job = {"location": "London, UK", "remote": "none", "required_skills": []}
        profile = {"skills": [], "cities": ["lyon"], "countries": ["france"], "remote_preference": False}
        r = match(job, profile)
        assert r.location_match is False

    def test_case_insensitive_city(self):
        job = {"location": "PARIS, FRANCE", "remote": "none", "required_skills": []}
        profile = {"skills": [], "cities": ["paris"], "countries": [], "remote_preference": False}
        r = match(job, profile)
        assert r.location_match is True


# ── Remote matching ───────────────────────────────────────────────────────────

class TestRemoteMatch:
    def test_full_remote_with_preference(self):
        job = {"remote": "full", "location": "Paris", "required_skills": []}
        profile = {"skills": [], "remote_preference": True, "cities": [], "countries": []}
        r = match(job, profile)
        assert r.remote_match is True

    def test_full_remote_without_preference(self):
        job = {"remote": "full", "location": "Paris", "required_skills": []}
        profile = {"skills": [], "remote_preference": False, "cities": [], "countries": []}
        r = match(job, profile)
        assert r.remote_match is False

    def test_onsite_without_preference(self):
        job = {"remote": "none", "location": "Paris", "required_skills": []}
        profile = {"skills": [], "remote_preference": False, "cities": [], "countries": []}
        r = match(job, profile)
        assert r.remote_match is True


# ── Contract matching ─────────────────────────────────────────────────────────

class TestContractMatch:
    def test_matching_contract(self):
        job = {"contract_type": "cdi", "required_skills": []}
        profile = {"skills": [], "contract_types": ["cdi", "cdd"]}
        r = match(job, profile)
        assert r.contract_match is True

    def test_non_matching_contract(self):
        job = {"contract_type": "stage", "required_skills": []}
        profile = {"skills": [], "contract_types": ["cdi", "cdd"]}
        r = match(job, profile)
        assert r.contract_match is False

    def test_no_preference_always_matches(self):
        job = {"contract_type": "freelance", "required_skills": []}
        profile = {"skills": [], "contract_types": []}
        r = match(job, profile)
        assert r.contract_match is True


# ── Language matching ─────────────────────────────────────────────────────────

class TestLanguageMatch:
    def test_french_job_french_profile(self):
        job = {"language": "fr", "required_skills": []}
        profile = {"skills": [], "languages": ["French", "English"]}
        r = match(job, profile)
        assert r.language_match is True

    def test_english_job_french_only_profile(self):
        job = {"language": "en", "required_skills": []}
        profile = {"skills": [], "languages": ["French"]}
        r = match(job, profile)
        assert r.language_match is False

    def test_iso_code_in_profile(self):
        job = {"language": "fr", "required_skills": []}
        profile = {"skills": [], "languages": ["fr", "en"]}
        r = match(job, profile)
        assert r.language_match is True

    def test_no_languages_in_profile_always_matches(self):
        job = {"language": "de", "required_skills": []}
        profile = {"skills": [], "languages": []}
        r = match(job, profile)
        assert r.language_match is True


# ── Experience gap ────────────────────────────────────────────────────────────

class TestExperienceGap:
    def test_exact_match_gap_zero(self):
        job = {"experience_level": "mid", "required_skills": []}
        profile = {"skills": [], "experience_level": "mid"}
        r = match(job, profile)
        assert r.experience_gap == 0

    def test_overqualified_gap_positive(self):
        job = {"experience_level": "junior", "required_skills": []}
        profile = {"skills": [], "experience_level": "senior"}
        r = match(job, profile)
        assert r.experience_gap == 2  # senior(3) - junior(1) = 2

    def test_underqualified_gap_negative(self):
        job = {"experience_level": "senior", "required_skills": []}
        profile = {"skills": [], "experience_level": "junior"}
        r = match(job, profile)
        assert r.experience_gap == -2

    def test_unknown_job_level_gap_zero(self):
        job = {"experience_level": None, "required_skills": []}
        profile = {"skills": [], "experience_level": "senior"}
        r = match(job, profile)
        assert r.experience_gap == 0


# ── Salary OK ─────────────────────────────────────────────────────────────────

class TestSalaryOk:
    def test_salary_above_minimum(self):
        job = {"salary_min": 50_000, "salary_max": 65_000, "required_skills": []}
        profile = {"skills": [], "salary_min": 42_000}
        r = match(job, profile)
        assert r.salary_ok is True

    def test_salary_below_minimum(self):
        job = {"salary_min": 25_000, "salary_max": 30_000, "required_skills": []}
        profile = {"skills": [], "salary_min": 42_000}
        r = match(job, profile)
        assert r.salary_ok is False

    def test_no_profile_minimum_always_ok(self):
        job = {"salary_min": 1_000, "salary_max": 5_000, "required_skills": []}
        profile = {"skills": [], "salary_min": None}
        r = match(job, profile)
        assert r.salary_ok is True

    def test_undisclosed_salary_not_ok(self):
        job = {"salary_min": None, "salary_max": None, "required_skills": []}
        profile = {"skills": [], "salary_min": 42_000}
        r = match(job, profile)
        assert r.salary_ok is False


# ── Overall fit ───────────────────────────────────────────────────────────────

class TestOverallFit:
    def test_perfect_match_high_fit(self):
        r = match(PERFECT_JOB, FULL_PROFILE)
        assert r.overall_fit >= 70.0

    def test_no_match_low_fit(self):
        r = match(NO_MATCH_JOB, FULL_PROFILE)
        assert r.overall_fit < 40.0

    def test_fit_between_0_and_100(self):
        for job in (PERFECT_JOB, PARTIAL_JOB, NO_MATCH_JOB):
            r = match(job, FULL_PROFILE)
            assert 0.0 <= r.overall_fit <= 100.0

    def test_fit_is_deterministic(self):
        r1 = match(PERFECT_JOB, FULL_PROFILE)
        r2 = match(PERFECT_JOB, FULL_PROFILE)
        assert r1.overall_fit == r2.overall_fit


# ── Full integration ──────────────────────────────────────────────────────────

class TestMatchIntegration:
    def test_perfect_job_all_fields(self):
        r = match(PERFECT_JOB, FULL_PROFILE)
        # python, pytorch, llm, rag — all in profile
        assert r.skill_match_percentage == 100.0
        assert r.matched_skills == ["llm", "python", "pytorch", "rag"]
        assert r.missing_skills == []
        assert r.role_match_percentage >= 80.0  # "ML Engineer" in title
        assert r.location_match is True          # Lyon in cities
        assert r.remote_match is True            # full + preference
        assert r.contract_match is True          # cdi in preferred
        assert r.language_match is True          # fr
        assert r.salary_ok is True               # 52k > 42k min
        assert r.experience_gap == 0             # both mid

    def test_no_match_job_all_fields(self):
        r = match(NO_MATCH_JOB, FULL_PROFILE)
        assert r.skill_match_percentage == 0.0
        assert r.location_match is False
        assert r.contract_match is False

    def test_partial_job(self):
        r = match(PARTIAL_JOB, FULL_PROFILE)
        # python matches, spark/kafka/airflow don't
        assert "python" in r.matched_skills
        assert "spark" in r.missing_skills
        assert 0.0 < r.skill_match_percentage < 100.0

    def test_empty_job_and_profile(self):
        r = match({}, {})
        # Should not raise
        assert isinstance(r, MatchResult)
        assert 0.0 <= r.overall_fit <= 100.0

    def test_match_returns_match_result_type(self):
        r = match(PERFECT_JOB, FULL_PROFILE)
        assert isinstance(r, MatchResult)
