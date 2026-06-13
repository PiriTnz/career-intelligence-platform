"""
API tests for /api/v1/applications/

Covers: list, create, get, status transitions (with auto-timestamps + timeline),
        notes update, delete, tracker, ready queue, metrics,
        job-id-scoped endpoints.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import USER_ID

APP_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
JOB_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def _make_app(status: str = "recommended") -> MagicMock:
    now = datetime.now(timezone.utc)
    app = MagicMock()
    app.id = APP_ID
    app.user_id = USER_ID
    app.job_id = JOB_ID
    app.status = status
    app.applied_at = None
    app.follow_up_at = None
    app.interview_at = None
    app.offer_at = None
    app.rejected_at = None
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


def _single_result(value):
    """Result that returns value from scalar_one_or_none."""
    r = MagicMock()
    r.scalar_one_or_none = lambda: value
    return r


def _scalars_result(items: list):
    """Result that returns items from scalars().all()."""
    r = MagicMock()
    r.scalars = lambda: MagicMock(all=lambda: items)
    return r


def _all_result(rows: list):
    """Result that returns rows from .all()."""
    r = MagicMock()
    r.all = lambda: rows
    return r


# ── List ──────────────────────────────────────────────────────────────────────

class TestListApplications:
    def test_returns_list(self, client, mock_session):
        app = _make_app()
        mock_session.execute = AsyncMock(return_value=_scalars_result([app]))
        resp = client.get("/api/v1/applications/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_empty_list(self, client, mock_session):
        mock_session.execute = AsyncMock(return_value=_scalars_result([]))
        resp = client.get("/api/v1/applications/")
        assert resp.status_code == 200
        assert resp.json() == []


# ── Create ────────────────────────────────────────────────────────────────────

class TestCreateApplication:
    def test_creates_with_recommended_status(self, client, mock_session):
        now = datetime.now(timezone.utc)

        async def _refresh(obj):
            obj.id = APP_ID
            obj.user_id = USER_ID
            obj.job_id = JOB_ID
            obj.status = "recommended"
            obj.applied_at = None
            obj.follow_up_at = None
            obj.interview_at = None
            obj.offer_at = None
            obj.rejected_at = None
            obj.notes = None
            obj.created_at = now
            obj.updated_at = now

        mock_session.refresh = _refresh
        resp = client.post("/api/v1/applications/", json={"job_id": str(JOB_ID)})
        assert resp.status_code == 201
        assert resp.json()["status"] == "recommended"


# ── Get by application_id ─────────────────────────────────────────────────────

class TestGetApplication:
    def test_returns_application(self, client, mock_session):
        app = _make_app()
        mock_session.execute = AsyncMock(return_value=_single_result(app))
        resp = client.get(f"/api/v1/applications/{APP_ID}")
        assert resp.status_code == 200

    def test_not_found_returns_404(self, client, mock_session):
        mock_session.execute = AsyncMock(return_value=_single_result(None))
        resp = client.get(f"/api/v1/applications/{APP_ID}")
        assert resp.status_code == 404


# ── Status update (application_id-scoped) ─────────────────────────────────────

class TestUpdateStatusById:
    def test_valid_transition_succeeds(self, client, mock_session):
        app = _make_app("recommended")
        mock_session.execute = AsyncMock(return_value=_single_result(app))
        resp = client.patch(
            f"/api/v1/applications/{APP_ID}/status",
            json={"status": "preparing"},
        )
        assert resp.status_code == 200
        assert app.status == "preparing"

    def test_applied_transition_sets_applied_at(self, client, mock_session):
        app = _make_app("ready_to_apply")
        mock_session.execute = AsyncMock(return_value=_single_result(app))
        resp = client.patch(
            f"/api/v1/applications/{APP_ID}/status",
            json={"status": "applied"},
        )
        assert resp.status_code == 200
        assert app.applied_at is not None

    def test_interview_transition_sets_interview_at(self, client, mock_session):
        app = _make_app("applied")
        mock_session.execute = AsyncMock(return_value=_single_result(app))
        resp = client.patch(
            f"/api/v1/applications/{APP_ID}/status",
            json={"status": "interview"},
        )
        assert resp.status_code == 200
        assert app.interview_at is not None

    def test_invalid_status_value_returns_422(self, client):
        resp = client.patch(
            f"/api/v1/applications/{APP_ID}/status",
            json={"status": "winning"},
        )
        assert resp.status_code == 422

    def test_invalid_transition_returns_400(self, client, mock_session):
        # Can't jump from recommended directly to applied
        app = _make_app("recommended")
        mock_session.execute = AsyncMock(return_value=_single_result(app))
        resp = client.patch(
            f"/api/v1/applications/{APP_ID}/status",
            json={"status": "applied"},
        )
        assert resp.status_code == 400

    def test_terminal_status_blocks_transition(self, client, mock_session):
        app = _make_app("offer")
        mock_session.execute = AsyncMock(return_value=_single_result(app))
        resp = client.patch(
            f"/api/v1/applications/{APP_ID}/status",
            json={"status": "interview"},
        )
        assert resp.status_code == 400

    def test_not_found_returns_404(self, client, mock_session):
        mock_session.execute = AsyncMock(return_value=_single_result(None))
        resp = client.patch(
            f"/api/v1/applications/{APP_ID}/status",
            json={"status": "preparing"},
        )
        assert resp.status_code == 404


# ── Notes update (application_id-scoped) ──────────────────────────────────────

class TestUpdateNotesById:
    def test_notes_updated(self, client, mock_session):
        app = _make_app()
        mock_session.execute = AsyncMock(return_value=_single_result(app))
        resp = client.patch(
            f"/api/v1/applications/{APP_ID}/notes",
            json={"notes": "Follow up next week"},
        )
        assert resp.status_code == 200
        assert app.notes == "Follow up next week"

    def test_not_found_returns_404(self, client, mock_session):
        mock_session.execute = AsyncMock(return_value=_single_result(None))
        resp = client.patch(
            f"/api/v1/applications/{APP_ID}/notes",
            json={"notes": "test"},
        )
        assert resp.status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────

class TestDeleteApplication:
    def test_delete_returns_204(self, client, mock_session):
        app = _make_app()
        mock_session.execute = AsyncMock(return_value=_single_result(app))
        mock_session.delete = AsyncMock()
        resp = client.delete(f"/api/v1/applications/{APP_ID}")
        assert resp.status_code == 204

    def test_delete_not_found_returns_404(self, client, mock_session):
        mock_session.execute = AsyncMock(return_value=_single_result(None))
        resp = client.delete(f"/api/v1/applications/{APP_ID}")
        assert resp.status_code == 404


# ── Tracker ───────────────────────────────────────────────────────────────────

class TestTrackerEndpoint:
    def test_tracker_returns_enriched_list(self, client, mock_session):
        app = _make_app("applied")
        job = _make_job()
        ws = _make_ws()
        mock_session.execute = AsyncMock(return_value=_all_result([(app, job, ws)]))
        resp = client.get("/api/v1/applications/tracker")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["job_title"] == "ML Engineer"
        assert data[0]["company_name"] == "ACME Corp"
        assert data[0]["readiness_score"] == 82
        assert data[0]["has_workspace"] is True
        assert data[0]["status"] == "applied"
        assert "follow_up_due" in data[0]

    def test_tracker_empty(self, client, mock_session):
        mock_session.execute = AsyncMock(return_value=_all_result([]))
        resp = client.get("/api/v1/applications/tracker")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_tracker_no_workspace(self, client, mock_session):
        app = _make_app("recommended")
        job = _make_job()
        mock_session.execute = AsyncMock(return_value=_all_result([(app, job, None)]))
        resp = client.get("/api/v1/applications/tracker")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["has_workspace"] is False
        assert data[0]["readiness_score"] is None


# ── Ready to apply queue ──────────────────────────────────────────────────────

class TestReadyToApply:
    def test_ready_returns_only_ready_applications(self, client, mock_session):
        app = _make_app("ready_to_apply")
        job = _make_job()
        mock_session.execute = AsyncMock(return_value=_all_result([(app, job, None)]))
        resp = client.get("/api/v1/applications/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "ready_to_apply"

    def test_ready_empty(self, client, mock_session):
        mock_session.execute = AsyncMock(return_value=_all_result([]))
        resp = client.get("/api/v1/applications/ready")
        assert resp.status_code == 200
        assert resp.json() == []


# ── Metrics ───────────────────────────────────────────────────────────────────

class TestMetrics:
    def test_metrics_returns_counts(self, client, mock_session):
        rows = [
            ("recommended", 3),
            ("preparing", 2),
            ("ready_to_apply", 1),
            ("applied", 4),
            ("interview", 1),
            ("offer", 0),
            ("rejected", 2),
        ]
        all_result = MagicMock()
        all_result.all = lambda: rows
        mock_session.execute = AsyncMock(return_value=all_result)
        resp = client.get("/api/v1/applications/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["recommended"] == 3
        assert data["ready_to_apply"] == 1
        assert data["applied"] == 4
        assert data["interview"] == 1
        assert data["follow_up"] == 0       # not in rows → defaults to 0
        assert data["total"] == 13

    def test_metrics_all_zero_when_no_applications(self, client, mock_session):
        all_result = MagicMock()
        all_result.all = lambda: []
        mock_session.execute = AsyncMock(return_value=all_result)
        resp = client.get("/api/v1/applications/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["applied"] == 0


# ── Job-id-scoped endpoints ───────────────────────────────────────────────────

class TestGetApplicationByJob:
    def test_returns_application_with_timeline(self, client, mock_session):
        app = _make_app("preparing")
        app_result = _single_result(app)
        timeline_result = _scalars_result([])
        mock_session.execute = AsyncMock(side_effect=[app_result, timeline_result])
        resp = client.get(f"/api/v1/applications/job/{JOB_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "preparing"
        assert data["timeline"] == []

    def test_not_found_returns_404(self, client, mock_session):
        mock_session.execute = AsyncMock(return_value=_single_result(None))
        resp = client.get(f"/api/v1/applications/job/{JOB_ID}")
        assert resp.status_code == 404


class TestUpdateStatusByJob:
    def test_valid_transition_via_job_id(self, client, mock_session):
        app = _make_app("preparing")
        app_result = _single_result(app)
        timeline_result = _scalars_result([])
        mock_session.execute = AsyncMock(side_effect=[app_result, timeline_result])
        resp = client.post(
            f"/api/v1/applications/job/{JOB_ID}/status",
            json={"status": "ready_to_apply"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready_to_apply"

    def test_invalid_transition_via_job_id_returns_400(self, client, mock_session):
        app = _make_app("recommended")
        mock_session.execute = AsyncMock(return_value=_single_result(app))
        resp = client.post(
            f"/api/v1/applications/job/{JOB_ID}/status",
            json={"status": "offer"},
        )
        assert resp.status_code == 400

    def test_not_found_returns_404(self, client, mock_session):
        mock_session.execute = AsyncMock(return_value=_single_result(None))
        resp = client.post(
            f"/api/v1/applications/job/{JOB_ID}/status",
            json={"status": "preparing"},
        )
        assert resp.status_code == 404


class TestUpdateNotesByJob:
    def test_notes_updated_via_job_id(self, client, mock_session):
        app = _make_app()
        mock_session.execute = AsyncMock(return_value=_single_result(app))
        resp = client.post(
            f"/api/v1/applications/job/{JOB_ID}/notes",
            json={"notes": "Deadline is Monday"},
        )
        assert resp.status_code == 200
        assert app.notes == "Deadline is Monday"

    def test_not_found_returns_404(self, client, mock_session):
        mock_session.execute = AsyncMock(return_value=_single_result(None))
        resp = client.post(
            f"/api/v1/applications/job/{JOB_ID}/notes",
            json={"notes": "test"},
        )
        assert resp.status_code == 404
