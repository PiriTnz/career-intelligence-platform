"""
Career Interview Agent.

Purpose: Build a richer evidence knowledge base than a standard CV.

Rules:
- The agent NEVER directly updates profile data.
- Every suggestion requires user confirmation before becoming evidence.
- Confirmed evidence is stored in skill_evidence with source=user_confirmed.
- Rejected evidence is deleted from evidence_pending (not stored as evidence).
- LLM is used ONLY for generating structured questions, not for scoring.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvidencePending, SkillEvidence
from app.db.models.profile_version import ProfileVersion
from app.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


# ── Evidence suggestion schema (LLM output validation) ────────────────────────

class EvidenceSuggestion(BaseModel):
    skill: str
    suggested_status: str  # verified | learning | transferable
    question: str
    reasoning: str = ""

    def model_post_init(self, __context: Any) -> None:
        self.skill = self.skill.lower().strip()
        valid_statuses = {"verified", "learning", "transferable"}
        if self.suggested_status not in valid_statuses:
            self.suggested_status = "learning"


# ── Pure helpers ──────────────────────────────────────────────────────────────

def build_agent_question_prompt(
    profile: dict[str, Any],
    knowledge_base: list[SkillEvidence],
    job: dict[str, Any],
    required_skills: list[str],
) -> str:
    profile_skills = list(profile.get("skills") or [])
    kb_skills = [e.skill for e in knowledge_base if e.status in ("verified", "learning")]
    all_known = list({s.lower() for s in profile_skills + kb_skills})

    missing = [s for s in required_skills if s.lower() not in {k.lower() for k in all_known}]

    return f"""You are a career advisor helping a candidate strengthen their evidence base for a job application.

GOAL: Identify potential skills or experience the candidate might have but hasn't documented yet.
Generate targeted questions — not assumptions. Only ask about things that seem plausible given their existing background.

CANDIDATE PROFILE:
Current skills: {", ".join(profile_skills) or "not specified"}
Target roles: {", ".join(profile.get("target_roles") or []) or "not specified"}
Experience level: {profile.get("experience_level") or "not specified"}

KNOWLEDGE BASE (already confirmed):
{", ".join(kb_skills) if kb_skills else "empty — not yet built"}

JOB BEING APPLIED FOR:
Title: {job.get("title")}
Company: {job.get("company_name")}
Required skills (not yet evidenced): {", ".join(missing) if missing else "all covered"}

TASK:
Generate 3–5 targeted questions about potential evidence for the missing required skills.
Each question should reference the candidate's existing background and explain why it's relevant.

Return ONLY a JSON array. No prose before or after. Example format:
[
  {{
    "skill": "azure",
    "suggested_status": "learning",
    "question": "You have Docker and Kubernetes experience. Have you deployed workloads to Azure Kubernetes Service or similar cloud container platforms?",
    "reasoning": "AKS is a common next step from bare Kubernetes; worth documenting if so."
  }}
]

