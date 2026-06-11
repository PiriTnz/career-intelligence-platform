"""
Prompt construction and explanation generation for job scores and match results.

Rule: LLM output is purely informational — it never changes the numeric score,
never filters jobs, and never re-ranks results.
"""
from __future__ import annotations

import logging

from app.llm.base import BaseLLMProvider
from app.services.scoring_service import ScoreBreakdown

logger = logging.getLogger(__name__)

_EXP_GAP_DESC: dict[int, str] = {
    0: "exact level match",
    1: "slightly overqualified (+1)",
    2: "overqualified by 2 levels",
    -1: "slightly underqualified (−1)",
    -2: "underqualified by 2 levels",
}


# ── Score-only explanation (original) ─────────────────────────────────────────

def build_score_prompt(
    *,
    job_title: str,
    company_name: str,
    location: str | None,
    remote: str,
    contract_type: str | None,
    required_skills: list[str],
    breakdown: ScoreBreakdown,
    confidence: int,
    candidate_skills: list[str],
    candidate_cities: list[str],
) -> str:
    matched = [s for s in required_skills if s.lower() in {c.lower() for c in candidate_skills}]
    missing = [s for s in required_skills if s.lower() not in {c.lower() for c in candidate_skills}]

    low_confidence_note = (
        "\nNote: extraction confidence is low — job description may be incomplete."
        if confidence < 60 else ""
    )

    return f"""You are a concise career advisor. Explain in exactly 2-3 sentences why this job scored {breakdown.total}/100.

Job: {job_title} at {company_name}
Location: {location or 'not specified'} | Remote: {remote} | Contract: {contract_type or 'not specified'}
Required skills: {', '.join(required_skills) or 'not specified'}
Skills matched: {', '.join(matched) or 'none'} | Skills missing: {', '.join(missing) or 'none'}
Candidate preferred cities: {', '.join(candidate_cities)}

Score breakdown:
  Skill match      {breakdown.skill_match}/30
  Experience       {breakdown.experience_match}/20
  Location         {breakdown.location_score}/15
  Salary           {breakdown.salary_score}/15
  Contract         {breakdown.contract_score}/10
  Company quality  {breakdown.company_score}/5
  Freshness        {breakdown.freshness_score}/5
  Total            {breakdown.total}/100
{low_confidence_note}
Rules: be specific, mention the strongest dimension and the biggest gap, no generic phrases, max 3 sentences."""


async def explain_score(
    provider: BaseLLMProvider,
    *,
    job_title: str,
    company_name: str,
    location: str | None,
    remote: str,
    contract_type: str | None,
    required_skills: list[str],
    breakdown: ScoreBreakdown,
    confidence: int,
    candidate_skills: list[str],
    candidate_cities: list[str],
) -> str:
    """
    Generate a human-readable explanation for a job score.
    Returns an empty string if the LLM is unavailable — callers must handle this.
    """
    prompt = build_score_prompt(
        job_title=job_title,
        company_name=company_name,
        location=location,
        remote=remote,
        contract_type=contract_type,
        required_skills=required_skills,
        breakdown=breakdown,
        confidence=confidence,
        candidate_skills=candidate_skills,
        candidate_cities=candidate_cities,
    )
    text = await provider.generate(prompt, max_tokens=200)
    if not text:
        logger.warning("LLM explanation empty for job '%s'", job_title)
    return text


# ── Match-aware explanation (score + matching engine data) ────────────────────

def build_match_explanation_prompt(
    *,
    job_title: str,
    company_name: str,
    breakdown: ScoreBreakdown,
    matched_skills: list[str],
    missing_skills: list[str],
    skill_match_percentage: float,
    role_match_percentage: float,
    best_matching_role: str | None,
    location_match: bool,
    remote_match: bool,
    contract_match: bool,
    language_match: bool,
    salary_ok: bool,
    overall_fit: float,
    candidate_experience_level: str | None = None,
    confidence: int = 100,
) -> str:
    matched_str = ", ".join(matched_skills) or "none"
    missing_str = ", ".join(missing_skills) or "none — fully qualified on skills"

    role_desc = (
        f"{best_matching_role} ({role_match_percentage:.0f}% match)"
        if best_matching_role
        else f"no direct target role ({role_match_percentage:.0f}%)"
    )

    logistics = " | ".join([
        f"location {'✓' if location_match else '✗'}",
        f"remote {'✓' if remote_match else '✗'}",
        f"contract {'✓' if contract_match else '✗'}",
        f"language {'✓' if language_match else '✗'}",
        f"salary {'✓' if salary_ok else '✗'}",
    ])

    low_confidence_note = (
        "\nNote: extraction confidence is low — job description may be incomplete."
        if confidence < 60 else ""
    )

    return f"""You are a concise career advisor. Explain in exactly 2-3 sentences why this job scored {breakdown.total}/100 with an overall fit of {overall_fit:.0f}%.

Job: {job_title} at {company_name}
Role fit: {role_desc}
Skills matched ({skill_match_percentage:.0f}%): {matched_str}
Skills missing: {missing_str}
Candidate level: {candidate_experience_level or 'unknown'}
Logistics: {logistics}

Score breakdown:
  Skill match      {breakdown.skill_match}/30
  Experience       {breakdown.experience_match}/20
  Location         {breakdown.location_score}/15
  Salary           {breakdown.salary_score}/15
  Contract         {breakdown.contract_score}/10
  Company quality  {breakdown.company_score}/5
  Freshness        {breakdown.freshness_score}/5
  Total            {breakdown.total}/100
{low_confidence_note}
Rules: be specific, cite 1-2 concrete score dimensions, name the strongest match and biggest gap, no filler phrases, max 3 sentences."""


