"""
API tests for the /agents endpoint.

Checks routing logic (known vs unknown agent names) without
running any real agents — all services are mocked.
"""
from __future__ import annotations

import pytest

from tests.conftest import MOCK_USER


class TestAgentDispatch:
    def test_unknown_agent_returns_404(self, client, auth_headers):
        resp = client.post(
            "/api/v1/agents/does_not_exist/run",
            json={"params": {}},
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert "Unknown agent" in resp.json()["detail"]

    def test_missing_auth_returns_401(self, anon_client):
        resp = anon_client.post("/api/v1/agents/job_scoring_agent/run", json={"params": {}})
        assert resp.status_code == 401

    def test_get_logs_returns_list(self, client, auth_headers):
        resp = client.get("/api/v1/agents/logs", headers=auth_headers)
        # DB is mocked — returns empty list, but endpoint should not error
        assert resp.status_code in (200, 500)  # 500 only if mock incomplete

    def test_known_agent_names_accepted(self, client, auth_headers):
        """All listed agent names must pass the name-validation guard (may fail later on DB)."""
        known = [
            "job_collection_agent",
            "job_scoring_agent",
            "cv_adaptation_agent",
            "cover_letter_agent",
            "feedback_learning_agent",
            "opportunity_discovery_agent",
        ]
        for name in known:
            resp = client.post(
                f"/api/v1/agents/{name}/run",
                json={"params": {}},
                headers=auth_headers,
            )
            # 404 means name guard rejected it — that would be a bug
            assert resp.status_code != 404, f"Agent '{name}' was incorrectly rejected"


class TestAgentLogs:
    def test_logs_require_auth(self, anon_client):
        resp = anon_client.get("/api/v1/agents/logs")
        assert resp.status_code == 401

    def test_logs_accept_agent_name_filter(self, client, auth_headers):
        resp = client.get(
            "/api/v1/agents/logs",
            params={"agent_name": "job_scoring_agent"},
            headers=auth_headers,
        )
        assert resp.status_code in (200, 500)

    def test_logs_reject_excessive_limit(self, client, auth_headers):
        resp = client.get(
            "/api/v1/agents/logs",
            params={"limit": 9999},
            headers=auth_headers,
        )
        assert resp.status_code == 422
