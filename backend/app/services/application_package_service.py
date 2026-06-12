"""
Application Package Agent.

CORE RULE: Never invent skills, experience, degrees, certifications, employers,
or achievements. All CV content must be evidence-based.

LLM is used ONLY for text generation (CV draft, cover letter). It never
influences the requirement classification, ready_to_apply_score, or warnings —
those are deterministic pure functions.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApplicationPackage, Job, Profile
from app.db.models.profile_version import ProfileVersion
from app.llm.base import BaseLLMProvider
from app.services import profile_service
from app.services.matching_engine import MatchResult
from app.services.matching_engine import match as engine_match

# ── Skill family map for transferable-skill detection ─────────────────────────

SKILL_FAMILIES: dict[str, frozenset[str]] = {
    "python_ecosystem": frozenset({
        "python", "pandas", "numpy", "scipy", "fastapi", "django", "flask",
        "uvicorn", "pydantic", "aiohttp", "celery",
    }),
    "ml_frameworks": frozenset({
        "pytorch", "tensorflow", "keras", "scikit-learn", "scikit learn",
        "jax", "mxnet", "xgboost", "lightgbm", "catboost",
    }),
    "llm_tools": frozenset({
        "langchain", "openai", "huggingface", "hugging face", "ollama",
        "transformers", "bert", "gpt", "llm", "rag", "langsmith",
        "llamaindex", "llama index", "embeddings", "vector database",
        "chroma", "pinecone", "weaviate", "qdrant",
    }),
    "databases": frozenset({
        "postgresql", "postgres", "mysql", "mongodb", "redis",
        "elasticsearch", "cassandra", "neo4j", "sqlite", "sql", "nosql",
        "dynamodb", "mariadb", "cockroachdb",
    }),
    "cloud": frozenset({
        "aws", "gcp", "azure", "google cloud", "ec2", "s3", "lambda",
        "cloud run", "cloud functions", "bigquery", "cloud storage",
        "eks", "ecs", "fargate",
    }),
    "containers": frozenset({
        "docker", "kubernetes", "helm", "podman", "containerd", "k8s",
        "docker compose", "openshift",
    }),
    "javascript_web": frozenset({
        "javascript", "typescript", "node.js", "nodejs", "react", "vue",
        "angular", "next.js", "nextjs", "svelte", "webpack", "vite",
        "express", "nestjs",
    }),
    "data_pipeline": frozenset({
        "airflow", "prefect", "dagster", "spark", "apache spark", "kafka",
        "flink", "dbt", "databricks", "hadoop", "hive", "presto", "trino",
    }),
    "mlops": frozenset({
        "mlflow", "dvc", "kubeflow", "bentoml", "mlops", "evidently",
        "whylogs", "seldon", "triton", "bento",
    }),
    "ci_cd": frozenset({
        "github actions", "gitlab ci", "jenkins", "ci/cd", "argocd",
        "circle ci", "travis ci", "tekton", "argo",
    }),
    "visualization": frozenset({
        "matplotlib", "seaborn", "plotly", "tableau", "power bi",
        "grafana", "kibana", "superset", "looker",
    }),
    "java_ecosystem": frozenset({
        "java", "spring", "spring boot", "maven", "gradle", "kotlin", "scala",
    }),
    "systems_languages": frozenset({
        "c", "c++", "rust", "go", "golang", "linux", "bash", "shell",
    }),
    "data_science": frozenset({
        "statistics", "probability", "linear algebra", "r", "matlab",
        "jupyter", "data analysis", "data science", "machine learning",
        "deep learning", "nlp", "computer vision",
    }),
}


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class TransferableSkillResult:
    skill: str   # required skill the user lacks
    via: str     # the user's bridging skill
    family: str  # skill family name


@dataclass
class RequirementClassification:
    verified_match: list[str] = field(default_factory=list)
    transferable_match: list[TransferableSkillResult] = field(default_factory=list)
    real_gap: list[str] = field(default_factory=list)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _families_of(skill: str) -> list[str]:
    key = skill.lower().strip()
    return [name for name, members in SKILL_FAMILIES.items() if key in members]


def _find_bridge(missing_skill: str, profile_skills: list[str]) -> tuple[str, str] | None:
    """Return (profile_skill, family_name) if any profile skill bridges the gap."""
    for family in _families_of(missing_skill):
        members = SKILL_FAMILIES[family]
        for ps in profile_skills:
            if ps.lower().strip() in members:
                return ps, family
    return None


def _format_json_list(items: list[Any], fallback: str) -> str:
    if not items:
        return fallback
    lines: list[str] = []
    for item in items:
        if isinstance(item, dict):
            parts = [f"{k}: {v}" for k, v in item.items() if v is not None and v != ""]
            lines.append("  - " + ", ".join(parts))
        else:
            lines.append(f"  - {item}")
    return "\n".join(lines) if lines else fallback


def _job_to_dict(job: Job) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "title": job.title,
        "company_name": job.company_name,
        "location": job.location,
        "remote": job.remote,
        "contract_type": job.contract_type,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "required_skills": list(job.required_skills or []),
        "experience_level": job.experience_level,
        "language": getattr(job, "language", "fr"),
    }


def _profile_to_dict(profile: Profile) -> dict[str, Any]:
    return {
        "skills": list(profile.skills or []),
        "target_roles": list(profile.target_roles or []),
        "experience_level": profile.experience_level,
        "countries": list(profile.countries or []),
        "cities": list(profile.cities or []),
        "remote_preference": profile.remote_preference,
        "contract_types": list(profile.contract_types or []),
        "salary_min": profile.salary_min,
        "salary_target": profile.salary_target,
        "languages": list(profile.languages or []),
        "certifications": list(profile.certifications or []),
        "education": list(profile.education or []),
        "experience": list(profile.experience or []),
    }


def _profile_version_to_dict(pv: ProfileVersion) -> dict[str, Any]:
    return {
        "full_name": pv.full_name,
        "extracted_skills": list(pv.extracted_skills or []),
        "inferred_skills": list(pv.inferred_skills or []),
        "education": list(pv.education or []),
        "experience": list(pv.experience or []),
        "certifications": list(pv.certifications or []),
    }


def _parse_analysis(data: dict) -> RequirementClassification:
    return RequirementClassification(
        verified_match=data.get("verified_match", []),
        transferable_match=[
            TransferableSkillResult(
                skill=t["skill"], via=t["via"], family=t["family"]
            )
            for t in data.get("transferable_match", [])
        ],
        real_gap=data.get("real_gap", []),
    )


# ── Pure functions ────────────────────────────────────────────────────────────

def classify_requirements(
    required_skills: list[str],
    profile_skills: list[str],
    match_result: MatchResult,
) -> RequirementClassification:
    """
    Pure function. No DB, no LLM.

    Uses the matching engine's pre-computed matched_skills as verified_match,
    then classifies missing_skills as transferable (same skill family) or
    real_gap (no family bridge).
    """
    verified = list(match_result.matched_skills)
    transferable: list[TransferableSkillResult] = []
    real_gap: list[str] = []

    for skill in match_result.missing_skills:
        bridge = _find_bridge(skill, profile_skills)
        if bridge is not None:
            via_skill, family_name = bridge
            transferable.append(TransferableSkillResult(skill=skill, via=via_skill, family=family_name))
        else:
            real_gap.append(skill)

    return RequirementClassification(
        verified_match=verified,
        transferable_match=transferable,
        real_gap=real_gap,
    )


def compute_ready_to_apply_score(
    classification: RequirementClassification,
    required_skills: list[str],
    match: MatchResult,
    profile_dict: dict[str, Any],
) -> int:
    """
    Deterministic 0–100 score. No LLM.

    Breakdown:
    - Skill coverage (40 pts): verified full credit + transferable partial
    - Experience fit  (20 pts)
    - Logistics       (20 pts): location/remote, contract, salary, language
    - Profile richness(20 pts): presence of key profile fields
    """
    n_required = max(len(required_skills), 1)

    verified_pts = (len(classification.verified_match) / n_required) * 35
    transfer_pts = (len(classification.transferable_match) / n_required) * 10
    skill_score = min(verified_pts + transfer_pts, 40.0)

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
        (5 if profile_dict.get("skills") else 0)
        + (5 if profile_dict.get("target_roles") else 0)
        + (5 if profile_dict.get("experience_level") else 0)
        + (5 if (profile_dict.get("countries") or profile_dict.get("cities")) else 0)
    )

    return min(int(round(skill_score + exp_score + logistics + richness)), 100)


def generate_warnings(
    classification: RequirementClassification,
    required_skills: list[str],
    match: MatchResult,
) -> list[str]:
    """Deterministic warnings list. No LLM."""
    warnings: list[str] = []
    n_required = len(required_skills)

    if n_required > 0 and classification.real_gap:
        gap_pct = len(classification.real_gap) / n_required * 100
        if gap_pct > 60:
            warnings.append(
                f"High skill gap: {len(classification.real_gap)} of {n_required} required "
                f"skills ({gap_pct:.0f}%) are missing with no transferable equivalent. "
                "Strengthen your profile before applying."
            )
        elif gap_pct > 25:
            warnings.append(
                f"Moderate skill gap: {len(classification.real_gap)} required skill(s) "
                "have no direct match or transferable equivalent."
            )

    if match.experience_gap < -1:
        warnings.append(
            "Experience level mismatch: this role requires significantly more experience. "
            "Emphasise project complexity and scope in your application."
        )
    elif match.experience_gap == -1:
        warnings.append(
            "Slight experience gap detected. Highlight leadership, ownership, and measurable impact."
        )

    if not match.location_match and not match.remote_match:
        warnings.append(
            "Location mismatch: job location does not match your preferences "
            "and remote work is not offered."
        )

    return warnings


def build_cv_adaptation_prompt(
    profile_dict: dict[str, Any],
    profile_version_data: dict[str, Any] | None,
    job_dict: dict[str, Any],
    classification: RequirementClassification,
) -> str:
    """
    Build LLM prompt for CV adaptation.
    Explicitly forbids real_gap skills to prevent invented proficiency claims.
    """
    pv = profile_version_data or {}
    full_name = pv.get("full_name") or "Candidate"

    verified_str = (
        ", ".join(classification.verified_match)
        if classification.verified_match
        else "none identified"
    )
    transferable_str = ", ".join(
        f"{t.skill} (via {t.via})" for t in classification.transferable_match
    )
    real_gap_str = (
        ", ".join(classification.real_gap) if classification.real_gap else "none"
    )

    all_skills = list(profile_dict.get("skills") or [])
    verified_lower = {v.lower() for v in classification.verified_match}
    other_skills = [s for s in all_skills if s.lower() not in verified_lower]

    education_raw = profile_dict.get("education") or pv.get("education") or []
    experience_raw = profile_dict.get("experience") or pv.get("experience") or []
    certifications = (
        ", ".join(profile_dict.get("certifications") or pv.get("certifications") or [])
        or "None"
    )
    languages = ", ".join(profile_dict.get("languages") or []) or "Not specified"
    target_roles = ", ".join(profile_dict.get("target_roles") or []) or "Not specified"
    experience_level = profile_dict.get("experience_level") or "Not specified"

    education_str = _format_json_list(education_raw, "No education data provided")
    experience_str = _format_json_list(experience_raw, "No experience data provided")

    required_skills_str = ", ".join(job_dict.get("required_skills") or []) or "Not listed"

    return f"""You are a professional career advisor adapting a CV for a specific job application.

