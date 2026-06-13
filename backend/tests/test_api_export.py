"""
API tests for /api/v1/export/{job_id}/*

Covers: cv.docx, cv.pdf, letter.docx, letter.pdf, messages,
        not-found (no package), empty draft guard.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import USER_ID

JOB_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PKG_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

NOW = datetime.now(timezone.utc)


def _make_pkg(cv: str = "# CV\n- item", letter: str = "Dear HM,\n\nI am great.\n\nBest,\nJane") -> MagicMock:
    pkg = MagicMock()
    pkg.id = PKG_ID
    pkg.user_id = USER_ID
    pkg.job_id = JOB_ID
    pkg.cv_draft = cv
    pkg.cover_letter_draft = letter
    pkg.exported_cv_at = None
    pkg.exported_cover_letter_at = None
    return pkg


def _make_job() -> MagicMock:
    job = MagicMock()
    job.id = JOB_ID
    job.title = "ML Engineer"
    job.company_name = "Acme Corp"
    return job


def _make_profile() -> MagicMock:
    profile = MagicMock()
    profile.personal_info = {"name": "Jane Smith"}
    return profile


def _single(value):
    r = MagicMock()
    r.scalar_one_or_none = lambda: value
    return r


# ── CV DOCX ───────────────────────────────────────────────────────────────────

class TestDownloadCvDocx:
    def test_returns_docx(self, client, mock_session):
        pkg = _make_pkg()
        mock_session.execute = AsyncMock(return_value=_single(pkg))
        resp = client.get(f"/api/v1/export/{JOB_ID}/cv.docx")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert resp.content[:2] == b"PK"

    def test_sets_export_timestamp_on_first_download(self, client, mock_session):
        pkg = _make_pkg()
        mock_session.execute = AsyncMock(return_value=_single(pkg))
        client.get(f"/api/v1/export/{JOB_ID}/cv.docx")
        assert pkg.exported_cv_at is not None

    def test_no_package_returns_404(self, client, mock_session):
        mock_session.execute = AsyncMock(return_value=_single(None))
        resp = client.get(f"/api/v1/export/{JOB_ID}/cv.docx")
        assert resp.status_code == 404

    def test_empty_cv_returns_404(self, client, mock_session):
        pkg = _make_pkg(cv="")
        mock_session.execute = AsyncMock(return_value=_single(pkg))
        resp = client.get(f"/api/v1/export/{JOB_ID}/cv.docx")
        assert resp.status_code == 404

    def test_does_not_overwrite_existing_timestamp(self, client, mock_session):
        pkg = _make_pkg()
        pkg.exported_cv_at = NOW
        mock_session.execute = AsyncMock(return_value=_single(pkg))
        client.get(f"/api/v1/export/{JOB_ID}/cv.docx")
        # should remain unchanged
        assert pkg.exported_cv_at == NOW


# ── CV PDF ────────────────────────────────────────────────────────────────────

class TestDownloadCvPdf:
    def test_returns_pdf(self, client, mock_session):
        pkg = _make_pkg()
        mock_session.execute = AsyncMock(return_value=_single(pkg))
        resp = client.get(f"/api/v1/export/{JOB_ID}/cv.pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:4] == b"%PDF"

    def test_no_package_returns_404(self, client, mock_session):
        mock_session.execute = AsyncMock(return_value=_single(None))
        resp = client.get(f"/api/v1/export/{JOB_ID}/cv.pdf")
        assert resp.status_code == 404


# ── Cover Letter DOCX ─────────────────────────────────────────────────────────

class TestDownloadLetterDocx:
    def test_returns_docx(self, client, mock_session):
        pkg = _make_pkg()
        mock_session.execute = AsyncMock(return_value=_single(pkg))
        resp = client.get(f"/api/v1/export/{JOB_ID}/letter.docx")
        assert resp.status_code == 200
        assert resp.content[:2] == b"PK"

    def test_sets_export_timestamp(self, client, mock_session):
        pkg = _make_pkg()
        mock_session.execute = AsyncMock(return_value=_single(pkg))
        client.get(f"/api/v1/export/{JOB_ID}/letter.docx")
        assert pkg.exported_cover_letter_at is not None

    def test_empty_letter_returns_404(self, client, mock_session):
        pkg = _make_pkg(letter="")
        mock_session.execute = AsyncMock(return_value=_single(pkg))
        resp = client.get(f"/api/v1/export/{JOB_ID}/letter.docx")
        assert resp.status_code == 404

    def test_no_package_returns_404(self, client, mock_session):
        mock_session.execute = AsyncMock(return_value=_single(None))
        resp = client.get(f"/api/v1/export/{JOB_ID}/letter.docx")
        assert resp.status_code == 404


# ── Cover Letter PDF ──────────────────────────────────────────────────────────

class TestDownloadLetterPdf:
    def test_returns_pdf(self, client, mock_session):
        pkg = _make_pkg()
        mock_session.execute = AsyncMock(return_value=_single(pkg))
        resp = client.get(f"/api/v1/export/{JOB_ID}/letter.pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:4] == b"%PDF"

    def test_no_package_returns_404(self, client, mock_session):
        mock_session.execute = AsyncMock(return_value=_single(None))
        resp = client.get(f"/api/v1/export/{JOB_ID}/letter.pdf")
        assert resp.status_code == 404


# ── Messages ──────────────────────────────────────────────────────────────────

class TestGetMessages:
    def _make_side_effects(self, pkg, job, profile):
        """Returns three sequential execute results: package, job, profile."""
        return [_single(pkg), _single(job), _single(profile)]

    def test_returns_both_messages(self, client, mock_session):
        pkg = _make_pkg()
        job = _make_job()
        profile = _make_profile()
        mock_session.execute = AsyncMock(
            side_effect=self._make_side_effects(pkg, job, profile)
        )
        resp = client.get(f"/api/v1/export/{JOB_ID}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert "hr_email" in data
        assert "linkedin_message" in data

    def test_hr_email_contains_job_info(self, client, mock_session):
        pkg = _make_pkg()
        job = _make_job()
        profile = _make_profile()
        mock_session.execute = AsyncMock(
            side_effect=self._make_side_effects(pkg, job, profile)
        )
        resp = client.get(f"/api/v1/export/{JOB_ID}/messages")
        data = resp.json()
        assert "ML Engineer" in data["hr_email"]
        assert "Acme Corp" in data["hr_email"]

    def test_linkedin_shorter_than_email(self, client, mock_session):
        pkg = _make_pkg()
        job = _make_job()
        profile = _make_profile()
        mock_session.execute = AsyncMock(
            side_effect=self._make_side_effects(pkg, job, profile)
        )
        resp = client.get(f"/api/v1/export/{JOB_ID}/messages")
        data = resp.json()
        assert len(data["linkedin_message"]) < len(data["hr_email"])

    def test_no_package_returns_404(self, client, mock_session):
        mock_session.execute = AsyncMock(return_value=_single(None))
        resp = client.get(f"/api/v1/export/{JOB_ID}/messages")
        assert resp.status_code == 404

    def test_falls_back_to_cv_when_no_letter(self, client, mock_session):
        pkg = _make_pkg(letter="")
        job = _make_job()
        profile = _make_profile()
        mock_session.execute = AsyncMock(
            side_effect=self._make_side_effects(pkg, job, profile)
        )
        resp = client.get(f"/api/v1/export/{JOB_ID}/messages")
        # Should still succeed (falls back to cv_draft)
        assert resp.status_code == 200

    def test_candidate_name_from_profile(self, client, mock_session):
        pkg = _make_pkg()
        job = _make_job()
        profile = _make_profile()
        mock_session.execute = AsyncMock(
            side_effect=self._make_side_effects(pkg, job, profile)
        )
        resp = client.get(f"/api/v1/export/{JOB_ID}/messages")
        data = resp.json()
        assert "Jane Smith" in data["hr_email"]

    def test_missing_profile_uses_candidate_fallback(self, client, mock_session):
        pkg = _make_pkg()
        job = _make_job()
        mock_session.execute = AsyncMock(
            side_effect=[_single(pkg), _single(job), _single(None)]
        )
        resp = client.get(f"/api/v1/export/{JOB_ID}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert "Candidate" in data["hr_email"]
