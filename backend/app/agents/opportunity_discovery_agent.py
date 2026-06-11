"""
Agent 6 — Opportunity Discovery Agent.
Discovers CIFRE/PhD/Research/MLOps/startup opportunities with specialised keyword sets.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.services.job_service import upsert_job
from app.services.normalizer import normalize
from app.services.sources.adzuna import fetch_jobs as adzuna_fetch
from app.services.sources.france_travail import fetch_jobs as ft_fetch

_KEYWORD_SETS = {
    "cifre": ["CIFRE thèse", "CIFRE doctorat", "CIFRE IA", "CIFRE ML"],
    "phd": ["PhD candidature", "doctorat informatique", "doctorat intelligence artificielle"],
    "research": ["Research Engineer AI", "ingénieur recherche IA", "Research Scientist ML"],
    "mlops": ["MLOps engineer", "ML platform engineer", "DataOps", "model serving"],
    "startup": ["AI startup", "LLM startup", "ML startup France"],
}


class OpportunityDiscoveryAgent(BaseAgent):
    name = "opportunity_discovery_agent"

    async def run(
        self,
        *,
        categories: list[str] | None = None,
        location_code: str = "69",
        location: str = "Lyon",
        max_per_keyword: int = 20,
        **kwargs,
    ) -> dict:
        cats = categories or list(_KEYWORD_SETS.keys())
        stats = {"fetched": 0, "inserted": 0, "categories": cats}

        await self._log("started", f"Discovery for categories: {cats}")

        for cat in cats:
            keywords = _KEYWORD_SETS.get(cat, [])
            for kw in keywords:
                # France Travail
                try:
                    jobs = await ft_fetch(kw, location_code=location_code, max_results=max_per_keyword)
                    for raw in jobs:
                        normalized = normalize(raw, "france_travail")
                        normalized.setdefault("tags", [])
                        normalized["tags"] = list(set(normalized.get("tags", []) + [cat]))
                        _, created = await upsert_job(self.db, normalized)
                        stats["fetched"] += 1
                        if created:
                            stats["inserted"] += 1
                except Exception as exc:
                    await self._log("warning", f"FT fetch error for '{kw}': {exc}")

                # Adzuna
                try:
                    jobs = await adzuna_fetch(kw, location=location, max_results=max_per_keyword)
                    for raw in jobs:
                        normalized = normalize(raw, "adzuna")
                        normalized.setdefault("tags", [])
                        normalized["tags"] = list(set(normalized.get("tags", []) + [cat]))
                        _, created = await upsert_job(self.db, normalized)
                        stats["fetched"] += 1
                        if created:
                            stats["inserted"] += 1
                except Exception as exc:
                    await self._log("warning", f"Adzuna fetch error for '{kw}': {exc}")

        await self.db.commit()
        await self._log("completed", f"Discovery done", stats)
        await self.db.commit()

        return {"success": True, **stats}
