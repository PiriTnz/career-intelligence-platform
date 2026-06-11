"""
Agent 0 — Profile Agent.
Parses a PDF CV, extracts structured profile data via LLM, and saves to DB.
"""
from __future__ import annotations

import io
import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.llm.base import BaseLLMProvider
from app.services.profile_service import create_profile_from_dict

_EXTRACTION_PROMPT = """You are a CV parser. Extract structured information from the CV text below.
Return ONLY valid JSON — no markdown, no explanation.

Required JSON schema:
{{
  "target_roles": ["string"],
  "skills": ["string"],
  "experience_level": "junior|mid|senior|lead",
  "cities": ["string"],
  "countries": ["string"],
  "languages": ["string"],
  "salary_min": null_or_integer,
  "salary_target": null_or_integer,
  "remote_preference": true_or_false
}}

Rules:
- skills: extract ALL technical skills (programming languages, frameworks, tools, platforms)
- target_roles: infer from job history and objective if present
- experience_level: estimate from years and seniority signals
- cities: where the candidate is based or wants to work
- languages: programming languages excluded — human languages only (e.g. French, English)
- salary: only include if explicitly mentioned, otherwise null

CV TEXT:
{cv_text}"""


class ProfileAgent(BaseAgent):
    name = "profile_agent"

    def __init__(self, db: AsyncSession, user_id: uuid.UUID, provider: BaseLLMProvider):
        super().__init__(db, user_id)
        self.provider = provider

    async def run(self, *, pdf_bytes: bytes | None = None, cv_text: str | None = None, **kwargs) -> dict:
        await self._log("started", "ProfileAgent started")

        text = cv_text or ""
        if pdf_bytes and not text:
            text = await self._extract_pdf_text(pdf_bytes)

        if not text.strip():
            await self._log("error", "No CV text to parse")
            return {"success": False, "error": "No CV text provided"}

        prompt = _EXTRACTION_PROMPT.format(cv_text=text[:4000])
        raw = await self.provider.generate(prompt, max_tokens=600)

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await self._log("error", "LLM returned invalid JSON", {"raw": raw[:300]})
            return {"success": False, "error": "Failed to parse LLM response as JSON"}

        # Defaults for optional fields
        data.setdefault("avoid_roles", [])
        data.setdefault("contract_types", ["CDI", "CDD", "freelance"])

        profile = await create_profile_from_dict(self.db, self.user_id, data)
        await self._log("completed", f"Profile v{profile.version} created", {"skills_count": len(profile.skills)})
        await self.db.commit()

        return {
            "success": True,
            "profile_id": str(profile.id),
            "version": profile.version,
            "skills_extracted": len(profile.skills),
        }

    async def _extract_pdf_text(self, pdf_bytes: bytes) -> str:
        try:
            import pypdf  # type: ignore
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            return ""
        except Exception:
            return ""
