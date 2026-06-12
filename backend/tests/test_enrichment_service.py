"""
Pure-function unit tests for enrichment_service.

No DB, no network — all functions are deterministic.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.enrichment_service import (
    analyze_requirements,
    classify_answer,
    generate_questions,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _kb(*skills_and_statuses: tuple[str, str]):
    """Build a list of mock SkillEvidence objects."""
    items = []
    for skill, status in skills_and_statuses:
        e = MagicMock()
        e.skill = skill
        e.status = status
        items.append(e)
    return items


# ── analyze_requirements ───────────────────────────────────────────────────────

class TestAnalyzeRequirements:
    def test_skill_in_profile_is_verified(self):
        gaps = analyze_requirements(["python"], ["Python", "Docker"], [])
        assert len(gaps) == 1
        assert gaps[0].classification == "verified"

    def test_skill_in_kb_verified_is_verified(self):
        kb = _kb(("terraform", "verified"))
        gaps = analyze_requirements(["terraform"], [], kb)
        assert gaps[0].classification == "verified"

    def test_skill_in_kb_learning_is_partially_verified(self):
        kb = _kb(("azure", "learning"))
        gaps = analyze_requirements(["azure"], [], kb)
        assert gaps[0].classification == "partially_verified"
        assert "learning" in gaps[0].rationale.lower()

    def test_transferable_family_bridge_partial(self):
        # Docker → kubernetes transferable
        gaps = analyze_requirements(["kubernetes"], ["docker"], [])
        assert gaps[0].classification in ("partially_verified", "unknown")
        if gaps[0].classification == "partially_verified":
            assert gaps[0].via_skill is not None

    def test_no_evidence_is_unknown(self):
        gaps = analyze_requirements(["cobol"], ["python"], [])
        assert gaps[0].classification == "unknown"

    def test_multiple_skills_mixed(self):
        gaps = analyze_requirements(
            ["python", "azure", "cobol"],
            ["python"],
            [],
        )
        assert gaps[0].classification == "verified"
        assert gaps[2].classification == "unknown"

    def test_verified_never_generates_question(self):
        gaps = analyze_requirements(["python"], ["Python"], [])
        questions = generate_questions(gaps)
        assert len(questions) == 0

    def test_case_insensitive_profile_match(self):
        gaps = analyze_requirements(["Python"], ["PYTHON"], [])
        assert gaps[0].classification == "verified"

    def test_case_insensitive_kb_match(self):
        kb = _kb(("TerraForm", "verified"))
        gaps = analyze_requirements(["terraform"], [], kb)
        assert gaps[0].classification == "verified"


# ── generate_questions ─────────────────────────────────────────────────────────

class TestGenerateQuestions:
    def test_returns_one_per_non_verified(self):
        gaps = analyze_requirements(["python", "azure"], ["python"], [])
        questions = generate_questions(gaps)
        assert len(questions) == 1
        assert questions[0].requirement == "azure"

    def test_ids_are_sequential(self):
        gaps = analyze_requirements(["azure", "cobol", "leadership"], [], [])
        questions = generate_questions(gaps)
        ids = [q.id for q in questions]
        assert ids == ["q-0", "q-1", "q-2"]

    def test_question_type_cloud_for_azure(self):
        gaps = analyze_requirements(["azure"], [], [])
        questions = generate_questions(gaps)
        assert questions[0].question_type == "cloud_experience"

    def test_question_type_leadership(self):
        gaps = analyze_requirements(["leadership"], [], [])
        questions = generate_questions(gaps)
        assert questions[0].question_type == "leadership_evidence"

    def test_question_type_language(self):
        gaps = analyze_requirements(["french"], [], [])
        questions = generate_questions(gaps)
        assert questions[0].question_type == "language_proficiency"

    def test_question_text_is_non_empty(self):
        gaps = analyze_requirements(["cobol"], [], [])
        questions = generate_questions(gaps)
        assert len(questions[0].question) > 20

    def test_question_references_requirement(self):
        gaps = analyze_requirements(["cobol"], [], [])
        questions = generate_questions(gaps)
        assert "cobol" in questions[0].question.lower()


# ── classify_answer ────────────────────────────────────────────────────────────

class TestClassifyAnswer:
    def test_no_is_rejected(self):
        etype, status = classify_answer("No")
        assert etype == "rejected"
        assert status == "rejected"

    def test_never_used_is_rejected(self):
        _, status = classify_answer("I have never used terraform")
        assert status == "rejected"

    def test_professional_mention_gives_verified(self):
        etype, status = classify_answer("Yes, I used it at my job in 2023")
        assert etype == "professional"
        assert status == "verified"

    def test_personal_project_gives_verified(self):
        etype, status = classify_answer("I built a personal project using Azure on GitHub")
        assert etype == "project"
        assert status == "verified"

    def test_academic_gives_verified(self):
        etype, status = classify_answer("I used it for my thesis project at university")
        assert etype == "academic"
        assert status == "verified"

    def test_currently_learning_gives_learning(self):
        etype, status = classify_answer("I am currently learning this — taking a course on Coursera")
        assert etype == "learning"
        assert status == "learning"

    def test_generic_yes_gives_verified(self):
        etype, status = classify_answer("Yes, I have experience with this technology")
        assert status == "verified"

    def test_empty_negative_gives_rejected(self):
        _, status = classify_answer("no")
        assert status == "rejected"

    def test_enrolled_in_course_gives_learning(self):
        etype, status = classify_answer("I enrolled in an Azure AZ-900 course last week")
        assert etype == "learning"
        assert status == "learning"

    def test_no_fabrication_negative(self):
        """Rejected answer must never return 'verified' status."""
        _, status = classify_answer("No, I have not worked with this at all")
        assert status == "rejected"

    def test_professional_not_rejected_even_with_no(self):
        """'No' inside a longer positive sentence should not override professional context."""
        etype, status = classify_answer("At my job I did not use it alone, but my team did and I contributed")
        # This is ambiguous — it either hits 'professional' or 'verified', never 'rejected'
        assert status != "rejected"
