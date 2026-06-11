"""
Agent 1 — Job Collection Agent.
Fetches from France Travail + Adzuna, normalizes, deduplicates, and saves jobs.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.services.job_service import get_profile_dict, upsert_job
from app.services.normalizer import normalize
from app.services.sources.adzuna import fetch_jobs as adzuna_fetch
from app.services.sources.france_travail import fetch_jobs as ft_fetch


class JobCollectionAgent(BaseAgent):
    name = "job_collection_agent"

    async def run(
        self,
        *,
        keywords: list[str] | None = None,
        location: str = "Lyon",
        location_code: str = "69",
        max_results: int = 50,
        **kwargs,
    ) -> dict:
        kw_list = keywords or ["AI engineer", "ML engineer", "LLM", "MLOps"]
        stats = {"fetched": 0, "inserted": 0, "updated": 0, "errors": 0}

        await self._log("started", "JobCollectionAgent started", {"keywords": kw_list})

        for kw in kw_list:
            # France Travail
            try:
                ft_jobs = await ft_fetch(kw, location_code=location_code, max_results=max_results // 2)
                for raw in ft_jobs:
                    stats["fetched"] += 1
                    normalized = normalize(raw, "france_travail")
                    _, created = await upsert_job(self.db, normalized)
                    if created:
                        stats["inserted"] += 1
                    else:
                        stats["updated"] += 1
            except Exception as exc:
                stats["errors"] += 1
                await self._log("warning", f"France Travail error for '{kw}': {exc}")

            # Adzuna
            try:
                az_jobs = await adzuna_fetch(kw, location=location, max_results=max_results // 2)
                for raw in az_jobs:
                    stats["fetched"] += 1
                    normalized = normalize(raw, "adzuna")
                    _, created = await upsert_job(self.db, normalized)
                    if created:
                        stats["inserted"] += 1
                    else:
                        stats["updated"] += 1
            except Exception as exc:
                stats["errors"] += 1
                await self._log("warning", f"Adzuna error for '{kw}': {exc}")

        await self.db.commit()
        await self._log("completed", "JobCollectionAgent done", stats)
        await self.db.commit()

        return {"success": True, **stats}
