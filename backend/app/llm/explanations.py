"""
Prompt construction and explanation generation for job scores.

Rule: LLM output is purely informational — it never changes the numeric score,
never filters jobs, and never re-ranks results.
"""
from __future__ import annotations

import logging

from app.llm.base import BaseLLMProvider
from app.services.scoring_service import ScoreBreakdown

logger = logging.getLogger(__name__)


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
