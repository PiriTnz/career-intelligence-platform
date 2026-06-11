"""
Shared fixtures for all test modules.

Strategy:
  - Pure-function tests (scoring, normalizer, security) need no fixtures.
  - API tests override get_db and get_current_active_user so PostgreSQL
    is not required for the test suite to run.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_active_user, get_current_user
from app.core.database import get_db
from app.core.security import create_access_token
from app.db.models import User
from app.main import app


# ── Suppress the lifespan DB connection for all API tests ─────────────────────

@asynccontextmanager
async def _noop_lifespan(app):
    yield


@pytest.fixture(autouse=True)
def _patch_lifespan(request):
    """Prevent the FastAPI lifespan from attempting a real DB connection.

    Pure unit tests (no 'client' fixture) skip this without side effects
    because patching router.lifespan_context has no impact on pure functions.
    """
    with patch.object(app.router, "lifespan_context", _noop_lifespan):
        yield


# ── Mock DB session ───────────────────────────────────────────────────────────

class _MockResult:
    """Wraps a value to mimic SQLAlchemy's CursorResult interface."""

    def __init__(self, value=None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return [self._value] if self._value is not None else []


def make_mock_session(query_result=None) -> AsyncMock:
    """Return an AsyncMock session where execute() returns query_result."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_MockResult(query_result))
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.rollback = AsyncMock()

    async def _refresh(obj):
        pass

    session.refresh = _refresh
    return session


# ── Mock user ─────────────────────────────────────────────────────────────────

USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _make_user() -> MagicMock:
    user = MagicMock(spec=User)
    user.id = USER_ID
    user.email = "tanaz@test.com"
    user.name = "Tanaz Test"
    user.is_active = True
    user.hashed_password = "hashed_pw"
    return user


MOCK_USER = _make_user()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_session():
    """A default mock session — execute returns None."""
    return make_mock_session(query_result=None)


@pytest.fixture
def client(mock_session):
    """TestClient with DB and auth overridden — acts as authenticated user."""
    async def _override_db():
        yield mock_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    app.dependency_overrides[get_current_active_user] = lambda: MOCK_USER

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def anon_client(mock_session):
    """TestClient with DB overridden but real JWT auth — unauthenticated caller gets 401."""
    async def _override_db():
        yield mock_session

    app.dependency_overrides[get_db] = _override_db

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def auth_token() -> str:
    return create_access_token(subject=str(USER_ID))


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}"}
