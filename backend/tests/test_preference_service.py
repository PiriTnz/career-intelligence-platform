"""
Unit tests for the preference service.

Pure-function tests require no DB or mocks.
Async tests for get_preference_profile mock the DB session.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.preference_service import (
    EVENT_WEIGHTS,
    VALID_EVENT_TYPES,
    PreferenceProfile,
    _extract_family,
    _word_overlap,
    blend_scores,
    compute_preference_score,
    get_preference_profile,
)


# ── _extract_family() ─────────────────────────────────────────────────────────

class TestExtractFamily:
    def test_basic_title(self):
        assert _extract_family("ML Engineer") == "ml engineer"

    def test_strips_senior_prefix(self):
        result = _extract_family("Senior ML Engineer")
        assert "senior" not in result
        assert "ml engineer" in result

    def test_strips_junior_prefix(self):
        result = _extract_family("Junior Data Scientist")
        assert "junior" not in result

    def test_separator_truncates(self):
        result = _extract_family("ML Engineer — Paris, France")
        assert "paris" not in result
        assert "ml engineer" in result

    def test_paren_truncates(self):
        result = _extract_family("Data Scientist (NLP) Full Remote")
        assert "nlp" not in result

    def test_handles_none(self):
        assert _extract_family(None) == ""

    def test_handles_empty_string(self):
        assert _extract_family("") == ""

    def test_stage_prefix_stripped(self):
        result = _extract_family("Stage Data Scientist 6 mois")
        assert "stage" not in result

    def test_max_three_words(self):
        result = _extract_family("Software Backend API Developer Engineer Lead")
        assert len(result.split()) <= 3

    def test_lowercase_output(self):
        result = _extract_family("LLM Research Engineer")
        assert result == result.lower()


# ── _word_overlap() ───────────────────────────────────────────────────────────

class TestWordOverlap:
    def test_identical_strings(self):
        assert _word_overlap("ml engineer", "ml engineer") == 1.0

    def test_no_overlap(self):
        assert _word_overlap("ml engineer", "java developer") == 0.0

    def test_partial_overlap(self):
        # "ml engineer" ∩ "data engineer" = {"engineer"}
        # union = {"ml", "engineer", "data"} → 1/3
        score = _word_overlap("ml engineer", "data engineer")
        assert 0 < score < 1

    def test_empty_string(self):
        assert _word_overlap("", "ml engineer") == 0.0

    def test_both_empty(self):
        assert _word_overlap("", "") == 0.0


# ── EVENT_WEIGHTS / VALID_EVENT_TYPES ─────────────────────────────────────────

class TestConstants:
    def test_all_event_types_defined(self):
        for et in ("viewed", "saved", "applied", "interview", "rejected"):
            assert et in EVENT_WEIGHTS

    def test_all_valid_event_types_present(self):
        assert VALID_EVENT_TYPES == frozenset(EVENT_WEIGHTS)

    def test_weight_ordering(self):
        assert EVENT_WEIGHTS["interview"] > EVENT_WEIGHTS["applied"]
        assert EVENT_WEIGHTS["applied"] > EVENT_WEIGHTS["saved"]
        assert EVENT_WEIGHTS["saved"] > EVENT_WEIGHTS["viewed"]
        assert EVENT_WEIGHTS["viewed"] == 0.0
        assert EVENT_WEIGHTS["rejected"] < 0


# ── PreferenceProfile dataclass ───────────────────────────────────────────────

class TestPreferenceProfile:
    def test_defaults_empty(self):
        p = PreferenceProfile()
        assert p.preferred_skills == []
        assert p.total_events == 0
        assert p.has_preferences is False

    def test_has_preferences_true_when_skills_present(self):
        p = PreferenceProfile(preferred_skills=[("python", 2.0)])
        assert p.has_preferences is True

    def test_has_preferences_true_when_any_category_present(self):
        for field_name in ("preferred_locations", "preferred_companies",
                           "preferred_contract_types", "preferred_job_families"):
            p = PreferenceProfile(**{field_name: [("x", 1.0)]})
            assert p.has_preferences is True

    def test_has_preferences_false_with_no_data(self):
        p = PreferenceProfile(total_events=5, signal_breakdown={"viewed": 5})
        assert p.has_preferences is False


# ── blend_scores() ────────────────────────────────────────────────────────────

class TestBlendScores:
    def test_no_preferences_returns_profile_score(self):
        assert blend_scores(75, 80.0, has_preferences=False) == 75

    def test_with_preferences_blends(self):
        result = blend_scores(100, 100.0, has_preferences=True)
        assert result == 100

    def test_blend_formula(self):
        # 0.70 * 60 + 0.30 * 80 = 42 + 24 = 66
        assert blend_scores(60, 80.0, has_preferences=True) == 66

    def test_blend_rounds_correctly(self):
        # 0.70 * 71 + 0.30 * 50 = 49.7 + 15 = 64.7 → 65
        assert blend_scores(71, 50.0, has_preferences=True) == 65

    def test_zero_profile_score(self):
        assert blend_scores(0, 100.0, has_preferences=True) == 30

    def test_zero_preference_score(self):
        # 0.70 * 80 + 0.30 * 0 = 56
        assert blend_scores(80, 0.0, has_preferences=True) == 56


# ── compute_preference_score() ───────────────────────────────────────────────

class TestComputePreferenceScore:
    def _prefs(self, **kwargs) -> PreferenceProfile:
        return PreferenceProfile(**kwargs)

    def test_returns_neutral_when_no_preferences(self):
        prefs = PreferenceProfile()
        score = compute_preference_score({"required_skills": ["python"]}, prefs)
        assert score == 50.0

    def test_perfect_skill_match_gives_full_skill_points(self):
        prefs = self._prefs(preferred_skills=[("python", 3.0), ("pytorch", 2.0)])
        job = {"required_skills": ["python", "pytorch"]}
        score = compute_preference_score(job, prefs)
        # skills = 40 pts max; location neutral 12.5; contract 7.5; company 5; family 5
        # skill part: both match at full weight → 40 pts
        assert score >= 40

    def test_no_skill_overlap_gives_zero_skill_points(self):
        prefs = self._prefs(preferred_skills=[("java", 2.0)])
        job = {"required_skills": ["python", "pytorch"]}
        score = compute_preference_score(job, prefs)
        assert score < 40  # no skill affinity contributes

    def test_location_match_scores_higher(self):
        prefs = self._prefs(preferred_locations=[("lyon", 3.0)])
        job_match = {"required_skills": [], "location": "lyon, france", "remote": "none"}
        job_no_match = {"required_skills": [], "location": "paris, france", "remote": "none"}
        assert compute_preference_score(job_match, prefs) > compute_preference_score(job_no_match, prefs)

    def test_remote_job_location_neutral(self):
        prefs = self._prefs(preferred_locations=[("lyon", 3.0)])
        job_remote = {"required_skills": [], "location": "paris", "remote": "full"}
        score = compute_preference_score(job_remote, prefs)
        # Should get neutral 12.5 for location, not 0
        assert score >= 12.0

    def test_contract_type_match_scores_higher(self):
        prefs = self._prefs(preferred_contract_types=[("cdi", 4.0)])
        job_cdi = {"required_skills": [], "contract_type": "cdi"}
        job_cdd = {"required_skills": [], "contract_type": "cdd"}
        assert compute_preference_score(job_cdi, prefs) > compute_preference_score(job_cdd, prefs)

    def test_company_match_scores_higher(self):
        prefs = self._prefs(preferred_companies=[("mistral ai", 3.0)])
        job_match = {"required_skills": [], "company_name": "Mistral AI"}
        job_no_match = {"required_skills": [], "company_name": "Unknown Corp"}
        assert compute_preference_score(job_match, prefs) > compute_preference_score(job_no_match, prefs)

    def test_job_family_match_scores_higher(self):
        prefs = self._prefs(preferred_job_families=[("ml engineer", 3.0)])
        job_match = {"title": "Senior ML Engineer", "required_skills": []}
        job_no_match = {"title": "Java Backend Developer", "required_skills": []}
        assert compute_preference_score(job_match, prefs) > compute_preference_score(job_no_match, prefs)

    def test_score_is_between_0_and_100(self):
        prefs = self._prefs(
            preferred_skills=[("python", 5.0)],
            preferred_locations=[("lyon", 3.0)],
            preferred_contract_types=[("cdi", 2.0)],
        )
        jobs = [
            {"required_skills": [], "location": "unknown", "contract_type": None},
            {"required_skills": ["python"], "location": "lyon, france", "contract_type": "cdi"},
            {"required_skills": ["java", "cobol"], "location": "london", "contract_type": "stage"},
        ]
        for job in jobs:
            s = compute_preference_score(job, prefs)
            assert 0.0 <= s <= 100.0, f"score {s} out of range for {job}"

    def test_score_is_deterministic(self):
        prefs = self._prefs(preferred_skills=[("python", 2.0), ("pytorch", 1.5)])
        job = {"required_skills": ["python", "pytorch"], "location": "lyon"}
        s1 = compute_preference_score(job, prefs)
        s2 = compute_preference_score(job, prefs)
        assert s1 == s2

    def test_rejected_skill_reduces_affinity(self):
        # net: python=applied(2)+viewed(0)-rejected(2)=0 → not in preferred_skills
        # So a job with only python gets zero skill affinity
        prefs = self._prefs(
            preferred_skills=[],  # net python affinity = 0, filtered out
        )
        job = {"required_skills": ["python"]}
        score = compute_preference_score(job, prefs)
        # No skill prefs → neutral 20 pts for skills
        assert score == 50.0  # all neutral

    def test_neutral_when_only_viewed_events(self):
        # viewed has weight 0 → no affinities accumulate
        prefs = PreferenceProfile(
            total_events=10,
            signal_breakdown={"viewed": 10},
            # All lists empty because viewed contributes 0
        )
        assert not prefs.has_preferences
        score = compute_preference_score({"required_skills": ["python"]}, prefs)
        assert score == 50.0


# ── get_preference_profile() (async, DB-mocked) ───────────────────────────────

class TestGetPreferenceProfile:
    def _make_event(self, outcome: str, job_id=None) -> MagicMock:
        ev = MagicMock()
        ev.outcome = outcome
        ev.job_id = job_id
        return ev

    def _make_job(self, job_id, **kwargs) -> MagicMock:
        job = MagicMock()
        job.id = job_id
        job.required_skills = kwargs.get("required_skills", [])
        job.location = kwargs.get("location")
        job.company_name = kwargs.get("company_name", "")
        job.contract_type = kwargs.get("contract_type")
        job.title = kwargs.get("title", "")
        return job

    async def test_returns_empty_profile_when_no_events(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        prefs = await get_preference_profile(db, uuid.uuid4())
        assert prefs.total_events == 0
        assert not prefs.has_preferences

    async def test_viewed_only_gives_no_preferences(self):
        job_id = uuid.uuid4()
        events = [self._make_event("viewed", job_id)]
        db = AsyncMock()
        call_count = 0

        async def _execute(q):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalars.return_value.all.return_value = events
            else:
                result.scalars.return_value = iter([])
            return result

        db.execute = _execute
        prefs = await get_preference_profile(db, uuid.uuid4())
        # viewed=0 weight → no job IDs in weighted_events → returns early
        assert not prefs.has_preferences

    async def test_applied_event_builds_skill_preferences(self):
        job_id = uuid.uuid4()
        events = [self._make_event("applied", job_id)]
        job = self._make_job(
            job_id,
            required_skills=["python", "pytorch"],
            location="Lyon, France",
            company_name="Mistral AI",
            contract_type="cdi",
            title="ML Engineer",
        )

        db = AsyncMock()
        call_count = 0

        async def _execute(q):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalars.return_value.all.return_value = events
            else:
                result.scalars.return_value = iter([job])
            return result

        db.execute = _execute
        prefs = await get_preference_profile(db, uuid.uuid4())
        assert prefs.has_preferences
        skill_names = [s for s, _ in prefs.preferred_skills]
        assert "python" in skill_names
        assert "pytorch" in skill_names

    async def test_rejected_event_reduces_affinity(self):
        job_id = uuid.uuid4()
        # Two applied events, one rejected → net +2+2-2=+2 per skill
        events = [
            self._make_event("applied", job_id),
            self._make_event("applied", job_id),
            self._make_event("rejected", job_id),
        ]
        job = self._make_job(job_id, required_skills=["java"], title="Java Dev")

        db = AsyncMock()
        call_count = 0

        async def _execute(q):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalars.return_value.all.return_value = events
            else:
                result.scalars.return_value = iter([job])
            return result

        db.execute = _execute
        prefs = await get_preference_profile(db, uuid.uuid4())
        # net java = 2+2-2 = 2 → positive → in preferred_skills
        skill_names = [s for s, _ in prefs.preferred_skills]
        assert "java" in skill_names
        aff = next(a for s, a in prefs.preferred_skills if s == "java")
        assert aff == 2.0

    async def test_fully_rejected_skill_not_in_preferences(self):
        job_id = uuid.uuid4()
        # one applied + one rejected → net 0 → filtered out
        events = [
            self._make_event("applied", job_id),
            self._make_event("rejected", job_id),
        ]
        job = self._make_job(job_id, required_skills=["cobol"], title="COBOL Dev")

        db = AsyncMock()
        call_count = 0

        async def _execute(q):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalars.return_value.all.return_value = events
            else:
                result.scalars.return_value = iter([job])
            return result

        db.execute = _execute
        prefs = await get_preference_profile(db, uuid.uuid4())
        skill_names = [s for s, _ in prefs.preferred_skills]
        assert "cobol" not in skill_names

    async def test_signal_breakdown_counts_all_events(self):
        job_id = uuid.uuid4()
        events = [
            self._make_event("applied", job_id),
            self._make_event("viewed", job_id),
            self._make_event("viewed", job_id),
            self._make_event("saved", job_id),
        ]
        db = AsyncMock()
        call_count = 0

        async def _execute(q):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalars.return_value.all.return_value = events
            else:
                result.scalars.return_value = iter([])
            return result

        db.execute = _execute
        prefs = await get_preference_profile(db, uuid.uuid4())
        assert prefs.signal_breakdown.get("applied") == 1
        assert prefs.signal_breakdown.get("viewed") == 2
        assert prefs.signal_breakdown.get("saved") == 1
        assert prefs.total_events == 4

    async def test_interview_has_highest_weight(self):
        job_id1 = uuid.uuid4()
        job_id2 = uuid.uuid4()
        events = [
            self._make_event("interview", job_id1),
            self._make_event("saved", job_id2),
        ]
        job1 = self._make_job(job_id1, required_skills=["pytorch"], title="ML")
        job2 = self._make_job(job_id2, required_skills=["pytorch"], title="ML")

        db = AsyncMock()
        call_count = 0

        async def _execute(q):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalars.return_value.all.return_value = events
            else:
                result.scalars.return_value = iter([job1, job2])
            return result

        db.execute = _execute
        prefs = await get_preference_profile(db, uuid.uuid4())
        # interview(3) + saved(1) = 4 for pytorch
        aff = next((a for s, a in prefs.preferred_skills if s == "pytorch"), None)
        assert aff == 4.0
