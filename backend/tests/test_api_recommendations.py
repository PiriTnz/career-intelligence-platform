"""
API tests for GET /jobs/recommendations.

All DB calls are mocked — no PostgreSQL required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_active_user, get_current_user
from app.core.database import get_db
from app.main import app
from tests.conftest import MOCK_USER, USER_ID, make_mock_session

NOW = datetime.now(timezone.utc)
JOB_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _mock_job(**overrides) -> MagicMock:
    j = MagicMock()
    j.id = JOB_ID
    j.title = "ML Engineer — LLM & RAG"
    j.company_name = "Mistral AI"
    j.location = "Lyon, France"
    j.remote = "full"
    j.contract_type = "cdi"
    j.salary_min = 52_000
    j.salary_max = 65_000
    j.required_skills = ["python", "pytorch", "llm", "rag"]
    j.experience_level = "mid"
    j.language = "fr"
    j.description = "Build LLM systems"
    j.published_at = NOW
    j.url = "https://ft.fr/offre/001"
    j.scraped_at = NOW
    for k, v in overrides.items():
        setattr(j, k, v)
    return j


MOCK_PROFILE = {
    "skills": ["python", "pytorch", "llm", "rag", "docker"],
    "target_roles": ["ML Engineer"],
    "experience_level": "mid",
    "salary_min": 42_000,
    "salary_target": 58_000,
    "remote_preference": True,
    "countries": ["france"],
    "cities": ["lyon"],
    "contract_types": ["cdi"],
    "languages": ["French", "English"],
    "version": 1,
}


# ── GET /jobs/recommendations ─────────────────────────────────────────────────

class TestGetRecommendations:
    def test_requires_auth(self, anon_client):
        resp = anon_client.get("/api/v1/jobs/recommendations")
        assert resp.status_code == 401

    def test_returns_400_when_no_profile(self, client):
        with patch(
            "app.api.v1.endpoints.jobs.job_service.get_profile_dict",
            new_callable=AsyncMock,
            return_value={},
        ):
            resp = client.get("/api/v1/jobs/recommendations")
        assert resp.status_code == 400
        assert "profile" in resp.json()["detail"].lower()

    def test_returns_empty_list_when_no_jobs(self, client):
        with patch(
            "app.api.v1.endpoints.jobs.job_service.get_profile_dict",
            new_callable=AsyncMock,
            return_value=MOCK_PROFILE,
        ), patch(
            "app.api.v1.endpoints.jobs.job_service.get_jobs_for_matching",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = client.get("/api/v1/jobs/recommendations")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_recommendation_with_score_and_match(self, client):
        job = _mock_job()
        with patch(
            "app.api.v1.endpoints.jobs.job_service.get_profile_dict",
            new_callable=AsyncMock,
            return_value=MOCK_PROFILE,
        ), patch(
            "app.api.v1.endpoints.jobs.job_service.get_jobs_for_matching",
            new_callable=AsyncMock,
            return_value=[job],
        ):
            resp = client.get("/api/v1/jobs/recommendations")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

        rec = data[0]
        # Job identity fields
        assert rec["title"] == "ML Engineer — LLM & RAG"
        assert rec["company_name"] == "Mistral AI"

        # Score breakdown present
        assert "score" in rec
        assert "total" in rec["score"]
        assert rec["score"]["total"] >= 0
        assert "skill_match" in rec["score"]
        assert "needs_review" in rec["score"]

        # Match detail present
        assert "match" in rec
        assert "matched_skills" in rec["match"]
        assert "missing_skills" in rec["match"]
        assert "skill_match_percentage" in rec["match"]
        assert "role_match_percentage" in rec["match"]
        assert "location_match" in rec["match"]
        assert "contract_match" in rec["match"]
        assert "language_match" in rec["match"]
        assert "overall_fit" in rec["match"]

    def test_score_reflects_profile_skills(self, client):
        """A job matching all profile skills should have high skill_match."""
        job = _mock_job(required_skills=["python", "pytorch"])
        with patch(
            "app.api.v1.endpoints.jobs.job_service.get_profile_dict",
            new_callable=AsyncMock,
            return_value=MOCK_PROFILE,
        ), patch(
            "app.api.v1.endpoints.jobs.job_service.get_jobs_for_matching",
            new_callable=AsyncMock,
            return_value=[job],
        ):
            resp = client.get("/api/v1/jobs/recommendations")

        rec = resp.json()[0]
        assert rec["score"]["skill_match"] == 30  # 2/2 = 100% × 30
        assert rec["match"]["skill_match_percentage"] == 100.0
        assert "python" in rec["match"]["matched_skills"]
        assert "pytorch" in rec["match"]["matched_skills"]
        assert rec["match"]["missing_skills"] == []

    def test_match_detail_location_match(self, client):
        """Lyon job against Lyon profile → location_match: true."""
        job = _mock_job(location="Lyon, France", remote="none")
        with patch(
            "app.api.v1.endpoints.jobs.job_service.get_profile_dict",
            new_callable=AsyncMock,
            return_value=MOCK_PROFILE,
        ), patch(
            "app.api.v1.endpoints.jobs.job_service.get_jobs_for_matching",
            new_callable=AsyncMock,
            return_value=[job],
        ):
            resp = client.get("/api/v1/jobs/recommendations")

        assert resp.json()[0]["match"]["location_match"] is True

    def test_match_detail_role_match(self, client):
        """Job titled 'ML Engineer' against target role 'ML Engineer' → high role_match_percentage."""
        job = _mock_job(title="ML Engineer")
        with patch(
            "app.api.v1.endpoints.jobs.job_service.get_profile_dict",
            new_callable=AsyncMock,
            return_value=MOCK_PROFILE,
        ), patch(
            "app.api.v1.endpoints.jobs.job_service.get_jobs_for_matching",
            new_callable=AsyncMock,
            return_value=[job],
        ):
            resp = client.get("/api/v1/jobs/recommendations")

        role_pct = resp.json()[0]["match"]["role_match_percentage"]
        assert role_pct >= 80.0

    def test_min_score_filter_excludes_low_scorers(self, client):
        """A job with no matching skills should be excluded by min_score=70."""
        job = _mock_job(
            required_skills=["cobol", "fortran"],
            location="London, UK",
            remote="none",
            contract_type="stage",
            salary_min=10_000,
            salary_max=15_000,
        )
        with patch(
            "app.api.v1.endpoints.jobs.job_service.get_profile_dict",
            new_callable=AsyncMock,
            return_value=MOCK_PROFILE,
        ), patch(
            "app.api.v1.endpoints.jobs.job_service.get_jobs_for_matching",
            new_callable=AsyncMock,
            return_value=[job],
        ):
            resp = client.get("/api/v1/jobs/recommendations?min_score=70")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_results_ordered_by_score_descending(self, client):
        """Multiple jobs should be returned highest score first."""
        high_score_job = _mock_job(
            id=uuid.uuid4(),
            title="ML Engineer",
            required_skills=["python", "pytorch", "llm", "rag"],
            remote="full",
            contract_type="cdi",
            salary_min=55_000,
            salary_max=70_000,
        )
        low_score_job = _mock_job(
            id=uuid.uuid4(),
            title="COBOL Developer",
            required_skills=["cobol", "fortran"],
            remote="none",
            location="Unknown City, Nowhere",
            contract_type="stage",
            salary_min=15_000,
            salary_max=20_000,
        )
        with patch(
            "app.api.v1.endpoints.jobs.job_service.get_profile_dict",
            new_callable=AsyncMock,
            return_value=MOCK_PROFILE,
        ), patch(
            "app.api.v1.endpoints.jobs.job_service.get_jobs_for_matching",
            new_callable=AsyncMock,
            return_value=[low_score_job, high_score_job],  # low first intentionally
        ):
            resp = client.get("/api/v1/jobs/recommendations")

        data = resp.json()
        assert len(data) == 2
        # First result should have higher or equal total score than second
        assert data[0]["score"]["total"] >= data[1]["score"]["total"]

    def test_remote_only_filter_passed_to_service(self, client):
        """remote_only=true should be forwarded to get_jobs_for_matching."""
        with patch(
            "app.api.v1.endpoints.jobs.job_service.get_profile_dict",
            new_callable=AsyncMock,
            return_value=MOCK_PROFILE,
        ) as _, patch(
            "app.api.v1.endpoints.jobs.job_service.get_jobs_for_matching",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_get_jobs:
            resp = client.get("/api/v1/jobs/recommendations?remote_only=true")

        assert resp.status_code == 200
        mock_get_jobs.assert_called_once()
        call_kwargs = mock_get_jobs.call_args.kwargs
        assert call_kwargs.get("remote_only") is True

    def test_limit_param_respected(self, client):
        jobs = [_mock_job(id=uuid.uuid4()) for _ in range(10)]
        with patch(
            "app.api.v1.endpoints.jobs.job_service.get_profile_dict",
            new_callable=AsyncMock,
            return_value=MOCK_PROFILE,
        ), patch(
            "app.api.v1.endpoints.jobs.job_service.get_jobs_for_matching",
            new_callable=AsyncMock,
            return_value=jobs,
        ):
            resp = client.get("/api/v1/jobs/recommendations?limit=3")

        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_rejects_limit_above_200(self, client):
        resp = client.get("/api/v1/jobs/recommendations?limit=999")
        assert resp.status_code == 422

    def test_rejects_min_score_above_100(self, client):
        resp = client.get("/api/v1/jobs/recommendations?min_score=101")
        assert resp.status_code == 422
