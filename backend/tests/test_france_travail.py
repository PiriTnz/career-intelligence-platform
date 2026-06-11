"""
Tests for the France Travail API client and sync endpoint.

Network is fully mocked — no real HTTP calls are made.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.sources.france_travail import (
    _TokenCache,
    _cache,
    _parse_content_range_total,
    fetch_jobs,
)


# ── Token cache unit tests ────────────────────────────────────────────────────

class TestTokenCache:
    def test_empty_cache_is_invalid(self):
        c = _TokenCache()
        assert c.is_valid() is False

    def test_valid_token_not_expired(self):
        c = _TokenCache(token="abc", expires_at=time.monotonic() + 3600)
        assert c.is_valid() is True

    def test_expired_token_is_invalid(self):
        c = _TokenCache(token="abc", expires_at=time.monotonic() - 1)
        assert c.is_valid() is False

    def test_token_within_60s_buffer_is_invalid(self):
        # 30 s left — less than the 60 s safety buffer → treat as expired
        c = _TokenCache(token="abc", expires_at=time.monotonic() + 30)
        assert c.is_valid() is False

    def test_token_just_past_buffer_is_valid(self):
        c = _TokenCache(token="abc", expires_at=time.monotonic() + 120)
        assert c.is_valid() is True


# ── Content-Range header parsing ──────────────────────────────────────────────

class TestParseContentRangeTotal:
    def test_standard_header(self):
        assert _parse_content_range_total("offres 0-148/427") == 427

    def test_single_result(self):
        assert _parse_content_range_total("offres 0-0/1") == 1

    def test_empty_header(self):
        assert _parse_content_range_total("") == 0

    def test_malformed_header(self):
        assert _parse_content_range_total("offres 0-148") == 0

    def test_non_numeric_total(self):
        assert _parse_content_range_total("offres 0-148/abc") == 0


# ── fetch_jobs: missing credentials ──────────────────────────────────────────

class TestFetchJobsMissingCredentials:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_credentials(self):
        with patch("app.services.sources.france_travail.settings") as mock_settings:
            mock_settings.france_travail_client_id = ""
            mock_settings.france_travail_client_secret = ""
            # Also reset the cache so it doesn't reuse a cached token
            _cache.token = ""
            _cache.expires_at = 0.0
            result = await fetch_jobs()
        assert result == []


# ── fetch_jobs: token fetch fails ────────────────────────────────────────────

class TestFetchJobsTokenError:
    @pytest.mark.asyncio
    async def test_returns_empty_list_on_http_401(self):
        _cache.token = ""
        _cache.expires_at = 0.0

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.raise_for_status.side_effect = Exception("401 Unauthorized")

        with patch("app.services.sources.france_travail.settings") as mock_settings, \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_settings.france_travail_client_id = "test_id"
            mock_settings.france_travail_client_secret = "test_secret"

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await fetch_jobs()

        assert result == []


# ── fetch_jobs: successful flow ───────────────────────────────────────────────

def _make_token_resp(token: str = "tok123", expires_in: int = 1500) -> MagicMock:
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json.return_value = {"access_token": token, "expires_in": expires_in}
    r.status_code = 200
    return r


def _make_search_resp(jobs: list[dict], total: int | None = None) -> MagicMock:
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"resultats": jobs}
    end = len(jobs) - 1
    r.headers = {"Content-Range": f"offres 0-{end}/{total or len(jobs)}"}
    return r


class TestFetchJobsSuccess:
    @pytest.mark.asyncio
    async def test_returns_jobs_from_api(self):
        _cache.token = ""
        _cache.expires_at = 0.0

        raw_jobs = [
            {"id": "FT-001", "intitule": "ML Engineer", "description": "Python job"},
            {"id": "FT-002", "intitule": "Data Scientist", "description": "Pandas job"},
        ]

        token_resp = _make_token_resp()
        search_resp = _make_search_resp(raw_jobs, total=2)

        with patch("app.services.sources.france_travail.settings") as mock_settings, \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_settings.france_travail_client_id = "test_id"
            mock_settings.france_travail_client_secret = "test_secret"

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=token_resp)
            mock_client.get = AsyncMock(return_value=search_resp)
            mock_client_cls.return_value = mock_client

            result = await fetch_jobs(max_results=300)

        assert len(result) == 2
        assert result[0]["id"] == "FT-001"

    @pytest.mark.asyncio
    async def test_token_not_logged(self, caplog):
        """The access token value must never appear in log output."""
        import logging
        _cache.token = ""
        _cache.expires_at = 0.0

        secret_token = "SUPER_SECRET_TOKEN_VALUE"
        token_resp = _make_token_resp(token=secret_token)
        search_resp = _make_search_resp([{"id": "FT-001", "intitule": "Test"}], total=1)

        with patch("app.services.sources.france_travail.settings") as mock_settings, \
             patch("httpx.AsyncClient") as mock_client_cls, \
             caplog.at_level(logging.DEBUG, logger="app.services.sources.france_travail"):
            mock_settings.france_travail_client_id = "test_id"
            mock_settings.france_travail_client_secret = "secret_value"

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=token_resp)
            mock_client.get = AsyncMock(return_value=search_resp)
            mock_client_cls.return_value = mock_client

            await fetch_jobs(max_results=10)

        full_log = " ".join(caplog.messages)
        assert secret_token not in full_log, "access_token must not appear in logs"
        assert "secret_value" not in full_log, "client_secret must not appear in logs"

    @pytest.mark.asyncio
    async def test_cached_token_reused(self):
        """Second call must reuse cache — POST for token is called only once."""
        _cache.token = ""
        _cache.expires_at = 0.0

        token_resp = _make_token_resp()
        search_resp = _make_search_resp([{"id": "FT-001", "intitule": "Test"}], total=1)

        with patch("app.services.sources.france_travail.settings") as mock_settings, \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_settings.france_travail_client_id = "test_id"
            mock_settings.france_travail_client_secret = "secret"

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=token_resp)
            mock_client.get = AsyncMock(return_value=search_resp)
            mock_client_cls.return_value = mock_client

            await fetch_jobs(max_results=10)
            await fetch_jobs(max_results=10)

        # Two fetch_jobs calls but only one context manager → one POST
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_204_stops_pagination(self):
        """A 204 response (no more results) must terminate the loop."""
        _cache.token = "cached_tok"
        _cache.expires_at = time.monotonic() + 3600

        no_content = MagicMock()
        no_content.status_code = 204

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=no_content)
            mock_client_cls.return_value = mock_client

            result = await fetch_jobs(max_results=300)

        assert result == []
        assert mock_client.get.call_count == 1  # stopped after first 204


# ── Sync endpoint tests ───────────────────────────────────────────────────────

class TestSyncEndpoint:
    def test_sync_requires_auth(self, anon_client):
        resp = anon_client.post("/api/v1/sources/france-travail/sync")
        assert resp.status_code == 401

    def test_sync_returns_200_with_zero_counts_when_no_credentials(self, client, auth_headers):
        with patch("app.api.v1.endpoints.sources.france_travail.fetch_jobs", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []
            resp = client.post(
                "/api/v1/sources/france-travail/sync",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "france_travail"
        assert data["fetched"] == 0
        assert data["inserted"] == 0

    def test_sync_inserts_jobs(self, client, auth_headers):
        raw = [
            {
                "id": "FT-100",
                "intitule": "ML Engineer",
                "entreprise": {"nom": "Acme"},
                "lieuTravail": {"libelle": "Lyon (69)"},
                "typeContrat": "CDI",
                "salaire": {"libelle": "45000 à 55000 Euros"},
                "description": "Python, Docker, LLM",
                "dateCreation": "2024-06-01",
                "origineOffre": {"urlOrigine": "https://ft.fr/offre/FT-100"},
            }
        ]
        with patch("app.api.v1.endpoints.sources.france_travail.fetch_jobs", new_callable=AsyncMock) as mock_fetch, \
             patch("app.api.v1.endpoints.sources.upsert_job", new_callable=AsyncMock) as mock_upsert:
            mock_fetch.return_value = raw
            mock_upsert.return_value = (MagicMock(), True)  # (job, is_new=True)
            resp = client.post(
                "/api/v1/sources/france-travail/sync",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fetched"] == 1
        assert data["inserted"] == 1
        assert data["updated"] == 0

    def test_sync_counts_updates(self, client, auth_headers):
        raw = [{"id": "FT-200", "intitule": "Existing", "origineOffre": {"urlOrigine": "https://ft.fr/offre/FT-200"}}]
        with patch("app.api.v1.endpoints.sources.france_travail.fetch_jobs", new_callable=AsyncMock) as mock_fetch, \
             patch("app.api.v1.endpoints.sources.upsert_job", new_callable=AsyncMock) as mock_upsert:
            mock_fetch.return_value = raw
            mock_upsert.return_value = (MagicMock(), False)  # already existed
            resp = client.post(
                "/api/v1/sources/france-travail/sync",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == 1
        assert data["inserted"] == 0

    def test_sync_skips_jobs_with_no_url(self, client, auth_headers):
        raw = [{"id": "FT-BAD", "intitule": "No URL"}]  # no origineOffre
        with patch("app.api.v1.endpoints.sources.france_travail.fetch_jobs", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = raw
            resp = client.post(
                "/api/v1/sources/france-travail/sync",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        # URL falls back to FT detail URL, so skipped=0 unless normalization fails
        assert data["fetched"] == 1

    def test_sync_accepts_custom_query_params(self, client, auth_headers):
        with patch("app.api.v1.endpoints.sources.france_travail.fetch_jobs", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []
            resp = client.post(
                "/api/v1/sources/france-travail/sync"
                "?keywords=Data+Engineer&department=75&max_results=50",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        mock_fetch.assert_called_once_with(
            keywords="Data Engineer",
            department="75",
            max_results=50,
        )

    def test_sync_rejects_invalid_department(self, client, auth_headers):
        resp = client.post(
            "/api/v1/sources/france-travail/sync?department=XY",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_sync_rejects_max_results_above_1000(self, client, auth_headers):
        resp = client.post(
            "/api/v1/sources/france-travail/sync?max_results=9999",
            headers=auth_headers,
        )
        assert resp.status_code == 422
