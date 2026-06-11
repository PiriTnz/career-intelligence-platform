"""
API tests for the feedback learning agent endpoints:

  POST /api/v1/jobs/{job_id}/feedback
  GET  /api/v1/profiles/preferences
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.preference_service import PreferenceProfile
from tests.conftest import USER_ID, make_mock_session


JOB_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
EVENT_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_job():
    job = MagicMock()
    job.id = JOB_ID
    job.title = "ML Engineer"
    job.company_name = "Mistral AI"
    job.location = "Paris, France"
    job.remote = "full"
    job.contract_type = "cdi"
    job.salary_min = 55000
    job.salary_max = 70000
    job.required_skills = ["python", "pytorch"]
    job.experience_level = "mid"
    job.language = "fr"
    job.url = "https://example.com/ml-engineer"
    job.published_at = None
    return job


def _make_event(event_type: str = "applied"):
    ev = MagicMock()
    ev.id = EVENT_ID
    ev.user_id = USER_ID
    ev.job_id = JOB_ID
    ev.outcome = event_type
    ev.created_at = datetime(2026, 6, 12, 10, 0, tzinfo=timezone.utc)
    return ev


# ── POST /api/v1/jobs/{job_id}/feedback ───────────────────────────────────────

class TestRecordFeedback:
    def test_applied_event_returns_201(self, client):
        job = _make_job()
        event = _make_event("applied")

        with patch("app.services.job_service.get_job", AsyncMock(return_value=job)), \
             patch("app.api.v1.endpoints.jobs.FeedbackEvent", return_value=event):
            resp = client.post(
                f"/api/v1/jobs/{JOB_ID}/feedback",
                json={"event_type": "applied"},
            )

        assert resp.status_code == 201

    def test_response_contains_event_type(self, client):
        job = _make_job()
        event = _make_event("saved")

        with patch("app.services.job_service.get_job", AsyncMock(return_value=job)), \
             patch("app.api.v1.endpoints.jobs.FeedbackEvent", return_value=event):
            resp = client.post(
                f"/api/v1/jobs/{JOB_ID}/feedback",
                json={"event_type": "saved"},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["event_type"] == "saved"

    def test_all_valid_event_types_accepted(self, client):
        job = _make_job()
        for et in ("viewed", "saved", "applied", "interview", "rejected"):
            event = _make_event(et)
            with patch("app.services.job_service.get_job", AsyncMock(return_value=job)), \
                 patch("app.api.v1.endpoints.jobs.FeedbackEvent", return_value=event):
                resp = client.post(
                    f"/api/v1/jobs/{JOB_ID}/feedback",
                    json={"event_type": et},
                )
            assert resp.status_code == 201, f"Expected 201 for event_type={et}"

    def test_invalid_event_type_returns_422(self, client):
        resp = client.post(
            f"/api/v1/jobs/{JOB_ID}/feedback",
            json={"event_type": "ghosted"},
        )
        assert resp.status_code == 422

    def test_missing_event_type_returns_422(self, client):
        resp = client.post(
            f"/api/v1/jobs/{JOB_ID}/feedback",
            json={},
        )
        assert resp.status_code == 422

    def test_job_not_found_returns_404(self, client):
        with patch("app.services.job_service.get_job", AsyncMock(return_value=None)):
            resp = client.post(
                f"/api/v1/jobs/{JOB_ID}/feedback",
                json={"event_type": "applied"},
            )
        assert resp.status_code == 404

    def test_response_contains_job_id(self, client):
        job = _make_job()
        event = _make_event("interview")
        with patch("app.services.job_service.get_job", AsyncMock(return_value=job)), \
             patch("app.api.v1.endpoints.jobs.FeedbackEvent", return_value=event):
            resp = client.post(
                f"/api/v1/jobs/{JOB_ID}/feedback",
                json={"event_type": "interview"},
            )
        assert resp.status_code == 201
        assert resp.json()["job_id"] == str(JOB_ID)

    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.post(
            f"/api/v1/jobs/{JOB_ID}/feedback",
            json={"event_type": "applied"},
        )
        assert resp.status_code == 401


# ── GET /api/v1/profiles/preferences ─────────────────────────────────────────

class TestGetPreferences:
    def _empty_prefs(self) -> PreferenceProfile:
        return PreferenceProfile()

    def _prefs_with_data(self) -> PreferenceProfile:
        return PreferenceProfile(
            preferred_skills=[("python", 5.0), ("pytorch", 3.0)],
            preferred_locations=[("lyon", 3.0)],
            preferred_companies=[("mistral ai", 2.0)],
            preferred_contract_types=[("cdi", 5.0)],
            preferred_job_families=[("ml engineer", 3.0)],
            total_events=8,
            signal_breakdown={"applied": 3, "saved": 3, "viewed": 2},
        )

    def test_returns_200(self, client):
        with patch(
            "app.services.preference_service.get_preference_profile",
            AsyncMock(return_value=self._empty_prefs()),
        ):
            resp = client.get("/api/v1/profiles/preferences")
        assert resp.status_code == 200

    def test_empty_preferences_when_no_events(self, client):
        with patch(
            "app.services.preference_service.get_preference_profile",
            AsyncMock(return_value=self._empty_prefs()),
        ):
            resp = client.get("/api/v1/profiles/preferences")
        data = resp.json()
        assert data["preferred_skills"] == []
        assert data["total_events"] == 0
        assert data["has_preferences"] is False

    def test_preferences_populated_from_feedback(self, client):
        with patch(
            "app.services.preference_service.get_preference_profile",
            AsyncMock(return_value=self._prefs_with_data()),
        ):
            resp = client.get("/api/v1/profiles/preferences")
        data = resp.json()
        assert data["has_preferences"] is True
        assert data["total_events"] == 8

        skill_names = [s["name"] for s in data["preferred_skills"]]
        assert "python" in skill_names
        assert "pytorch" in skill_names

    def test_affinity_items_have_name_and_affinity(self, client):
        with patch(
            "app.services.preference_service.get_preference_profile",
            AsyncMock(return_value=self._prefs_with_data()),
        ):
            resp = client.get("/api/v1/profiles/preferences")
        skills = resp.json()["preferred_skills"]
        for item in skills:
            assert "name" in item
            assert "affinity" in item
            assert item["affinity"] >= 0

    def test_skills_sorted_by_affinity_descending(self, client):
        with patch(
            "app.services.preference_service.get_preference_profile",
            AsyncMock(return_value=self._prefs_with_data()),
        ):
            resp = client.get("/api/v1/profiles/preferences")
        skills = resp.json()["preferred_skills"]
        affinities = [s["affinity"] for s in skills]
        assert affinities == sorted(affinities, reverse=True)

    def test_signal_breakdown_present(self, client):
        with patch(
            "app.services.preference_service.get_preference_profile",
            AsyncMock(return_value=self._prefs_with_data()),
        ):
            resp = client.get("/api/v1/profiles/preferences")
        breakdown = resp.json()["signal_breakdown"]
        assert breakdown.get("applied") == 3
        assert breakdown.get("saved") == 3

    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.get("/api/v1/profiles/preferences")
        assert resp.status_code == 401

    def test_all_preference_categories_present(self, client):
        with patch(
            "app.services.preference_service.get_preference_profile",
            AsyncMock(return_value=self._prefs_with_data()),
        ):
            resp = client.get("/api/v1/profiles/preferences")
        data = resp.json()
        for key in ("preferred_skills", "preferred_locations", "preferred_companies",
                    "preferred_contract_types", "preferred_job_families"):
            assert key in data, f"Missing key: {key}"


# ── Recommendation integration (preference scoring wired in) ──────────────────

class TestRecommendationsWithPreferences:
    def _make_profile(self) -> dict:
        return {
            "skills": ["python", "pytorch"],
            "target_roles": ["ML Engineer"],
            "experience_level": "mid",
            "salary_min": 42000,
            "salary_target": 58000,
            "remote_preference": True,
            "countries": ["france"],
            "cities": ["paris"],
            "contract_types": ["cdi"],
            "languages": ["French", "English"],
            "version": 1,
        }

    def test_recommendations_include_preference_and_final_score(self, client):
        job = _make_job()
        empty_prefs = PreferenceProfile()

        with patch("app.services.job_service.get_profile_dict", AsyncMock(return_value=self._make_profile())), \
             patch("app.services.job_service.get_jobs_for_matching", AsyncMock(return_value=[job])), \
             patch("app.services.preference_service.get_preference_profile", AsyncMock(return_value=empty_prefs)):
            resp = client.get("/api/v1/jobs/recommendations")

        assert resp.status_code == 200
        recs = resp.json()
        assert len(recs) == 1
        rec = recs[0]
        assert "preference_score" in rec
        assert "final_score" in rec

    def test_no_preferences_final_score_equals_profile_score(self, client):
        job = _make_job()
        empty_prefs = PreferenceProfile()

        with patch("app.services.job_service.get_profile_dict", AsyncMock(return_value=self._make_profile())), \
             patch("app.services.job_service.get_jobs_for_matching", AsyncMock(return_value=[job])), \
             patch("app.services.preference_service.get_preference_profile", AsyncMock(return_value=empty_prefs)):
            resp = client.get("/api/v1/jobs/recommendations")

        rec = resp.json()[0]
        # No preferences → final_score = profile_score
        assert rec["final_score"] == rec["score"]["total"]

    def test_preference_score_is_neutral_when_no_events(self, client):
        job = _make_job()
        empty_prefs = PreferenceProfile()

        with patch("app.services.job_service.get_profile_dict", AsyncMock(return_value=self._make_profile())), \
             patch("app.services.job_service.get_jobs_for_matching", AsyncMock(return_value=[job])), \
             patch("app.services.preference_service.get_preference_profile", AsyncMock(return_value=empty_prefs)):
            resp = client.get("/api/v1/jobs/recommendations")

        rec = resp.json()[0]
        assert rec["preference_score"] == 50.0

    def test_with_preferences_final_score_is_blend(self, client):
        job = _make_job()
        prefs = PreferenceProfile(
            preferred_skills=[("python", 5.0), ("pytorch", 3.0)],
            preferred_contract_types=[("cdi", 4.0)],
            total_events=3,
            signal_breakdown={"applied": 3},
        )

        with patch("app.services.job_service.get_profile_dict", AsyncMock(return_value=self._make_profile())), \
             patch("app.services.job_service.get_jobs_for_matching", AsyncMock(return_value=[job])), \
             patch("app.services.preference_service.get_preference_profile", AsyncMock(return_value=prefs)):
            resp = client.get("/api/v1/jobs/recommendations")

        rec = resp.json()[0]
        profile_score = rec["score"]["total"]
        pref_score = rec["preference_score"]
        expected_final = round(0.70 * profile_score + 0.30 * pref_score)
        assert rec["final_score"] == expected_final
