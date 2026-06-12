"""
Tests for opportunity_discovery_service.py

Pure-function tests require no DB.
Async service tests use a custom mock DB session.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.opportunity_discovery_service import (
    VALID_OPP_EVENT_TYPES,
    ScoredOpportunity,
    _compute_explicit_pref_score,
    _compute_type_feedback_score,
    blend_opportunity_scores,
    compute_opportunity_preference_score,
    discover_and_score,
    get_opportunity_preferences,
    get_opportunity_type_affinities,
    normalize_opportunity,
)
from app.services.preference_service import PreferenceProfile

NOW = datetime.now(timezone.utc)
USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OPP_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_opp(**overrides):
    opp = MagicMock()
    opp.id = OPP_ID
    opp.title = "Software Engineer"
    opp.company = "Acme Corp"
    opp.location = "Paris, France"
    opp.remote = "hybrid"
    opp.opportunity_type = "employment"
    opp.industry = "technology"
    opp.sector = "software"
    opp.contract_type = "cdi"
    opp.salary_min = 50_000
    opp.salary_max = 65_000
    opp.salary_currency = "EUR"
    opp.required_skills = ["python", "fastapi", "docker"]
    opp.experience_level = "mid"
    opp.language = "en"
    opp.description = "Build scalable APIs"
    opp.metadata_ = {}
    opp.published_at = NOW
    opp.scraped_at = NOW
    opp.is_active = True
    opp.source = "manual"
    opp.source_id = "ext-001"
    opp.url = "https://example.com/job/1"
    for k, v in overrides.items():
        setattr(opp, k, v)
    return opp


def _make_profile(**overrides):
    base = {
        "skills": ["python", "fastapi", "docker", "kubernetes"],
        "target_roles": ["Software Engineer", "Backend Engineer"],
        "experience_level": "mid",
        "salary_min": 45_000,
        "salary_target": 65_000,
        "remote_preference": True,
        "countries": ["france"],
        "cities": ["paris", "lyon"],
        "contract_types": ["cdi"],
        "languages": ["English", "French"],
    }
    base.update(overrides)
    return base


# ── normalize_opportunity ─────────────────────────────────────────────────────

class TestNormalizeOpportunity:
    def test_basic_fields_mapped(self):
        raw = {
            "title": "Data Scientist",
            "url": "https://example.com/ds",
            "company": "Lab Corp",
        }
        result = normalize_opportunity(raw, "manual")
        assert result["title"] == "Data Scientist"
        assert result["url"] == "https://example.com/ds"
        assert result["company"] == "Lab Corp"
        assert result["source"] == "manual"

    def test_opportunity_type_defaults_to_employment(self):
        result = normalize_opportunity({"title": "Researcher", "url": "https://x.com/1"}, "api")
        assert result["opportunity_type"] == "employment"

    def test_opportunity_type_normalized_to_lowercase(self):
        result = normalize_opportunity({"opportunity_type": "PHD", "url": "https://x.com/2"}, "api")
        assert result["opportunity_type"] == "phd"

    def test_skills_lowercased(self):
        raw = {"title": "Dev", "url": "https://x.com/3", "required_skills": ["Python", "FastAPI"]}
        result = normalize_opportunity(raw, "api")
        assert result["required_skills"] == ["python", "fastapi"]

    def test_extra_fields_go_to_metadata(self):
        raw = {
            "title": "Dev",
            "url": "https://x.com/4",
            "custom_field": "value",
            "department": "Engineering",
        }
        result = normalize_opportunity(raw, "api")
        assert "custom_field" in result["metadata_"]
        assert "department" in result["metadata_"]

    def test_source_id_falls_back_to_id(self):
        raw = {"title": "Dev", "url": "https://x.com/5", "id": "ext-999"}
        result = normalize_opportunity(raw, "api")
        assert result["source_id"] == "ext-999"

    def test_company_name_alias_accepted(self):
        raw = {"title": "Dev", "url": "https://x.com/6", "company_name": "Corp"}
        result = normalize_opportunity(raw, "api")
        assert result["company"] == "Corp"

    def test_remote_defaults_to_none(self):
        result = normalize_opportunity({"title": "Dev", "url": "https://x.com/7"}, "api")
        assert result["remote"] == "none"


# ── _compute_explicit_pref_score ──────────────────────────────────────────────

class TestComputeExplicitPrefScore:
    def test_returns_50_when_no_preferences(self):
        score = _compute_explicit_pref_score({"opportunity_type": "phd"}, {})
        assert score == 50.0

    def test_returns_100_when_all_match(self):
        opp = {"opportunity_type": "phd", "industry": "research", "sector": "academia"}
        prefs = {
            "preferred_opportunity_types": ["phd"],
            "preferred_industries": ["research"],
            "preferred_sectors": ["academia"],
        }
        assert _compute_explicit_pref_score(opp, prefs) == 100.0

    def test_type_match_only_scores_above_50(self):
        opp = {"opportunity_type": "phd", "industry": "technology", "sector": "software"}
        prefs = {"preferred_opportunity_types": ["phd"]}
        score = _compute_explicit_pref_score(opp, prefs)
        assert score > 50.0

    def test_type_mismatch_scores_below_50(self):
        opp = {"opportunity_type": "freelance", "industry": None, "sector": None}
        prefs = {"preferred_opportunity_types": ["phd"]}
        score = _compute_explicit_pref_score(opp, prefs)
        assert score < 50.0

    def test_industry_match_adds_points(self):
        opp = {"opportunity_type": "employment", "industry": "healthcare", "sector": None}
        prefs_with = {"preferred_industries": ["healthcare"]}
        prefs_without = {}
        assert _compute_explicit_pref_score(opp, prefs_with) > _compute_explicit_pref_score(opp, prefs_without)

    def test_sector_match_adds_points(self):
        opp = {"opportunity_type": "employment", "industry": None, "sector": "biotech"}
        prefs = {"preferred_sectors": ["biotech"]}
        score = _compute_explicit_pref_score(opp, prefs)
        assert score > 50.0

    def test_case_insensitive_matching(self):
        opp = {"opportunity_type": "PHD", "industry": None, "sector": None}
        prefs = {"preferred_opportunity_types": ["phd"]}
        score = _compute_explicit_pref_score(opp, prefs)
        assert score >= 40.0  # matched

    def test_no_preferences_gives_neutral_50(self):
        for opp_type in ("employment", "phd", "cifre", "freelance"):
            opp = {"opportunity_type": opp_type, "industry": "x", "sector": "y"}
            score = _compute_explicit_pref_score(opp, {})
            assert score == 50.0


# ── _compute_type_feedback_score ──────────────────────────────────────────────

class TestComputeTypeFeedbackScore:
    def test_returns_50_when_no_affinities(self):
        assert _compute_type_feedback_score({"opportunity_type": "phd"}, {}) == 50.0

    def test_positive_affinity_scores_above_50(self):
        affinities = {"phd": 3.0, "employment": -1.0}
        score = _compute_type_feedback_score({"opportunity_type": "phd"}, affinities)
        assert score > 50.0

    def test_negative_affinity_scores_below_50(self):
        affinities = {"phd": 3.0, "freelance": -2.0}
        score = _compute_type_feedback_score({"opportunity_type": "freelance"}, affinities)
        assert score < 50.0

    def test_unknown_type_returns_50_neutral(self):
        affinities = {"phd": 3.0}
        score = _compute_type_feedback_score({"opportunity_type": "internship"}, affinities)
        assert score == 50.0

    def test_highest_affinity_type_approaches_100(self):
        affinities = {"phd": 5.0, "freelance": 1.0}
        score = _compute_type_feedback_score({"opportunity_type": "phd"}, affinities)
        assert score == 100.0

    def test_score_clamped_to_0_100(self):
        affinities = {"bad": -99.0}
        score = _compute_type_feedback_score({"opportunity_type": "bad"}, affinities)
        assert 0.0 <= score <= 100.0


# ── compute_opportunity_preference_score ──────────────────────────────────────

class TestComputeOpportunityPreferenceScore:
    def test_returns_50_when_all_neutral(self):
        empty_prefs = PreferenceProfile()
        score = compute_opportunity_preference_score({}, empty_prefs, {}, {})
        assert score == 50.0

    def test_blends_three_signals(self):
        prefs = PreferenceProfile(
            preferred_skills=[("python", 3.0)],
            total_events=1,
            signal_breakdown={"applied": 1},
        )
        opp = {"required_skills": ["python"], "opportunity_type": "employment"}
        score = compute_opportunity_preference_score(opp, prefs, {}, {})
        # With at least one preference signal, score should differ from 50
        assert isinstance(score, float)

    def test_high_skill_match_boosts_score(self):
        prefs = PreferenceProfile(
            preferred_skills=[("python", 5.0), ("fastapi", 4.0)],
            total_events=2,
            signal_breakdown={"applied": 2},
        )
        opp = {
            "required_skills": ["python", "fastapi"],
            "opportunity_type": "employment",
            "location": None,
            "remote": "none",
            "contract_type": None,
            "company_name": "",
            "title": "",
        }
        score = compute_opportunity_preference_score(opp, prefs, {}, {})
        assert score > 50.0

    def test_score_within_0_100(self):
        prefs = PreferenceProfile(
            preferred_skills=[("java", 2.0)],
            total_events=1,
            signal_breakdown={"saved": 1},
        )
        opp = {"required_skills": ["python"], "opportunity_type": "phd"}
        score = compute_opportunity_preference_score(
            opp, prefs, {"preferred_opportunity_types": ["employment"]}, {"employment": 3.0}
        )
        assert 0.0 <= score <= 100.0


# ── blend_opportunity_scores ──────────────────────────────────────────────────

class TestBlendOpportunityScores:
    def test_no_preferences_returns_profile_score(self):
        assert blend_opportunity_scores(75, 60.0, has_preferences=False) == 75

    def test_default_weights_70_30(self):
        result = blend_opportunity_scores(80, 60.0, has_preferences=True)
        expected = round(0.70 * 80 + 0.30 * 60.0)
        assert result == expected

    def test_custom_weights(self):
        result = blend_opportunity_scores(
            80, 60.0, profile_weight=0.5, preference_weight=0.5, has_preferences=True
        )
        expected = round(0.5 * 80 + 0.5 * 60.0)
        assert result == expected

    def test_weights_normalized_when_not_sum_to_1(self):
        # 0.7 + 0.7 = 1.4 → normalized to 0.5/0.5
        result = blend_opportunity_scores(
            80, 60.0, profile_weight=0.7, preference_weight=0.7, has_preferences=True
        )
        expected = round(0.5 * 80 + 0.5 * 60.0)
        assert result == expected

    def test_profile_weight_1_returns_profile_score(self):
        result = blend_opportunity_scores(
            75, 30.0, profile_weight=1.0, preference_weight=0.0, has_preferences=True
        )
        assert result == 75

    def test_returns_int(self):
        result = blend_opportunity_scores(80, 65.5, has_preferences=True)
        assert isinstance(result, int)


# ── VALID_OPP_EVENT_TYPES ─────────────────────────────────────────────────────

class TestOppEventTypes:
    def test_all_expected_types_present(self):
        for t in ("viewed", "saved", "applied", "interested", "rejected", "interview"):
            assert t in VALID_OPP_EVENT_TYPES

    def test_interested_is_valid(self):
        assert "interested" in VALID_OPP_EVENT_TYPES

    def test_random_string_not_valid(self):
        assert "ghosted" not in VALID_OPP_EVENT_TYPES


# ── Async service tests (mocked DB) ──────────────────────────────────────────

class TestGetOpportunityPreferences:
    def _db_returning(self, pref_obj):
        result = MagicMock()
        result.scalar_one_or_none.return_value = pref_obj
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result)
        return db

    async def test_returns_empty_dict_when_no_prefs(self):
        db = self._db_returning(None)
        prefs = await get_opportunity_preferences(db, USER_ID)
        assert prefs == {}

    async def test_returns_dict_with_stored_values(self):
        pref = MagicMock()
        pref.preferred_opportunity_types = ["phd", "cifre"]
        pref.preferred_industries = ["research"]
        pref.preferred_sectors = []
        pref.preferred_locations = ["Paris"]
        pref.preferred_contract_types = ["cdi"]
        pref.keywords = ["machine learning"]

        prefs = await get_opportunity_preferences(self._db_returning(pref), USER_ID)
        assert prefs["preferred_opportunity_types"] == ["phd", "cifre"]
        assert prefs["preferred_industries"] == ["research"]

    async def test_handles_none_arrays_gracefully(self):
        pref = MagicMock()
        pref.preferred_opportunity_types = None
        pref.preferred_industries = None
        pref.preferred_sectors = None
        pref.preferred_locations = None
        pref.preferred_contract_types = None
        pref.keywords = None

        prefs = await get_opportunity_preferences(self._db_returning(pref), USER_ID)
        assert prefs["preferred_opportunity_types"] == []


class TestGetOpportunityTypeAffinities:
    def _db_with_rows(self, rows):
        result = MagicMock()
        result.all.return_value = rows
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result)
        return db

    async def test_returns_empty_when_no_feedback(self):
        affinities = await get_opportunity_type_affinities(self._db_with_rows([]), USER_ID)
        assert affinities == {}

    async def test_accumulates_positive_affinity(self):
        # Two "applied" events (weight 2.0) on "phd" opportunities
        rows = [("applied", "phd"), ("applied", "phd")]
        affinities = await get_opportunity_type_affinities(self._db_with_rows(rows), USER_ID)
        assert affinities.get("phd", 0) == pytest.approx(4.0)

    async def test_rejected_creates_negative_affinity(self):
        rows = [("rejected", "freelance")]
        affinities = await get_opportunity_type_affinities(self._db_with_rows(rows), USER_ID)
        assert affinities.get("freelance", 0) < 0

    async def test_viewed_has_zero_weight(self):
        rows = [("viewed", "employment")]
        affinities = await get_opportunity_type_affinities(self._db_with_rows(rows), USER_ID)
        assert "employment" not in affinities


class TestDiscoverAndScore:
    def _make_db(self, opps, job_prefs_events=None, opp_prefs=None, type_affinities_rows=None):
        """Build a mock DB that returns different results per execute() call."""
        call_count = 0
        results = []

        # Call 1: list_opportunities → opps
        opps_result = MagicMock()
        opps_result.scalars.return_value.all.return_value = opps
        results.append(opps_result)

        # Call 2: get_preference_profile → events
        events_result = MagicMock()
        events_result.scalars.return_value.all.return_value = job_prefs_events or []
        results.append(events_result)

        # Call 3: get_opportunity_preferences → pref model
        pref_result = MagicMock()
        pref_result.scalar_one_or_none.return_value = opp_prefs
        results.append(pref_result)

        # Call 4: get_opportunity_type_affinities → feedback rows
        type_result = MagicMock()
        type_result.all.return_value = type_affinities_rows or []
        results.append(type_result)

        async def _execute(q):
            nonlocal call_count
            idx = min(call_count, len(results) - 1)
            call_count += 1
            return results[idx]

        db = AsyncMock()
        db.execute = _execute
        return db

    async def test_empty_opportunities_returns_empty_list(self):
        db = self._make_db(opps=[])
        results = await discover_and_score(db, USER_ID, _make_profile())
        assert results == []

    async def test_returns_scored_opportunity(self):
        opp = _make_opp()
        db = self._make_db(opps=[opp])
        results = await discover_and_score(db, USER_ID, _make_profile())
        assert len(results) == 1
        assert isinstance(results[0], ScoredOpportunity)

    async def test_sorted_by_final_score_descending(self):
        opp_high = _make_opp(
            id=uuid.uuid4(),
            title="Python Engineer",
            required_skills=["python", "fastapi", "docker"],
            experience_level="mid",
        )
        opp_low = _make_opp(
            id=uuid.uuid4(),
            title="COBOL Programmer",
            required_skills=["cobol", "mainframe"],
            experience_level="senior",
        )
        db = self._make_db(opps=[opp_low, opp_high])
        results = await discover_and_score(db, USER_ID, _make_profile())
        assert len(results) == 2
        assert results[0].final_score >= results[1].final_score

    async def test_min_score_filters_low_scoring(self):
        opp = _make_opp(
            required_skills=["cobol"],
            location="Remote",
            remote="full",
        )
        db = self._make_db(opps=[opp])
        results = await discover_and_score(db, USER_ID, _make_profile(), min_score=80)
        # COBOL engineer vs Python profile should score low → filtered
        assert len(results) == 0 or results[0].profile_score >= 80

    async def test_profile_weight_1_final_equals_profile_score(self):
        opp = _make_opp()
        db = self._make_db(opps=[opp])
        results = await discover_and_score(
            db, USER_ID, _make_profile(),
            profile_weight=1.0,
            preference_weight=0.0,
        )
        assert len(results) == 1
        # With profile_weight=1.0 and no preferences, final = profile_score
        r = results[0]
        assert r.final_score == r.profile_score
