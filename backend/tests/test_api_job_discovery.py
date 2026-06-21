"""
Tests for the three job-discovery endpoints:
  POST /jobs/discover  — search Adzuna
  POST /jobs/import    — import from URL
  POST /jobs/manual    — manual entry
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import USER_ID, make_mock_session

JOB_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


# ── Shared mock factories ─────────────────────────────────────────────────────

def _mock_job(title: str = "ML Engineer", source: str = "adzuna") -> MagicMock:
    job = MagicMock()
    job.id = JOB_ID
    job.title = title
    job.company_name = "Acme Corp"
    job.location = "Paris, France"
    job.remote = "hybrid"
    job.contract_type = "cdi"
    job.salary_min = 50_000
    job.salary_max = 70_000
    job.required_skills = ["Python", "ML"]
    job.url = "https://example.com/jobs/1"
    job.source = source
    job.description = "Great ML job in Paris."
    return job


def _mock_breakdown() -> MagicMock:
    bd = MagicMock()
    bd.total = 82
    bd.skill_match = 75
    bd.experience_match = 80
    bd.location_score = 90
    bd.salary_score = 85
    bd.contract_score = 100
    bd.company_score = 60
    bd.freshness_score = 70
    bd.needs_review = False
    return bd


# ── POST /jobs/discover ───────────────────────────────────────────────────────

class TestDiscover:
    @patch("app.api.v1.endpoints.jobs.settings")
    @patch("app.api.v1.endpoints.jobs.adzuna.fetch_jobs", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.job_service.get_profile_dict", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.job_service.upsert_job", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.scoring_service.score_job")
    @patch("app.api.v1.endpoints.jobs.scoring_service.save_score", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.normalizer.normalize")
    def test_discover_returns_new_jobs(
        self, mock_normalize, mock_save, mock_score, mock_upsert,
        mock_profile, mock_fetch, mock_settings, client,
    ):
        mock_settings.adzuna_app_id = "test_id"
        mock_settings.adzuna_app_key = "test_key"

        raw = {"id": "x", "title": "ML Engineer", "redirect_url": "https://example.com/1"}
        mock_fetch.return_value = [raw]
        mock_profile.return_value = {"version": 1, "skills": ["Python"]}
        mock_normalize.return_value = {
            "url": "https://example.com/1",
            "title": "ML Engineer",
            "company_name": "Acme",
            "location": "Paris",
            "remote": "none",
            "contract_type": "cdi",
            "salary_min": None,
            "salary_max": None,
            "required_skills": ["Python"],
            "source": "adzuna",
        }

        job = _mock_job()
        mock_upsert.return_value = (job, True)
        mock_score.return_value = (_mock_breakdown(), 0.9)

        resp = client.post("/api/v1/jobs/discover", json={"keywords": "ML Python", "location": "Paris"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["new_count"] == 1
        assert body["total_count"] == 1
        assert body["jobs"][0]["title"] == "ML Engineer"
        assert body["jobs"][0]["is_new"] is True

    @patch("app.api.v1.endpoints.jobs.settings")
    @patch("app.api.v1.endpoints.jobs.job_service.get_profile_dict", new_callable=AsyncMock)
    def test_discover_no_adzuna_credentials_returns_empty(
        self, mock_profile, mock_settings, client,
    ):
        mock_settings.adzuna_app_id = ""
        mock_settings.adzuna_app_key = ""
        mock_profile.return_value = {}

        resp = client.post("/api/v1/jobs/discover", json={"keywords": "dev", "location": "Lyon"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 0
        assert body["jobs"] == []

    @patch("app.api.v1.endpoints.jobs.settings")
    @patch("app.api.v1.endpoints.jobs.adzuna.fetch_jobs", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.job_service.get_profile_dict", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.job_service.upsert_job", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.normalizer.normalize")
    def test_discover_existing_job_not_rescored(
        self, mock_normalize, mock_upsert, mock_profile, mock_fetch, mock_settings, client,
    ):
        mock_settings.adzuna_app_id = "id"
        mock_settings.adzuna_app_key = "key"
        mock_fetch.return_value = [{"id": "y"}]
        mock_profile.return_value = {"version": 1}
        mock_normalize.return_value = {
            "url": "https://example.com/2",
            "title": "Dev",
            "company_name": "Corp",
            "source": "adzuna",
        }
        job = _mock_job(title="Dev")
        mock_upsert.return_value = (job, False)  # already exists

        resp = client.post("/api/v1/jobs/discover", json={"keywords": "dev", "location": "France"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["new_count"] == 0
        assert body["jobs"][0]["is_new"] is False
        assert body["jobs"][0]["score_total"] is None

    @patch("app.api.v1.endpoints.jobs.settings")
    @patch("app.api.v1.endpoints.jobs.adzuna.fetch_jobs", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.job_service.get_profile_dict", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.job_service.upsert_job", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.normalizer.normalize")
    def test_discover_filters_remote_only(
        self, mock_normalize, mock_upsert, mock_profile, mock_fetch, mock_settings, client,
    ):
        mock_settings.adzuna_app_id = "id"
        mock_settings.adzuna_app_key = "key"
        mock_fetch.return_value = [{"id": "z"}]
        mock_profile.return_value = {}
        mock_normalize.return_value = {
            "url": "https://example.com/3",
            "title": "Dev",
            "company_name": "Corp",
            "remote": "none",
            "source": "adzuna",
        }
        job = _mock_job()
        mock_upsert.return_value = (job, True)

        resp = client.post("/api/v1/jobs/discover", json={"keywords": "dev", "location": "France", "remote_only": True})
        assert resp.status_code == 200
        # non-remote job filtered out
        assert resp.json()["total_count"] == 0

    def test_discover_unauthenticated(self, anon_client):
        resp = anon_client.post("/api/v1/jobs/discover", json={"keywords": "dev", "location": "France"})
        assert resp.status_code == 401

    def test_discover_missing_keywords_uses_default(self, client):
        with (
            patch("app.api.v1.endpoints.jobs.settings") as ms,
            patch("app.api.v1.endpoints.jobs.job_service.get_profile_dict", new_callable=AsyncMock) as mp,
        ):
            ms.adzuna_app_id = ""
            mp.return_value = {}
            resp = client.post("/api/v1/jobs/discover", json={})
            assert resp.status_code == 200


# ── POST /jobs/import ─────────────────────────────────────────────────────────

class TestImport:
    @patch("app.api.v1.endpoints.jobs.job_import_service.fetch_and_parse", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.job_service.get_profile_dict", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.job_service.upsert_job", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.scoring_service.score_job")
    @patch("app.api.v1.endpoints.jobs.scoring_service.save_score", new_callable=AsyncMock)
    def test_import_success(
        self, mock_save, mock_score, mock_upsert, mock_profile, mock_fetch_parse, client,
    ):
        mock_fetch_parse.return_value = {
            "url": "https://example.com/job",
            "title": "Data Engineer",
            "company_name": "TechCo",
            "location": "Lyon",
            "remote": "hybrid",
            "contract_type": "cdi",
            "salary_min": 45_000,
            "salary_max": 60_000,
            "required_skills": ["Spark", "Python"],
            "source": "import",
        }
        mock_profile.return_value = {"version": 1, "skills": ["Python"]}
        job = _mock_job(title="Data Engineer", source="import")
        mock_upsert.return_value = (job, True)
        mock_score.return_value = (_mock_breakdown(), 0.85)

        resp = client.post("/api/v1/jobs/import", json={"url": "https://example.com/job"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_new"] is True
        assert body["score_total"] == 82

    @patch("app.api.v1.endpoints.jobs.job_import_service.fetch_and_parse", new_callable=AsyncMock)
    def test_import_bad_url_returns_422(self, mock_fetch_parse, client):
        mock_fetch_parse.side_effect = ValueError("HTTP 404 fetching URL")
        resp = client.post("/api/v1/jobs/import", json={"url": "https://example.com/missing"})
        assert resp.status_code == 422
        assert "404" in resp.json()["detail"]

    def test_import_missing_url_returns_422(self, client):
        resp = client.post("/api/v1/jobs/import", json={})
        assert resp.status_code == 422

    def test_import_too_short_url_returns_422(self, client):
        resp = client.post("/api/v1/jobs/import", json={"url": "http://x"})
        assert resp.status_code == 422

    @patch("app.api.v1.endpoints.jobs.job_import_service.fetch_and_parse", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.job_service.get_profile_dict", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.job_service.upsert_job", new_callable=AsyncMock)
    def test_import_existing_job_not_rescored(
        self, mock_upsert, mock_profile, mock_fetch_parse, client,
    ):
        mock_fetch_parse.return_value = {
            "url": "https://example.com/job",
            "title": "Dev",
            "company_name": "Corp",
            "source": "import",
        }
        mock_profile.return_value = {}
        job = _mock_job()
        mock_upsert.return_value = (job, False)

        resp = client.post("/api/v1/jobs/import", json={"url": "https://example.com/job"})
        assert resp.status_code == 200
        assert resp.json()["is_new"] is False
        assert resp.json()["score_total"] is None

    def test_import_unauthenticated(self, anon_client):
        resp = anon_client.post("/api/v1/jobs/import", json={"url": "https://example.com/job"})
        assert resp.status_code == 401


# ── POST /jobs/manual ─────────────────────────────────────────────────────────

class TestManual:
    VALID_BODY = {
        "title": "Senior Python Dev",
        "company_name": "Startup SAS",
        "location": "Remote",
        "remote": "full",
        "contract_type": "cdi",
        "salary_min": 55_000,
        "salary_max": 75_000,
        "description": "Build scalable Python APIs with FastAPI and PostgreSQL.",
        "required_skills": ["Python", "FastAPI", "PostgreSQL"],
    }

    @patch("app.api.v1.endpoints.jobs.job_service.get_profile_dict", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.job_service.upsert_job", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.scoring_service.score_job")
    @patch("app.api.v1.endpoints.jobs.scoring_service.save_score", new_callable=AsyncMock)
    def test_manual_create_success(
        self, mock_save, mock_score, mock_upsert, mock_profile, client,
    ):
        mock_profile.return_value = {"version": 1, "skills": ["Python"]}
        job = _mock_job(title="Senior Python Dev", source="manual")
        mock_upsert.return_value = (job, True)
        mock_score.return_value = (_mock_breakdown(), 0.88)

        resp = client.post("/api/v1/jobs/manual", json=self.VALID_BODY)
        assert resp.status_code == 201
        body = resp.json()
        assert body["is_new"] is True
        assert body["score_total"] == 82

    @patch("app.api.v1.endpoints.jobs.job_service.get_profile_dict", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.job_service.upsert_job", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.scoring_service.score_job")
    @patch("app.api.v1.endpoints.jobs.scoring_service.save_score", new_callable=AsyncMock)
    def test_manual_generates_url_when_absent(
        self, mock_save, mock_score, mock_upsert, mock_profile, client,
    ):
        mock_profile.return_value = {}
        job = _mock_job(source="manual")
        mock_upsert.return_value = (job, True)
        mock_score.return_value = (_mock_breakdown(), 0.7)

        body = {k: v for k, v in self.VALID_BODY.items()}
        body.pop("description", None)

        # Capture what was passed to upsert_job
        captured = {}

        async def _capture(db, data):
            captured.update(data)
            return (job, True)

        mock_upsert.side_effect = _capture

        resp = client.post("/api/v1/jobs/manual", json=body)
        assert resp.status_code == 201
        assert captured.get("url", "").startswith("manual://")

    @patch("app.api.v1.endpoints.jobs.job_service.get_profile_dict", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.job_service.upsert_job", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.scoring_service.score_job")
    @patch("app.api.v1.endpoints.jobs.scoring_service.save_score", new_callable=AsyncMock)
    def test_manual_extracts_skills_from_description(
        self, mock_save, mock_score, mock_upsert, mock_profile, client,
    ):
        mock_profile.return_value = {}
        job = _mock_job(source="manual")
        mock_upsert.return_value = (job, True)
        mock_score.return_value = (_mock_breakdown(), 0.7)

        captured = {}

        async def _capture(db, data):
            captured.update(data)
            return (job, True)

        mock_upsert.side_effect = _capture

        body = {"title": "Dev", "company_name": "Corp", "description": "Needs Python and Docker expertise."}
        resp = client.post("/api/v1/jobs/manual", json=body)
        assert resp.status_code == 201
        # skills should have been extracted from description
        assert isinstance(captured.get("required_skills"), list)

    def test_manual_missing_title_returns_422(self, client):
        resp = client.post("/api/v1/jobs/manual", json={"company_name": "Corp"})
        assert resp.status_code == 422

    def test_manual_missing_company_returns_422(self, client):
        resp = client.post("/api/v1/jobs/manual", json={"title": "Dev"})
        assert resp.status_code == 422

    def test_manual_unauthenticated(self, anon_client):
        resp = anon_client.post("/api/v1/jobs/manual", json=self.VALID_BODY)
        assert resp.status_code == 401

    @patch("app.api.v1.endpoints.jobs.job_service.get_profile_dict", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.job_service.upsert_job", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.jobs.scoring_service.score_job")
    @patch("app.api.v1.endpoints.jobs.scoring_service.save_score", new_callable=AsyncMock)
    def test_manual_custom_url_preserved(
        self, mock_save, mock_score, mock_upsert, mock_profile, client,
    ):
        mock_profile.return_value = {}
        job = _mock_job(source="manual")
        mock_upsert.return_value = (job, True)
        mock_score.return_value = (_mock_breakdown(), 0.7)

        captured = {}

        async def _capture(db, data):
            captured.update(data)
            return (job, True)

        mock_upsert.side_effect = _capture

        body = {**self.VALID_BODY, "url": "https://my-company.fr/careers/dev"}
        resp = client.post("/api/v1/jobs/manual", json=body)
        assert resp.status_code == 201
        assert captured["url"] == "https://my-company.fr/careers/dev"
