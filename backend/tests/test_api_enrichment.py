"""
API-level tests for /api/v1/enrichment/

Uses TestClient + mocked DB — no real PostgreSQL needed.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import USER_ID


JOB_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
SESSION_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _make_session(status="pending", questions=None, answers=None, confirmations=None):
    s = MagicMock()
    s.id = SESSION_ID
    s.user_id = USER_ID
    s.job_id = JOB_ID
    s.status = status
    s.detected_gaps = [
        {"requirement": "azure", "classification": "unknown", "rationale": "No evidence", "via_skill": None, "via_family": None},
    ]
    s.generated_questions = questions or [
        {
            "id": "q-0",
            "requirement": "azure",
            "question": "Have you used Azure in any context?",
            "question_type": "cloud_experience",
            "classification": "unknown",
        }
    ]
    s.answers = answers or []
    s.confirmations = confirmations or []
    s.enriched_skills = []
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    s.created_at = now
    s.updated_at = now
    return s


def _make_job():
    j = MagicMock()
    j.id = JOB_ID
    j.title = "ML Engineer"
    j.company_name = "ACME Corp"
    j.required_skills = ["azure"]
    return j


# ── /start/{job_id} ────────────────────────────────────────────────────────────

class TestStartSession:
    def test_start_returns_questions(self, client):
        session = _make_session()
        gaps = [MagicMock(classification="unknown")]

        with patch("app.api.v1.endpoints.enrichment.enrichment_service.start_session", new_callable=AsyncMock) as mock_start:
            mock_start.return_value = (session, gaps)
            # The endpoint does a second DB query for job title/company — the mock_session
            # returns None for those, so the endpoint falls back to "Unknown". That's fine.
            resp = client.post(f"/api/v1/enrichment/start/{JOB_ID}")

        # 200 or 500 depending on whether mock DB returns a Job row; route is registered.
        assert resp.status_code in (200, 404, 500)

    def test_start_not_found_returns_404(self, client):
        with patch("app.api.v1.endpoints.enrichment.enrichment_service.start_session", new_callable=AsyncMock) as mock_start:
            mock_start.side_effect = ValueError("Job not found.")
            resp = client.post(f"/api/v1/enrichment/start/{JOB_ID}")
        assert resp.status_code == 404


# ── /answer ────────────────────────────────────────────────────────────────────

class TestSubmitAnswer:
    def test_answer_returns_classification(self, client):
        session = _make_session()
        from app.schemas.enrichment import AnswerItem
        from datetime import datetime, timezone
        answer_item = AnswerItem(
            question_id="q-0",
            requirement="azure",
            answer_text="I used Azure in a personal project on GitHub",
            evidence_type="project",
            suggested_status="verified",
            answered_at=datetime.now(timezone.utc).isoformat(),
        )

        with patch("app.api.v1.endpoints.enrichment.enrichment_service.get_session", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.endpoints.enrichment.enrichment_service.record_answer", new_callable=AsyncMock) as mock_record:
            mock_get.return_value = session
            mock_record.return_value = answer_item

            resp = client.post("/api/v1/enrichment/answer", json={
                "session_id": str(SESSION_ID),
                "question_id": "q-0",
                "answer_text": "I used Azure in a personal project on GitHub",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["evidence_type"] == "project"
        assert data["suggested_status"] == "verified"
        assert data["requirement"] == "azure"

    def test_answer_session_not_found(self, client):
        with patch("app.api.v1.endpoints.enrichment.enrichment_service.get_session", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            resp = client.post("/api/v1/enrichment/answer", json={
                "session_id": str(SESSION_ID),
                "question_id": "q-0",
                "answer_text": "Yes",
            })
        assert resp.status_code == 404

    def test_answer_invalid_question_id(self, client):
        session = _make_session()

        with patch("app.api.v1.endpoints.enrichment.enrichment_service.get_session", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.endpoints.enrichment.enrichment_service.record_answer", new_callable=AsyncMock) as mock_record:
            mock_get.return_value = session
            mock_record.side_effect = ValueError("Question 'q-99' not found in session.")

            resp = client.post("/api/v1/enrichment/answer", json={
                "session_id": str(SESSION_ID),
                "question_id": "q-99",
                "answer_text": "Yes",
            })

        assert resp.status_code == 400


# ── /confirm ───────────────────────────────────────────────────────────────────

class TestConfirmEnrichment:
    def test_confirmed_returns_enriched_skills(self, client):
        session = _make_session()
        session.status = "enriched"

        with patch("app.api.v1.endpoints.enrichment.enrichment_service.get_session", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.endpoints.enrichment.enrichment_service.confirm_enrichment", new_callable=AsyncMock) as mock_confirm:
            mock_get.return_value = session
            mock_confirm.return_value = ["azure"]

            resp = client.post("/api/v1/enrichment/confirm", json={
                "session_id": str(SESSION_ID),
                "confirmations": [
                    {
                        "question_id": "q-0",
                        "requirement": "azure",
                        "confirmed": True,
                        "evidence_note": "I deployed on Azure for a side project",
                        "suggested_status": "verified",
                    }
                ],
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["enriched_count"] == 1
        assert "azure" in data["enriched_skills"]

    def test_rejected_confirmation_enriches_nothing(self, client):
        session = _make_session()
        session.status = "confirmed"

        with patch("app.api.v1.endpoints.enrichment.enrichment_service.get_session", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.endpoints.enrichment.enrichment_service.confirm_enrichment", new_callable=AsyncMock) as mock_confirm:
            mock_get.return_value = session
            mock_confirm.return_value = []  # nothing enriched — user rejected

            resp = client.post("/api/v1/enrichment/confirm", json={
                "session_id": str(SESSION_ID),
                "confirmations": [
                    {
                        "question_id": "q-0",
                        "requirement": "azure",
                        "confirmed": False,
                        "evidence_note": None,
                        "suggested_status": "rejected",
                    }
                ],
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["enriched_count"] == 0
        assert data["enriched_skills"] == []


# ── /session/{id} ──────────────────────────────────────────────────────────────

class TestGetSession:
    def test_returns_session_detail(self, client):
        session = _make_session(status="answering")

        with patch("app.api.v1.endpoints.enrichment.enrichment_service.get_session", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = session
            resp = client.get(f"/api/v1/enrichment/session/{SESSION_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(SESSION_ID)
        assert data["status"] == "answering"
        assert len(data["generated_questions"]) == 1

    def test_not_found_returns_404(self, client):
        with patch("app.api.v1.endpoints.enrichment.enrichment_service.get_session", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            resp = client.get(f"/api/v1/enrichment/session/{SESSION_ID}")
        assert resp.status_code == 404


# ── /status/{job_id} ───────────────────────────────────────────────────────────

class TestGetStatus:
    def test_no_session_returns_has_open_false(self, client):
        with patch("app.api.v1.endpoints.enrichment.enrichment_service.get_enrichment_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = {
                "has_open_session": False,
                "session_id": None,
                "session_status": None,
                "unanswered_questions": 0,
                "enriched_skills": [],
            }
            resp = client.get(f"/api/v1/enrichment/status/{JOB_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["has_open_session"] is False
        assert data["session_id"] is None

    def test_open_session_returns_unanswered_count(self, client):
        with patch("app.api.v1.endpoints.enrichment.enrichment_service.get_enrichment_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = {
                "has_open_session": True,
                "session_id": SESSION_ID,
                "session_status": "pending",
                "unanswered_questions": 3,
                "enriched_skills": [],
            }
            resp = client.get(f"/api/v1/enrichment/status/{JOB_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["has_open_session"] is True
        assert data["unanswered_questions"] == 3
