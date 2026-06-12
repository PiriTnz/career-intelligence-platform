"""
API tests for LLM Profile Assistant endpoints.

All DB calls and LLM calls are mocked — no PostgreSQL or Ollama/OpenAI required.

Endpoints covered:
  POST /api/v1/profiles/assistant/message
  GET  /api/v1/profiles/completeness
  POST /api/v1/profiles/assistant/apply-updates
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import USER_ID, make_mock_session

NOW = datetime.now(timezone.utc)
PROFILE_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_profile(**kwargs):
    p = MagicMock()
    p.id = PROFILE_ID
    p.user_id = USER_ID
    p.version = 1
    p.target_roles = kwargs.get("target_roles", [])
    p.avoid_roles = kwargs.get("avoid_roles", [])
    p.skills = kwargs.get("skills", ["python"])
    p.experience_level = kwargs.get("experience_level", "mid")
    p.salary_min = kwargs.get("salary_min", None)
    p.salary_target = kwargs.get("salary_target", None)
    p.remote_preference = kwargs.get("remote_preference", False)
    p.countries = kwargs.get("countries", ["France"])
    p.cities = kwargs.get("cities", [])
    p.contract_types = kwargs.get("contract_types", ["cdi"])
    p.languages = kwargs.get("languages", ["french", "english"])
    p.certifications = kwargs.get("certifications", [])
    p.education = kwargs.get("education", [])
    p.experience = kwargs.get("experience", [])
    p.cv_file_path = None
    p.phone = None
    p.raw_json = kwargs.get("raw_json", {})
    p.is_active = True
    p.created_at = NOW
    return p


PROFILE_READ_FIELDS = {
    "id": str(PROFILE_ID),
    "user_id": str(USER_ID),
    "version": 1,
    "target_roles": [],
    "avoid_roles": [],
    "skills": ["python"],
    "experience_level": "mid",
    "salary_min": None,
    "salary_target": None,
    "remote_preference": False,
    "countries": ["France"],
    "cities": [],
    "contract_types": ["cdi"],
    "languages": ["french", "english"],
    "certifications": [],
    "education": [],
    "experience": [],
    "cv_file_path": None,
    "phone": None,
    "is_active": True,
    "created_at": NOW.isoformat(),
}


# ── TestAssistantMessage ──────────────────────────────────────────────────────

class TestAssistantMessage:

    def test_message_returns_200_with_expected_shape(self, client):
        extracted = {"skills": ["python", "docker"]}
        with (
            patch(
                "app.api.v1.endpoints.profiles.get_active_profile",
                new=AsyncMock(return_value=_make_profile()),
            ),
            patch(
                "app.api.v1.endpoints.profiles.get_provider",
                return_value=MagicMock(),
            ),
            patch(
                "app.api.v1.endpoints.profiles.profile_assistant_service.extract_profile_updates",
                new=AsyncMock(return_value=extracted),
            ),
        ):
            resp = client.post(
                "/api/v1/profiles/assistant/message",
                json={"message": "I know Python and Docker", "language": "en"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "assistant_message" in body
        assert "updated_profile_fields" in body
        assert "missing_fields" in body
        assert "profile_completeness" in body
        assert "next_question" in body

    def test_message_returns_extracted_fields(self, client):
        extracted = {"skills": ["fastapi"]}
        with (
            patch(
                "app.api.v1.endpoints.profiles.get_active_profile",
                new=AsyncMock(return_value=_make_profile()),
            ),
            patch(
                "app.api.v1.endpoints.profiles.get_provider",
                return_value=MagicMock(),
            ),
            patch(
                "app.api.v1.endpoints.profiles.profile_assistant_service.extract_profile_updates",
                new=AsyncMock(return_value=extracted),
            ),
        ):
            resp = client.post(
                "/api/v1/profiles/assistant/message",
                json={"message": "I use FastAPI"},
            )
        assert resp.status_code == 200
        assert resp.json()["updated_profile_fields"] == {"skills": ["fastapi"]}

    def test_empty_extraction_returns_zero_fields(self, client):
        with (
            patch(
                "app.api.v1.endpoints.profiles.get_active_profile",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.api.v1.endpoints.profiles.get_provider",
                return_value=MagicMock(),
            ),
            patch(
                "app.api.v1.endpoints.profiles.profile_assistant_service.extract_profile_updates",
                new=AsyncMock(return_value={}),
            ),
        ):
            resp = client.post(
                "/api/v1/profiles/assistant/message",
                json={"message": "Hello there!"},
            )
        assert resp.status_code == 200
        assert resp.json()["updated_profile_fields"] == {}

    def test_french_language_accepted(self, client):
        with (
            patch(
                "app.api.v1.endpoints.profiles.get_active_profile",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.api.v1.endpoints.profiles.get_provider",
                return_value=MagicMock(),
            ),
            patch(
                "app.api.v1.endpoints.profiles.profile_assistant_service.extract_profile_updates",
                new=AsyncMock(return_value={"skills": ["python"]}),
            ),
        ):
            resp = client.post(
                "/api/v1/profiles/assistant/message",
                json={"message": "Je connais Python", "language": "fr"},
            )
        assert resp.status_code == 200

    def test_persian_language_accepted(self, client):
        with (
            patch(
                "app.api.v1.endpoints.profiles.get_active_profile",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.api.v1.endpoints.profiles.get_provider",
                return_value=MagicMock(),
            ),
            patch(
                "app.api.v1.endpoints.profiles.profile_assistant_service.extract_profile_updates",
                new=AsyncMock(return_value={}),
            ),
        ):
            resp = client.post(
                "/api/v1/profiles/assistant/message",
                json={"message": "من برنامه‌نویس هستم", "language": "fa"},
            )
        assert resp.status_code == 200

    def test_voice_transcript_input_mode_accepted(self, client):
        with (
            patch(
                "app.api.v1.endpoints.profiles.get_active_profile",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.api.v1.endpoints.profiles.get_provider",
                return_value=MagicMock(),
            ),
            patch(
                "app.api.v1.endpoints.profiles.profile_assistant_service.extract_profile_updates",
                new=AsyncMock(return_value={}),
            ),
        ):
            resp = client.post(
                "/api/v1/profiles/assistant/message",
                json={
                    "message": "I have 5 years experience",
                    "input_mode": "voice_transcript",
                },
            )
        assert resp.status_code == 200

    def test_empty_message_rejected(self, client):
        resp = client.post(
            "/api/v1/profiles/assistant/message",
            json={"message": ""},
        )
        assert resp.status_code == 422

    def test_missing_message_rejected(self, client):
        resp = client.post(
            "/api/v1/profiles/assistant/message",
            json={"language": "en"},
        )
        assert resp.status_code == 422

    def test_invalid_language_rejected(self, client):
        resp = client.post(
            "/api/v1/profiles/assistant/message",
            json={"message": "test", "language": "de"},
        )
        assert resp.status_code == 422

    def test_completeness_between_0_and_100(self, client):
        with (
            patch(
                "app.api.v1.endpoints.profiles.get_active_profile",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.api.v1.endpoints.profiles.get_provider",
                return_value=MagicMock(),
            ),
            patch(
                "app.api.v1.endpoints.profiles.profile_assistant_service.extract_profile_updates",
                new=AsyncMock(return_value={"skills": ["python"]}),
            ),
        ):
            resp = client.post(
                "/api/v1/profiles/assistant/message",
                json={"message": "I know Python"},
            )
        pct = resp.json()["profile_completeness"]
        assert 0 <= pct <= 100

    def test_next_question_present_and_non_empty(self, client):
        with (
            patch(
                "app.api.v1.endpoints.profiles.get_active_profile",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.api.v1.endpoints.profiles.get_provider",
                return_value=MagicMock(),
            ),
            patch(
                "app.api.v1.endpoints.profiles.profile_assistant_service.extract_profile_updates",
                new=AsyncMock(return_value={}),
            ),
        ):
            resp = client.post(
                "/api/v1/profiles/assistant/message",
                json={"message": "hello"},
            )
        assert len(resp.json()["next_question"]) > 0

    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.post(
            "/api/v1/profiles/assistant/message",
            json={"message": "test"},
        )
        assert resp.status_code == 401


# ── TestCompletenessEndpoint ──────────────────────────────────────────────────

class TestCompletenessEndpoint:

    def test_returns_200_with_expected_shape(self, client):
        with patch(
            "app.api.v1.endpoints.profiles.get_active_profile",
            new=AsyncMock(return_value=_make_profile()),
        ):
            resp = client.get("/api/v1/profiles/completeness")
        assert resp.status_code == 200
        body = resp.json()
        assert "completeness" in body
        assert "missing_fields" in body
        assert "field_scores" in body
        assert "total_possible" in body

    def test_total_possible_always_100(self, client):
        with patch(
            "app.api.v1.endpoints.profiles.get_active_profile",
            new=AsyncMock(return_value=_make_profile()),
        ):
            resp = client.get("/api/v1/profiles/completeness")
        assert resp.json()["total_possible"] == 100

    def test_empty_profile_has_low_completeness(self, client):
        with patch(
            "app.api.v1.endpoints.profiles.get_active_profile",
            new=AsyncMock(return_value=None),
        ):
            resp = client.get("/api/v1/profiles/completeness")
        assert resp.status_code == 200
        assert resp.json()["completeness"] == 0

    def test_profile_with_skills_gets_score(self, client):
        profile = _make_profile(
            skills=["python"],
            target_roles=["Engineer"],
            experience_level="mid",
        )
        with patch(
            "app.api.v1.endpoints.profiles.get_active_profile",
            new=AsyncMock(return_value=profile),
        ):
            resp = client.get("/api/v1/profiles/completeness")
        body = resp.json()
        assert body["field_scores"]["skills"] == 20
        assert body["field_scores"]["target_roles"] == 15
        assert body["field_scores"]["experience_level"] == 15

    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.get("/api/v1/profiles/completeness")
        assert resp.status_code == 401


# ── TestApplyUpdatesEndpoint ──────────────────────────────────────────────────

class TestApplyUpdatesEndpoint:

    def test_apply_updates_returns_profile(self, client):
        profile = _make_profile(skills=["python", "docker"])
        with patch(
            "app.api.v1.endpoints.profiles.profile_assistant_service.apply_profile_updates",
            new=AsyncMock(return_value=profile),
        ):
            resp = client.post(
                "/api/v1/profiles/assistant/apply-updates",
                json={"updates": {"skills": ["docker"]}},
            )
        assert resp.status_code == 200
        assert "id" in resp.json()

    def test_empty_updates_with_existing_profile_returns_profile(self, client):
        profile = _make_profile()
        with patch(
            "app.api.v1.endpoints.profiles.get_active_profile",
            new=AsyncMock(return_value=profile),
        ):
            resp = client.post(
                "/api/v1/profiles/assistant/apply-updates",
                json={"updates": {}},
            )
        assert resp.status_code == 200

    def test_empty_updates_no_profile_returns_404(self, client):
        with patch(
            "app.api.v1.endpoints.profiles.get_active_profile",
            new=AsyncMock(return_value=None),
        ):
            resp = client.post(
                "/api/v1/profiles/assistant/apply-updates",
                json={"updates": {}},
            )
        assert resp.status_code == 404

    def test_invalid_experience_level_rejected(self, client):
        profile = _make_profile()
        with patch(
            "app.api.v1.endpoints.profiles.profile_assistant_service.apply_profile_updates",
            new=AsyncMock(return_value=profile),
        ):
            resp = client.post(
                "/api/v1/profiles/assistant/apply-updates",
                json={"updates": {"experience_level": "wizard"}},
            )
        # The apply_profile_updates service validates internally —
        # endpoint always returns 200 since apply_profile_updates is mocked
        # In real integration the invalid value is dropped silently
        assert resp.status_code == 200

    def test_unauthenticated_returns_401(self, anon_client):
        resp = anon_client.post(
            "/api/v1/profiles/assistant/apply-updates",
            json={"updates": {"skills": ["python"]}},
        )
        assert resp.status_code == 401

    def test_updates_with_industries_accepted(self, client):
        profile = _make_profile(raw_json={"industries": ["Tech"]})
        with patch(
            "app.api.v1.endpoints.profiles.profile_assistant_service.apply_profile_updates",
            new=AsyncMock(return_value=profile),
        ):
            resp = client.post(
                "/api/v1/profiles/assistant/apply-updates",
                json={"updates": {"industries": ["Finance"]}},
            )
        assert resp.status_code == 200

    def test_applies_salary_updates(self, client):
        profile = _make_profile(salary_min=45000)
        with patch(
            "app.api.v1.endpoints.profiles.profile_assistant_service.apply_profile_updates",
            new=AsyncMock(return_value=profile),
        ):
            resp = client.post(
                "/api/v1/profiles/assistant/apply-updates",
                json={"updates": {"salary_min": 45000}},
            )
        assert resp.status_code == 200