async def explain_match(
    provider: BaseLLMProvider,
    *,
    job_title: str,
    company_name: str,
    breakdown: ScoreBreakdown,
    matched_skills: list[str],
    missing_skills: list[str],
    skill_match_percentage: float,
    role_match_percentage: float,
    best_matching_role: str | None,
    location_match: bool,
    remote_match: bool,
    contract_match: bool,
    language_match: bool,
    salary_ok: bool,
    overall_fit: float,
    candidate_experience_level: str | None = None,
    confidence: int = 100,
) -> str:
    """
    Generate a richer explanation using both score breakdown and matching engine data.
    Returns an empty string if the LLM is unavailable — callers must handle this.
    """
    prompt = build_match_explanation_prompt(
        job_title=job_title,
        company_name=company_name,
        breakdown=breakdown,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        skill_match_percentage=skill_match_percentage,
        role_match_percentage=role_match_percentage,
        best_matching_role=best_matching_role,
        location_match=location_match,
        remote_match=remote_match,
        contract_match=contract_match,
        language_match=language_match,
        salary_ok=salary_ok,
        overall_fit=overall_fit,
        candidate_experience_level=candidate_experience_level,
        confidence=confidence,
    )
    text = await provider.generate(prompt, max_tokens=250)
    if not text:
        logger.warning("LLM match explanation empty for job '%s'", job_title)
    return text


# ── Gap analysis ──────────────────────────────────────────────────────────────

def build_gap_analysis_prompt(
    *,
    job_title: str,
    company_name: str,
    required_skills: list[str],
    matched_skills: list[str],
    missing_skills: list[str],
    skill_match_percentage: float,
    experience_gap: int,
    candidate_skills: list[str],
    candidate_experience_level: str | None,
    job_experience_level: str | None,
) -> str:
    exp_desc = _EXP_GAP_DESC.get(experience_gap, f"gap of {experience_gap:+d} levels")
    missing_str = ", ".join(missing_skills) or "none — fully qualified on skills"
    n_matched = len(matched_skills)
    n_required = len(required_skills)

    return f"""You are a career coach. Give actionable upskilling advice in 3-4 sentences.

Role: {job_title} at {company_name}
Required skills: {', '.join(required_skills) or 'not specified'} (level: {job_experience_level or 'not specified'})
Candidate skills: {', '.join(candidate_skills[:15]) or 'none listed'} (level: {candidate_experience_level or 'unknown'})
Coverage: {skill_match_percentage:.0f}% ({n_matched}/{n_required} skills matched)
Missing skills: {missing_str}
Experience gap: {exp_desc}

Answer: Which 2-3 missing skills should the candidate prioritise, and is this application worth pursuing now or after upskilling?
Rules: be specific and actionable, name concrete skills, no filler phrases, max 4 sentences."""


async def gap_analysis(
    provider: BaseLLMProvider,
    *,
    job_title: str,
    company_name: str,
    required_skills: list[str],
    matched_skills: list[str],
    missing_skills: list[str],
    skill_match_percentage: float,
    experience_gap: int,
    candidate_skills: list[str],
    candidate_experience_level: str | None,
    job_experience_level: str | None,
) -> str:
    """
    Generate actionable skill-gap advice for a specific job.
    Returns an empty string if the LLM is unavailable — callers must handle this.
    """
    prompt = build_gap_analysis_prompt(
        job_title=job_title,
        company_name=company_name,
        required_skills=required_skills,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        skill_match_percentage=skill_match_percentage,
        experience_gap=experience_gap,
        candidate_skills=candidate_skills,
        candidate_experience_level=candidate_experience_level,
        job_experience_level=job_experience_level,
    )
    text = await provider.generate(prompt, max_tokens=300)
    if not text:
        logger.warning("LLM gap analysis empty for job '%s'", job_title)
    return text
