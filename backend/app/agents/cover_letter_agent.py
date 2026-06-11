"""
Agent 4 — Cover Letter Agent.
Generates cover_letter, motivation, or email_hr content via LLM.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.llm.base import BaseLLMProvider
from app.services.cover_letter_service import generate_cover_letter


class CoverLetterAgent(BaseAgent):
    name = "cover_letter_agent"

    def __init__(self, db: AsyncSession, user_id: uuid.UUID, provider: BaseLLMProvider):
        super().__init__(db, user_id)
        self.provider = provider

    async def run(
        self,
        *,
        job_id: uuid.UUID,
        letter_type: str = "cover_letter",
        language: str = "fr",
        **kwargs,
    ) -> dict:
        await self._log("started", f"Generating {letter_type} for job {job_id}")

        try:
            letter = await generate_cover_letter(
                self.db,
                user_id=self.user_id,
                job_id=job_id,
                letter_type=letter_type,
                language=language,
                provider=self.provider,
            )
            await self._log("completed", f"{letter_type} generated", {"letter_id": str(letter.id)})
            await self.db.commit()
            return {
                "success": True,
                "letter_id": str(letter.id),
                "type": letter_type,
                "language": language,
                "word_count": len(letter.content.split()),
            }
        except Exception as exc:
            await self._log("error", f"Cover letter generation failed: {exc}")
            await self.db.commit()
            return {"success": False, "error": str(exc)}
