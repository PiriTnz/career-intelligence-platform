"""
Adzuna job search API client.

Docs: https://developer.adzuna.com/docs/search
Auth: app_id + app_key as query parameters
Search: GET https://api.adzuna.com/v1/api/jobs/fr/search/{page}
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.adzuna.com/v1/api/jobs/fr/search"


async def fetch_jobs(
    keywords: str = "AI Machine Learning MLOps LLM",
    location: str = "Lyon",
    max_results: int = 100,
) -> list[dict]:
    """
    Fetch job listings from Adzuna France.
    Returns [] if credentials are missing or the API fails.
    """
    if not settings.adzuna_app_id:
        logger.warning("Adzuna: no credentials configured — skipping")
        return []

    page_size = 50
    jobs: list[dict] = []

    async with httpx.AsyncClient() as client:
        for page in range(1, (max_results // page_size) + 2):
            try:
                resp = await client.get(
                    f"{_BASE_URL}/{page}",
                    params={
                        "app_id": settings.adzuna_app_id,
                        "app_key": settings.adzuna_app_key,
                        "what": keywords,
                        "where": location,
                        "results_per_page": page_size,
                        "content-type": "application/json",
                        "sort_by": "date",
                    },
                    timeout=20,
                )
                resp.raise_for_status()
                data = resp.json()
                batch = data.get("results", [])
                jobs.extend(batch)
                if len(batch) < page_size or len(jobs) >= max_results:
                    break
            except Exception as exc:
                logger.error("Adzuna search error (page %s): %s", page, exc)
                break

    logger.info("Adzuna: fetched %d jobs", len(jobs))
    return jobs