⚠️  CRITICAL RULES — VIOLATION IS FORBIDDEN:
1. Use ONLY the skills, experience, and qualifications listed below in the PROFILE section.
2. Do NOT add, invent, or imply proficiency in any skill absent from the PROFILE.
3. These skills are MISSING — do NOT claim them anywhere in the CV: {real_gap_str}
4. If a detail is unavailable (employer name, date), write "[Employer]" or "[Year]".
5. Reorder sections to emphasise relevance to the target role.
6. Use only truthful bullet points derived from the experience and education data below.

═══ APPLICANT PROFILE ═══
Full name: {full_name}
Target roles: {target_roles}
Experience level: {experience_level}
Languages: {languages}
Certifications: {certifications}

VERIFIED SKILLS (emphasise these first): {verified_str}
ADDITIONAL PROFILE SKILLS: {", ".join(other_skills) or "None"}
TRANSFERABLE BACKGROUND: {transferable_str or "None"}

EDUCATION:
{education_str}

WORK EXPERIENCE:
{experience_str}

═══ TARGET JOB ═══
Title: {job_dict.get("title")}
Company: {job_dict.get("company_name")}
Location: {job_dict.get("location") or "Not specified"}
Contract: {job_dict.get("contract_type") or "Not specified"}
Required skills: {required_skills_str}

