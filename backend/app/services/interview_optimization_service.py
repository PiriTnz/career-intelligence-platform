"""
Interview Optimization Engine.

Converts job requirements + evidence knowledge base into a complete
interview optimization workspace.

Rules:
- Classification, scoring, concerns, and mitigations are deterministic (no LLM).
- LLM is used ONLY for CV text generation and cover letter prose.
- VERIFIED skills → full credit; appear in CV skills section.
- TRANSFERABLE skills → bridge language in cover letter only; never as direct claim.
- LEARNING skills → appear ONLY in "Currently Learning" CV section.
- MISSING skills → internal gap analysis only; never appear in CV or cover letter as claimed experience.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InterviewWorkspace, Job
from app.db.models.profile_version import ProfileVersion
from app.db.models.skill_evidence import SkillEvidence
from app.llm.base import BaseLLMProvider
from app.services import career_interview_service, profile_service
from app.services.application_package_service import (
    SKILL_FAMILIES,
    _find_bridge,
    _format_json_list,
    _job_to_dict,
    _profile_to_dict,
    _profile_version_to_dict,
)
from app.services.matching_engine import MatchResult
from app.services.matching_engine import match as engine_match


# ── Extended classification dataclasses ───────────────────────────────────────

@dataclass
class TransferableSkill:
    skill: str
    via: str
    family: str
    rationale: str = ""


@dataclass
class ExtendedClassification:
    verified: list[str] = field(default_factory=list)
    transferable: list[TransferableSkill] = field(default_factory=list)
    learning: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


@dataclass
class RecruiterConcern:
    skill: str
    concern: str


@dataclass
class MitigationStrategy:
    skill: str
    strategy: str


@dataclass
class ReadinessResult:
    label: str   # excellent | strong | moderate | weak
    score: int   # 0-100
    explanation: str


# ── Pure classification ───────────────────────────────────────────────────────

def classify_skills_extended(
    required_skills: list[str],
    profile_skills: list[str],
    knowledge_base: list[SkillEvidence],
    match_result: MatchResult,
) -> ExtendedClassification:
    """
    Four-category evidence classification. Pure function, no I/O.

    Priority for missing skills (highest → lowest):
    1. LEARNING — in knowledge_base with status="learning"
    2. TRANSFERABLE — same skill family as a profile or verified KB skill
    3. MISSING — no evidence whatsoever

    VERIFIED = match_result.matched_skills UNION KB skills with status="verified"
    that overlap with required_skills.
    """
    kb_by_skill: dict[str, SkillEvidence] = {e.skill: e for e in knowledge_base}
    required_lower = [s.lower().strip() for s in required_skills]

    # Build verified set — engine matched OR KB-verified
    engine_matched_lower = {s.lower().strip() for s in match_result.matched_skills}
    kb_verified_lower = {
        s for s, e in kb_by_skill.items() if e.status == "verified"
    }
    kb_learning_lower = {
        s for s, e in kb_by_skill.items() if e.status == "learning"
    }

    verified: list[str] = []
    transferable: list[TransferableSkill] = []
    learning: list[str] = []
    missing: list[str] = []

    # All profile skills + KB-verified skills form the "bridge pool" for transferable detection
    bridge_pool = list({s.lower() for s in profile_skills} | kb_verified_lower)

    for req_lower, req_original in zip(required_lower, required_skills):
        if req_lower in engine_matched_lower or req_lower in kb_verified_lower:
            verified.append(req_original)
        elif req_lower in kb_learning_lower:
            learning.append(req_original)
        else:
            bridge = _find_bridge(req_original, bridge_pool)
            if bridge is not None:
                via_skill, family_name = bridge
                rationale = (
                    f"Your experience with '{via_skill}' in the {family_name.replace('_', ' ')} "
                    "domain is directly transferable."
                )
                transferable.append(
                    TransferableSkill(
                        skill=req_original,
                        via=via_skill,
                        family=family_name,
                        rationale=rationale,
                    )
                )
            else:
                missing.append(req_original)

    return ExtendedClassification(
        verified=verified,
        transferable=transferable,
        learning=learning,
        missing=missing,
    )


def compute_readiness(
    classification: ExtendedClassification,
    required_skills: list[str],
    match: MatchResult,
    profile_dict: dict[str, Any],
) -> ReadinessResult:
    """
    Deterministic readiness score (0-100) and label. No LLM.

    Components:
    - Skill coverage (50 pts): verified=full, transferable=50%, learning=25%
    - Experience fit  (20 pts)
    - Logistics       (20 pts): location/remote, contract, salary, language
    - Profile richness (10 pts)
    """
    n_required = max(len(required_skills), 1)

    verified_pts = (len(classification.verified) / n_required) * 45
    transfer_pts = (len(classification.transferable) / n_required) * 15
    learning_pts = (len(classification.learning) / n_required) * 5
    skill_score = min(verified_pts + transfer_pts + learning_pts, 50.0)

    gap = match.experience_gap
    if gap >= 0:
        exp_score = 20.0
    elif gap == -1:
        exp_score = 12.0
    else:
        exp_score = max(0.0, 20.0 + gap * 5)

    logistics = (
        (5 if (match.location_match or match.remote_match) else 0)
        + (5 if match.contract_match else 0)
        + (5 if match.salary_ok else 0)
        + (5 if match.language_match else 0)
    )

    richness = (
        (3 if profile_dict.get("skills") else 0)
        + (3 if profile_dict.get("target_roles") else 0)
        + (2 if profile_dict.get("experience_level") else 0)
        + (2 if (profile_dict.get("countries") or profile_dict.get("cities")) else 0)
    )

    score = min(int(round(skill_score + exp_score + logistics + richness)), 100)

    if score >= 80:
        label = "excellent"
    elif score >= 60:
        label = "strong"
    elif score >= 40:
        label = "moderate"
    else:
        label = "weak"

    explanation = _build_readiness_explanation(classification, match, required_skills, score)
    return ReadinessResult(label=label, score=score, explanation=explanation)


def _build_readiness_explanation(
    cls: ExtendedClassification,
    match: MatchResult,
    required_skills: list[str],
    score: int,
) -> str:
    n_total = len(required_skills)
    parts: list[str] = []

    if cls.verified:
        sample = cls.verified[:3]
        suffix = "..." if len(cls.verified) > 3 else ""
        parts.append(
            f"You directly match {len(cls.verified)}/{n_total} required skills "
            f"({', '.join(sample)}{suffix})"
        )
    if cls.transferable:
        parts.append(
            f"{len(cls.transferable)} skill(s) are transferable from adjacent experience"
        )
    if cls.learning:
        parts.append(
            f"You are actively learning {len(cls.learning)} required technology(ies) — "
            "include these in a 'Currently Learning' section"
        )
    if cls.missing:
        parts.append(
            f"{len(cls.missing)} required skill(s) represent genuine gaps "
            "(no current evidence or bridge)"
        )
    if match.experience_gap < -1:
        parts.append(
            f"Experience level is {abs(match.experience_gap)} step(s) below requirement — "
            "lead with project impact and scope"
        )
    elif match.experience_gap == -1:
        parts.append("Slight experience gap — emphasise ownership and achievements")
    elif match.experience_gap > 0:
        parts.append(f"You are overqualified by {match.experience_gap} level(s)")

    if not match.location_match and not match.remote_match:
        parts.append("Location mismatch — be prepared to address relocation or remote preference")

    return ". ".join(parts) + "." if parts else f"Overall readiness score: {score}/100."


def generate_recruiter_concerns(
    classification: ExtendedClassification,
    required_skills: list[str],
    match: MatchResult,
) -> list[RecruiterConcern]:
    """Deterministic. No LLM."""
    concerns: list[RecruiterConcern] = []

    for skill in classification.missing:
        concerns.append(RecruiterConcern(
            skill=skill,
            concern=f"No direct experience with {skill} — no evidence or adjacent bridge found in profile.",
        ))

    for skill in classification.learning:
        concerns.append(RecruiterConcern(
            skill=skill,
            concern=f"Currently learning {skill} — may raise questions about readiness to deliver from day one.",
        ))

    if match.experience_gap < -1:
        concerns.append(RecruiterConcern(
            skill="experience_level",
            concern=f"Experience level is {abs(match.experience_gap)} step(s) below the stated requirement.",
        ))
    elif match.experience_gap == -1:
        concerns.append(RecruiterConcern(
            skill="experience_level",
            concern="Slight experience gap — one level below the stated requirement.",
        ))

    if not match.location_match and not match.remote_match:
        concerns.append(RecruiterConcern(
            skill="location",
            concern="Candidate location does not match job location and remote is not offered.",
        ))

    return concerns


def generate_mitigation_strategies(
    concerns: list[RecruiterConcern],
    classification: ExtendedClassification,
) -> list[MitigationStrategy]:
    """Deterministic. No LLM."""
    strategies: list[MitigationStrategy] = []

    transferable_map = {t.skill.lower(): t for t in classification.transferable}

    for concern in concerns:
        skill = concern.skill

        if skill == "experience_level":
            strategies.append(MitigationStrategy(
                skill=skill,
                strategy=(
                    "Lead with project complexity, scope, and measurable impact rather than years. "
                    "Highlight any leadership, ownership, or cross-functional contributions."
                ),
            ))
        elif skill == "location":
            strategies.append(MitigationStrategy(
                skill=skill,
                strategy=(
                    "Address location proactively in the cover letter. "
                    "Express willingness to relocate or discuss flexible arrangements."
                ),
            ))
        elif skill.lower() in {s.lower() for s in classification.learning}:
            # Find family bridges if available
            bridge = _find_bridge(skill, [v for v in classification.verified])
            bridge_note = (
                f" Leverage your '{bridge[0]}' background to accelerate ramp-up."
                if bridge else ""
            )
            strategies.append(MitigationStrategy(
                skill=skill,
                strategy=(
                    f"Include {skill} in the 'Currently Learning' CV section. "
                    f"In the cover letter, describe your active learning trajectory.{bridge_note}"
                ),
            ))
        else:
            # Missing skill — find any transferable that can partially mitigate
            t = transferable_map.get(skill.lower())
            if t:
                strategies.append(MitigationStrategy(
                    skill=skill,
                    strategy=(
                        f"Highlight your '{t.via}' background as a foundation. "
                        f"Frame it as rapid adoption capability in the {t.family.replace('_', ' ')} domain."
                    ),
                ))
            else:
                # No bridge — honest acknowledgment is the only strategy
                family_hint = ""
                for fam_name, members in SKILL_FAMILIES.items():
                    if skill.lower() in members:
                        related = [m for m in members if m in {v.lower() for v in classification.verified}]
                        if related:
                            family_hint = (
                                f" Your experience with {related[0]} shows competency "
                                f"in the {fam_name.replace('_', ' ')} domain."
                            )
                        break
                strategies.append(MitigationStrategy(
                    skill=skill,
                    strategy=(
                        f"Acknowledge this gap honestly in the cover letter.{family_hint} "
                        "Express concrete commitment to upskilling. "
                        "Do NOT claim this skill in the CV."
                    ),
                ))

    return strategies


def generate_warnings(
    classification: ExtendedClassification,
    required_skills: list[str],
    match: MatchResult,
) -> list[str]:
    warnings: list[str] = []
    n_required = len(required_skills)

    if n_required > 0 and classification.missing:
        pct = len(classification.missing) / n_required * 100
        if pct > 60:
            warnings.append(
                f"High skill gap: {len(classification.missing)}/{n_required} required skills "
                f"({pct:.0f}%) have no evidence or transferable bridge."
            )
        elif pct > 25:
            warnings.append(
                f"Moderate gap: {len(classification.missing)} required skill(s) have no evidence."
            )

    if match.experience_gap < -2:
        warnings.append(
            "Significant experience level mismatch. Application may be screened out at resume stage."
        )
    elif match.experience_gap == -1:
        warnings.append("Slight experience gap — emphasise achievement scope over tenure.")

    if not match.location_match and not match.remote_match:
        warnings.append("Location mismatch with no remote option — address proactively.")

    return warnings


# ── LLM prompt builders ───────────────────────────────────────────────────────

def build_cv_optimization_prompt(
    profile_dict: dict[str, Any],
    pv_dict: dict[str, Any] | None,
    job_dict: dict[str, Any],
    classification: ExtendedClassification,
) -> str:
    pv = pv_dict or {}
    full_name = pv.get("full_name") or "Candidate"
    verified_str = ", ".join(classification.verified) or "none confirmed"
    transfer_str = ", ".join(f"{t.skill} (via {t.via})" for t in classification.transferable)
    learning_str = ", ".join(classification.learning) or "none"
    missing_str = ", ".join(classification.missing) or "none"

    education_raw = profile_dict.get("education") or pv.get("education") or []
    experience_raw = profile_dict.get("experience") or pv.get("experience") or []
    education_str = _format_json_list(education_raw, "No education data provided")
    experience_str = _format_json_list(experience_raw, "No experience data provided")
    certs = ", ".join(profile_dict.get("certifications") or pv.get("certifications") or []) or "None"
    langs = ", ".join(profile_dict.get("languages") or []) or "Not specified"
    roles = ", ".join(profile_dict.get("target_roles") or []) or "Not specified"
    exp_level = profile_dict.get("experience_level") or "Not specified"

    other_skills = [
        s for s in (profile_dict.get("skills") or [])
        if s.lower() not in {v.lower() for v in classification.verified}
    ]

    return f"""You are an expert career advisor optimising a CV for maximum interview probability.

