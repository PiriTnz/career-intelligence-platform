"""
API tests for /scores endpoints.

All DB calls are mocked — no PostgreSQL required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.api.deps import get_current_active_user, get_current_user
from app.main import app
from tests.conftest import MOCK_USER, USER_ID, make_mock_session


# ── Helpers ───────────────────────────────────────────────────────────────────

JOB_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
SCORE_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

NOW = datetime.now(timezone.utc)


def _mock_score(**overrides) -> MagicMock:
    s = MagicMock()
    s.id = SCORE_ID
    s.job_id = JOB_ID
    s.user_id = USER_ID
    s.profile_version = 1
    s.skill_match = 24
    s.experience_match = 20
    s.location_score = 15
    s.salary_score = 12
    s.contract_score = 10
    s.company_score = 3
    s.freshness_score = 5
    s.total = 89
    s.extraction_confidence = 100
    s.needs_review = False
    s.llm_explanation = None
    s.created_at = NOW
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def _mock_job(**overrides) -> MagicMock:
    j = MagicMock()
    j.id = JOB_ID
    j.title = "ML Engineer"
    j.company_name = "Acme"
    j.location = "Lyon, France"
    j.remote = "full"
    j.contract_type = "cdi"
    j.salary_min = 50_000
    j.salary_max = 65_000
    j.required_skills = ["python", "fastapi", "docker"]
    j.experience_level = "mid"
    j.language = "fr"
    j.description = "Python, FastAPI, Docker"
    j.published_at = NOW
    j.url = "https://ft.fr/offre/FT-001"
    for k, v in overrides.items():
        setattr(j, k, v)
    return j


# ── GET /scores (list) ────────────────────────────────────────────────────────

class TestListScores:
    def test_requires_auth(self, anon_client):
        resp = anon_client.get("/api/v1/scores")
        assert resp.status_code == 401

    def test_returns_200_empty_list(self, client, auth_headers):
        # execute returns an iterable of (score, job) tuples — empty
        session = make_mock_session()
        session.execute = AsyncMock(return_value=iter([]))

        async def _db():
            yield session

        app.dependency_overrides[get_db] = _db
        resp = client.get("/api/v1/scores", headers=auth_headers)
        app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_scored_jobs_ordered_by_total(self, client, auth_headers):
        score = _mock_score()
        job = _mock_job()

        session = make_mock_session()
        session.execute = AsyncMock(return_value=iter([(score, job)]))

        async def _db():
            yield session

        app.dependency_overrides[get_db] = _db
        resp = client.get("/api/v1/scores", headers=auth_headers)
        app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["total"] == 89
        assert data[0]["job_title"] == "ML Engineer"
        assert data[0]["company_name"] == "Acme"

    def test_min_score_param_accepted(self, client, auth_headers):
        session = make_mock_session()
        session.execute = AsyncMock(return_value=iter([]))

        async def _db():
            yield session

        app.dependency_overrides[get_db] = _db
        resp = client.get("/api/v1/scores?min_score=75", headers=auth_headers)
        app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200

    def test_rejects_limit_above_200(self, client, auth_headers):
        resp = client.get("/api/v1/scores?limit=999", headers=auth_headers)
        assert resp.status_code == 422


# ── GET /scores/{job_id} ──────────────────────────────────────────────────────

class TestGetScore:
    def test_requires_auth(self, anon_client):
        resp = anon_client.get(f"/api/v1/scores/{JOB_ID}")
        assert resp.status_code == 401

    def test_returns_404_when_not_found(self, client, auth_headers):
        session = make_mock_session(query_result=None)

        async def _db():
            yield session

        app.dependency_overrides[get_db] = _db
        resp = client.get(f"/api/v1/scores/{JOB_ID}", headers=auth_headers)
        app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404

    def test_returns_score_when_found(self, client, auth_headers):
        score = _mock_score()
        session = make_mock_session(query_result=score)

        async def _db():
            yield session

        app.dependency_overrides[get_db] = _db
        resp = client.get(f"/api/v1/scores/{JOB_ID}", headers=auth_headers)
        app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        assert resp.json()["total"] == 89
        assert resp.json()["skill_match"] == 24


# ── POST /scores/{job_id}/compute ─────────────────────────────────────────────

class TestComputeScore:
    def test_requires_auth(self, anon_client):
        resp = anon_client.post(f"/api/v1/scores/{JOB_ID}/compute")
        assert resp.status_code == 401

    def test_returns_404_when_job_missing(self, client, auth_headers):
        session = make_mock_session(query_result=None)

        async def _db():
            yield session

        app.dependency_overrides[get_db] = _db
        resp = client.post(f"/api/v1/scores/{JOB_ID}/compute", headers=auth_headers)
        app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404

    def test_returns_400_when_no_profile(self, client, auth_headers):
        job = _mock_job()

        call_count = 0

        class _MultiResult:
            def __init__(self):
                pass
            def scalar_one_or_none(self):
                nonlocal call_count
                call_count += 1
                # First call returns job, second returns None (no profile)
                return job if call_count == 1 else None
            def scalars(self):
                return self
            def all(self):
                return []

        session = MagicMock()
        session.execute = AsyncMock(return_value=_MultiResult())
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.refresh = AsyncMock()

        async def _db():
            yield session

        app.dependency_overrides[get_db] = _db
        resp = client.post(f"/api/v1/scores/{JOB_ID}/compute", headers=auth_headers)
        app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 400
        assert "profile" in resp.json()["detail"].lower()


# ── POST /scores/batch-compute ────────────────────────────────────────────────

class TestBatchComputeScores:
    def test_requires_auth(self, anon_client):
        resp = anon_client.post("/api/v1/scores/batch-compute")
        assert resp.status_code == 401

    def test_returns_400_when_no_profile(self, client, auth_headers):
        # All queries return None — no profile found
        session = make_mock_session(query_result=None)

        async def _db():
            yield session

        app.dependency_overrides[get_db] = _db
        resp = client.post("/api/v1/scores/batch-compute", headers=auth_headers)
        app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 400

    def test_rejects_limit_above_2000(self, client, auth_headers):
        resp = client.post(
            "/api/v1/scores/batch-compute?limit=9999",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_scores_unscored_jobs(self, client, auth_headers):
        """When profile exists and jobs are present, returns scored count."""
        job = _mock_job()
        score = _mock_score()

        # We need to patch the service functions to avoid complex DB mock setup
        with patch("app.api.v1.endpoints.scores.job_service.get_profile_dict", new_callable=AsyncMock) as mock_profile, \
             patch("app.api.v1.endpoints.scores.scoring_service.save_score", new_callable=AsyncMock) as mock_save:

            mock_profile.return_value = {
                "skills": ["python", "fastapi", "docker"],
                "experience_level": "mid",
                "salary_min": 40_000,
                "salary_target": 55_000,
                "remote_preference": True,
                "cities": ["lyon"],
                "countries": ["france"],
                "contract_types": ["cdi"],
                "version": 1,
            }
            mock_save.return_value = score

            # DB session: first execute returns existing scores (empty), second returns jobs
            class _SequencedResult:
                _calls = 0
                def scalar_one_or_none(self):
                    return None
                def scalars(self):
                    return self
                def all(self):
                    self._calls += 1
                    return [] if self._calls == 1 else [job]

            session = MagicMock()
            seq = _SequencedResult()
            session.execute = AsyncMock(return_value=seq)
            session.add = MagicMock()
            session.flush = AsyncMock()
            session.commit = AsyncMock()
            session.rollback = AsyncMock()
            session.refresh = AsyncMock()

            async def _db():
                yield session

            app.dependency_overrides[get_db] = _db
            resp = client.post("/api/v1/scores/batch-compute", headers=auth_headers)
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert "scored" in data
        assert "skipped" in data
        assert "profile_version" in data
        assert data["profile_version"] == 1
