"""
Unit tests for the deterministic scoring engine.
No I/O, no mocking — score_job is a pure function.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.scoring_service import ScoreBreakdown, score_job


# ── Fixtures ──────────────────────────────────────────────────────────────────

FULL_PROFILE = {
    "skills": ["python", "fastapi", "docker", "llm", "rag", "kubernetes"],
    "experience_level": "mid",
    "salary_min": 40_000,
    "salary_target": 55_000,
    "remote_preference": True,
    "countries": ["france"],
    "cities": ["lyon", "paris"],
    "contract_types": ["cdi", "cdd"],
}

FULL_JOB = {
    "title": "ML Engineer",
    "required_skills": ["python", "fastapi", "docker", "llm"],
    "experience_level": "mid",
    "location": "Lyon, France",
    "remote": "full",
    "contract_type": "cdi",
    "salary_min": 45_000,
    "salary_max": 60_000,
    "company_quality_score": 80,
    "published_at": datetime.now(timezone.utc).isoformat(),
}


# ── ScoreBreakdown dataclass ───────────────────────────────────────────────────

class TestScoreBreakdown:
    def test_total_is_sum_of_all_dimensions(self):
        bd = ScoreBreakdown(
            skill_match=20,
            experience_match=15,
            location_score=10,
            salary_score=12,
            contract_score=8,
            company_score=4,
            freshness_score=3,
        )
        assert bd.total == 72

    def test_total_zero_for_empty_breakdown(self):
        assert ScoreBreakdown().total == 0

    def test_needs_review_when_high_total_low_skill(self):
        bd = ScoreBreakdown(
            skill_match=5,        # < 10 triggers review
            experience_match=20,
            location_score=15,
            salary_score=15,
            contract_score=10,
            company_score=5,
            freshness_score=5,
        )
        assert bd.total == 75     # >= 60
        assert bd.needs_review is True

    def test_needs_review_false_when_skill_match_high(self):
        bd = ScoreBreakdown(skill_match=20, experience_match=20)
        assert bd.needs_review is False

    def test_needs_review_false_when_total_below_threshold(self):
        bd = ScoreBreakdown(skill_match=5, experience_match=10)
        assert bd.total == 15    # < 60
        assert bd.needs_review is False


# ── Skill match ───────────────────────────────────────────────────────────────

class TestSkillMatch:
    def test_perfect_match_scores_30(self):
        job = {"required_skills": ["python", "docker"]}
        profile = {"skills": ["python", "docker", "kubernetes"]}
        bd, _ = score_job(job, profile)
        assert bd.skill_match == 30

    def test_no_match_scores_zero(self):
        job = {"required_skills": ["cobol", "fortran"]}
        profile = {"skills": ["python", "docker"]}
        bd, _ = score_job(job, profile)
        assert bd.skill_match == 0

    def test_partial_match_is_proportional(self):
        job = {"required_skills": ["python", "java", "c++", "cobol"]}
        profile = {"skills": ["python"]}
        bd, _ = score_job(job, profile)
        assert bd.skill_match == round(1 / 4 * 30)

    def test_case_insensitive_matching(self):
        job = {"required_skills": ["Python", "Docker"]}
        profile = {"skills": ["python", "DOCKER"]}
        bd, _ = score_job(job, profile)
        assert bd.skill_match == 30

    def test_empty_required_skills_gives_half_credit(self):
        job = {"required_skills": []}
        profile = {"skills": ["python"]}
        bd, _ = score_job(job, profile)
        assert bd.skill_match == 15


# ── Experience match ──────────────────────────────────────────────────────────

class TestExperienceMatch:
    def test_exact_level_match_scores_20(self):
        job = {"experience_level": "mid"}
        profile = {"experience_level": "mid"}
        bd, _ = score_job(job, profile)
        assert bd.experience_match == 20

    def test_one_level_off_scores_10(self):
        job = {"experience_level": "senior"}
        profile = {"experience_level": "mid"}
        bd, _ = score_job(job, profile)
        assert bd.experience_match == 10

    def test_two_levels_off_scores_zero(self):
        job = {"experience_level": "senior"}
        profile = {"experience_level": "junior"}
        bd, _ = score_job(job, profile)
        assert bd.experience_match == 0

    def test_unknown_job_level_gives_half_credit(self):
        job = {"experience_level": None}
        profile = {"experience_level": "mid"}
        bd, _ = score_job(job, profile)
        assert bd.experience_match == 10


# ── Location score ────────────────────────────────────────────────────────────

class TestLocationScore:
    def test_full_remote_with_preference_scores_15(self):
        job = {"remote": "full", "location": "Paris"}
        profile = {"remote_preference": True, "cities": [], "countries": []}
        bd, _ = score_job(job, profile)
        assert bd.location_score == 15

    def test_city_match_scores_15(self):
        job = {"remote": "none", "location": "Lyon, France"}
        profile = {"remote_preference": False, "cities": ["lyon"], "countries": []}
        bd, _ = score_job(job, profile)
        assert bd.location_score == 15

    def test_country_match_scores_8(self):
        job = {"remote": "none", "location": "Bordeaux, France"}
        profile = {"remote_preference": False, "cities": ["lyon"], "countries": ["france"]}
        bd, _ = score_job(job, profile)
        assert bd.location_score == 8

    def test_hybrid_remote_scores_6(self):
        job = {"remote": "hybrid", "location": "Tokyo"}
        profile = {"remote_preference": False, "cities": [], "countries": []}
        bd, _ = score_job(job, profile)
        assert bd.location_score == 6

    def test_no_match_scores_zero(self):
        job = {"remote": "none", "location": "London, UK"}
        profile = {"remote_preference": False, "cities": ["lyon"], "countries": ["france"]}
        bd, _ = score_job(job, profile)
        assert bd.location_score == 0


# ── Salary score ──────────────────────────────────────────────────────────────

class TestSalaryScore:
    def test_salary_above_target_scores_15(self):
        job = {"salary_min": 60_000, "salary_max": 70_000}
        profile = {"salary_min": 40_000, "salary_target": 55_000}
        bd, _ = score_job(job, profile)
        assert bd.salary_score == 15

    def test_salary_at_minimum_scores_10(self):
        job = {"salary_min": 42_000, "salary_max": 44_000}
        profile = {"salary_min": 40_000, "salary_target": None}
        bd, _ = score_job(job, profile)
        assert bd.salary_score == 10

    def test_salary_below_minimum_scores_zero(self):
        job = {"salary_min": 25_000, "salary_max": 30_000}
        profile = {"salary_min": 40_000, "salary_target": 55_000}
        bd, _ = score_job(job, profile)
        assert bd.salary_score == 0

    def test_missing_salary_gives_half_credit(self):
        job = {"salary_min": None, "salary_max": None}
        profile = {"salary_min": 40_000, "salary_target": 55_000}
        bd, _ = score_job(job, profile)
        assert bd.salary_score == 7


# ── Contract score ────────────────────────────────────────────────────────────

class TestContractScore:
    def test_matching_contract_scores_10(self):
        job = {"contract_type": "cdi"}
        profile = {"contract_types": ["cdi", "cdd"]}
        bd, _ = score_job(job, profile)
        assert bd.contract_score == 10

    def test_non_matching_contract_scores_zero(self):
        job = {"contract_type": "stage"}
        profile = {"contract_types": ["cdi", "cdd"]}
        bd, _ = score_job(job, profile)
        assert bd.contract_score == 0

    def test_no_preference_gives_half_credit(self):
        job = {"contract_type": "cdi"}
        profile = {"contract_types": []}
        bd, _ = score_job(job, profile)
        assert bd.contract_score == 5


# ── Freshness score ───────────────────────────────────────────────────────────

class TestFreshnessScore:
    def test_published_today_scores_5(self):
        job = {"published_at": datetime.now(timezone.utc).isoformat()}
        bd, _ = score_job(job, {})
        assert bd.freshness_score == 5

    def test_published_3_days_ago_scores_3(self):
        dt = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        bd, _ = score_job({"published_at": dt}, {})
        assert bd.freshness_score == 3

    def test_published_10_days_ago_scores_1(self):
        dt = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        bd, _ = score_job({"published_at": dt}, {})
        assert bd.freshness_score == 1

    def test_published_30_days_ago_scores_0(self):
        dt = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        bd, _ = score_job({"published_at": dt}, {})
        assert bd.freshness_score == 0

    def test_missing_published_at_scores_2(self):
        bd, _ = score_job({"published_at": None}, {})
        assert bd.freshness_score == 2


# ── Extraction confidence ─────────────────────────────────────────────────────

class TestExtractionConfidence:
    def test_all_fields_present_gives_100(self):
        job = {
            "required_skills": ["python"],
            "experience_level": "mid",
            "salary_min": 40_000,
            "location": "Lyon",
            "contract_type": "cdi",
        }
        _, confidence = score_job(job, {})
        assert confidence == 100

    def test_no_fields_gives_0(self):
        _, confidence = score_job({}, {})
        assert confidence == 0

    def test_partial_fields_proportional(self):
        job = {"required_skills": ["python"], "location": "Lyon"}  # 2 of 5
        _, confidence = score_job(job, {})
        assert confidence == 40


# ── Full integration ──────────────────────────────────────────────────────────

class TestScoreJobIntegration:
    def test_perfect_candidate_scores_near_max(self):
        bd, conf = score_job(FULL_JOB, FULL_PROFILE)
        # skill_match: 4/4 = 30, experience: 20, location: 15 (full remote + pref),
        # salary: 15 (mid above target), contract: 10, company: 4, freshness: 5
        assert bd.total >= 90
        assert conf == 100

    def test_total_never_exceeds_100(self):
        bd, _ = score_job(FULL_JOB, FULL_PROFILE)
        assert bd.total <= 100

    def test_empty_job_and_profile_scores_low(self):
        bd, conf = score_job({}, {})
        # Gets half-credit on unknowns: skill=15, exp=10, salary=7, contract=5, freshness=2
        assert bd.total > 0
        assert bd.total < 50
        assert conf == 0

    def test_score_is_deterministic(self):
        """Same inputs must always produce the same output."""
        bd1, c1 = score_job(FULL_JOB, FULL_PROFILE)
        bd2, c2 = score_job(FULL_JOB, FULL_PROFILE)
        assert bd1.total == bd2.total
        assert c1 == c2