⚠️  ABSOLUTE RULES — NEVER VIOLATE:
1. Use ONLY skills and experience from the EVIDENCE section below.
2. FORBIDDEN in CV skills section: {missing_str if missing_str != "none" else "no forbidden skills"}
3. LEARNING skills appear ONLY in a "Currently Learning" section — never as professional skills.
4. TRANSFERABLE skills appear ONLY as experience bullet context — never as standalone claimed skills.
5. Do not invent employers, projects, degrees, certifications, or achievements.
6. If a specific detail is unknown, write "[Company]" or "[Year]" as placeholder.

═══ EVIDENCE BASE ═══
Full name: {full_name}
Target roles: {roles}
Experience level: {exp_level}
Languages: {langs}
Certifications: {certs}

VERIFIED SKILLS (prioritise these): {verified_str}
OTHER PROFILE SKILLS: {", ".join(other_skills) or "none"}
TRANSFERABLE (context only): {transfer_str or "none"}
CURRENTLY LEARNING (separate section): {learning_str}
MISSING — DO NOT INCLUDE: {missing_str}

EDUCATION:
{education_str}

WORK EXPERIENCE:
{experience_str}

═══ TARGET JOB ═══
Title: {job_dict.get("title")}
Company: {job_dict.get("company_name")}
Location: {job_dict.get("location") or "Not specified"}
Contract: {job_dict.get("contract_type") or "Not specified"}
Required skills (matched): {", ".join(classification.verified) or "none"}

