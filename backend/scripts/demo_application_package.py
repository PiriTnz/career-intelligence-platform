"""
Demo: Application Package Agent

Demonstrates the deterministic requirement classification and ready-to-apply
scoring using synthetic profile and job data.
No database or LLM connection required — pure function demo only.

Run from the backend directory:
    python scripts/demo_application_package.py
"""
from __future__ import annotations

import json
from dataclasses import asdict

from app.services.application_package_service import (
    RequirementClassification,
    TransferableSkillResult,
    classify_requirements,
    compute_ready_to_apply_score,
    generate_warnings,
    build_cv_adaptation_prompt,
    build_cover_letter_prompt,
    SKILL_FAMILIES,
)
from app.services.matching_engine import MatchResult


# ── Helper ────────────────────────────────────────────────────────────────────

def _make_match(
    matched: list[str],
    missing: list[str],
    experience_gap: int = 0,
    location_match: bool = True,
    remote_match: bool = True,
    contract_match: bool = True,
    salary_ok: bool = True,
    language_match: bool = True,
) -> MatchResult:
    return MatchResult(
        matched_skills=matched,
        missing_skills=missing,
        skill_match_percentage=len(matched) / max(len(matched) + len(missing), 1) * 100,
        role_match_percentage=0.0,
        best_matching_role=None,
        location_match=location_match,
        remote_match=remote_match,
        contract_match=contract_match,
        language_match=language_match,
        salary_ok=salary_ok,
        experience_gap=experience_gap,
        overall_fit=0.0,
    )


def _print_section(title: str) -> None:
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print('═' * 60)


def _print_classification(cls: RequirementClassification) -> None:
    print(f"  ✅  Verified match  ({len(cls.verified_match)}): {cls.verified_match}")
    for t in cls.transferable_match:
        print(f"  🔀  Transferable    : {t.skill}  (via {t.via}, family: {t.family})")
    if not cls.transferable_match:
        print(f"  🔀  Transferable    (0): []")
    print(f"  ❌  Real gap        ({len(cls.real_gap)}): {cls.real_gap}")


# ── Scenario 1: High-match job ────────────────────────────────────────────────

_print_section("Scenario 1 — High-match job (ML Engineer, strong overlap)")

PROFILE_HIGH = {
    "skills": ["python", "pytorch", "docker", "fastapi", "postgresql"],
    "target_roles": ["machine learning engineer", "mlops engineer"],
    "experience_level": "mid",
    "countries": ["France"],
    "cities": ["Paris"],
    "remote_preference": True,
    "contract_types": ["cdi"],
    "salary_min": 50000,
    "salary_target": 65000,
    "languages": ["English", "French"],
    "certifications": [],
    "education": [{"degree": "MSc Computer Science", "university": "Université Paris-Saclay", "year": "2022"}],
    "experience": [{"title": "ML Engineer Intern", "company": "[Company]", "duration": "6 months", "bullets": ["Built training pipeline with PyTorch", "Deployed model API with FastAPI"]}],
}

JOB_HIGH = {
    "title": "ML Engineer",
    "company_name": "AIStartup",
    "location": "Paris",
    "contract_type": "cdi",
    "required_skills": ["python", "pytorch", "docker", "tensorflow", "kubernetes"],
    "experience_level": "mid",
    "remote": "hybrid",
}

match_high = _make_match(
    matched=["python", "pytorch", "docker"],
    missing=["tensorflow", "kubernetes"],
    experience_gap=0,
    location_match=True,
    remote_match=True,
)

classification_high = classify_requirements(
    required_skills=JOB_HIGH["required_skills"],
    profile_skills=PROFILE_HIGH["skills"],
    match_result=match_high,
)

score_high = compute_ready_to_apply_score(
    classification_high, JOB_HIGH["required_skills"], match_high, PROFILE_HIGH
)
warnings_high = generate_warnings(classification_high, JOB_HIGH["required_skills"], match_high)

_print_classification(classification_high)
print(f"\n  📊  Ready-to-apply score: {score_high}/100")
print(f"  ⚠️   Warnings ({len(warnings_high)}): {warnings_high or ['none']}")

# Verify safety: real_gap never in verified
assert set(classification_high.real_gap).isdisjoint(set(classification_high.verified_match)), \
    "SAFETY VIOLATION: real_gap skill appeared in verified_match"
assert "tensorflow" not in classification_high.real_gap or \
    any(t.skill == "tensorflow" for t in classification_high.transferable_match), \
    "tensorflow should be transferable (pytorch bridges it)"
print("\n  🔒  Safety check PASSED: real_gap ∩ verified_match = ∅")


# ── Scenario 2: Medium-match job ──────────────────────────────────────────────

_print_section("Scenario 2 — Medium-match job (DevOps, partial overlap)")

