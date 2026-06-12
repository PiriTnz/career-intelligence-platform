"""
API tests for Application Package endpoints.

POST /api/v1/applications/{job_id}/prepare
GET  /api/v1/applications/{job_id}/package
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


# ── Shared test data ──────────────────────────────────────────────────────────

JOB_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

_ANALYSIS = {
    "verified_match": ["python", "docker"],
    "transferable_match": [{"skill": "tensorflow", "via": "pytorch", "family": "ml_frameworks"}],
    "real_gap": ["kubernetes"],
}

_WARNINGS = ["Moderate skill gap: 1 required skill(s) have no direct match."]


def _make_package(
    job_id: uuid.UUID = JOB_ID,
    cv_draft: str = "# CV\n\n## Summary\nExperienced engineer.",
    cover_letter_draft: str = "Dear Hiring Manager,\n\nI am excited...",
    score: int = 72,
    analysis: dict | None = None,
    warnings: list[str] | None = None,
) -> MagicMock:
    pkg = MagicMock()
    pkg.id = uuid.uuid4()
    pkg.user_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    pkg.job_id = job_id
    pkg.cv_draft = cv_draft
    pkg.cover_letter_draft = cover_letter_draft
    pkg.requirement_analysis = analysis if analysis is not None else _ANALYSIS
    pkg.warnings = warnings if warnings is not None else _WARNINGS
    pkg.ready_to_apply_score = score
    return pkg


# ── TestPrepareEndpoint ───────────────────────────────────────────────────────

class TestPrepareEndpoint:
    def test_returns_200_on_success(self, client: TestClient):
        pkg = _make_package()
        with patch(
            "app.api.v1.endpoints.applications.application_package_service.prepare_application_package",
            new_callable=AsyncMock,
            return_value=pkg,
        ), patch("app.api.v1.endpoints.applications.get_provider"):
            resp = client.post(f"/api/v1/applications/{JOB_ID}/prepare")
        assert resp.status_code == 200

    def test_response_contains_required_fields(self, client: TestClient):
        pkg = _make_package()
        with patch(
            "app.api.v1.endpoints.applications.application_package_service.prepare_application_package",
            new_callable=AsyncMock,
            return_value=pkg,
        ), patch("app.api.v1.endpoints.applications.get_provider"):
            resp = client.post(f"/api/v1/applications/{JOB_ID}/prepare")

        data = resp.json()
        assert "job_id" in data
        assert "cv_draft" in data
        assert "cover_letter_draft" in data
        assert "requirement_analysis" in data
        assert "warnings" in data
        assert "ready_to_apply_score" in data

    def test_requirement_analysis_has_correct_structure(self, client: TestClient):
        pkg = _make_package()
        with patch(
            "app.api.v1.endpoints.applications.application_package_service.prepare_application_package",
            new_callable=AsyncMock,
            return_value=pkg,
        ), patch("app.api.v1.endpoints.applications.get_provider"):
            resp = client.post(f"/api/v1/applications/{JOB_ID}/prepare")

        analysis = resp.json()["requirement_analysis"]
        assert "verified_match" in analysis
        assert "transferable_match" in analysis
        assert "real_gap" in analysis
        assert isinstance(analysis["verified_match"], list)
        assert isinstance(analysis["transferable_match"], list)
        assert isinstance(analysis["real_gap"], list)

    def test_transferable_match_has_skill_via_family(self, client: TestClient):
        pkg = _make_package()
        with patch(
            "app.api.v1.endpoints.applications.application_package_service.prepare_application_package",
            new_callable=AsyncMock,
            return_value=pkg,
        ), patch("app.api.v1.endpoints.applications.get_provider"):
            resp = client.post(f"/api/v1/applications/{JOB_ID}/prepare")

        tm = resp.json()["requirement_analysis"]["transferable_match"]
        assert len(tm) == 1
        assert tm[0]["skill"] == "tensorflow"
        assert tm[0]["via"] == "pytorch"
        assert tm[0]["family"] == "ml_frameworks"

    def test_ready_to_apply_score_in_response(self, client: TestClient):
        pkg = _make_package(score=72)
        with patch(
            "app.api.v1.endpoints.applications.application_package_service.prepare_application_package",
            new_callable=AsyncMock,
            return_value=pkg,
        ), patch("app.api.v1.endpoints.applications.get_provider"):
            resp = client.post(f"/api/v1/applications/{JOB_ID}/prepare")

        assert resp.json()["ready_to_apply_score"] == 72

    def test_404_when_job_not_found(self, client: TestClient):
        with patch(
            "app.api.v1.endpoints.applications.application_package_service.prepare_application_package",
            new_callable=AsyncMock,
            side_effect=ValueError(f"Job {JOB_ID} not found."),
        ), patch("app.api.v1.endpoints.applications.get_provider"):
            resp = client.post(f"/api/v1/applications/{JOB_ID}/prepare")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_400_when_no_profile(self, client: TestClient):
        with patch(
            "app.api.v1.endpoints.applications.application_package_service.prepare_application_package",
            new_callable=AsyncMock,
            side_effect=ValueError("No active profile found."),
        ), patch("app.api.v1.endpoints.applications.get_provider"):
            resp = client.post(f"/api/v1/applications/{JOB_ID}/prepare")

        assert resp.status_code == 400
        assert "profile" in resp.json()["detail"].lower()

    def test_401_without_authentication(self, anon_client: TestClient):
        resp = anon_client.post(f"/api/v1/applications/{JOB_ID}/prepare")
        assert resp.status_code == 401

    def test_job_id_echoed_in_response(self, client: TestClient):
        pkg = _make_package(job_id=JOB_ID)
        with patch(
            "app.api.v1.endpoints.applications.application_package_service.prepare_application_package",
            new_callable=AsyncMock,
            return_value=pkg,
        ), patch("app.api.v1.endpoints.applications.get_provider"):
            resp = client.post(f"/api/v1/applications/{JOB_ID}/prepare")

        assert resp.json()["job_id"] == str(JOB_ID)

    def test_warnings_list_in_response(self, client: TestClient):
        pkg = _make_package(warnings=["High skill gap: 3 of 5 required skills."])
        with patch(
            "app.api.v1.endpoints.applications.application_package_service.prepare_application_package",
            new_callable=AsyncMock,
            return_value=pkg,
        ), patch("app.api.v1.endpoints.applications.get_provider"):
            resp = client.post(f"/api/v1/applications/{JOB_ID}/prepare")

        warnings = resp.json()["warnings"]
        assert isinstance(warnings, list)
        assert len(warnings) == 1

    def test_cv_draft_and_cover_letter_in_response(self, client: TestClient):
        pkg = _make_package(cv_draft="My CV content", cover_letter_draft="Dear HM")
        with patch(
            "app.api.v1.endpoints.applications.application_package_service.prepare_application_package",
            new_callable=AsyncMock,
            return_value=pkg,
        ), patch("app.api.v1.endpoints.applications.get_provider"):
            resp = client.post(f"/api/v1/applications/{JOB_ID}/prepare")

        data = resp.json()
        assert data["cv_draft"] == "My CV content"
        assert data["cover_letter_draft"] == "Dear HM"

    def test_empty_real_gap_is_valid(self, client: TestClient):
        analysis = {
            "verified_match": ["python", "docker", "tensorflow"],
            "transferable_match": [],
            "real_gap": [],
        }
        pkg = _make_package(score=90, analysis=analysis, warnings=[])
        with patch(
            "app.api.v1.endpoints.applications.application_package_service.prepare_application_package",
            new_callable=AsyncMock,
            return_value=pkg,
        ), patch("app.api.v1.endpoints.applications.get_provider"):
            resp = client.post(f"/api/v1/applications/{JOB_ID}/prepare")

        assert resp.status_code == 200
        assert resp.json()["requirement_analysis"]["real_gap"] == []
        assert resp.json()["ready_to_apply_score"] == 90


# ── TestGetPackageEndpoint ────────────────────────────────────────────────────

class TestGetPackageEndpoint:
    def test_returns_200_when_package_exists(self, client: TestClient):
        pkg = _make_package()
        with patch(
            "app.api.v1.endpoints.applications.application_package_service.get_application_package",
            new_callable=AsyncMock,
            return_value=pkg,
        ):
            resp = client.get(f"/api/v1/applications/{JOB_ID}/package")

        assert resp.status_code == 200

    def test_returns_correct_fields(self, client: TestClient):
        pkg = _make_package(score=65)
        with patch(
            "app.api.v1.endpoints.applications.application_package_service.get_application_package",
            new_callable=AsyncMock,
            return_value=pkg,
        ):
            resp = client.get(f"/api/v1/applications/{JOB_ID}/package")

        data = resp.json()
        assert data["ready_to_apply_score"] == 65
        assert "cv_draft" in data
        assert "cover_letter_draft" in data
        assert "requirement_analysis" in data

    def test_404_when_package_does_not_exist(self, client: TestClient):
        with patch(
            "app.api.v1.endpoints.applications.application_package_service.get_application_package",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = client.get(f"/api/v1/applications/{JOB_ID}/package")

        assert resp.status_code == 404
        assert "prepare" in resp.json()["detail"].lower()

    def test_401_without_authentication(self, anon_client: TestClient):
        resp = anon_client.get(f"/api/v1/applications/{JOB_ID}/package")
        assert resp.status_code == 401

    def test_requirement_analysis_deserialized_correctly(self, client: TestClient):
        analysis = {
            "verified_match": ["python"],
            "transferable_match": [{"skill": "tensorflow", "via": "pytorch", "family": "ml_frameworks"}],
            "real_gap": ["kubernetes"],
        }
        pkg = _make_package(analysis=analysis)
        with patch(
            "app.api.v1.endpoints.applications.application_package_service.get_application_package",
            new_callable=AsyncMock,
            return_value=pkg,
        ):
            resp = client.get(f"/api/v1/applications/{JOB_ID}/package")

        ra = resp.json()["requirement_analysis"]
        assert ra["verified_match"] == ["python"]
        assert ra["real_gap"] == ["kubernetes"]
        assert ra["transferable_match"][0]["skill"] == "tensorflow"
        assert ra["transferable_match"][0]["via"] == "pytorch"

    def test_job_id_in_response_matches_request(self, client: TestClient):
        pkg = _make_package(job_id=JOB_ID)
        with patch(
            "app.api.v1.endpoints.applications.application_package_service.get_application_package",
            new_callable=AsyncMock,
            return_value=pkg,
        ):
            resp = client.get(f"/api/v1/applications/{JOB_ID}/package")

        assert resp.json()["job_id"] == str(JOB_ID)

    def test_empty_transferable_match_valid(self, client: TestClient):
        analysis = {
            "verified_match": ["python", "docker"],
            "transferable_match": [],
            "real_gap": [],
        }
        pkg = _make_package(analysis=analysis, warnings=[])
        with patch(
            "app.api.v1.endpoints.applications.application_package_service.get_application_package",
            new_callable=AsyncMock,
            return_value=pkg,
        ):
            resp = client.get(f"/api/v1/applications/{JOB_ID}/package")

        assert resp.status_code == 200
        assert resp.json()["requirement_analysis"]["transferable_match"] == []