═══ CV STRUCTURE ═══
1. Professional Summary — 2–3 sentences, ATS-optimised, tailored to this specific role
2. Core Skills — VERIFIED SKILLS first; never include: {missing_str}
3. Work Experience — reordered by relevance; honest bullets from evidence above
4. Education
5. Certifications (if any)
6. Currently Learning — include ONLY: {learning_str if learning_str != "none" else "(omit if empty)"}
7. Languages

Rewrite bullets for ATS keywords where they match VERIFIED skills. Keep it truthful."""


def build_cover_letter_prompt(
    profile_dict: dict[str, Any],
    pv_dict: dict[str, Any] | None,
    job_dict: dict[str, Any],
    classification: ExtendedClassification,
    concerns: list[RecruiterConcern],
) -> str:
    pv = pv_dict or {}
    full_name = pv.get("full_name") or "the applicant"
    verified_str = ", ".join(classification.verified) or "general technical background"
    transfer_str = ", ".join(
        f"{t.skill} (transferable via {t.via})" for t in classification.transferable
    )
    learning_str = ", ".join(classification.learning) or "none"
    missing_str = ", ".join(classification.missing) or "none"
    exp_level = profile_dict.get("experience_level") or "not specified"
    langs = ", ".join(profile_dict.get("languages") or []) or "not specified"

    concern_summary = "; ".join(c.concern for c in concerns[:3]) if concerns else "none"

    return f"""Write a highly personalised cover letter that maximises interview probability.