═══ OUTPUT INSTRUCTIONS ═══
Write a professional CV adapted for this role using this exact structure:
1. Professional Summary (2–3 sentences tailored specifically to this role and company)
2. Core Skills (list VERIFIED SKILLS first, then other profile skills; never include: {real_gap_str})
3. Work Experience (most relevant first; honest bullet points from the profile data above)
4. Education
5. Certifications (if any)
6. Languages

Keep it concise, honest, and professional. Do not fabricate any detail."""


def build_cover_letter_prompt(
    profile_dict: dict[str, Any],
    profile_version_data: dict[str, Any] | None,
    job_dict: dict[str, Any],
    classification: RequirementClassification,
) -> str:
    """
    Build LLM prompt for cover letter.
    Enforces bridge language for transferable skills; forbids real_gap claims.
    """
    pv = profile_version_data or {}
    full_name = pv.get("full_name") or "the applicant"

    verified_str = (
        ", ".join(classification.verified_match)
        if classification.verified_match
        else "general technical background"
    )
    transferable_str = ", ".join(
        f"{t.skill} (transferable from {t.via})" for t in classification.transferable_match
    )
    real_gap_str = (
        ", ".join(classification.real_gap) if classification.real_gap else "none"
    )

    experience_level = profile_dict.get("experience_level") or "not specified"
    languages = ", ".join(profile_dict.get("languages") or []) or "not specified"

    return f"""Write a professional cover letter for a job application.

