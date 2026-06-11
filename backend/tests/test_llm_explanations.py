"""
Unit tests for LLM prompt builders and explanation functions.

Prompt builders are pure functions — no mocks needed.
LLM caller functions (explain_match, gap_analysis) are tested with an AsyncMock provider.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.llm.explanations import (
    build_gap_analysis_prompt,
    build_match_explanation_prompt,
    build_score_prompt,
    explain_match,
    explain_score,
    gap_analysis,
)
from app.services.scoring_service import ScoreBreakdown


# ── Shared fixtures ───────────────────────────────────────────────────────────

def _breakdown(
    skill=20, exp=15, loc=10, sal=10, con=8, comp=4, fresh=4
) -> ScoreBreakdown:
    return ScoreBreakdown(
        skill_match=skill,
        experience_match=exp,
        location_score=loc,
        salary_score=sal,
        contract_score=con,
        company_score=comp,
        freshness_score=fresh,
    )


def _provider(text: str = "Generated explanation.") -> AsyncMock:
    p = AsyncMock()
    p.generate = AsyncMock(return_value=text)
    return p


# ── build_score_prompt() ──────────────────────────────────────────────────────

class TestBuildScorePrompt:
    def test_contains_job_title_and_company(self):
        prompt = build_score_prompt(
            job_title="ML Engineer",
            company_name="Acme Corp",
            location="Paris",
            remote="hybrid",
            contract_type="cdi",
            required_skills=["python"],
            breakdown=_breakdown(),
            confidence=80,
            candidate_skills=["python"],
            candidate_cities=["paris"],
        )
        assert "ML Engineer" in prompt
        assert "Acme Corp" in prompt

    def test_contains_total_score(self):
        bd = _breakdown()
        prompt = build_score_prompt(
            job_title="X", company_name="Y", location=None,
            remote="none", contract_type=None,
            required_skills=[], breakdown=bd, confidence=80,
            candidate_skills=[], candidate_cities=[],
        )
        assert str(bd.total) in prompt

    def test_matched_skills_listed(self):
        prompt = build_score_prompt(
            job_title="X", company_name="Y", location=None,
            remote="none", contract_type=None,
            required_skills=["python", "docker"],
            breakdown=_breakdown(), confidence=80,
            candidate_skills=["python"],
            candidate_cities=[],
        )
        assert "python" in prompt

    def test_missing_skills_listed(self):
        prompt = build_score_prompt(
            job_title="X", company_name="Y", location=None,
            remote="none", contract_type=None,
            required_skills=["python", "docker"],
            breakdown=_breakdown(), confidence=80,
            candidate_skills=["python"],
            candidate_cities=[],
        )
        assert "docker" in prompt

    def test_low_confidence_note_added(self):
        prompt = build_score_prompt(
            job_title="X", company_name="Y", location=None,
            remote="none", contract_type=None,
            required_skills=[], breakdown=_breakdown(), confidence=40,
            candidate_skills=[], candidate_cities=[],
        )
        assert "confidence" in prompt.lower()

    def test_no_low_confidence_note_above_threshold(self):
        prompt = build_score_prompt(
            job_title="X", company_name="Y", location=None,
            remote="none", contract_type=None,
            required_skills=[], breakdown=_breakdown(), confidence=60,
            candidate_skills=[], candidate_cities=[],
        )
        assert "extraction confidence is low" not in prompt

    def test_score_breakdown_dimensions_present(self):
        bd = _breakdown(skill=25, exp=18, loc=12, sal=9, con=7, comp=3, fresh=2)
        prompt = build_score_prompt(
            job_title="X", company_name="Y", location="Lyon",
            remote="full", contract_type="cdi",
            required_skills=[], breakdown=bd, confidence=90,
            candidate_skills=[], candidate_cities=["lyon"],
        )
        assert "25/30" in prompt
        assert "18/20" in prompt


# ── build_match_explanation_prompt() ─────────────────────────────────────────

class TestBuildMatchExplanationPrompt:
    def _base_kwargs(self, **overrides):
        kw = dict(
            job_title="ML Engineer",
            company_name="Mistral AI",
            breakdown=_breakdown(),
            matched_skills=["python", "pytorch"],
            missing_skills=["rag"],
            skill_match_percentage=66.7,
            role_match_percentage=90.0,
            best_matching_role="ML Engineer",
            location_match=True,
            remote_match=True,
            contract_match=True,
            language_match=True,
            salary_ok=True,
            overall_fit=82.0,
            candidate_experience_level="mid",
            confidence=85,
        )
        kw.update(overrides)
        return kw

    def test_contains_job_title(self):
        prompt = build_match_explanation_prompt(**self._base_kwargs())
        assert "ML Engineer" in prompt

    def test_contains_overall_fit(self):
        prompt = build_match_explanation_prompt(**self._base_kwargs(overall_fit=75.0))
        assert "75" in prompt

    def test_matched_skills_in_prompt(self):
        prompt = build_match_explanation_prompt(**self._base_kwargs())
        assert "python" in prompt
        assert "pytorch" in prompt

    def test_missing_skills_in_prompt(self):
        prompt = build_match_explanation_prompt(**self._base_kwargs())
        assert "rag" in prompt

    def test_role_match_percentage_in_prompt(self):
        prompt = build_match_explanation_prompt(**self._base_kwargs(role_match_percentage=90.0))
        assert "90" in prompt

    def test_best_matching_role_in_prompt(self):
        prompt = build_match_explanation_prompt(**self._base_kwargs(best_matching_role="LLM Engineer"))
        assert "LLM Engineer" in prompt

    def test_no_best_role_shows_fallback(self):
        prompt = build_match_explanation_prompt(**self._base_kwargs(best_matching_role=None))
        assert "no direct target role" in prompt

    def test_logistics_checks_present(self):
        prompt = build_match_explanation_prompt(**self._base_kwargs(
            location_match=True, remote_match=False, contract_match=True
        ))
        assert "✓" in prompt
        assert "✗" in prompt

    def test_low_confidence_note(self):
        prompt = build_match_explanation_prompt(**self._base_kwargs(confidence=55))
        assert "confidence" in prompt.lower()

    def test_high_confidence_no_note(self):
        prompt = build_match_explanation_prompt(**self._base_kwargs(confidence=95))
        assert "extraction confidence is low" not in prompt

    def test_candidate_experience_level_in_prompt(self):
        prompt = build_match_explanation_prompt(**self._base_kwargs(candidate_experience_level="senior"))
        assert "senior" in prompt

    def test_score_total_in_prompt(self):
        bd = _breakdown()
        prompt = build_match_explanation_prompt(**self._base_kwargs(breakdown=bd))
        assert str(bd.total) in prompt


# ── build_gap_analysis_prompt() ───────────────────────────────────────────────

class TestBuildGapAnalysisPrompt:
    def _base_kwargs(self, **overrides):
        kw = dict(
            job_title="Senior ML Engineer",
            company_name="Hugging Face",
            required_skills=["python", "pytorch", "rag", "langchain"],
            matched_skills=["python", "pytorch"],
            missing_skills=["rag", "langchain"],
            skill_match_percentage=50.0,
            experience_gap=0,
            candidate_skills=["python", "pytorch", "fastapi"],
            candidate_experience_level="mid",
            job_experience_level="senior",
        )
        kw.update(overrides)
        return kw

    def test_contains_job_title(self):
        prompt = build_gap_analysis_prompt(**self._base_kwargs())
        assert "Senior ML Engineer" in prompt

    def test_contains_missing_skills(self):
        prompt = build_gap_analysis_prompt(**self._base_kwargs())
        assert "rag" in prompt
        assert "langchain" in prompt

    def test_skill_coverage_percentage(self):
        prompt = build_gap_analysis_prompt(**self._base_kwargs(skill_match_percentage=50.0))
        assert "50" in prompt

    def test_experience_gap_exact_match_label(self):
        prompt = build_gap_analysis_prompt(**self._base_kwargs(experience_gap=0))
        assert "exact level match" in prompt

    def test_experience_gap_underqualified_label(self):
        prompt = build_gap_analysis_prompt(**self._base_kwargs(experience_gap=-1))
        assert "underqualified" in prompt

    def test_experience_gap_overqualified_label(self):
        prompt = build_gap_analysis_prompt(**self._base_kwargs(experience_gap=1))
        assert "overqualified" in prompt

    def test_no_missing_skills_shows_qualified_message(self):
        prompt = build_gap_analysis_prompt(**self._base_kwargs(missing_skills=[]))
        assert "fully qualified" in prompt

    def test_required_skills_listed(self):
        prompt = build_gap_analysis_prompt(**self._base_kwargs())
        assert "pytorch" in prompt

    def test_candidate_skills_listed(self):
        prompt = build_gap_analysis_prompt(**self._base_kwargs())
        assert "fastapi" in prompt

    def test_candidate_and_job_levels_present(self):
        prompt = build_gap_analysis_prompt(**self._base_kwargs(
            candidate_experience_level="mid", job_experience_level="senior"
        ))
        assert "mid" in prompt
        assert "senior" in prompt


# ── explain_score() ───────────────────────────────────────────────────────────

class TestExplainScore:
    async def test_calls_provider_generate(self):
        provider = _provider("Score explanation.")
        result = await explain_score(
            provider,
            job_title="ML Engineer", company_name="Acme",
            location="Paris", remote="none", contract_type="cdi",
            required_skills=["python"], breakdown=_breakdown(),
            confidence=80, candidate_skills=["python"], candidate_cities=["paris"],
        )
        assert result == "Score explanation."
        provider.generate.assert_called_once()

    async def test_returns_empty_string_when_llm_fails(self):
        provider = _provider("")
        result = await explain_score(
            provider,
            job_title="ML Engineer", company_name="Acme",
            location=None, remote="none", contract_type=None,
            required_skills=[], breakdown=_breakdown(),
            confidence=80, candidate_skills=[], candidate_cities=[],
        )
        assert result == ""


# ── explain_match() ───────────────────────────────────────────────────────────

class TestExplainMatch:
    def _kwargs(self, provider):
        return dict(
            provider=provider,
            job_title="ML Engineer",
            company_name="Acme",
            breakdown=_breakdown(),
            matched_skills=["python"],
            missing_skills=["rag"],
            skill_match_percentage=50.0,
            role_match_percentage=80.0,
            best_matching_role="ML Engineer",
            location_match=True,
            remote_match=False,
            contract_match=True,
            language_match=True,
            salary_ok=True,
            overall_fit=70.0,
        )

    async def test_calls_provider_generate(self):
        provider = _provider("Match explanation.")
        result = await explain_match(**self._kwargs(provider))
        assert result == "Match explanation."
        provider.generate.assert_called_once()

    async def test_returns_empty_string_when_llm_fails(self):
        provider = _provider("")
        result = await explain_match(**self._kwargs(provider))
        assert result == ""

    async def test_uses_higher_max_tokens_than_score_prompt(self):
        provider = _provider("ok")
        await explain_match(**self._kwargs(provider))
        _, kwargs = provider.generate.call_args
        assert kwargs.get("max_tokens", 0) >= 200


# ── gap_analysis() ────────────────────────────────────────────────────────────

class TestGapAnalysis:
    def _kwargs(self, provider):
        return dict(
            provider=provider,
            job_title="Senior ML Engineer",
            company_name="Hugging Face",
            required_skills=["python", "pytorch", "rag"],
            matched_skills=["python", "pytorch"],
            missing_skills=["rag"],
            skill_match_percentage=66.7,
            experience_gap=-1,
            candidate_skills=["python", "pytorch"],
            candidate_experience_level="mid",
            job_experience_level="senior",
        )

    async def test_calls_provider_generate(self):
        provider = _provider("Gap advice.")
        result = await gap_analysis(**self._kwargs(provider))
        assert result == "Gap advice."
        provider.generate.assert_called_once()

    async def test_returns_empty_string_when_llm_fails(self):
        provider = _provider("")
        result = await gap_analysis(**self._kwargs(provider))
        assert result == ""

    async def test_uses_higher_max_tokens(self):
        provider = _provider("ok")
        await gap_analysis(**self._kwargs(provider))
        _, kwargs = provider.generate.call_args
        assert kwargs.get("max_tokens", 0) >= 250