Allowed suggested_status values: verified, learning, transferable
Return ONLY skills from this list: {", ".join(missing) if missing else "any relevant skill"}"""


def _parse_llm_suggestions(raw: str) -> list[EvidenceSuggestion]:
    """Parse and validate LLM JSON output. Drop malformed entries silently."""
    if not raw:
        return []
    try:
        # Strip markdown fences if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        data = json.loads(text)
        if not isinstance(data, list):
            return []
        suggestions = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                suggestions.append(EvidenceSuggestion(**item))
            except (ValidationError, TypeError):
                continue
        return suggestions
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Failed to parse LLM evidence suggestions: %s", exc)
        return []


def _application_status_to_stage(status: str) -> str:
    mapping = {
        "found": "recommended",
        "shortlisted": "recommended",
        "cv_generated": "ready_to_apply",
        "approved": "ready_to_apply",
        "applied": "applied",
        "viewed": "applied",
        "replied": "follow_up",
        "interview": "interview",
        "rejected": "rejected",
        "archived": "rejected",
        "offer": "offer",
    }
    return mapping.get(status, "recommended")


# ── Async service functions ───────────────────────────────────────────────────

async def get_knowledge_base(db: AsyncSession, user_id: uuid.UUID) -> list[SkillEvidence]:
    result = await db.execute(
        select(SkillEvidence)
        .where(SkillEvidence.user_id == user_id)
        .order_by(SkillEvidence.skill)
    )
    return list(result.scalars().all())


async def get_pending_evidence(db: AsyncSession, user_id: uuid.UUID) -> list[EvidencePending]:
    result = await db.execute(
        select(EvidencePending)
        .where(EvidencePending.user_id == user_id)
        .order_by(EvidencePending.created_at.desc())
    )
    return list(result.scalars().all())


async def seed_knowledge_base_from_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
    profile: Any,
    profile_version: ProfileVersion | None,
) -> int:
    """
    Seed the knowledge base from profile.skills and profile_version.extracted_skills.
    Only adds entries not already present. Returns count of new entries added.
    """
    existing_result = await db.execute(
        select(SkillEvidence.skill).where(SkillEvidence.user_id == user_id)
    )
    existing_skills = {row for (row,) in existing_result.all()}

    to_add: list[SkillEvidence] = []

    # Profile skills → verified
    for skill in list(profile.skills or []):
        key = skill.lower().strip()
        if key and key not in existing_skills:
            existing_skills.add(key)
            to_add.append(SkillEvidence(
                user_id=user_id,
                skill=key,
                status="verified",
                source="profile",
                confidence=1.0,
            ))

    # Profile certifications → verified
    for cert in list(profile.certifications or []):
        key = cert.lower().strip()
        if key and key not in existing_skills:
            existing_skills.add(key)
            to_add.append(SkillEvidence(
                user_id=user_id,
                skill=key,
                status="verified",
                source="profile",
                confidence=0.9,
            ))

    # CV-extracted skills → verified (slightly lower confidence)
    if profile_version:
        for skill in list(profile_version.extracted_skills or []):
            key = skill.lower().strip()
            if key and key not in existing_skills:
                existing_skills.add(key)
                to_add.append(SkillEvidence(
                    user_id=user_id,
                    skill=key,
                    status="verified",
                    source="cv_extracted",
                    confidence=0.85,
                ))
        # Inferred skills → transferable
        for skill in list(profile_version.inferred_skills or []):
            key = skill.lower().strip()
            if key and key not in existing_skills:
                existing_skills.add(key)
                to_add.append(SkillEvidence(
                    user_id=user_id,
                    skill=key,
                    status="transferable",
                    source="cv_extracted",
                    confidence=0.7,
                ))

    if to_add:
        db.add_all(to_add)
        await db.flush()

    return len(to_add)


async def confirm_evidence(
    db: AsyncSession,
    user_id: uuid.UUID,
    pending_id: uuid.UUID,
    override_status: str | None = None,
    evidence_notes: str | None = None,
) -> SkillEvidence | None:
    """
    Confirm a pending evidence suggestion: create/update SkillEvidence, delete pending.
    Returns the created/updated SkillEvidence, or None if pending_id not found.
    """
    pending_result = await db.execute(
        select(EvidencePending).where(
            EvidencePending.id == pending_id,
            EvidencePending.user_id == user_id,
        )
    )
    pending = pending_result.scalar_one_or_none()
    if pending is None:
        return None

    confirmed_status = override_status or pending.suggested_status

    # Upsert into skill_evidence
    existing_result = await db.execute(
        select(SkillEvidence).where(
            SkillEvidence.user_id == user_id,
            SkillEvidence.skill == pending.skill,
        )
    )
    evidence = existing_result.scalar_one_or_none()

    if evidence is None:
        evidence = SkillEvidence(
            user_id=user_id,
            skill=pending.skill,
            status=confirmed_status,
            source="user_confirmed",
            confidence=0.95,
            evidence_notes=evidence_notes,
        )
        db.add(evidence)
    else:
        evidence.status = confirmed_status
        evidence.source = "user_confirmed"
        if evidence_notes:
            evidence.evidence_notes = evidence_notes

    # Remove the pending record
    await db.execute(
        delete(EvidencePending).where(EvidencePending.id == pending_id)
    )
    await db.commit()
    await db.refresh(evidence)
    return evidence


async def reject_evidence(
    db: AsyncSession,
    user_id: uuid.UUID,
    pending_id: uuid.UUID,
) -> bool:
    """
    Reject a pending suggestion: delete from evidence_pending.
    Returns True if found and deleted, False if not found.
    """
    pending_result = await db.execute(
        select(EvidencePending).where(
            EvidencePending.id == pending_id,
            EvidencePending.user_id == user_id,
        )
    )
    pending = pending_result.scalar_one_or_none()
    if pending is None:
        return False

    await db.execute(
        delete(EvidencePending).where(EvidencePending.id == pending_id)
    )
    await db.commit()
    return True


async def generate_agent_questions(
    provider: BaseLLMProvider,
    db: AsyncSession,
    user_id: uuid.UUID,
    profile: Any,
    knowledge_base: list[SkillEvidence],
    job: dict[str, Any],
    required_skills: list[str],
) -> list[EvidencePending]:
    """
    Ask the LLM to generate targeted questions about potential evidence.
    Suggestions are stored as EvidencePending records (not confirmed yet).
    Returns the list of created pending records.
    """
    prompt = build_agent_question_prompt(
        {
            "skills": list(profile.skills or []),
            "target_roles": list(profile.target_roles or []),
            "experience_level": profile.experience_level,
        },
        knowledge_base,
        job,
        required_skills,
    )

    raw = await provider.generate(prompt, max_tokens=600)
    suggestions = _parse_llm_suggestions(raw)

    created: list[EvidencePending] = []
    kb_skills = {e.skill for e in knowledge_base}

    for suggestion in suggestions:
        # Skip if already in knowledge base
        if suggestion.skill in kb_skills:
            continue
        pending = EvidencePending(
            user_id=user_id,
            skill=suggestion.skill,
            suggested_status=suggestion.suggested_status,
            agent_question=suggestion.question,
            agent_reasoning=suggestion.reasoning or None,
            source_context=f"{job.get('title')} at {job.get('company_name')}",
        )
        db.add(pending)
        created.append(pending)

    if created:
        await db.flush()
        await db.commit()
        for p in created:
            await db.refresh(p)

    return created
