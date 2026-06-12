"""
Job-Aware Profile Enrichment Agent.

CORE RULES:
- Never fabricate skills, experience, employers, projects, or certifications.
- Only use CV evidence, profile evidence, and user-confirmed answers.
- Every answer must be classified and confirmed before touching skill_evidence.
- Confirmed evidence is stored with source="user_confirmed".

Lifecycle:
  start_session  → analyse gaps → generate questions  (status: pending)
  record_answers → classify each answer               (status: answering)
  confirm        → create skill_evidence rows          (status: enriched)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, SkillEvidence
from app.db.models.job_enrichment_session import JobEnrichmentSession
from app.db.models.profile_version import ProfileVersion
from app.schemas.enrichment import (
    AnswerItem,
    ConfirmationItem,
    GapItem,
    QuestionItem,
)
from app.services import profile_service
from app.services.application_package_service import SKILL_FAMILIES, _find_bridge


# ── Question-type family map ───────────────────────────────────────────────────

_CLOUD_SKILLS: frozenset[str] = SKILL_FAMILIES.get("cloud", frozenset())
_CONTAINER_SKILLS: frozenset[str] = (
    SKILL_FAMILIES.get("containers", frozenset())
    | SKILL_FAMILIES.get("ci_cd", frozenset())
    | SKILL_FAMILIES.get("mlops", frozenset())
)
_RESEARCH_SKILLS: frozenset[str] = (
    SKILL_FAMILIES.get("ml_frameworks", frozenset())
    | SKILL_FAMILIES.get("llm_tools", frozenset())
    | SKILL_FAMILIES.get("data_science", frozenset())
)

_LEADERSHIP_KEYWORDS = frozenset({"lead", "leadership", "manage", "management", "team", "mentor", "coordinate", "supervise"})
_LANGUAGE_NAMES = frozenset({"french", "english", "spanish", "german", "arabic", "persian", "chinese", "portuguese", "italian", "dutch", "japanese", "korean"})
_STARTUP_KEYWORDS = frozenset({"startup", "entrepreneurship", "founding", "early stage", "venture"})
_CERT_KEYWORDS = frozenset({"certif", "aws certified", "azure certified", "gcp certified", "pmp", "scrum", "prince2"})


def _detect_question_type(requirement: str) -> str:
    """Determine question type from the requirement name. Pure function."""
    req_lower = requirement.lower().strip()

    if any(kw in req_lower for kw in _LEADERSHIP_KEYWORDS):
        return "leadership_evidence"
    if req_lower in _LANGUAGE_NAMES:
        return "language_proficiency"
    if any(kw in req_lower for kw in _CERT_KEYWORDS):
        return "certification_evidence"
    if any(kw in req_lower for kw in _STARTUP_KEYWORDS):
        return "startup_experience"
    if req_lower in _CLOUD_SKILLS:
        return "cloud_experience"
    if req_lower in _CONTAINER_SKILLS:
        return "devops_experience"
    if req_lower in _RESEARCH_SKILLS:
        return "research_experience"

    return "skill_evidence"


def _build_question_text(
    requirement: str,
    classification: str,
    via_skill: str | None,
    question_type: str,
) -> str:
    """Generate a human-readable targeted question. Pure function."""
    existing = via_skill or requirement

    templates: dict[str, dict[str, str]] = {
        "cloud_experience": {
            "partially_verified": (
                f"You have cloud/infrastructure experience with {existing}. "
                f"Have you also worked with {requirement} — even in a training exercise, "
                "personal deployment, or free-tier experiment?"
            ),
            "unknown": (
                f"Have you used {requirement}, or any other cloud platform "
                "(AWS, GCP, Azure), for any personal project, internship, "
                "certification, or training exercise?"
            ),
        },
        "devops_experience": {
            "partially_verified": (
                f"Given your experience with {existing}, have you also used {requirement} "
                "— perhaps in a different project, CI pipeline, or learning context?"
            ),
            "unknown": (
                f"Have you used {requirement} or similar DevOps tools in any context "
                "— a personal CI/CD pipeline, containerised deployment, or infrastructure experiment?"
            ),
        },
        "research_experience": {
            "partially_verified": (
                f"You have related experience with {existing}. "
                f"Have you also directly used {requirement} — in a project, "
                "research, hackathon, or self-study?"
            ),
            "unknown": (
                f"Have you applied {requirement} in any context — a research project, "
                "academic course, hackathon, or personal experiment?"
            ),
        },
        "leadership_evidence": {
            "partially_verified": (
                "Beyond your current experience, have you taken on leadership responsibilities "
                "— such as leading a cross-functional project, coordinating a small team, "
                "or mentoring a colleague?"
            ),
            "unknown": (
                "Have you ever led a project, coordinated a team, mentored others, "
                "or taken ownership of a major initiative — at work, in school, "
                "or in a personal / open-source context?"
            ),
        },
        "language_proficiency": {
            "partially_verified": (
                f"What is your current proficiency level in {requirement}? "
                "(e.g., native, professional, conversational, beginner)"
            ),
            "unknown": (
                f"Do you have any proficiency in {requirement}? "
                "If yes, what level? (native, professional, conversational, beginner)"
            ),
        },
        "certification_evidence": {
            "partially_verified": (
                f"Given your related experience, have you pursued or are you planning "
                f"to pursue a {requirement} certification or training programme?"
            ),
            "unknown": (
                f"Do you hold a {requirement} certification, or are you currently working "
                "towards one? Any completed course or recognised bootcamp counts."
            ),
        },
        "startup_experience": {
            "partially_verified": (
                "Beyond your current experience, have you worked in a startup environment, "
                "contributed to early-stage products, or operated with high autonomy and limited resources?"
            ),
            "unknown": (
                "Have you worked in a startup environment, founded a project, contributed to "
                "early-stage products, or operated with high autonomy and limited resources?"
            ),
        },
        "skill_evidence": {
            "partially_verified": (
                f"You have experience with {existing}, which is related to {requirement}. "
                f"Have you also directly worked with {requirement} — even briefly or in a learning context?"
            ),
            "unknown": (
                f"Have you used {requirement} in any project, coursework, job, or personal context "
                "— even a basic implementation or tutorial?"
            ),
        },
        "project_evidence": {
            "partially_verified": (
                f"You have some background near {requirement}. "
                f"Have you built or contributed to a project that used {requirement} specifically?"
            ),
            "unknown": (
                f"Have you built or contributed to a project that involved {requirement}?"
            ),
        },
    }

    tset = templates.get(question_type, templates["skill_evidence"])
    return tset.get(classification, tset.get("unknown", f"Do you have any experience with {requirement}?"))


# ── Pure: requirement analysis ─────────────────────────────────────────────────

def analyze_requirements(
    required_skills: list[str],
    profile_skills: list[str],
    knowledge_base: list[SkillEvidence],
) -> list[GapItem]:
    """
    Classify each required skill into one of three categories.
    Pure function — no DB, no LLM.

    already_verified  — skill is in profile or KB.verified
    partially_verified — skill is in KB.learning OR a transferable family bridge exists
    unknown           — no evidence at all
    """
    profile_lower = {s.lower().strip() for s in profile_skills}
    kb_by_skill: dict[str, SkillEvidence] = {
        e.skill.lower().strip(): e for e in knowledge_base
    }
    kb_verified = {s for s, e in kb_by_skill.items() if e.status == "verified"}
    bridge_pool = list(profile_lower | kb_verified)

    gaps: list[GapItem] = []

    for req in required_skills:
        req_lower = req.lower().strip()

        # 1. Already verified
        if req_lower in profile_lower or req_lower in kb_verified:
            gaps.append(
                GapItem(
                    requirement=req,
                    classification="already_verified",
                    rationale=f"'{req}' is verified in your profile or knowledge base.",
                )
            )
            continue

        # 2. In knowledge base as learning
        kb_entry = kb_by_skill.get(req_lower)
        if kb_entry and kb_entry.status == "learning":
            gaps.append(
                GapItem(
                    requirement=req,
                    classification="partially_verified",
                    rationale=f"You are currently learning '{req}' (recorded in your knowledge base).",
                )
            )
            continue

        # 3. Transferable family bridge exists
        bridge = _find_bridge(req, bridge_pool)
        if bridge is not None:
            via_skill, family = bridge
            gaps.append(
                GapItem(
                    requirement=req,
                    classification="partially_verified",
                    rationale=(
                        f"Your experience with '{via_skill}' "
                        f"({family.replace('_', ' ')} family) is related to '{req}'."
                    ),
                    via_skill=via_skill,
                    via_family=family,
                )
            )
            continue

        # 4. No evidence found
        gaps.append(
            GapItem(
                requirement=req,
                classification="unknown",
                rationale=f"No evidence of '{req}' found in your profile or knowledge base.",
            )
        )

    return gaps


# ── Pure: question generation ──────────────────────────────────────────────────

def generate_questions(gaps: list[GapItem]) -> list[QuestionItem]:
    """
    Generate targeted questions for gaps that need clarification.
    Skips already_verified gaps — no question needed.
    Pure function.
    """
    questions: list[QuestionItem] = []
    idx = 0
    for gap in gaps:
        if gap.classification == "already_verified":
            continue
        qtype = _detect_question_type(gap.requirement)
        text = _build_question_text(
            gap.requirement, gap.classification, gap.via_skill, qtype
        )
        questions.append(
            QuestionItem(
                id=f"q-{idx}",
                requirement=gap.requirement,
                question=text,
                question_type=qtype,  # type: ignore[arg-type]
                classification=gap.classification,  # type: ignore[arg-type]
            )
        )
        idx += 1
    return questions


# ── Pure: answer classification ────────────────────────────────────────────────

def classify_answer(answer_text: str) -> tuple[str, str]:
    """
    Classify a user's free-text answer.
    Returns (evidence_type, suggested_status).

    evidence_type : professional | project | academic | learning | verified | rejected
    suggested_status : verified | learning | rejected

    This function NEVER invents information — it only classifies what the user said.
    """
    text = answer_text.lower().strip()

    # Very short negative
    if len(text) <= 15 and any(
        text.startswith(kw)
        for kw in ("no", "nope", "never", "not ", "nah", "unfortunately no")
    ):
        return "rejected", "rejected"

    # Explicit rejection patterns
    _rejection = (
        "no, i haven", "i have not", "i don't have", "i do not have",
        "never used", "never worked", "not at all", "no experience",
        "no relevant", "unfortunately i", "i'm afraid not",
        "i have never", "i've never",
    )
    if any(kw in text for kw in _rejection):
        return "rejected", "rejected"

    # Professional evidence
    _professional = (
        "at my job", "at work", "in my company", "in production", "at the company",
        "during my internship", "for a client", "my team", "my colleague",
        "my manager", "my employer", "professional project", "work project",
        "for my employer",
    )
    if any(kw in text for kw in _professional):
        return "professional", "verified"

    # Project evidence
    _project = (
        "personal project", "side project", "open source", "open-source", "github",
        "deployed", "built a", "i built", "created a", "portfolio", "pet project",
        "weekend project", "hobby project", "demo project", "i deployed",
    )
    if any(kw in text for kw in _project):
        return "project", "verified"

    # Academic evidence
    _academic = (
        "thesis", "dissertation", "university project", "school project",
        "course project", "academic project", "research lab", "lab project",
        "coursework", "for my degree", "as part of my studies",
    )
    if any(kw in text for kw in _academic):
        return "academic", "verified"

    # Learning / in-progress
    _learning = (
        "currently studying", "currently learning", "taking a course",
        "enrolled in", "certification in progress", "just started",
        "getting started", "started learning", "doing a course",
        "i'm learning", "i am learning", "beginner level",
    )
    if any(kw in text for kw in _learning):
        return "learning", "learning"

    # Generic positive confirmation
    _positive = (
        "yes", "i have", "i've used", "i used", "i use", "i know",
        "i worked with", "experience with", "i'm familiar", "i am familiar",
        "familiar with", "i've worked",
    )
    if any(kw in text for kw in _positive):
        return "verified", "verified"

    # Ambiguous — default to learning (not fully verified, not rejected)
    return "learning", "learning"


# ── Async DB helpers ───────────────────────────────────────────────────────────

async def _get_profile_skills(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    """Return profile skills + latest CV version extracted skills."""
    profile = await profile_service.get_active_profile(db, user_id)
    skills = list(profile.skills or []) if profile else []

    pv_result = await db.execute(
        select(ProfileVersion)
        .where(ProfileVersion.profile_id == profile.id)  # type: ignore[union-attr]
        .order_by(ProfileVersion.version.desc())
        .limit(1)
        if profile else select(ProfileVersion).where(ProfileVersion.profile_id == None)  # noqa: E711
    )
    pv = pv_result.scalar_one_or_none()
    if pv:
        skills += list(pv.extracted_skills or [])
        skills += list(pv.inferred_skills or [])
    return list({s.lower().strip() for s in skills})


async def _get_knowledge_base(db: AsyncSession, user_id: uuid.UUID) -> list[SkillEvidence]:
    result = await db.execute(
        select(SkillEvidence).where(SkillEvidence.user_id == user_id)
    )
    return list(result.scalars().all())


# ── Public async API ───────────────────────────────────────────────────────────

async def start_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
) -> tuple[JobEnrichmentSession, list[GapItem]]:
    """
    Analyse job requirements against the user's current profile and KB.
    Create and persist a new enrichment session.
    Returns (session, gaps) — gaps include already_verified for transparency.
    """
    # Load job
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise ValueError(f"Job {job_id} not found.")

    required_skills: list[str] = list(job.required_skills or [])
    if not required_skills:
        raise ValueError("Job has no required skills to analyse.")

    # Load profile + KB
    profile_skills = await _get_profile_skills(db, user_id)
    knowledge_base = await _get_knowledge_base(db, user_id)

    # Analyse gaps
    gaps = analyze_requirements(required_skills, profile_skills, knowledge_base)
    questions = generate_questions(gaps)

    # Persist session
    session = JobEnrichmentSession(
        id=uuid.uuid4(),
        user_id=user_id,
        job_id=job_id,
        status="pending",
        detected_gaps=[g.model_dump() for g in gaps],
        generated_questions=[q.model_dump() for q in questions],
        answers=[],
        confirmations=[],
        enriched_skills=[],
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session, gaps


async def get_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> JobEnrichmentSession | None:
    result = await db.execute(
        select(JobEnrichmentSession).where(
            JobEnrichmentSession.id == session_id,
            JobEnrichmentSession.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def record_answer(
    db: AsyncSession,
    session: JobEnrichmentSession,
    question_id: str,
    answer_text: str,
) -> AnswerItem:
    """
    Classify and store a single answer in the session.
    Does NOT modify skill_evidence — only records the raw answer + classification.
    """
    # Find the question
    questions = [QuestionItem(**q) for q in (session.generated_questions or [])]
    question = next((q for q in questions if q.id == question_id), None)
    if question is None:
        raise ValueError(f"Question '{question_id}' not found in session.")

    evidence_type, suggested_status = classify_answer(answer_text)

    item = AnswerItem(
        question_id=question_id,
        requirement=question.requirement,
        answer_text=answer_text,
        evidence_type=evidence_type,  # type: ignore[arg-type]
        suggested_status=suggested_status,  # type: ignore[arg-type]
        answered_at=datetime.now(timezone.utc).isoformat(),
    )

    # Merge into existing answers (replace if same question_id)
    existing = [a for a in (session.answers or []) if a.get("question_id") != question_id]
    session.answers = existing + [item.model_dump()]
    session.status = "answering"

    await db.commit()
    await db.refresh(session)
    return item


async def confirm_enrichment(
    db: AsyncSession,
    user_id: uuid.UUID,
    session: JobEnrichmentSession,
    confirmations: list[ConfirmationItem],
) -> list[str]:
    """
    For each confirmed item, create a skill_evidence record (source=user_confirmed).
    Rejected items are silently skipped — never stored as evidence.
    Returns list of newly enriched skill names.
    """
    enriched: list[str] = []

    for conf in confirmations:
        if not conf.confirmed or conf.suggested_status == "rejected":
            continue

        skill_lower = conf.requirement.lower().strip()

        # Check if skill_evidence already exists for this user
        existing_result = await db.execute(
            select(SkillEvidence).where(
                SkillEvidence.user_id == user_id,
                SkillEvidence.skill == skill_lower,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing is not None:
            # Update status if we have stronger evidence
            status_rank = {"verified": 3, "learning": 2, "transferable": 1, "rejected": 0}
            if status_rank.get(conf.suggested_status, 0) > status_rank.get(existing.status, 0):
                existing.status = conf.suggested_status
                existing.source = "user_confirmed"
                existing.evidence_notes = conf.evidence_note
        else:
            evidence = SkillEvidence(
                id=uuid.uuid4(),
                user_id=user_id,
                skill=skill_lower,
                status=conf.suggested_status,
                source="user_confirmed",
                confidence=0.9,
                evidence_notes=conf.evidence_note,
            )
            db.add(evidence)

        enriched.append(conf.requirement)

    # Persist confirmations + enriched skills
    session.confirmations = [c.model_dump() for c in confirmations]
    session.enriched_skills = list(session.enriched_skills or []) + enriched
    session.status = "enriched" if enriched else "confirmed"

    await db.commit()
    await db.refresh(session)
    return enriched


async def get_enrichment_status(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Return latest enrichment session status for a job.
    Used by the Application Workspace to show enrichment opportunities.
    """
    from typing import Any  # local to avoid circular at module level

    result = await db.execute(
        select(JobEnrichmentSession)
        .where(
            JobEnrichmentSession.user_id == user_id,
            JobEnrichmentSession.job_id == job_id,
        )
        .order_by(JobEnrichmentSession.created_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()

    if session is None:
        return {
            "has_open_session": False,
            "session_id": None,
            "session_status": None,
            "unanswered_questions": 0,
            "enriched_skills": [],
        }

    answered_ids = {a.get("question_id") for a in (session.answers or [])}
    total_questions = len(session.generated_questions or [])
    unanswered = total_questions - len(answered_ids)

    return {
        "has_open_session": session.status not in ("enriched",),
        "session_id": session.id,
        "session_status": session.status,
        "unanswered_questions": max(unanswered, 0),
        "enriched_skills": list(session.enriched_skills or []),
    }
