"""
Agent 3 — CV Adaptation Agent.
Generates ATS-optimized CVs in FR + EN for a specific job via LLM.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.llm.base import BaseLLMProvider
from app.services.cv_service import generate_cv


class CVAdaptationAgent(BaseAgent):
    name = "cv_adaptation_agent"

    def __init__(self, db: AsyncSession, user_id: uuid.UUID, provider: BaseLLMProvider):
        super().__init__(db, user_id)
        self.provider = provider

    async def run(self, *, job_id: uuid.UUID, languages: list[str] | None = None, **kwargs) -> dict:
        langs = languages or ["fr", "en"]
        results = []

        await self._log("started", f"Generating CV for job {job_id} in {langs}")

        for lang in langs:
            try:
                cv = await generate_cv(
                    self.db,
                    user_id=self.user_id,
                    job_id=job_id,
                    language=lang,
                    provider=self.provider,
                )
                results.append({"language": lang, "cv_id": str(cv.id), "ats_score": cv.ats_score})
                await self._log("info", f"CV generated in {lang}", {"cv_id": str(cv.id), "ats_score": cv.ats_score})
            except Exception as exc:
                await self._log("warning", f"CV generation failed for {lang}: {exc}")
                results.append({"language": lang, "error": str(exc)})

        await self._log("completed", f"CVAdaptationAgent done — {len(results)} CVs")
        await self.db.commit()

        return {"success": True, "job_id": str(job_id), "cvs": results}
