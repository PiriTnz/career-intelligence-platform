"""
API tests for auth endpoints.

The DB is mocked — no PostgreSQL required.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import hash_password
from app.db.models import User
from app.main import app


class _MockResult:
    def __init__(self, value=None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


def _session_returning(value):
    s = AsyncMock()
    s.execute = AsyncMock(return_value=_MockResult(value))
    s.add = MagicMock()
    s.commit = AsyncMock()
    s.flush = AsyncMock()

    async def _refresh(obj):
        obj.id = uuid.uuid4()
        obj.is_active = True
        obj.created_at = "2024-01-01T00:00:00"

    s.refresh = _refresh
    return s


@pytest.fixture
def client_no_user():
    """TestClient with DB returning None (email not found)."""
    session = _session_returning(None)

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def existing_user():
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = "existing@example.com"
    user.name = "Existing User"
    user.is_active = True
    user.hashed_password = hash_password("password123")
    user.created_at = "2024-01-01T00:00:00"
    return user


@pytest.fixture
def client_with_user(existing_user):
    """TestClient with DB returning the existing user."""
    session = _session_returning(existing_user)

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


class TestRegisterEndpoint:
    def test_register_new_user_returns_201(self, client_no_user):
        resp = client_no_user.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": "StrongPass1", "name": "New User"},
        )
        assert resp.status_code == 201

    def test_register_weak_password_returns_422(self, client_no_user):
        resp = client_no_user.post(
            "/api/v1/auth/register",
            json={"email": "user@example.com", "password": "short"},
        )
        assert resp.status_code == 422

    def test_register_invalid_email_returns_422(self, client_no_user):
        resp = client_no_user.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "StrongPass1"},
        )
        assert resp.status_code == 422

    def test_register_duplicate_email_returns_409(self, client_with_user, existing_user):
        resp = client_with_user.post(
            "/api/v1/auth/register",
            json={"email": existing_user.email, "password": "StrongPass1"},
        )
        assert resp.status_code == 409

    def test_register_missing_email_returns_422(self, client_no_user):
        resp = client_no_user.post(
            "/api/v1/auth/register",
            json={"password": "StrongPass1"},
        )
        assert resp.status_code == 422


class TestLoginEndpoint:
    def test_login_valid_credentials_returns_token(self, client_with_user, existing_user):
        resp = client_with_user.post(
            "/api/v1/auth/login",
            json={"email": existing_user.email, "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password_returns_401(self, client_with_user, existing_user):
        resp = client_with_user.post(
            "/api/v1/auth/login",
            json={"email": existing_user.email, "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    def test_login_unknown_email_returns_401(self, client_no_user):
        resp = client_no_user.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": "password123"},
        )
        assert resp.status_code == 401

    def test_login_missing_fields_returns_422(self, client_no_user):
        resp = client_no_user.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422


class TestProtectedEndpoints:
    def test_users_me_without_token_returns_401(self):
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/v1/users/me")
        assert resp.status_code == 401

    def test_jobs_without_token_returns_401(self):
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/v1/jobs")
        assert resp.status_code == 401

    def test_profiles_without_token_returns_401(self):
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/v1/profiles/me")
        assert resp.status_code == 401