⚠️  ABSOLUTE RULES:
1. Claim ONLY verified skills as direct proficiency: {verified_str}
2. TRANSFERABLE skills: bridge language ONLY.
   Examples: "My experience with {classification.transferable[0].via if classification.transferable else 'X'} translates directly to {classification.transferable[0].skill if classification.transferable else 'Y'}."
3. LEARNING skills: acknowledge actively, not as current proficiency.
   Example: "I am actively developing my {classification.learning[0] if classification.learning else 'X'} skills and can demonstrate progress."
4. MISSING skills ({missing_str}): never claim. If critical, acknowledge and pivot to bridge.
   Example: "While I have not yet worked directly with X, my background in Y gives me a strong foundation to ramp up quickly."
5. Do NOT invent employers, projects, or achievements.

═══ APPLICANT ═══
Name: {full_name}
Experience level: {exp_level}
Verified skills: {verified_str}
Transferable: {transfer_str or "none"}
Learning: {learning_str}
Languages: {langs}

═══ JOB ═══
Title: {job_dict.get("title")}
Company: {job_dict.get("company_name")}
Location: {job_dict.get("location") or "not specified"}
Contract: {job_dict.get("contract_type") or "not specified"}

═══ KEY CONCERNS TO ADDRESS ═══
{concern_summary}

