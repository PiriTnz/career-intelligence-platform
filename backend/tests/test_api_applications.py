"""
API tests for /api/v1/applications/

Covers: list, create, get, status update (with auto-timestamps),
        notes update, delete, tracker endpoint.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import USER_ID

APP_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
JOB_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def _make_app(status: str = "found") -> MagicMock:
    now = datetime.now(timezone.utc)
    app = MagicMock()
    app.id = APP_ID
    app.user_id = USER_ID
    app.job_id = JOB_ID
    app.status = status
    app.applied_at = None
    app.approved_at = None
    app.replied_at = None
    app.interview_at = None
    app.notes = None
    app.created_at = now
    app.updated_at = now
    return app


def _make_job() -> MagicMock:
    job = MagicMock()
    job.id = JOB_ID
    job.title = "ML Engineer"
    job.company_name = "ACME Corp"
    job.location = "Paris"
    job.remote = "hybrid"
    return job


def _make_ws() -> MagicMock:
    ws = MagicMock()
    ws.readiness_score = 82
    ws.readiness_label = "strong"
    return ws


# ── List ──────────────────────────────────────────────────────────────────────

class TestListApplications:
    def test_returns_list(self, client, mock_session):
        app = _make_app()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: [app]))
        )
        resp = client.get("/api/v1/applications/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_empty_list(self, client, mock_session):
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: []))
        )
        resp = client.get("/api/v1/applications/")
        assert resp.status_code == 200
        assert resp.json() == []


# ── Create ────────────────────────────────────────────────────────────────────

class TestCreateApplication:
    def test_creates_with_found_status(self, client, mock_session):
        app = _make_app("found")

        async def _refresh(obj):
            obj.id = APP_ID
            obj.user_id = USER_ID
            obj.job_id = JOB_ID
            obj.status = "found"
            obj.applied_at = None
            obj.approved_at = None
            obj.replied_at = None
            obj.interview_at = None
            obj.notes = None
            from datetime import datetime, timezone
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = datetime.now(timezone.utc)

        mock_session.refresh = _refresh
        resp = client.post("/api/v1/applications/", json={"job_id": str(JOB_ID)})
        assert resp.status_code == 201


# ── Get ───────────────────────────────────────────────────────────────────────

class TestGetApplication:
    def test_returns_application(self, client, mock_session):
        app = _make_app()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=lambda: app)
        )
        resp = client.get(f"/api/v1/applications/{APP_ID}")
        assert resp.status_code == 200

    def test_not_found_returns_404(self, client, mock_session):
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=lambda: None)
        )
        resp = client.get(f"/api/v1/applications/{APP_ID}")
        assert resp.status_code == 404


# ── Status update ─────────────────────────────────────────────────────────────

class TestUpdateStatus:
    def test_status_updated(self, client, mock_session):
        app = _make_app("found")
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=lambda: app)
        )
        resp = client.patch(
            f"/api/v1/applications/{APP_ID}/status",
            json={"status": "shortlisted"},
        )
        assert resp.status_code == 200

    def test_applied_status_sets_applied_at(self, client, mock_session):
        app = _make_app("approved")
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=lambda: app)
        )
        resp = client.patch(
            f"/api/v1/applications/{APP_ID}/status",
            json={"status": "applied"},
        )
        assert resp.status_code == 200
        # applied_at should have been set on the mock object
        assert app.applied_at is not None

    def test_interview_status_sets_interview_at(self, client, mock_session):
        app = _make_app("replied")
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=lambda: app)
        )
        resp = client.patch(
            f"/api/v1/applications/{APP_ID}/status",
            json={"status": "interview"},
        )
        assert resp.status_code == 200
        assert app.interview_at is not None

    def test_invalid_status_returns_422(self, client):
        resp = client.patch(
            f"/api/v1/applications/{APP_ID}/status",
            json={"status": "winning"},
        )
        assert resp.status_code == 422

    def test_not_found_returns_404(self, client, mock_session):
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=lambda: None)
        )
        resp = client.patch(
            f"/api/v1/applications/{APP_ID}/status",
            json={"status": "applied"},
        )
        assert resp.status_code == 404


# ── Notes update ──────────────────────────────────────────────────────────────

class TestUpdateNotes:
    def test_notes_updated(self, client, mock_session):
        app = _make_app()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=lambda: app)
        )
        resp = client.patch(
            f"/api/v1/applications/{APP_ID}/notes",
            json={"notes": "Follow up next week"},
        )
        assert resp.status_code == 200
        assert app.notes == "Follow up next week"

    def test_not_found_returns_404(self, client, mock_session):
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=lambda: None)
        )
        resp = client.patch(
            f"/api/v1/applications/{APP_ID}/notes",
            json={"notes": "test"},
        )
        assert resp.status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────

class TestDeleteApplication:
    def test_delete_returns_204(self, client, mock_session):
        app = _make_app()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=lambda: app)
        )
        mock_session.delete = AsyncMock()
        resp = client.delete(f"/api/v1/applications/{APP_ID}")
        assert resp.status_code == 204

    def test_delete_not_found_returns_404(self, client, mock_session):
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=lambda: None)
        )
        resp = client.delete(f"/api/v1/applications/{APP_ID}")
        assert resp.status_code == 404


# ── Tracker ───────────────────────────────────────────────────────────────────

class TestTrackerEndpoint:
    def test_tracker_returns_enriched_list(self, client, mock_session):
        app = _make_app("applied")
        job = _make_job()
        ws = _make_ws()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(all=lambda: [(app, job, ws)])
        )
        resp = client.get("/api/v1/applications/tracker")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["job_title"] == "ML Engineer"
        assert data[0]["company_name"] == "ACME Corp"
        assert data[0]["readiness_score"] == 82
        assert data[0]["has_workspace"] is True
        assert data[0]["status"] == "applied"

    def test_tracker_empty(self, client, mock_session):
        mock_session.execute = AsyncMock(
            return_value=MagicMock(all=lambda: [])
        )
        resp = client.get("/api/v1/applications/tracker")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_tracker_no_workspace(self, client, mock_session):
        app = _make_app("found")
        job = _make_job()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(all=lambda: [(app, job, None)])
        )
        resp = client.get("/api/v1/applications/tracker")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["has_workspace"] is False
        assert data[0]["readiness_score"] is None
