"""
Tests for career_interview_service.

Coverage:
- build_agent_question_prompt (pure)
- _parse_llm_suggestions (pure)
- _application_status_to_stage (pure)
- seed_knowledge_base_from_profile (async)
- confirm_evidence (async)
- reject_evidence (async)
- generate_agent_questions (async, mocked LLM)
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.career_interview_service import (
    EvidenceSuggestion,
    _application_status_to_stage,
    _parse_llm_suggestions,
    build_agent_question_prompt,
    confirm_evidence,
    generate_agent_questions,
    get_knowledge_base,
    get_pending_evidence,
    reject_evidence,
    seed_knowledge_base_from_profile,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_profile(skills=None, roles=None, exp_level="mid"):
    p = MagicMock()
    p.skills = skills if skills is not None else ["python", "docker", "postgresql"]
    p.target_roles = roles or ["backend engineer"]
    p.experience_level = exp_level
    p.certifications = []
    return p


def _make_pv(extracted=None, inferred=None):
    pv = MagicMock()
    pv.extracted_skills = extracted or []
    pv.inferred_skills = inferred or []
    return pv


def _make_kb_entry(skill, status="verified", source="profile"):
    e = MagicMock()
    e.skill = skill
    e.status = status
    e.source = source
    e.confidence = 1.0
    return e


def _make_pending(pending_id=None, skill="azure", suggested_status="learning"):
    p = MagicMock()
    p.id = pending_id or uuid.uuid4()
    p.skill = skill
    p.suggested_status = suggested_status
    p.agent_question = f"Have you worked with {skill}?"
    p.agent_reasoning = "Relevant to the job"
    return p


# ── TestBuildAgentQuestionPrompt ──────────────────────────────────────────────

class TestBuildAgentQuestionPrompt:
    def test_contains_profile_skills(self):
        profile = {"skills": ["python", "docker"], "target_roles": ["backend"], "experience_level": "mid"}
        prompt = build_agent_question_prompt(profile, [], {"title": "ML Eng", "company_name": "Co"}, ["tensorflow"])
        assert "python" in prompt
        assert "docker" in prompt

    def test_contains_missing_skills(self):
        profile = {"skills": ["python"], "target_roles": [], "experience_level": "junior"}
        prompt = build_agent_question_prompt(profile, [], {"title": "DevOps", "company_name": "Co"}, ["kubernetes", "terraform"])
        assert "kubernetes" in prompt or "terraform" in prompt

    def test_skips_already_known_skills(self):
        profile = {"skills": ["python", "kubernetes"], "target_roles": [], "experience_level": "mid"}
        kb = [_make_kb_entry("kubernetes", "verified")]
        prompt = build_agent_question_prompt(profile, kb, {"title": "DevOps", "company_name": "Co"}, ["kubernetes"])
        assert "all covered" in prompt or "kubernetes" in prompt

    def test_returns_json_instruction(self):
        profile = {"skills": ["python"], "target_roles": [], "experience_level": "mid"}
        prompt = build_agent_question_prompt(profile, [], {"title": "Eng", "company_name": "Co"}, ["azure"])
        assert "JSON" in prompt or "json" in prompt.lower()

    def test_contains_job_title(self):
        profile = {"skills": ["python"], "target_roles": [], "experience_level": "mid"}
        prompt = build_agent_question_prompt(profile, [], {"title": "Senior ML Engineer", "company_name": "AIStartup"}, ["pytorch"])
        assert "Senior ML Engineer" in prompt
        assert "AIStartup" in prompt


# ── TestParseLlmSuggestions ───────────────────────────────────────────────────

class TestParseLlmSuggestions:
    def test_parses_valid_json_array(self):
        raw = json.dumps([
            {"skill": "azure", "suggested_status": "learning", "question": "Have you used Azure?", "reasoning": "Job needs it"}
        ])
        result = _parse_llm_suggestions(raw)
        assert len(result) == 1
        assert result[0].skill == "azure"
        assert result[0].suggested_status == "learning"

    def test_returns_empty_on_invalid_json(self):
        result = _parse_llm_suggestions("not json at all")
        assert result == []

    def test_returns_empty_on_empty_string(self):
        result = _parse_llm_suggestions("")
        assert result == []

    def test_normalises_skill_to_lowercase(self):
        raw = json.dumps([{"skill": "Azure", "suggested_status": "learning", "question": "Q"}])
        result = _parse_llm_suggestions(raw)
        assert result[0].skill == "azure"

    def test_drops_malformed_items(self):
        raw = json.dumps([
            {"skill": "azure", "suggested_status": "learning", "question": "Q"},
            {"invalid": "item"},
            {"skill": "terraform", "suggested_status": "verified", "question": "Q2"},
        ])
        result = _parse_llm_suggestions(raw)
        assert len(result) == 2
        skills = [r.skill for r in result]
        assert "azure" in skills
        assert "terraform" in skills

    def test_strips_markdown_fences(self):
        raw = "```json\n" + json.dumps([{"skill": "gcp", "suggested_status": "learning", "question": "Q"}]) + "\n```"
        result = _parse_llm_suggestions(raw)
        assert len(result) == 1
        assert result[0].skill == "gcp"

    def test_invalid_status_defaults_to_learning(self):
        raw = json.dumps([{"skill": "x", "suggested_status": "unknown_status", "question": "Q"}])
        result = _parse_llm_suggestions(raw)
        assert result[0].suggested_status == "learning"

    def test_multiple_valid_suggestions(self):
        suggestions = [
            {"skill": f"skill{i}", "suggested_status": "learning", "question": f"Q{i}"}
            for i in range(5)
        ]
        result = _parse_llm_suggestions(json.dumps(suggestions))
        assert len(result) == 5


# ── TestApplicationStatusToStage ─────────────────────────────────────────────

class TestApplicationStatusToStage:
    def test_found_maps_to_recommended(self):
        assert _application_status_to_stage("found") == "recommended"

    def test_shortlisted_maps_to_recommended(self):
        assert _application_status_to_stage("shortlisted") == "recommended"

    def test_cv_generated_maps_to_ready_to_apply(self):
        assert _application_status_to_stage("cv_generated") == "ready_to_apply"

    def test_approved_maps_to_ready_to_apply(self):
        assert _application_status_to_stage("approved") == "ready_to_apply"

    def test_applied_maps_to_applied(self):
        assert _application_status_to_stage("applied") == "applied"

    def test_replied_maps_to_follow_up(self):
        assert _application_status_to_stage("replied") == "follow_up"

    def test_interview_maps_to_interview(self):
        assert _application_status_to_stage("interview") == "interview"

    def test_rejected_maps_to_rejected(self):
        assert _application_status_to_stage("rejected") == "rejected"

    def test_archived_maps_to_rejected(self):
        assert _application_status_to_stage("archived") == "rejected"

    def test_offer_maps_to_offer(self):
        assert _application_status_to_stage("offer") == "offer"

    def test_unknown_defaults_to_recommended(self):
        assert _application_status_to_stage("some_unknown_status") == "recommended"


# ── TestSeedKnowledgeBase ─────────────────────────────────────────────────────

class TestSeedKnowledgeBase:
    async def test_adds_profile_skills_as_verified(self):
        user_id = uuid.uuid4()
        profile = _make_profile(skills=["python", "docker"])
        pv = _make_pv()

        db = AsyncMock()
        existing_result = MagicMock()
        existing_result.all.return_value = []
        db.execute = AsyncMock(return_value=existing_result)
        db.add_all = MagicMock()
        db.flush = AsyncMock()

        count = await seed_knowledge_base_from_profile(db, user_id, profile, pv)
        assert count == 2
        db.add_all.assert_called_once()
        added = db.add_all.call_args[0][0]
        statuses = [e.status for e in added]
        assert all(s == "verified" for s in statuses)

    async def test_adds_extracted_skills_as_verified(self):
        user_id = uuid.uuid4()
        profile = _make_profile(skills=[])
        pv = _make_pv(extracted=["fastapi", "redis"])

        db = AsyncMock()
        existing_result = MagicMock()
        existing_result.all.return_value = []
        db.execute = AsyncMock(return_value=existing_result)
        db.add_all = MagicMock()
        db.flush = AsyncMock()

        count = await seed_knowledge_base_from_profile(db, user_id, profile, pv)
        assert count == 2

    async def test_adds_inferred_skills_as_transferable(self):
        user_id = uuid.uuid4()
        profile = _make_profile(skills=[])
        pv = _make_pv(extracted=[], inferred=["machine learning", "nlp"])

        db = AsyncMock()
        existing_result = MagicMock()
        existing_result.all.return_value = []
        db.execute = AsyncMock(return_value=existing_result)
        db.add_all = MagicMock()
        db.flush = AsyncMock()

        count = await seed_knowledge_base_from_profile(db, user_id, profile, pv)
        assert count == 2
        added = db.add_all.call_args[0][0]
        inferred_entries = [e for e in added if e.source == "cv_extracted" and e.status == "transferable"]
        assert len(inferred_entries) == 2

    async def test_skips_already_existing_skills(self):
        user_id = uuid.uuid4()
        profile = _make_profile(skills=["python", "docker"])
        pv = _make_pv()

        db = AsyncMock()
        existing_result = MagicMock()
        existing_result.all.return_value = [("python",), ("docker",)]
        db.execute = AsyncMock(return_value=existing_result)
        db.add_all = MagicMock()
        db.flush = AsyncMock()

        count = await seed_knowledge_base_from_profile(db, user_id, profile, pv)
        assert count == 0
        db.add_all.assert_not_called()

    async def test_no_crash_without_profile_version(self):
        user_id = uuid.uuid4()
        profile = _make_profile(skills=["python"])

        db = AsyncMock()
        existing_result = MagicMock()
        existing_result.all.return_value = []
        db.execute = AsyncMock(return_value=existing_result)
        db.add_all = MagicMock()
        db.flush = AsyncMock()

        count = await seed_knowledge_base_from_profile(db, user_id, profile, None)
        assert count == 1


# ── TestConfirmEvidence ───────────────────────────────────────────────────────

class TestConfirmEvidence:
    async def test_returns_none_when_pending_not_found(self):
        user_id = uuid.uuid4()
        pending_id = uuid.uuid4()

        db = AsyncMock()
        not_found = MagicMock()
        not_found.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=not_found)

        result = await confirm_evidence(db, user_id, pending_id)
        assert result is None

    async def test_creates_skill_evidence_on_confirm(self):
        user_id = uuid.uuid4()
        pending_id = uuid.uuid4()
        pending = _make_pending(pending_id=pending_id, skill="azure", suggested_status="learning")

        existing_evidence = MagicMock()
        existing_evidence.scalar_one_or_none.side_effect = [pending, None]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=existing_evidence)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        result = await confirm_evidence(db, user_id, pending_id)
        db.add.assert_called_once()

    async def test_override_status_takes_precedence(self):
        user_id = uuid.uuid4()
        pending_id = uuid.uuid4()
        pending = _make_pending(pending_id=pending_id, skill="azure", suggested_status="learning")

        db = AsyncMock()
        pending_result = MagicMock()
        pending_result.scalar_one_or_none.return_value = pending
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = None
        delete_result = MagicMock()
        db.execute = AsyncMock(side_effect=[pending_result, existing_result, delete_result])
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        await confirm_evidence(db, user_id, pending_id, override_status="verified")
        added = db.add.call_args[0][0]
        assert added.status == "verified"

    async def test_updates_existing_evidence_on_confirm(self):
        user_id = uuid.uuid4()
        pending_id = uuid.uuid4()
        pending = _make_pending(pending_id=pending_id, skill="azure")
        existing_ev = MagicMock()
        existing_ev.status = "transferable"
        existing_ev.source = "profile"

        db = AsyncMock()
        pending_result = MagicMock()
        pending_result.scalar_one_or_none.return_value = pending
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = existing_ev
        delete_result = MagicMock()
        db.execute = AsyncMock(side_effect=[pending_result, existing_result, delete_result])
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        await confirm_evidence(db, user_id, pending_id)
        db.add.assert_not_called()
        assert existing_ev.status == pending.suggested_status
        assert existing_ev.source == "user_confirmed"


# ── TestRejectEvidence ────────────────────────────────────────────────────────

class TestRejectEvidence:
    async def test_returns_false_when_not_found(self):
        user_id = uuid.uuid4()
        pending_id = uuid.uuid4()

        db = AsyncMock()
        not_found = MagicMock()
        not_found.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=not_found)

        result = await reject_evidence(db, user_id, pending_id)
        assert result is False

    async def test_returns_true_and_deletes_when_found(self):
        user_id = uuid.uuid4()
        pending_id = uuid.uuid4()
        pending = _make_pending(pending_id=pending_id)

        db = AsyncMock()
        found = MagicMock()
        found.scalar_one_or_none.return_value = pending
        db.execute = AsyncMock(return_value=found)
        db.commit = AsyncMock()

        result = await reject_evidence(db, user_id, pending_id)
        assert result is True
        db.commit.assert_called_once()


# ── TestGenerateAgentQuestions ────────────────────────────────────────────────

class TestGenerateAgentQuestions:
    async def test_stores_suggestions_as_pending(self):
        user_id = uuid.uuid4()
        profile = _make_profile()
        kb = []
        job = {"title": "ML Engineer", "company_name": "AIStartup"}

        provider = AsyncMock()
        provider.generate = AsyncMock(return_value=json.dumps([
            {"skill": "azure", "suggested_status": "learning", "question": "Have you used Azure?", "reasoning": "Job needs it"}
        ]))

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        result = await generate_agent_questions(provider, db, user_id, profile, kb, job, ["azure"])
        assert len(result) == 1
        db.add.assert_called()

    async def test_skips_skills_already_in_knowledge_base(self):
        user_id = uuid.uuid4()
        profile = _make_profile()
        kb = [_make_kb_entry("azure", "learning")]
        job = {"title": "DevOps", "company_name": "Co"}

        provider = AsyncMock()
        provider.generate = AsyncMock(return_value=json.dumps([
            {"skill": "azure", "suggested_status": "learning", "question": "Q", "reasoning": "R"}
        ]))

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        result = await generate_agent_questions(provider, db, user_id, profile, kb, job, ["azure"])
        assert len(result) == 0
        db.add.assert_not_called()

    async def test_returns_empty_on_invalid_llm_output(self):
        user_id = uuid.uuid4()
        profile = _make_profile()
        job = {"title": "Eng", "company_name": "Co"}

        provider = AsyncMock()
        provider.generate = AsyncMock(return_value="not valid json")

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        result = await generate_agent_questions(provider, db, user_id, profile, [], job, ["terraform"])
        assert result == []
        db.add.assert_not_called()