═══ STRUCTURE (4 paragraphs) ═══
Paragraph 1 — Opening: Genuine enthusiasm for this specific role. Why this company and position.
Paragraph 2 — Strengths: What you directly bring (VERIFIED skills; concrete examples from experience).
Paragraph 3 — Bridge/Growth: How transferable experience applies; mention active learning honestly.
Paragraph 4 — Closing: Strong call to action; offer to discuss how you would ramp up quickly on gaps.

Write in first person. Professional but warm tone. No filler phrases."""


# ── Async service ─────────────────────────────────────────────────────────────

async def prepare_workspace(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    provider: BaseLLMProvider,
) -> InterviewWorkspace:
    """
    Full workspace preparation pipeline:
    load → seed KB → match → classify → readiness → concerns → generate text → upsert.
    Raises ValueError for missing job or profile.
    """
    # Load job
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise ValueError(f"Job {job_id} not found.")

    # Load profile
    active_profile = await profile_service.get_active_profile(db, user_id)
    if active_profile is None:
        raise ValueError("No active profile found. Complete your profile first.")

    # Load profile version
    pv_result = await db.execute(
        select(ProfileVersion)
        .where(ProfileVersion.user_id == user_id)
        .order_by(ProfileVersion.created_at.desc())
        .limit(1)
    )
    profile_version = pv_result.scalar_one_or_none()

    # Seed knowledge base from profile (idempotent — skips existing skills)
    await career_interview_service.seed_knowledge_base_from_profile(
        db, user_id, active_profile, profile_version
    )

    # Load knowledge base (post-seed)
    knowledge_base = await career_interview_service.get_knowledge_base(db, user_id)

    # Build dicts for matching engine
    job_dict = _job_to_dict(job)
    profile_dict = _profile_to_dict(active_profile)
    pv_dict = _profile_version_to_dict(profile_version) if profile_version else None

    # Run matching engine (deterministic)
    match_result: MatchResult = engine_match(job_dict, profile_dict)

    # Extended classification (deterministic)
    required_skills = list(job.required_skills or [])
    classification = classify_skills_extended(
        required_skills=required_skills,
        profile_skills=list(active_profile.skills or []),
        knowledge_base=knowledge_base,
        match_result=match_result,
    )

    # Readiness, concerns, mitigations, warnings (all deterministic)
    readiness = compute_readiness(classification, required_skills, match_result, profile_dict)
    concerns = generate_recruiter_concerns(classification, required_skills, match_result)
    mitigations = generate_mitigation_strategies(concerns, classification)
    warnings = generate_warnings(classification, required_skills, match_result)

    # Generate CV and cover letter via LLM
    cv_prompt = build_cv_optimization_prompt(profile_dict, pv_dict, job_dict, classification)
    cl_prompt = build_cover_letter_prompt(profile_dict, pv_dict, job_dict, classification, concerns)

    cv_draft = await provider.generate(cv_prompt, max_tokens=1400)
    cover_letter_draft = await provider.generate(cl_prompt, max_tokens=900)

    # Serialise for storage
    transferable_json = [
        {"skill": t.skill, "via": t.via, "family": t.family, "rationale": t.rationale}
        for t in classification.transferable
    ]
    concerns_json = [{"skill": c.skill, "concern": c.concern} for c in concerns]
    mitigations_json = [{"skill": m.skill, "strategy": m.strategy} for m in mitigations]

    # Upsert workspace
    existing_result = await db.execute(
        select(InterviewWorkspace).where(
            InterviewWorkspace.user_id == user_id,
            InterviewWorkspace.job_id == job_id,
        )
    )
    ws = existing_result.scalar_one_or_none()

    if ws is None:
        ws = InterviewWorkspace(
            user_id=user_id,
            job_id=job_id,
            verified_matches=classification.verified,
            transferable_matches=transferable_json,
            learning_skills=classification.learning,
            real_gaps=classification.missing,
            recruiter_concerns=concerns_json,
            mitigation_strategies=mitigations_json,
            cv_draft=cv_draft,
            cover_letter_draft=cover_letter_draft,
            readiness_label=readiness.label,
            readiness_score=readiness.score,
            readiness_explanation=readiness.explanation,
            warnings=warnings,
        )
        db.add(ws)
    else:
        ws.verified_matches = classification.verified
        ws.transferable_matches = transferable_json
        ws.learning_skills = classification.learning
        ws.real_gaps = classification.missing
        ws.recruiter_concerns = concerns_json
        ws.mitigation_strategies = mitigations_json
        ws.cv_draft = cv_draft
        ws.cover_letter_draft = cover_letter_draft
        ws.readiness_label = readiness.label
        ws.readiness_score = readiness.score
        ws.readiness_explanation = readiness.explanation
        ws.warnings = warnings

    await db.commit()
    await db.refresh(ws)
    return ws


async def get_workspace(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
) -> InterviewWorkspace | None:
    result = await db.execute(
        select(InterviewWorkspace).where(
            InterviewWorkspace.user_id == user_id,
            InterviewWorkspace.job_id == job_id,
        )
    )
    return result.scalar_one_or_none()


async def get_application_pipeline(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[dict]:
    """
    Merge InterviewWorkspaces + Applications for the user into a pipeline view.
    Returns list of pipeline items ordered by readiness_score desc.
    """
    from app.db.models import Application

    ws_result = await db.execute(
        select(InterviewWorkspace, Job)
        .join(Job, InterviewWorkspace.job_id == Job.id)
        .where(InterviewWorkspace.user_id == user_id)
        .order_by(InterviewWorkspace.readiness_score.desc())
    )
    ws_rows = ws_result.all()

    app_result = await db.execute(
        select(Application).where(Application.user_id == user_id)
    )
    apps = {a.job_id: a for a in app_result.scalars().all()}

    pipeline: list[dict] = []
    seen_jobs: set = set()

    for ws, job in ws_rows:
        app = apps.get(job.id)
        stage = (
            career_interview_service._application_status_to_stage(app.status)
            if app
            else "recommended"
        )
        pipeline.append({
            "job_id": ws.job_id,
            "job_title": job.title,
            "company_name": job.company_name,
            "stage": stage,
            "readiness_label": ws.readiness_label,
            "readiness_score": ws.readiness_score,
            "has_workspace": True,
            "has_application": app is not None,
            "application_id": app.id if app else None,
            "application_status": app.status if app else None,
        })
        seen_jobs.add(job.id)

    # Applications without workspaces
    for job_id, app in apps.items():
        if job_id in seen_jobs:
            continue
        job_result2 = await db.execute(select(Job).where(Job.id == job_id))
        job2 = job_result2.scalar_one_or_none()
        if job2 is None:
            continue
        stage = career_interview_service._application_status_to_stage(app.status)
        pipeline.append({
            "job_id": job_id,
            "job_title": job2.title,
            "company_name": job2.company_name,
            "stage": stage,
            "readiness_label": None,
            "readiness_score": None,
            "has_workspace": False,
            "has_application": True,
            "application_id": app.id,
            "application_status": app.status,
        })

    return pipeline
