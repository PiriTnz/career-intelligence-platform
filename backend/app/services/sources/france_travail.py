"""
France Travail (ex-Pôle Emploi) job search API client.

Auth: OAuth2 client_credentials
  POST https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire

Search: GET https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search

Pagination: `range` param (0-indexed, inclusive, max window 149 items per call).
The response header `Content-Range: offres 0-48/1234` tells the true total.

Security contract: this module NEVER logs the client_secret or the access_token.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
API_BASE_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2"
_SEARCH_URL = f"{API_BASE_URL}/offres/search"
_SCOPE = "api_offresdemploiv2 o2dsoffre"
_BATCH_SIZE = 149  # API max per range window (0-148 = 149 items)


# ── Token cache ───────────────────────────────────────────────────────────────

@dataclass
class _TokenCache:
    token: str = ""
    expires_at: float = 0.0          # monotonic seconds
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    def is_valid(self) -> bool:
        # Refresh 60 s before true expiry to avoid edge-case rejections
        return bool(self.token) and time.monotonic() < self.expires_at - 60


_cache = _TokenCache()


async def _get_token(client: httpx.AsyncClient) -> str | None:
    """Return a valid Bearer token, fetching a new one only when needed.

    Credentials are sent but NEVER logged.
    """
    async with _cache._lock:
        if _cache.is_valid():
            return _cache.token

        if not settings.france_travail_client_id or not settings.france_travail_client_secret:
            logger.warning("France Travail: credentials not configured in env")
            return None

        try:
            resp = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.france_travail_client_id,
                    "client_secret": settings.france_travail_client_secret,
                    "scope": _SCOPE,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Log status code only — never log response body (may echo credentials)
            logger.error(
                "France Travail token request failed: HTTP %s", exc.response.status_code
            )
            return None
        except Exception as exc:
            logger.error("France Travail token request error: %s", type(exc).__name__)
            return None

        body = resp.json()
        token = body.get("access_token", "")
        expires_in = int(body.get("expires_in", 1500))  # FT default ~25 min

        if not token:
            logger.error("France Travail: token response missing access_token field")
            return None

        _cache.token = token
        _cache.expires_at = time.monotonic() + expires_in
        logger.info("France Travail: token obtained (expires_in=%ds)", expires_in)
        return token


# ── Job search ────────────────────────────────────────────────────────────────

async def fetch_jobs(
    *,
    keywords: str = "AI Machine Learning MLOps",
    department: str = "69",   # Rhône / Lyon
    max_results: int = 300,
) -> list[dict]:
    """Fetch raw job listings from France Travail.

    Returns the raw France Travail dicts (not normalized).
    Returns [] when credentials are absent or the API fails.
    The Authorization header value is never logged.
    """
    async with httpx.AsyncClient() as client:
        token = await _get_token(client)
        if token is None:
            return []

        headers = {"Authorization": f"Bearer {token}"}
        jobs: list[dict] = []
        start = 0

        while start < max_results:
            end = min(start + _BATCH_SIZE, max_results) - 1
            try:
                resp = await client.get(
                    _SEARCH_URL,
                    params={
                        "motsCles": keywords,
                        "departement": department,
                        "range": f"{start}-{end}",
                        "sort": "1",      # most recent first
                        "publieeDepuis": "31",
                    },
                    headers=headers,
                    timeout=20,
                )
            except Exception as exc:
                logger.error(
                    "France Travail search request error (range %d-%d): %s",
                    start, end, type(exc).__name__,
                )
                break

            if resp.status_code == 204:
                # 204 No Content = no more results for this range
                break

            if resp.status_code not in (200, 206):
                logger.error(
                    "France Travail search HTTP %s (range %d-%d)",
                    resp.status_code, start, end,
                )
                break

            batch = resp.json().get("resultats", [])
            jobs.extend(batch)

            # Parse Content-Range to know true total, e.g. "offres 0-148/427"
            content_range = resp.headers.get("Content-Range", "")
            api_total = _parse_content_range_total(content_range)
            effective_max = min(max_results, api_total) if api_total else max_results

            if not batch or start + len(batch) >= effective_max:
                break

            start += len(batch)

        logger.info("France Travail: fetched %d jobs", len(jobs))
        return jobs


def _parse_content_range_total(header: str) -> int:
    """Parse 'offres 0-148/427' → 427. Returns 0 if unparseable."""
    # header format: "offres <start>-<end>/<total>"
    if "/" in header:
        try:
            return int(header.split("/")[-1].strip())
        except ValueError:
            pass
    return 0
