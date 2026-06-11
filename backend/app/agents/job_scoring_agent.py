"""
Agent 2 — Job Scoring Agent.
Scores all unscored jobs for a user. Deterministic only; LLM writes explanation only.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.db.models import Job, Score
from app.services.job_service import get_profile_dict
from app.services.scoring_service import save_score, score_job


class JobScoringAgent(BaseAgent):
    name = "job_scoring_agent"

    async def run(self, *, batch_size: int = 100, **kwargs) -> dict:
        profile = await get_profile_dict(self.db, self.user_id)
        if not profile:
            await self._log("error", "No active profile — cannot score jobs")
            return {"success": False, "error": "No active profile"}

        # Jobs not yet scored for this user
        scored_ids_result = await self.db.execute(
            select(Score.job_id).where(Score.user_id == self.user_id)
        )
        scored_ids = {row[0] for row in scored_ids_result}

        jobs_result = await self.db.execute(
            select(Job).where(Job.id.not_in(scored_ids)).limit(batch_size)
        )
        jobs = list(jobs_result.scalars().all())

        stats = {"scored": 0, "errors": 0, "needs_review": 0}
        await self._log("started", f"Scoring {len(jobs)} unscored jobs")

        for job in jobs:
            try:
                job_dict = {
                    "title": job.title or "",
                    "required_skills": job.required_skills or [],
                    "location": job.location or "",
                    "remote": job.remote or False,
                    "contract_type": job.contract_type,
                    "salary_min": job.salary_min,
                    "salary_max": job.salary_max,
                    "company_name": job.company_name or "",
                    "scraped_at": job.scraped_at.isoformat() if job.scraped_at else None,
                }
                breakdown, confidence = score_job(job_dict, profile)
                await save_score(
                    self.db,
                    job_id=job.id,
                    user_id=self.user_id,
                    profile_version=profile.get("version", 1),
                    breakdown=breakdown,
                    confidence=confidence,
                    explanation="",
                )
                stats["scored"] += 1
                if breakdown.needs_review:
                    stats["needs_review"] += 1
            except Exception as exc:
                stats["errors"] += 1
                await self._log("warning", f"Scoring error for job {job.id}: {exc}")

        await self.db.commit()
        await self._log("completed", "JobScoringAgent done", stats)
        await self.db.commit()

        return {"success": True, **stats}
