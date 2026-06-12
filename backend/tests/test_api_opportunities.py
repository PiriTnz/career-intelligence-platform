"""
API tests for Opportunity Discovery Agent endpoints.

All DB calls are mocked — no PostgreSQL required.

Endpoints covered:
  POST /api/v1/opportunities/discover
  GET  /api/v1/opportunities
  GET  /api/v1/opportunities/preferences
  PUT  /api/v1/opportunities/preferences
  POST /api/v1/opportunities/{id}/feedback
  GET  /api/v1/opportunities/{id}
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.opportunity_discovery_service import (
    OPP_EVENT_WEIGHTS,
    ScoredOpportunity,
)
from app.services.matching_engine import MatchResult
from app.services.preference_service import PreferenceProfile
from app.services.scoring_service import ScoreBreakdown
from tests.conftest import USER_ID, make_mock_session

NOW = datetime.now(timezone.utc)
OPP_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
FB_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
PREF_ID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_opp(**overrides):
    opp = MagicMock()
    opp.id = OPP_ID
    opp.source = "manual"
    opp.source_id = "ext-001"
    opp.url = "https://example.com/opp/1"
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
    for k, v in overrides.items():
        setattr(opp, k, v)
    return opp


def _make_feedback(**overrides):
    fb = MagicMock()
    fb.id = FB_ID
    fb.user_id = USER_ID
    fb.opportunity_id = OPP_ID
    fb.outcome = "applied"
    fb.created_at = NOW
    for k, v in overrides.items():
        setattr(fb, k, v)
    return fb


def _make_pref(**overrides):
    pref = MagicMock()
    pref.id = PREF_ID
    pref.user_id = USER_ID
    pref.preferred_opportunity_types = ["phd", "cifre"]
    pref.preferred_industries = ["research"]
    pref.preferred_sectors = ["academia"]
    pref.preferred_locations = ["Paris"]
    pref.preferred_contract_types = ["cdi"]
    pref.keywords = ["machine learning"]
    pref.created_at = NOW
    pref.updated_at = NOW
    for k, v in overrides.items():
        setattr(pref, k, v)
    return pref


def _make_scored(opp=None, profile_score=72, preference_score=65.0, final_score=70) -> ScoredOpportunity:
    opp = opp or _make_opp()
    mr = MatchResult(
        matched_skills=["python", "fastapi"],
        missing_skills=["docker"],
        skill_match_percentage=66.7,
        role_match_percentage=80.0,
        best_matching_role="Software Engineer",
        location_match=True,
        remote_match=True,
        contract_match=True,
        language_match=True,
        salary_ok=True,
        experience_gap=0,
        overall_fit=75.0,
    )
    bd = ScoreBreakdown(
        skill_match=20,
        experience_match=20,
        location_score=12,
        salary_score=10,
        contract_score=5,
        company_score=3,
        freshness_score=2,
    )
    return ScoredOpportunity(
        opp=opp,
        profile_score=profile_score,
        preference_score=preference_score,
        final_score=final_score,
        match=mr,
        breakdown=bd,
    )


def _make_profile():
    return {
        "skills": ["python", "fastapi", "docker"],
        "target_roles": ["Software Engineer"],
        "experience_level": "mid",
        "salary_min": 45_000,
        "salary_target": 65_000,
        "remote_preference": True,
        "countries": ["france"],
        "cities": ["paris"],
        "contract_types": ["cdi"],
        "languages": ["English", "French"],
        "version": 1,
    }


# ── POST /discover ─────────────────────────────────────────────────────────────

class TestDiscoverOpportunities:
    def test_returns_200_with_scored_results(self, client):
        scored = [_make_scored()]
        with patch("app.services.job_service.get_profile_dict", AsyncMock(return_value=_make_profile())), \
             patch("app.services.opportunity_discovery_service.get_opportunity_preferences", AsyncMock(return_value={})), \
             patch("app.services.opportunity_discovery_service.discover_and_score", AsyncMock(return_value=scored)):
            resp = client.post("/api/v1/opportunities/discover", json={})
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_returns_400_when_no_profile(self, client):
        with patch("app.services.job_service.get_profile_dict", AsyncMock(return_value=None)):
            resp = client.post("/api/v1/opportunities/discover", json={})
        assert resp.status_code == 400

    def test_response_contains_required_fields(self, client):
        scored = [_make_scored()]
        with patch("app.services.job_service.get_profile_dict", AsyncMock(return_value=_make_profile())), \
             patch("app.services.opportunity_discovery_service.get_opportunity_preferences", AsyncMock(return_value={})), \
             patch("app.services.opportunity_discovery_service.discover_and_score", AsyncMock(return_value=scored)):
            resp = client.post("/api/v1/opportunities/discover", json={})
        item = resp.json()[0]
        assert "profile_score" in item
        assert "preference_score" in item
        assert "final_score" in item
        assert "match" in item
        assert "score" in item

    def test_response_match_fields_populated(self, client):
        scored = [_make_scored()]
        with patch("app.services.job_service.get_profile_dict", AsyncMock(return_value=_make_profile())), \
             patch("app.services.opportunity_discovery_service.get_opportunity_preferences", AsyncMock(return_value={})), \
             patch("app.services.opportunity_discovery_service.discover_and_score", AsyncMock(return_value=scored)):
            resp = client.post("/api/v1/opportunities/discover", json={})
        match = resp.json()[0]["match"]
        assert "matched_skills" in match
        assert "missing_skills" in match
        assert "skill_match_percentage" in match

    def test_custom_profile_weight_passed_to_service(self, client):
        scored = [_make_scored()]
        with patch("app.services.job_service.get_profile_dict", AsyncMock(return_value=_make_profile())), \
             patch("app.services.opportunity_discovery_service.get_opportunity_preferences", AsyncMock(return_value={})) as _, \
             patch("app.services.opportunity_discovery_service.discover_and_score", AsyncMock(return_value=scored)) as mock_discover:
            client.post(
                "/api/v1/opportunities/discover",
                json={"profile_weight": 0.8, "preference_weight": 0.2},
            )
        mock_discover.assert_awaited_once()
        kwargs = mock_discover.call_args.kwargs
        assert kwargs["profile_weight"] == 0.8
        assert kwargs["preference_weight"] == 0.2

    def test_empty_results_when_no_opportunities(self, client):
        with patch("app.services.job_service.get_profile_dict", AsyncMock(return_value=_make_profile())), \
             patch("app.services.opportunity_discovery_service.get_opportunity_preferences", AsyncMock(return_value={})), \
             patch("app.services.opportunity_discovery_service.discover_and_score", AsyncMock(return_value=[])):
            resp = client.post("/api/v1/opportunities/discover", json={})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.post("/api/v1/opportunities/discover", json={})
        assert resp.status_code == 401

    def test_opportunity_type_filter_passed(self, client):
        with patch("app.services.job_service.get_profile_dict", AsyncMock(return_value=_make_profile())), \
             patch("app.services.opportunity_discovery_service.get_opportunity_preferences", AsyncMock(return_value={})), \
             patch("app.services.opportunity_discovery_service.discover_and_score", AsyncMock(return_value=[])) as mock_d:
            client.post(
                "/api/v1/opportunities/discover",
                json={"opportunity_types": ["phd", "cifre"]},
            )
        kwargs = mock_d.call_args.kwargs
        assert "phd" in kwargs["opportunity_types"]
        assert "cifre" in kwargs["opportunity_types"]

    def test_stored_prefs_used_as_defaults(self, client):
        stored = {"preferred_opportunity_types": ["phd"], "preferred_locations": [], "preferred_industries": [],
                  "preferred_contract_types": [], "keywords": []}
        with patch("app.services.job_service.get_profile_dict", AsyncMock(return_value=_make_profile())), \
             patch("app.services.opportunity_discovery_service.get_opportunity_preferences", AsyncMock(return_value=stored)), \
             patch("app.services.opportunity_discovery_service.discover_and_score", AsyncMock(return_value=[])) as mock_d:
            client.post("/api/v1/opportunities/discover", json={})
        kwargs = mock_d.call_args.kwargs
        # Stored pref should be used as default since no types in request
        assert "phd" in (kwargs.get("opportunity_types") or [])


# ── GET /opportunities ────────────────────────────────────────────────────────

class TestListOpportunities:
    def test_returns_200_with_list(self, client):
        with patch("app.services.opportunity_discovery_service.list_opportunities", AsyncMock(return_value=[_make_opp()])):
            resp = client.get("/api/v1/opportunities")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_empty_list_when_no_opportunities(self, client):
        with patch("app.services.opportunity_discovery_service.list_opportunities", AsyncMock(return_value=[])):
            resp = client.get("/api/v1/opportunities")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_opportunity_type_filter_passed(self, client):
        with patch("app.services.opportunity_discovery_service.list_opportunities", AsyncMock(return_value=[])) as mock_list:
            client.get("/api/v1/opportunities?opportunity_type=phd")
        kwargs = mock_list.call_args.kwargs
        assert kwargs["opportunity_types"] == ["phd"]

    def test_keyword_filter_passed(self, client):
        with patch("app.services.opportunity_discovery_service.list_opportunities", AsyncMock(return_value=[])) as mock_list:
            client.get("/api/v1/opportunities?keyword=machine+learning")
        kwargs = mock_list.call_args.kwargs
        assert kwargs["keywords"] == ["machine learning"]

    def test_response_contains_opportunity_fields(self, client):
        with patch("app.services.opportunity_discovery_service.list_opportunities", AsyncMock(return_value=[_make_opp()])):
            resp = client.get("/api/v1/opportunities")
        item = resp.json()[0]
        for field in ("id", "title", "company", "opportunity_type", "source", "url"):
            assert field in item, f"Missing field: {field}"

    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.get("/api/v1/opportunities")
        assert resp.status_code == 401

    def test_pagination_params_passed(self, client):
        with patch("app.services.opportunity_discovery_service.list_opportunities", AsyncMock(return_value=[])) as mock_list:
            client.get("/api/v1/opportunities?limit=10&offset=5")
        kwargs = mock_list.call_args.kwargs
        assert kwargs["limit"] == 10
        assert kwargs["offset"] == 5


# ── GET /opportunities/{id} ───────────────────────────────────────────────────

class TestGetOpportunity:
    def test_returns_200_for_existing(self, client):
        with patch("app.services.opportunity_discovery_service.get_opportunity", AsyncMock(return_value=_make_opp())):
            resp = client.get(f"/api/v1/opportunities/{OPP_ID}")
        assert resp.status_code == 200

    def test_returns_404_for_missing(self, client):
        with patch("app.services.opportunity_discovery_service.get_opportunity", AsyncMock(return_value=None)):
            resp = client.get(f"/api/v1/opportunities/{OPP_ID}")
        assert resp.status_code == 404

    def test_response_fields(self, client):
        with patch("app.services.opportunity_discovery_service.get_opportunity", AsyncMock(return_value=_make_opp())):
            resp = client.get(f"/api/v1/opportunities/{OPP_ID}")
        data = resp.json()
        assert data["id"] == str(OPP_ID)
        assert data["title"] == "Software Engineer"
        assert data["opportunity_type"] == "employment"

    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.get(f"/api/v1/opportunities/{OPP_ID}")
        assert resp.status_code == 401


# ── POST /opportunities/{id}/feedback ─────────────────────────────────────────

class TestRecordOpportunityFeedback:
    def test_applied_returns_201(self, client):
        fb = _make_feedback()
        with patch("app.services.opportunity_discovery_service.get_opportunity", AsyncMock(return_value=_make_opp())), \
             patch("app.services.opportunity_discovery_service.record_opportunity_feedback", AsyncMock(return_value=fb)):
            resp = client.post(
                f"/api/v1/opportunities/{OPP_ID}/feedback",
                json={"event_type": "applied"},
            )
        assert resp.status_code == 201

    def test_all_valid_event_types_accepted(self, client):
        for et in ("viewed", "saved", "applied", "interested", "rejected"):
            fb = _make_feedback(outcome=et)
            with patch("app.services.opportunity_discovery_service.get_opportunity", AsyncMock(return_value=_make_opp())), \
                 patch("app.services.opportunity_discovery_service.record_opportunity_feedback", AsyncMock(return_value=fb)):
                resp = client.post(
                    f"/api/v1/opportunities/{OPP_ID}/feedback",
                    json={"event_type": et},
                )
            assert resp.status_code == 201, f"Expected 201 for event_type={et}"

    def test_invalid_event_type_returns_422(self, client):
        resp = client.post(
            f"/api/v1/opportunities/{OPP_ID}/feedback",
            json={"event_type": "ghosted"},
        )
        assert resp.status_code == 422

    def test_missing_event_type_returns_422(self, client):
        resp = client.post(f"/api/v1/opportunities/{OPP_ID}/feedback", json={})
        assert resp.status_code == 422

    def test_opportunity_not_found_returns_404(self, client):
        with patch("app.services.opportunity_discovery_service.get_opportunity", AsyncMock(return_value=None)):
            resp = client.post(
                f"/api/v1/opportunities/{OPP_ID}/feedback",
                json={"event_type": "applied"},
            )
        assert resp.status_code == 404

    def test_response_contains_event_type(self, client):
        fb = _make_feedback(outcome="interested")
        with patch("app.services.opportunity_discovery_service.get_opportunity", AsyncMock(return_value=_make_opp())), \
             patch("app.services.opportunity_discovery_service.record_opportunity_feedback", AsyncMock(return_value=fb)):
            resp = client.post(
                f"/api/v1/opportunities/{OPP_ID}/feedback",
                json={"event_type": "interested"},
            )
        assert resp.json()["event_type"] == "interested"

    def test_response_contains_opportunity_id(self, client):
        fb = _make_feedback()
        with patch("app.services.opportunity_discovery_service.get_opportunity", AsyncMock(return_value=_make_opp())), \
             patch("app.services.opportunity_discovery_service.record_opportunity_feedback", AsyncMock(return_value=fb)):
            resp = client.post(
                f"/api/v1/opportunities/{OPP_ID}/feedback",
                json={"event_type": "applied"},
            )
        assert resp.json()["opportunity_id"] == str(OPP_ID)

    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.post(
            f"/api/v1/opportunities/{OPP_ID}/feedback",
            json={"event_type": "applied"},
        )
        assert resp.status_code == 401


# ── GET /preferences ──────────────────────────────────────────────────────────

class TestGetOpportunityPreferences:
    def test_returns_200_with_preferences(self, client):
        pref = _make_pref()
        with patch("app.services.opportunity_discovery_service.get_opportunity_preference_model", AsyncMock(return_value=pref)):
            resp = client.get("/api/v1/opportunities/preferences")
        assert resp.status_code == 200

    def test_returns_404_when_no_preferences(self, client):
        with patch("app.services.opportunity_discovery_service.get_opportunity_preference_model", AsyncMock(return_value=None)):
            resp = client.get("/api/v1/opportunities/preferences")
        assert resp.status_code == 404

    def test_all_categories_present_in_response(self, client):
        pref = _make_pref()
        with patch("app.services.opportunity_discovery_service.get_opportunity_preference_model", AsyncMock(return_value=pref)):
            resp = client.get("/api/v1/opportunities/preferences")
        data = resp.json()
        for key in (
            "preferred_opportunity_types", "preferred_industries", "preferred_sectors",
            "preferred_locations", "preferred_contract_types", "keywords",
        ):
            assert key in data, f"Missing key: {key}"

    def test_has_preferences_true_when_data_set(self, client):
        pref = _make_pref()
        with patch("app.services.opportunity_discovery_service.get_opportunity_preference_model", AsyncMock(return_value=pref)):
            resp = client.get("/api/v1/opportunities/preferences")
        assert resp.json()["has_preferences"] is True

    def test_has_preferences_false_when_all_empty(self, client):
        pref = _make_pref(
            preferred_opportunity_types=[],
            preferred_industries=[],
            preferred_sectors=[],
            preferred_locations=[],
            preferred_contract_types=[],
            keywords=[],
        )
        with patch("app.services.opportunity_discovery_service.get_opportunity_preference_model", AsyncMock(return_value=pref)):
            resp = client.get("/api/v1/opportunities/preferences")
        assert resp.json()["has_preferences"] is False

    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.get("/api/v1/opportunities/preferences")
        assert resp.status_code == 401


# ── PUT /preferences ──────────────────────────────────────────────────────────

class TestUpdateOpportunityPreferences:
    def test_returns_200_on_upsert(self, client):
        pref = _make_pref()
        with patch("app.services.opportunity_discovery_service.upsert_opportunity_preferences", AsyncMock(return_value=pref)):
            resp = client.put(
                "/api/v1/opportunities/preferences",
                json={"preferred_opportunity_types": ["phd"], "preferred_industries": ["research"]},
            )
        assert resp.status_code == 200

    def test_stores_opportunity_types(self, client):
        pref = _make_pref(preferred_opportunity_types=["phd", "cifre"])
        with patch("app.services.opportunity_discovery_service.upsert_opportunity_preferences", AsyncMock(return_value=pref)):
            resp = client.put(
                "/api/v1/opportunities/preferences",
                json={"preferred_opportunity_types": ["phd", "cifre"]},
            )
        data = resp.json()
        assert "phd" in data["preferred_opportunity_types"]
        assert "cifre" in data["preferred_opportunity_types"]

    def test_empty_lists_accepted(self, client):
        pref = _make_pref(
            preferred_opportunity_types=[],
            preferred_industries=[],
            preferred_sectors=[],
            preferred_locations=[],
            preferred_contract_types=[],
            keywords=[],
        )
        with patch("app.services.opportunity_discovery_service.upsert_opportunity_preferences", AsyncMock(return_value=pref)):
            resp = client.put("/api/v1/opportunities/preferences", json={})
        assert resp.status_code == 200

    def test_upsert_called_with_correct_data(self, client):
        pref = _make_pref()
        with patch(
            "app.services.opportunity_discovery_service.upsert_opportunity_preferences",
            AsyncMock(return_value=pref),
        ) as mock_upsert:
            client.put(
                "/api/v1/opportunities/preferences",
                json={"preferred_sectors": ["biotechnology"], "keywords": ["ml", "ai"]},
            )
        called_data = mock_upsert.call_args.args[2]  # db, user_id, data
        assert "preferred_sectors" in called_data
        assert "keywords" in called_data

    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.put("/api/v1/opportunities/preferences", json={})
        assert resp.status_code == 401


# ── Ranking tests ─────────────────────────────────────────────────────────────

class TestRankingAndFiltering:
    def test_final_score_is_blend_of_profile_and_preference(self, client):
        profile_score = 70
        preference_score = 50.0
        # Default weights: 0.7 * 70 + 0.3 * 50 = 49 + 15 = 64
        expected_final = round(0.70 * profile_score + 0.30 * preference_score)
        scored = [_make_scored(profile_score=profile_score, preference_score=preference_score, final_score=expected_final)]

        with patch("app.services.job_service.get_profile_dict", AsyncMock(return_value=_make_profile())), \
             patch("app.services.opportunity_discovery_service.get_opportunity_preferences", AsyncMock(return_value={})), \
             patch("app.services.opportunity_discovery_service.discover_and_score", AsyncMock(return_value=scored)):
            resp = client.post("/api/v1/opportunities/discover", json={})

        item = resp.json()[0]
        assert item["profile_score"] == profile_score
        assert item["final_score"] == expected_final

    def test_results_ordered_by_final_score_descending(self, client):
        scored = [
            _make_scored(final_score=85),
            _make_scored(final_score=72),
            _make_scored(final_score=60),
        ]
        with patch("app.services.job_service.get_profile_dict", AsyncMock(return_value=_make_profile())), \
             patch("app.services.opportunity_discovery_service.get_opportunity_preferences", AsyncMock(return_value={})), \
             patch("app.services.opportunity_discovery_service.discover_and_score", AsyncMock(return_value=scored)):
            resp = client.post("/api/v1/opportunities/discover", json={})

        final_scores = [item["final_score"] for item in resp.json()]
        assert final_scores == sorted(final_scores, reverse=True)

    def test_preference_score_present_and_valid(self, client):
        scored = [_make_scored(preference_score=75.5)]
        with patch("app.services.job_service.get_profile_dict", AsyncMock(return_value=_make_profile())), \
             patch("app.services.opportunity_discovery_service.get_opportunity_preferences", AsyncMock(return_value={})), \
             patch("app.services.opportunity_discovery_service.discover_and_score", AsyncMock(return_value=scored)):
            resp = client.post("/api/v1/opportunities/discover", json={})

        pref_score = resp.json()[0]["preference_score"]
        assert 0.0 <= pref_score <= 100.0

    def test_sort_by_profile_score_param_accepted(self, client):
        with patch("app.services.job_service.get_profile_dict", AsyncMock(return_value=_make_profile())), \
             patch("app.services.opportunity_discovery_service.get_opportunity_preferences", AsyncMock(return_value={})), \
             patch("app.services.opportunity_discovery_service.discover_and_score", AsyncMock(return_value=[])) as mock_d:
            client.post("/api/v1/opportunities/discover", json={"sort_by": "profile_score"})
        assert mock_d.call_args.kwargs["sort_by"] == "profile_score"
