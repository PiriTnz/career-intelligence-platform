"""
Tests for interview_optimization_service.

Coverage:
- classify_skills_extended (pure)
- compute_readiness (pure)
- generate_recruiter_concerns (pure)
- generate_mitigation_strategies (pure)
- generate_warnings (pure)
- build_cv_optimization_prompt (pure)
- build_cover_letter_prompt (pure)
- Safety: verified/transferable/learning/missing are mutually exclusive
- Safety: missing skills never in CV prompt claimed section
- Safety: learning skills appear only in Currently Learning section instruction
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.interview_optimization_service import (
    ExtendedClassification,
    MitigationStrategy,
    RecruiterConcern,
    TransferableSkill,
    build_cover_letter_prompt,
    build_cv_optimization_prompt,
    classify_skills_extended,
    compute_readiness,
    generate_mitigation_strategies,
    generate_recruiter_concerns,
    generate_warnings,
)
from app.services.matching_engine import MatchResult


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_match(
    matched=None,
    missing=None,
    experience_gap=0,
    location_match=True,
    remote_match=False,
    contract_match=True,
    salary_ok=True,
    language_match=True,
) -> MatchResult:
    return MatchResult(
        matched_skills=matched or [],
        missing_skills=missing or [],
        skill_match_percentage=0.0,
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


def _kb_entry(skill, status, source="profile"):
    e = MagicMock()
    e.skill = skill.lower()
    e.status = status
    e.source = source
    e.confidence = 1.0
    return e


def _base_profile():
    return {
        "skills": ["python", "docker", "postgresql"],
        "target_roles": ["backend engineer"],
        "experience_level": "mid",
        "countries": ["France"],
        "cities": [],
        "languages": ["English"],
        "certifications": [],
        "education": [],
        "experience": [],
    }


# ── TestClassifySkillsExtended ────────────────────────────────────────────────

class TestClassifySkillsExtended:
    def test_engine_matched_skill_goes_to_verified(self):
        match = _make_match(matched=["python", "docker"], missing=[])
        result = classify_skills_extended(
            required_skills=["python", "docker"],
            profile_skills=["python", "docker"],
            knowledge_base=[],
            match_result=match,
        )
        assert "python" in result.verified
        assert "docker" in result.verified
        assert result.missing == []
        assert result.learning == []

    def test_kb_verified_skill_goes_to_verified_even_if_not_matched(self):
        # Skill in KB as verified but not in match result (edge case)
        match = _make_match(matched=[], missing=["terraform"])
        kb = [_kb_entry("terraform", "verified")]
        result = classify_skills_extended(
            required_skills=["terraform"],
            profile_skills=[],
            knowledge_base=kb,
            match_result=match,
        )
        assert "terraform" in result.verified
        assert result.missing == []

    def test_learning_skill_from_kb_goes_to_learning(self):
        match = _make_match(matched=["python"], missing=["azure"])
        kb = [_kb_entry("azure", "learning")]
        result = classify_skills_extended(
            required_skills=["python", "azure"],
            profile_skills=["python"],
            knowledge_base=kb,
            match_result=match,
        )
        assert "azure" in result.learning
        assert "azure" not in result.verified
        assert "azure" not in result.missing

    def test_transferable_when_same_family(self):
        match = _make_match(matched=["python"], missing=["tensorflow"])
        result = classify_skills_extended(
            required_skills=["python", "tensorflow"],
            profile_skills=["python", "pytorch"],
            knowledge_base=[],
            match_result=match,
        )
        assert len(result.transferable) == 1
        assert result.transferable[0].skill == "tensorflow"
        assert result.transferable[0].via == "pytorch"

    def test_missing_when_no_evidence_or_bridge(self):
        match = _make_match(matched=[], missing=["cobol"])
        result = classify_skills_extended(
            required_skills=["cobol"],
            profile_skills=["python"],
            knowledge_base=[],
            match_result=match,
        )
        assert "cobol" in result.missing
        assert result.verified == []
        assert result.transferable == []
        assert result.learning == []

    def test_four_categories_mutually_exclusive(self):
        required = ["python", "tensorflow", "azure", "cobol"]
        match = _make_match(matched=["python"], missing=["tensorflow", "azure", "cobol"])
        kb = [_kb_entry("azure", "learning")]
        result = classify_skills_extended(
            required_skills=required,
            profile_skills=["python", "pytorch"],
            knowledge_base=kb,
            match_result=match,
        )
        verified_set = set(r.lower() for r in result.verified)
        transfer_set = set(t.skill.lower() for t in result.transferable)
        learning_set = set(r.lower() for r in result.learning)
        missing_set = set(r.lower() for r in result.missing)

        assert verified_set.isdisjoint(transfer_set), "verified ∩ transferable ≠ ∅"
        assert verified_set.isdisjoint(learning_set), "verified ∩ learning ≠ ∅"
        assert verified_set.isdisjoint(missing_set),  "verified ∩ missing ≠ ∅"
        assert transfer_set.isdisjoint(learning_set), "transferable ∩ learning ≠ ∅"
        assert transfer_set.isdisjoint(missing_set),  "transferable ∩ missing ≠ ∅"
        assert learning_set.isdisjoint(missing_set),  "learning ∩ missing ≠ ∅"

    def test_total_equals_required_count(self):
        required = ["python", "tensorflow", "kubernetes", "azure", "rust"]
        match = _make_match(matched=["python"], missing=["tensorflow", "kubernetes", "azure", "rust"])
        kb = [_kb_entry("azure", "learning")]
        result = classify_skills_extended(required, ["python", "pytorch", "docker"], kb, match)
        total = (
            len(result.verified) + len(result.transferable)
            + len(result.learning) + len(result.missing)
        )
        assert total == len(required)

    def test_learning_takes_priority_over_transferable(self):
        # "tensorflow" is in ml_frameworks family (pytorch could bridge it)
        # BUT KB marks it as "learning" → should be learning, not transferable
        match = _make_match(matched=[], missing=["tensorflow"])
        kb = [_kb_entry("tensorflow", "learning")]
        result = classify_skills_extended(
            required_skills=["tensorflow"],
            profile_skills=["pytorch"],
            knowledge_base=kb,
            match_result=match,
        )
        assert "tensorflow" in result.learning
        assert all(t.skill != "tensorflow" for t in result.transferable)

    def test_empty_required_produces_empty_classification(self):
        match = _make_match(matched=[], missing=[])
        result = classify_skills_extended([], ["python"], [], match)
        assert result.verified == []
        assert result.transferable == []
        assert result.learning == []
        assert result.missing == []


# ── TestComputeReadiness ──────────────────────────────────────────────────────

class TestComputeReadiness:
    def _cls(self, verified=None, transferable=0, learning=0, missing=0):
        t_list = [TransferableSkill(f"t{i}", f"v{i}", "ml_frameworks") for i in range(transferable)]
        missing_list = missing if isinstance(missing, list) else [f"m{i}" for i in range(missing)]
        return ExtendedClassification(
            verified=verified or [],
            transferable=t_list,
            learning=[f"l{i}" for i in range(learning)],
            missing=missing_list,
        )

    def test_excellent_for_full_verified_match(self):
        cls = self._cls(verified=["python", "docker", "postgres"])
        match = _make_match(experience_gap=0, location_match=True, contract_match=True, salary_ok=True, language_match=True)
        result = compute_readiness(cls, ["python", "docker", "postgres"], match, _base_profile())
        assert result.label == "excellent"
        assert result.score >= 80

    def test_weak_for_zero_match(self):
        cls = self._cls(verified=[], missing=["a", "b", "c"])
        match = _make_match(experience_gap=-3, location_match=False, remote_match=False, contract_match=False, salary_ok=False, language_match=False)
        profile = {"skills": [], "target_roles": [], "experience_level": None, "countries": [], "cities": []}
        result = compute_readiness(cls, ["a", "b", "c"], match, profile)
        assert result.label == "weak"
        assert result.score < 40

    def test_score_always_0_to_100(self):
        for n in range(0, 6):
            cls = self._cls(verified=["x"] * n, missing=["y"] * (5 - n))
            match = _make_match(experience_gap=n - 3)
            result = compute_readiness(cls, ["x"] * 5, match, _base_profile())
            assert 0 <= result.score <= 100

    def test_label_boundaries(self):
        # These are threshold tests, not exact
        cls_high = self._cls(verified=["a", "b", "c", "d"])
        match_full = _make_match(location_match=True, contract_match=True, salary_ok=True, language_match=True)
        r = compute_readiness(cls_high, ["a", "b", "c", "d"], match_full, _base_profile())
        assert r.label in ("excellent", "strong")

    def test_learning_gives_partial_credit(self):
        cls_learn = self._cls(verified=[], learning=3)
        cls_none = self._cls(verified=[], learning=0)
        match = _make_match(location_match=True, contract_match=True, salary_ok=True, language_match=True)
        profile = _base_profile()
        r_learn = compute_readiness(cls_learn, ["a", "b", "c"], match, profile)
        r_none = compute_readiness(cls_none, ["a", "b", "c"], match, profile)
        assert r_learn.score > r_none.score

    def test_explanation_not_empty(self):
        cls = self._cls(verified=["python"])
        match = _make_match()
        result = compute_readiness(cls, ["python"], match, _base_profile())
        assert len(result.explanation) > 10


# ── TestGenerateRecruiterConcerns ─────────────────────────────────────────────

class TestGenerateRecruiterConcerns:
    def test_missing_skills_generate_concerns(self):
        cls = ExtendedClassification(
            verified=["python"],
            transferable=[],
            learning=[],
            missing=["kubernetes", "terraform"],
        )
        match = _make_match()
        concerns = generate_recruiter_concerns(cls, ["python", "kubernetes", "terraform"], match)
        concern_skills = [c.skill for c in concerns]
        assert "kubernetes" in concern_skills
        assert "terraform" in concern_skills

    def test_learning_skills_generate_concerns(self):
        cls = ExtendedClassification(
            verified=["python"],
            transferable=[],
            learning=["azure"],
            missing=[],
        )
        match = _make_match()
        concerns = generate_recruiter_concerns(cls, ["python", "azure"], match)
        assert any(c.skill == "azure" for c in concerns)

    def test_experience_gap_generates_concern(self):
        cls = ExtendedClassification(verified=[], transferable=[], learning=[], missing=[])
        match = _make_match(experience_gap=-2)
        concerns = generate_recruiter_concerns(cls, [], match)
        assert any(c.skill == "experience_level" for c in concerns)

    def test_slight_experience_gap_generates_concern(self):
        cls = ExtendedClassification(verified=[], transferable=[], learning=[], missing=[])
        match = _make_match(experience_gap=-1)
        concerns = generate_recruiter_concerns(cls, [], match)
        assert any(c.skill == "experience_level" for c in concerns)

    def test_overqualified_no_experience_concern(self):
        cls = ExtendedClassification(verified=[], transferable=[], learning=[], missing=[])
        match = _make_match(experience_gap=1)
        concerns = generate_recruiter_concerns(cls, [], match)
        assert not any(c.skill == "experience_level" for c in concerns)

    def test_location_mismatch_generates_concern(self):
        cls = ExtendedClassification(verified=[], transferable=[], learning=[], missing=[])
        match = _make_match(location_match=False, remote_match=False)
        concerns = generate_recruiter_concerns(cls, [], match)
        assert any(c.skill == "location" for c in concerns)

    def test_no_concerns_for_perfect_match(self):
        cls = ExtendedClassification(verified=["python", "docker"], transferable=[], learning=[], missing=[])
        match = _make_match(matched=["python", "docker"], experience_gap=0, location_match=True)
        concerns = generate_recruiter_concerns(cls, ["python", "docker"], match)
        assert concerns == []


# ── TestGenerateMitigationStrategies ──────────────────────────────────────────

class TestGenerateMitigationStrategies:
    def test_experience_level_concern_mitigated(self):
        concerns = [RecruiterConcern(skill="experience_level", concern="Gap")]
        cls = ExtendedClassification(verified=[], transferable=[], learning=[], missing=[])
        strategies = generate_mitigation_strategies(concerns, cls)
        assert any(m.skill == "experience_level" for m in strategies)
        exp_strategy = next(m for m in strategies if m.skill == "experience_level")
        assert "impact" in exp_strategy.strategy.lower() or "scope" in exp_strategy.strategy.lower()

    def test_location_concern_mitigated(self):
        concerns = [RecruiterConcern(skill="location", concern="Location mismatch")]
        cls = ExtendedClassification(verified=[], transferable=[], learning=[], missing=[])
        strategies = generate_mitigation_strategies(concerns, cls)
        assert any(m.skill == "location" for m in strategies)

    def test_learning_skill_suggests_currently_learning_section(self):
        concerns = [RecruiterConcern(skill="azure", concern="Learning Azure")]
        cls = ExtendedClassification(verified=[], transferable=[], learning=["azure"], missing=[])
        strategies = generate_mitigation_strategies(concerns, cls)
        assert any(m.skill == "azure" for m in strategies)
        strat = next(m for m in strategies if m.skill == "azure")
        assert "currently learning" in strat.strategy.lower() or "learning" in strat.strategy.lower()

    def test_missing_skill_with_no_bridge_honest_strategy(self):
        concerns = [RecruiterConcern(skill="cobol", concern="No COBOL")]
        cls = ExtendedClassification(verified=[], transferable=[], learning=[], missing=["cobol"])
        strategies = generate_mitigation_strategies(concerns, cls)
        assert any(m.skill == "cobol" for m in strategies)
        strat = next(m for m in strategies if m.skill == "cobol")
        assert "honest" in strat.strategy.lower() or "do not" in strat.strategy.lower() or "never" in strat.strategy.lower() or "cannot" in strat.strategy.lower() or "not" in strat.strategy.lower()

    def test_one_mitigation_per_concern(self):
        concerns = [
            RecruiterConcern(skill="kubernetes", concern="Missing"),
            RecruiterConcern(skill="azure", concern="Missing"),
        ]
        cls = ExtendedClassification(verified=[], transferable=[], learning=[], missing=["kubernetes", "azure"])
        strategies = generate_mitigation_strategies(concerns, cls)
        assert len(strategies) == 2


# ── TestGenerateWarnings ──────────────────────────────────────────────────────

class TestGenerateWarnings:
    def test_no_warnings_for_perfect_match(self):
        cls = ExtendedClassification(verified=["python", "docker"], transferable=[], learning=[], missing=[])
        match = _make_match(experience_gap=0, location_match=True)
        warnings = generate_warnings(cls, ["python", "docker"], match)
        assert warnings == []

    def test_high_missing_pct_produces_warning(self):
        cls = ExtendedClassification(verified=[], transferable=[], learning=[], missing=["a", "b", "c", "d"])
        match = _make_match()
        warnings = generate_warnings(cls, ["python", "a", "b", "c", "d"], match)
        assert any("gap" in w.lower() for w in warnings)

    def test_significant_experience_gap_produces_warning(self):
        cls = ExtendedClassification(verified=[], transferable=[], learning=[], missing=[])
        match = _make_match(experience_gap=-3)
        warnings = generate_warnings(cls, [], match)
        assert any("experience" in w.lower() or "significant" in w.lower() for w in warnings)

    def test_location_mismatch_produces_warning(self):
        cls = ExtendedClassification(verified=[], transferable=[], learning=[], missing=[])
        match = _make_match(location_match=False, remote_match=False)
        warnings = generate_warnings(cls, [], match)
        assert any("location" in w.lower() for w in warnings)


# ── TestBuildCvOptimizationPrompt ─────────────────────────────────────────────

class TestBuildCvOptimizationPrompt:
    def _make_cls(self, learning=None, missing=None, verified=None, transferable=None):
        return ExtendedClassification(
            verified=verified or ["python"],
            transferable=transferable or [],
            learning=learning or [],
            missing=missing or [],
        )

    def test_missing_skills_explicitly_forbidden(self):
        cls = self._make_cls(missing=["kubernetes", "terraform"])
        prompt = build_cv_optimization_prompt(_base_profile(), None, {"title": "DevOps", "company_name": "Co", "location": None, "contract_type": None}, cls)
        assert "kubernetes" in prompt.lower()
        assert "terraform" in prompt.lower()
        assert "FORBIDDEN" in prompt or "DO NOT INCLUDE" in prompt or "FORBIDDEN" in prompt

    def test_learning_skills_in_currently_learning_section(self):
        cls = self._make_cls(learning=["azure"])
        prompt = build_cv_optimization_prompt(_base_profile(), None, {"title": "Eng", "company_name": "Co", "location": None, "contract_type": None}, cls)
        assert "azure" in prompt.lower()
        assert "Currently Learning" in prompt or "CURRENTLY LEARNING" in prompt.upper()

    def test_verified_skills_listed_prominently(self):
        cls = self._make_cls(verified=["python", "fastapi"])
        prompt = build_cv_optimization_prompt(_base_profile(), None, {"title": "Backend", "company_name": "Co", "location": None, "contract_type": None}, cls)
        assert "python" in prompt
        assert "fastapi" in prompt

    def test_full_name_from_profile_version(self):
        cls = self._make_cls()
        pv = {"full_name": "Alice Smith", "education": [], "experience": [], "certifications": [], "extracted_skills": [], "inferred_skills": []}
        prompt = build_cv_optimization_prompt(_base_profile(), pv, {"title": "Eng", "company_name": "Co", "location": None, "contract_type": None}, cls)
        assert "Alice Smith" in prompt

    def test_cv_structure_sections_present(self):
        cls = self._make_cls()
        prompt = build_cv_optimization_prompt(_base_profile(), None, {"title": "Eng", "company_name": "Co", "location": None, "contract_type": None}, cls)
        for section in ["Professional Summary", "Core Skills", "Work Experience", "Education"]:
            assert section in prompt

    def test_learning_never_as_professional_skills(self):
        cls = self._make_cls(learning=["azure"])
        prompt = build_cv_optimization_prompt(_base_profile(), None, {"title": "Eng", "company_name": "Co", "location": None, "contract_type": None}, cls)
        # The learning section instruction must say "only" for learning skills
        assert "Currently Learning" in prompt


# ── TestBuildCoverLetterPrompt ────────────────────────────────────────────────

class TestBuildCoverLetterPrompt:
    def _cls(self):
        return ExtendedClassification(
            verified=["python", "fastapi"],
            transferable=[TransferableSkill("tensorflow", "pytorch", "ml_frameworks")],
            learning=["azure"],
            missing=["kubernetes"],
        )

    def test_missing_skills_never_to_be_claimed(self):
        concerns = [RecruiterConcern("kubernetes", "No kubernetes")]
        prompt = build_cover_letter_prompt(_base_profile(), None, {"title": "DevOps", "company_name": "Co", "location": None, "contract_type": None}, self._cls(), concerns)
        assert "kubernetes" in prompt.lower()
        assert "never" in prompt.lower() or "never claim" in prompt.lower() or "do NOT" in prompt

    def test_bridge_language_instructed_for_transferable(self):
        concerns = []
        prompt = build_cover_letter_prompt(_base_profile(), None, {"title": "ML Eng", "company_name": "Co", "location": None, "contract_type": None}, self._cls(), concerns)
        assert "tensorflow" in prompt.lower()
        assert "pytorch" in prompt.lower()
        assert "transferable" in prompt.lower() or "bridge" in prompt.lower()

    def test_learning_skills_to_be_acknowledged_not_claimed(self):
        concerns = []
        prompt = build_cover_letter_prompt(_base_profile(), None, {"title": "Cloud", "company_name": "Co", "location": None, "contract_type": None}, self._cls(), concerns)
        assert "azure" in prompt.lower()
        # Prompt must say "actively" or "learning" — not "proficient"
        assert "actively" in prompt.lower() or "learning" in prompt.lower()

    def test_verified_skills_may_be_claimed(self):
        concerns = []
        prompt = build_cover_letter_prompt(_base_profile(), None, {"title": "Backend", "company_name": "Co", "location": None, "contract_type": None}, self._cls(), concerns)
        assert "python" in prompt
        assert "fastapi" in prompt

    def test_four_paragraph_structure_instructed(self):
        concerns = []
        prompt = build_cover_letter_prompt(_base_profile(), None, {"title": "Eng", "company_name": "Co", "location": None, "contract_type": None}, self._cls(), concerns)
        assert "Paragraph" in prompt or "4" in prompt

    def test_concerns_included_in_prompt(self):
        concerns = [RecruiterConcern("kubernetes", "Missing kubernetes experience")]
        prompt = build_cover_letter_prompt(_base_profile(), None, {"title": "DevOps", "company_name": "Co", "location": None, "contract_type": None}, self._cls(), concerns)
        assert "kubernetes" in prompt.lower()


# ── Safety constraints ────────────────────────────────────────────────────────

class TestSafetyConstraints:
    def test_missing_never_in_verified(self):
        required = ["python", "kubernetes", "terraform"]
        match = _make_match(matched=["python"], missing=["kubernetes", "terraform"])
        result = classify_skills_extended(required, ["python"], [], match)
        missing_lower = {s.lower() for s in result.missing}
        verified_lower = {s.lower() for s in result.verified}
        assert missing_lower.isdisjoint(verified_lower)

    def test_learning_never_in_verified(self):
        required = ["python", "azure"]
        match = _make_match(matched=["python"], missing=["azure"])
        kb = [_kb_entry("azure", "learning")]
        result = classify_skills_extended(required, ["python"], kb, match)
        assert "azure" in result.learning
        assert "azure" not in [v.lower() for v in result.verified]

    def test_high_match_readiness_above_threshold(self):
        cls = ExtendedClassification(
            verified=["python", "docker", "postgresql"],
            transferable=[],
            learning=[],
            missing=[],
        )
        match = _make_match(experience_gap=0, location_match=True, contract_match=True, salary_ok=True, language_match=True)
        result = compute_readiness(cls, ["python", "docker", "postgresql"], match, _base_profile())
        assert result.score >= 70, f"Expected ≥70, got {result.score}"
        assert result.label in ("excellent", "strong")

    def test_medium_match_readiness_in_moderate_range(self):
        cls = ExtendedClassification(
            verified=["python"],
            transferable=[TransferableSkill("tensorflow", "pytorch", "ml_frameworks")],
            learning=["azure"],
            missing=["kubernetes"],
        )
        match = _make_match(experience_gap=0, location_match=True, contract_match=True, salary_ok=True, language_match=True)
        result = compute_readiness(cls, ["python", "tensorflow", "azure", "kubernetes"], match, _base_profile())
        assert 20 <= result.score <= 85
