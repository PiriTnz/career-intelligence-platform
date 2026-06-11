"""
API tests for profile endpoints including CV upload.

All DB calls are mocked — no PostgreSQL required.
"""
from __future__ import annotations

import io
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
PROFILE_ID = uuid.uuid4()

# Minimal valid PDF bytes (%PDF magic + enough to not fail pypdf badly)
_FAKE_PDF = b"%PDF-1.4\n1 0 obj\n<</Type /Catalog>>\nendobj\n%%EOF"


def _mock_profile(**overrides) -> MagicMock:
    p = MagicMock()
    p.id = PROFILE_ID
    p.user_id = USER_ID
    p.version = 1
    p.target_roles = ["ML Engineer"]
    p.avoid_roles = []
    p.skills = ["python", "pytorch"]
    p.experience_level = "mid"
    p.salary_min = None
    p.salary_target = None
    p.remote_preference = False
    p.countries = ["france"]
    p.cities = ["lyon"]
    p.contract_types = []
    p.languages = ["fr", "en"]
    p.phone = None
    p.certifications = []
    p.education = []
    p.experience = []
    p.cv_file_path = None
    p.raw_json = None
    p.is_active = True
    p.created_at = NOW
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


def _mock_profile_version(**overrides) -> MagicMock:
    pv = MagicMock()
    pv.id = 1
    pv.user_id = USER_ID
    pv.profile_id = PROFILE_ID
    pv.version = 1
    pv.source = "cv_upload"
    pv.cv_file_path = "/tmp/test.pdf"
    pv.raw_text = "Sample CV text"
    pv.full_name = "Tanaz Piriaei"
    pv.phone = None
    pv.email_extracted = "tanaz@test.com"
    pv.location_raw = "Lyon"
    pv.education = []
    pv.experience = []
    pv.certifications = []
    pv.extracted_skills = ["python", "pytorch"]
    pv.inferred_skills = []
    pv.missing_fields = ["phone"]
    pv.suggested_roles = ["ML Engineer"]
    pv.extraction_confidence = 75
    pv.created_at = NOW
    for k, v in overrides.items():
        setattr(pv, k, v)
    return pv


# ── GET /profiles/me ──────────────────────────────────────────────────────────

class TestGetProfile:
    def test_requires_auth(self, anon_client):
        resp = anon_client.get("/api/v1/profiles/me")
        assert resp.status_code == 401

    def test_returns_404_when_no_profile(self, client):
        resp = client.get("/api/v1/profiles/me")
        assert resp.status_code == 404

    def test_returns_profile_when_found(self, client):
        profile = _mock_profile()
        session = make_mock_session(query_result=profile)

        async def _db():
            yield session

        app.dependency_overrides[get_db] = _db
        resp = client.get("/api/v1/profiles/me")
        app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 1
        assert "python" in data["skills"]


# ── POST /profiles/me ─────────────────────────────────────────────────────────

class TestCreateProfile:
    def test_requires_auth(self, anon_client):
        resp = anon_client.post("/api/v1/profiles/me", json={})
        assert resp.status_code == 401

    def test_creates_profile(self, client):
        profile = _mock_profile()

        with patch(
            "app.api.v1.endpoints.profiles.create_profile",
            new_callable=AsyncMock,
            return_value=profile,
        ):
            resp = client.post(
                "/api/v1/profiles/me",
                json={"skills": ["python", "pytorch"], "experience_level": "mid"},
            )

        assert resp.status_code == 201
        assert resp.json()["version"] == 1


# ── POST /profiles/upload-cv ──────────────────────────────────────────────────

class TestUploadCV:
    def test_requires_auth(self, anon_client):
        resp = anon_client.post(
            "/api/v1/profiles/upload-cv",
            files={"file": ("cv.pdf", _FAKE_PDF, "application/pdf")},
        )
        assert resp.status_code == 401

    def test_rejects_non_pdf_content_type(self, client):
        resp = client.post(
            "/api/v1/profiles/upload-cv",
            files={"file": ("cv.txt", b"plain text", "text/plain")},
        )
        assert resp.status_code == 422

    def test_rejects_fake_pdf_bytes(self, client):
        resp = client.post(
            "/api/v1/profiles/upload-cv",
            files={"file": ("cv.pdf", b"not a pdf", "application/pdf")},
        )
        assert resp.status_code == 422

    def test_successful_upload(self, client):
        profile = _mock_profile()
        pv = _mock_profile_version()

        with patch(
            "app.api.v1.endpoints.profiles.profile_service.create_profile_from_cv",
            new_callable=AsyncMock,
            return_value=(profile, pv),
        ), patch(
            "app.api.v1.endpoints.profiles.extract_text_from_pdf",
            return_value="Tanaz Piriaei\ntanaz@test.com\nPython PyTorch ML Engineer",
        ), patch(
            "os.makedirs"
        ), patch(
            "builtins.open", MagicMock()
        ):
            # DB session needs commit + refresh to not error
            session = make_mock_session()
            session.commit = AsyncMock()

            async def _db():
                yield session

            app.dependency_overrides[get_db] = _db
            resp = client.post(
                "/api/v1/profiles/upload-cv",
                files={"file": ("cv.pdf", _FAKE_PDF, "application/pdf")},
            )
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 201
        data = resp.json()
        assert "extraction_confidence" in data
        assert "profile_version" in data
        assert "missing_fields" in data
        assert "message" in data

    def test_upload_returns_skills(self, client):
        profile = _mock_profile(skills=["python", "pytorch", "docker"])
        pv = _mock_profile_version(
            extracted_skills=["python", "pytorch", "docker"],
            suggested_roles=["ML Engineer"],
        )

        with patch(
            "app.api.v1.endpoints.profiles.profile_service.create_profile_from_cv",
            new_callable=AsyncMock,
            return_value=(profile, pv),
        ), patch(
            "app.api.v1.endpoints.profiles.extract_text_from_pdf",
            return_value="Python PyTorch Docker",
        ), patch("os.makedirs"), patch("builtins.open", MagicMock()):
            session = make_mock_session()

            async def _db():
                yield session

            app.dependency_overrides[get_db] = _db
            resp = client.post(
                "/api/v1/profiles/upload-cv",
                files={"file": ("cv.pdf", _FAKE_PDF, "application/pdf")},
            )
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 201
        data = resp.json()
        assert isinstance(data["extracted_skills"], list)
        assert isinstance(data["suggested_roles"], list)


# ── GET /profiles/versions ────────────────────────────────────────────────────

class TestGetProfileVersions:
    def test_requires_auth(self, anon_client):
        resp = anon_client.get("/api/v1/profiles/versions")
        assert resp.status_code == 401

    def test_returns_empty_list_when_no_uploads(self, client):
        session = make_mock_session(query_result=None)

        async def _db():
            yield session

        app.dependency_overrides[get_db] = _db
        resp = client.get("/api/v1/profiles/versions")
        app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_list_of_versions(self, client):
        pv = _mock_profile_version()
        session = make_mock_session(query_result=pv)

        async def _db():
            yield session

        app.dependency_overrides[get_db] = _db
        resp = client.get("/api/v1/profiles/versions")
        app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        versions = resp.json()
        assert len(versions) >= 1
        assert versions[0]["extraction_confidence"] == 75
        assert versions[0]["source"] == "cv_upload"