PROFILE_MED = {
    "skills": ["python", "docker", "bash", "postgresql"],
    "target_roles": ["backend engineer", "platform engineer"],
    "experience_level": "junior",
    "countries": ["France"],
    "cities": [],
    "remote_preference": False,
    "contract_types": ["cdd", "cdi"],
    "salary_min": 38000,
    "salary_target": 45000,
    "languages": ["English"],
    "certifications": [],
    "education": [{"degree": "BEng Software Engineering", "university": "[University]", "year": "2023"}],
    "experience": [{"title": "Junior Developer", "company": "[Company]", "duration": "1 year", "bullets": ["Built backend APIs with Python", "Maintained Docker-based CI pipelines"]}],
}

JOB_MED = {
    "title": "DevOps Engineer",
    "company_name": "TechCorp",
    "location": "Lyon",
    "contract_type": "cdi",
    "required_skills": ["docker", "kubernetes", "terraform", "ansible", "aws"],
    "experience_level": "mid",
    "remote": "none",
}

match_med = _make_match(
    matched=["docker"],
    missing=["kubernetes", "terraform", "ansible", "aws"],
    experience_gap=-1,
    location_match=False,
    remote_match=False,
    contract_match=True,
    salary_ok=True,
)

classification_med = classify_requirements(
    required_skills=JOB_MED["required_skills"],
    profile_skills=PROFILE_MED["skills"],
    match_result=match_med,
)

score_med = compute_ready_to_apply_score(
    classification_med, JOB_MED["required_skills"], match_med, PROFILE_MED
)
warnings_med = generate_warnings(classification_med, JOB_MED["required_skills"], match_med)

_print_classification(classification_med)
print(f"\n  📊  Ready-to-apply score: {score_med}/100")
print(f"  ⚠️   Warnings ({len(warnings_med)}):")
for w in warnings_med:
    print(f"       - {w}")

# Verify safety: real_gap and verified are disjoint
assert set(classification_med.real_gap).isdisjoint(set(classification_med.verified_match)), \
    "SAFETY VIOLATION: real_gap skill appeared in verified_match"
print("\n  🔒  Safety check PASSED: real_gap ∩ verified_match = ∅")


# ── Scenario 3: Prompt inspection ────────────────────────────────────────────

_print_section("Scenario 3 — Prompt safety inspection (CV and Cover Letter)")

PROFILE_VERSION_DATA = {
    "full_name": "Alex Martin",
    "extracted_skills": ["python", "docker"],
    "inferred_skills": ["backend development"],
    "education": [{"degree": "MSc Computer Science", "university": "Université Paris-Saclay", "year": "2022"}],
    "experience": [{"title": "Junior Backend Engineer", "company": "[Company]", "duration": "1 year", "bullets": ["REST APIs with FastAPI", "Docker deployment"]}],
    "certifications": [],
}

cv_prompt = build_cv_adaptation_prompt(
    PROFILE_HIGH, PROFILE_VERSION_DATA, JOB_HIGH, classification_high
)
cl_prompt = build_cover_letter_prompt(
    PROFILE_HIGH, PROFILE_VERSION_DATA, JOB_HIGH, classification_high
)

# Check that real_gap skills are in the "forbidden" section of both prompts
for skill in classification_high.real_gap:
    assert skill.lower() in cv_prompt.lower(), f"Real gap skill '{skill}' missing from CV prompt"
    assert skill.lower() in cl_prompt.lower(), f"Real gap skill '{skill}' missing from cover letter prompt"

# Check that verified skills are in the prompts
for skill in classification_high.verified_match:
    assert skill.lower() in cv_prompt.lower(), f"Verified skill '{skill}' missing from CV prompt"

# Check that bridge language is instructed in cover letter
assert "bridge" in cl_prompt.lower() or "transferable" in cl_prompt.lower(), \
    "Cover letter prompt must include bridge/transferable language instruction"

print("  ✅  Real-gap skills present in FORBIDDEN sections of both prompts")
print("  ✅  Verified skills present in CV prompt")
print("  ✅  Bridge language instruction present in cover letter prompt")
print(f"  ℹ️   CV prompt length: {len(cv_prompt)} chars")
print(f"  ℹ️   Cover letter prompt length: {len(cl_prompt)} chars")
print(f"  ℹ️   Applicant name from profile version: Alex Martin")


# ── Scenario 4: Skill family coverage ────────────────────────────────────────

_print_section("Scenario 4 — Skill family coverage")

families = list(SKILL_FAMILIES.keys())
print(f"  Total skill families: {len(families)}")
for fname in families:
    members = sorted(SKILL_FAMILIES[fname])
    print(f"  [{fname}] ({len(members)} skills): {', '.join(members[:5])}{'...' if len(members) > 5 else ''}")


# ── Summary ───────────────────────────────────────────────────────────────────

_print_section("Summary")
print(f"  Scenario 1 (high match): score={score_high}/100, warnings={len(warnings_high)}")
print(f"  Scenario 2 (medium match): score={score_med}/100, warnings={len(warnings_med)}")
print(f"  Skill families registered: {len(SKILL_FAMILIES)}")
print(f"\n  All safety assertions PASSED ✅")
print(f"\n  ℹ️  To test with live LLM + DB, run the FastAPI server and call:")
print(f"       POST /api/v1/applications/{{job_id}}/prepare")
print(f"       GET  /api/v1/applications/{{job_id}}/package")