⚠️  CRITICAL RULES — VIOLATION IS FORBIDDEN:
1. VERIFIED skills ({verified_str}) may be claimed as direct expertise.
2. TRANSFERABLE skills: use bridge language ONLY.
   Examples: "similar experience with X", "background in related Y frameworks",
   "transferable skills from working with Z", "experience in adjacent tools".
3. REAL GAPS ({real_gap_str}): if mentioned, acknowledge honestly and positively.
   Example: "I am actively developing skills in X."
   Never claim current proficiency in: {real_gap_str}
4. Do NOT invent employers, project names, degrees, or achievements.
5. Write naturally in first person. Keep to 4 paragraphs.

═══ APPLICANT ═══
Name: {full_name}
Experience level: {experience_level}
Verified skills: {verified_str}
Transferable background: {transferable_str or "none"}
Languages: {languages}

═══ JOB ═══
Title: {job_dict.get("title")}
Company: {job_dict.get("company_name")}
Location: {job_dict.get("location") or "not specified"}
Contract: {job_dict.get("contract_type") or "not specified"}

═══ PARAGRAPH STRUCTURE ═══
Paragraph 1 — Opening: Specific enthusiasm for this role at this company. Why this position matters.
Paragraph 2 — Strengths: What you directly bring (VERIFIED skills and experience only).
Paragraph 3 — Bridge / Gaps: How transferable experience applies. If there are real gaps, acknowledge briefly and positively (not apologetically).
Paragraph 4 — Closing: Call to action and genuine enthusiasm to contribute."""


# ── Async functions ───────────────────────────────────────────────────────────

async def generate_cv_draft(provider: BaseLLMProvider, prompt: str) -> str:
    return await provider.generate(prompt, max_tokens=1200)


async def generate_cover_letter(provider: BaseLLMProvider, prompt: str) -> str:
    return await provider.generate(prompt, max_tokens=800)


async def prepare_application_package(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    provider: BaseLLMProvider,
) -> ApplicationPackage:
    """
    Full package generation pipeline:
    load data → match → classify → score → generate text → upsert.

    Raises ValueError if job or profile is not found.
    """
    # Load job
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise ValueError(f"Job {job_id} not found.")

    # Load profile
    active_profile = await profile_service.get_active_profile(db, user_id)
    if active_profile is None:
        raise ValueError(
            "No active profile found. Complete your profile before generating an application package."
        )

    # Load latest profile version (for full_name and raw CV data)
    pv_result = await db.execute(
        select(ProfileVersion)
        .where(ProfileVersion.user_id == user_id)
        .order_by(ProfileVersion.created_at.desc())
        .limit(1)
    )
    profile_version = pv_result.scalar_one_or_none()

    # Convert to dicts for matching engine and prompts
    job_dict = _job_to_dict(job)
    profile_dict = _profile_to_dict(active_profile)
    pv_dict = _profile_version_to_dict(profile_version) if profile_version else None

    # Run matching engine (deterministic)
    match_result: MatchResult = engine_match(job_dict, profile_dict)

    # Classify requirements (deterministic, pure)
    classification = classify_requirements(
        required_skills=list(job.required_skills or []),
        profile_skills=list(active_profile.skills or []),
        match_result=match_result,
    )

    # Compute score and warnings (deterministic, pure)
    score = compute_ready_to_apply_score(
        classification,
        list(job.required_skills or []),
        match_result,
        profile_dict,
    )
    warnings = generate_warnings(
        classification,
        list(job.required_skills or []),
        match_result,
    )

    # Generate CV and cover letter via LLM (text only, never influences score)
    cv_prompt = build_cv_adaptation_prompt(profile_dict, pv_dict, job_dict, classification)
    cl_prompt = build_cover_letter_prompt(profile_dict, pv_dict, job_dict, classification)

    cv_draft = await generate_cv_draft(provider, cv_prompt)
    cover_letter_draft = await generate_cover_letter(provider, cl_prompt)

    # Serialise classification for storage
    analysis_dict: dict = {
        "verified_match": classification.verified_match,
        "transferable_match": [
            {"skill": t.skill, "via": t.via, "family": t.family}
            for t in classification.transferable_match
        ],
        "real_gap": classification.real_gap,
    }

    # Upsert — one package per (user, job), regenerate on re-run
    existing_result = await db.execute(
        select(ApplicationPackage).where(
            ApplicationPackage.user_id == user_id,
            ApplicationPackage.job_id == job_id,
        )
    )
    pkg = existing_result.scalar_one_or_none()

    if pkg is None:
        pkg = ApplicationPackage(
            user_id=user_id,
            job_id=job_id,
            cv_draft=cv_draft,
            cover_letter_draft=cover_letter_draft,
            requirement_analysis=analysis_dict,
            warnings=warnings,
            ready_to_apply_score=score,
        )
        db.add(pkg)
    else:
        pkg.cv_draft = cv_draft
        pkg.cover_letter_draft = cover_letter_draft
        pkg.requirement_analysis = analysis_dict
        pkg.warnings = warnings
        pkg.ready_to_apply_score = score

    await db.commit()
    await db.refresh(pkg)
    return pkg


async def get_application_package(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
) -> ApplicationPackage | None:
    result = await db.execute(
        select(ApplicationPackage).where(
            ApplicationPackage.user_id == user_id,
            ApplicationPackage.job_id == job_id,
        )
    )
    return result.scalar_one_or_none()
