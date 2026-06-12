"""
Tests for profile_assistant_service.py

Covers:
  - compute_profile_completeness (pure function)
  - validate_extracted_updates (pydantic validation + rejection)
  - build_assistant_message (multilingual, pure)
  - get_next_question (priority ordering)
  - build_extraction_prompt (structure check)
  - extract_profile_updates (async, mocked LLM)
  - apply_profile_updates (async, mocked DB)
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.profile_assistant import ExtractedProfileUpdate
from app.services.profile_assistant_service import (
    COMPLETENESS_FIELDS,
    COMPLETENESS_PRIORITY,
    CompletenessResult,
    _parse_llm_json,
    _profile_has,
    apply_profile_updates,
    build_assistant_message,
    build_extraction_prompt,
    compute_profile_completeness,
    extract_profile_updates,
    get_next_question,
    profile_model_to_dict,
    validate_extracted_updates,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _full_profile() -> dict:
    return {
        "skills":           ["python", "docker"],
        "target_roles":     ["Data Engineer"],
        "experience_level": "senior",
        "countries":        ["France"],
        "cities":           [],
        "salary_min":       50000,
        "salary_target":    65000,
        "education":        [{"degree": "MSc"}],
        "languages":        ["English", "French"],
        "contract_types":   ["cdi"],
        "certifications":   ["AWS"],
        "raw_json":         {"opportunity_types": ["employment"]},
    }


def _empty_profile() -> dict:
    return {}


# ── TestComputeProfileCompleteness ────────────────────────────────────────────

class TestComputeProfileCompleteness:

    def test_full_profile_is_100(self):
        result = compute_profile_completeness(_full_profile())
        assert result.completeness == 100
        assert result.missing_fields == []
        assert result.total_possible == 100

    def test_empty_profile_is_0(self):
        result = compute_profile_completeness(_empty_profile())
        assert result.completeness == 0
        assert len(result.missing_fields) == len(COMPLETENESS_FIELDS)

    def test_skills_worth_20(self):
        p = {"skills": ["python"]}
        result = compute_profile_completeness(p)
        assert result.field_scores["skills"] == 20

    def test_empty_skills_list_not_counted(self):
        p = {"skills": []}
        result = compute_profile_completeness(p)
        assert result.field_scores["skills"] == 0

    def test_location_satisfied_by_countries(self):
        p = {"countries": ["France"]}
        result = compute_profile_completeness(p)
        assert result.field_scores["location"] == 10

    def test_location_satisfied_by_cities(self):
        p = {"cities": ["Paris"]}
        result = compute_profile_completeness(p)
        assert result.field_scores["location"] == 10

    def test_location_missing_when_both_empty(self):
        p = {"countries": [], "cities": []}
        result = compute_profile_completeness(p)
        assert result.field_scores["location"] == 0

    def test_salary_satisfied_by_salary_min(self):
        p = {"salary_min": 40000}
        result = compute_profile_completeness(p)
        assert result.field_scores["salary"] == 10

    def test_salary_satisfied_by_salary_target(self):
        p = {"salary_target": 60000}
        result = compute_profile_completeness(p)
        assert result.field_scores["salary"] == 10

    def test_salary_zero_not_counted(self):
        # salary_min=0 is falsy
        p = {"salary_min": 0}
        result = compute_profile_completeness(p)
        assert result.field_scores["salary"] == 0

    def test_opportunity_types_in_raw_json(self):
        p = {"raw_json": {"opportunity_types": ["employment"]}}
        result = compute_profile_completeness(p)
        assert result.field_scores["opportunity_types"] == 5

    def test_opportunity_types_missing_when_empty_raw_json(self):
        p = {"raw_json": {"opportunity_types": []}}
        result = compute_profile_completeness(p)
        assert result.field_scores["opportunity_types"] == 0

    def test_partial_profile_correct_total(self):
        # skills(20) + target_roles(15) = 35
        p = {"skills": ["python"], "target_roles": ["Engineer"]}
        result = compute_profile_completeness(p)
        assert result.completeness == 35

    def test_field_scores_keys_match_completeness_fields(self):
        result = compute_profile_completeness(_empty_profile())
        expected_keys = {cf.key for cf in COMPLETENESS_FIELDS}
        assert set(result.field_scores.keys()) == expected_keys

    def test_completeness_capped_at_100(self):
        # Even with extra raw_json data, cannot exceed 100
        p = _full_profile()
        p["extra_fake_field"] = "value"
        result = compute_profile_completeness(p)
        assert result.completeness <= 100


# ── TestValidateExtractedUpdates ──────────────────────────────────────────────

class TestValidateExtractedUpdates:

    def test_valid_skills_lowercased(self):
        clean, rejected = validate_extracted_updates({"skills": ["Python", "DOCKER"]})
        assert clean["skills"] == ["python", "docker"]
        assert rejected == []

    def test_valid_experience_level(self):
        clean, _ = validate_extracted_updates({"experience_level": "senior"})
        assert clean["experience_level"] == "senior"

    def test_invalid_experience_level_dropped(self):
        clean, _ = validate_extracted_updates({"experience_level": "expert"})
        assert "experience_level" not in clean

    def test_salary_valid_range(self):
        clean, _ = validate_extracted_updates({"salary_min": 35000, "salary_target": 60000})
        assert clean["salary_min"] == 35000
        assert clean["salary_target"] == 60000

    def test_salary_negative_dropped(self):
        clean, _ = validate_extracted_updates({"salary_min": -100})
        assert "salary_min" not in clean

    def test_salary_over_million_dropped(self):
        clean, _ = validate_extracted_updates({"salary_min": 2_000_000})
        assert "salary_min" not in clean

    def test_years_experience_infers_level(self):
        clean, _ = validate_extracted_updates({"years_experience": 7})
        assert clean.get("experience_level") == "senior"
        assert "years_experience" not in clean

    def test_years_experience_junior(self):
        clean, _ = validate_extracted_updates({"years_experience": 1})
        assert clean.get("experience_level") == "junior"

    def test_years_experience_mid(self):
        clean, _ = validate_extracted_updates({"years_experience": 4})
        assert clean.get("experience_level") == "mid"

    def test_years_experience_not_in_clean_dict(self):
        clean, _ = validate_extracted_updates({"years_experience": 3})
        assert "years_experience" not in clean

    def test_unknown_field_rejected(self):
        clean, rejected = validate_extracted_updates({"unknown_field": "value"})
        assert "unknown_field" in rejected
        assert "unknown_field" not in clean

    def test_contract_types_lowercased(self):
        clean, _ = validate_extracted_updates({"contract_types": ["CDI", "Freelance"]})
        assert clean["contract_types"] == ["cdi", "freelance"]

    def test_empty_dict_returns_empty(self):
        clean, rejected = validate_extracted_updates({})
        assert clean == {}
        assert rejected == []

    def test_extra_ignore_config_works(self):
        # Extra fields are rejected without crashing
        clean, rejected = validate_extracted_updates({
            "skills": ["python"],
            "random_key": "oops",
        })
        assert clean.get("skills") == ["python"]
        assert "random_key" in rejected

    def test_remote_preference_bool(self):
        clean, _ = validate_extracted_updates({"remote_preference": True})
        assert clean["remote_preference"] is True

    def test_industries_preserved_as_list(self):
        clean, _ = validate_extracted_updates({"industries": ["Tech", "Finance"]})
        assert clean["industries"] == ["Tech", "Finance"]

    def test_opportunity_types_preserved(self):
        clean, _ = validate_extracted_updates({"opportunity_types": ["employment", "phd"]})
        assert "phd" in clean["opportunity_types"]


# ── TestParseLlmJson ──────────────────────────────────────────────────────────

class TestParseLlmJson:

    def test_plain_json(self):
        assert _parse_llm_json('{"skills": ["python"]}') == {"skills": ["python"]}

    def test_markdown_json_block(self):
        raw = '```json\n{"skills": ["python"]}\n```'
        assert _parse_llm_json(raw) == {"skills": ["python"]}

    def test_markdown_block_no_language(self):
        raw = '```\n{"skills": ["python"]}\n```'
        assert _parse_llm_json(raw) == {"skills": ["python"]}

    def test_empty_string_returns_empty(self):
        assert _parse_llm_json("") == {}

    def test_invalid_json_returns_empty(self):
        assert _parse_llm_json("not json at all") == {}

    def test_nested_json_in_prose(self):
        raw = 'Here is the result: {"skills": ["java"]} end.'
        result = _parse_llm_json(raw)
        assert result == {"skills": ["java"]}

    def test_empty_json_object(self):
        assert _parse_llm_json("{}") == {}


# ── TestBuildAssistantMessage ─────────────────────────────────────────────────

class TestBuildAssistantMessage:

    def test_english_with_extracted_fields(self):
        msg = build_assistant_message("en", {"skills": ["python"]}, ["target job roles"], 40)
        assert "skills" in msg
        assert "40%" in msg

    def test_english_no_extracted_no_update_message(self):
        msg = build_assistant_message("en", {}, ["target job roles"], 0)
        assert "couldn't find" in msg.lower() or "career goals" in msg.lower()

    def test_french_fields_captured(self):
        msg = build_assistant_message("fr", {"skills": ["python"]}, [], 100)
        assert "compétences" in msg or "noté" in msg

    def test_persian_completeness(self):
        msg = build_assistant_message("fa", {}, [], 50)
        assert "50" in msg

    def test_missing_hint_included(self):
        msg = build_assistant_message("en", {"skills": []}, ["target job roles"], 20)
        assert "target job roles" in msg

    def test_no_missing_hint_when_complete(self):
        msg = build_assistant_message("en", {"skills": ["x"]}, [], 100)
        assert "improve" not in msg.lower()

    def test_unknown_language_falls_back_to_en(self):
        msg = build_assistant_message("de", {"skills": ["python"]}, [], 50)
        assert "50%" in msg


# ── TestGetNextQuestion ───────────────────────────────────────────────────────

class TestGetNextQuestion:

    def test_target_roles_highest_priority(self):
        missing = ["target job roles", "technical skills", "experience level"]
        q = get_next_question(missing, "en")
        assert "roles" in q.lower() or "titles" in q.lower()

    def test_skills_second_priority(self):
        missing = ["technical skills", "experience level"]
        q = get_next_question(missing, "en")
        assert "skill" in q.lower()

    def test_all_complete_returns_done_message(self):
        q = get_next_question([], "en")
        assert "great" in q.lower() or "anything" in q.lower()

    def test_french_question(self):
        missing = ["technical skills"]
        q = get_next_question(missing, "fr")
        assert "compétences" in q.lower() or "Quelles" in q

    def test_persian_question(self):
        missing = ["target job roles"]
        q = get_next_question(missing, "fa")
        assert len(q) > 0

    def test_unknown_language_falls_back_to_en(self):
        missing = ["technical skills"]
        q = get_next_question(missing, "de")
        assert len(q) > 0


# ── TestBuildExtractionPrompt ─────────────────────────────────────────────────

class TestBuildExtractionPrompt:

    def test_message_in_prompt(self):
        prompt = build_extraction_prompt("I know Python", {}, "en")
        assert "I know Python" in prompt

    def test_json_schema_in_prompt(self):
        prompt = build_extraction_prompt("test", {}, "en")
        assert "skills" in prompt
        assert "target_roles" in prompt
        assert "experience_level" in prompt

    def test_profile_context_included_when_present(self):
        profile = {"skills": ["java"], "target_roles": ["Dev"], "experience_level": "mid"}
        prompt = build_extraction_prompt("test", profile, "en")
        assert "java" in prompt
        assert "Dev" in prompt

    def test_no_profile_context_when_empty(self):
        prompt = build_extraction_prompt("test", {}, "en")
        assert "Current profile" not in prompt

    def test_french_hint(self):
        prompt = build_extraction_prompt("je suis dev", {}, "fr")
        assert "French" in prompt

    def test_persian_hint(self):
        prompt = build_extraction_prompt("من برنامه‌نویس هستم", {}, "fa")
        assert "Persian" in prompt or "Farsi" in prompt

    def test_only_valid_json_instruction(self):
        prompt = build_extraction_prompt("test", {}, "en")
        assert "ONLY valid JSON" in prompt


# ── TestExtractProfileUpdates ─────────────────────────────────────────────────

class TestExtractProfileUpdates:

    async def test_valid_llm_response(self):
        provider = AsyncMock()
        provider.generate = AsyncMock(return_value='{"skills": ["python", "sql"]}')
        result = await extract_profile_updates(provider, "I know Python and SQL", {}, "en")
        assert "skills" in result
        assert "python" in result["skills"]

    async def test_llm_failure_returns_empty(self):
        provider = AsyncMock()
        provider.generate = AsyncMock(side_effect=Exception("timeout"))
        result = await extract_profile_updates(provider, "test", {}, "en")
        assert result == {}

    async def test_invalid_json_returns_empty(self):
        provider = AsyncMock()
        provider.generate = AsyncMock(return_value="not json")
        result = await extract_profile_updates(provider, "test", {}, "en")
        assert result == {}

    async def test_invalid_field_values_dropped(self):
        provider = AsyncMock()
        provider.generate = AsyncMock(return_value='{"experience_level": "wizard", "skills": ["python"]}')
        result = await extract_profile_updates(provider, "test", {}, "en")
        assert "experience_level" not in result
        assert result.get("skills") == ["python"]

    async def test_markdown_wrapped_json_parsed(self):
        provider = AsyncMock()
        provider.generate = AsyncMock(return_value='```json\n{"target_roles": ["Engineer"]}\n```')
        result = await extract_profile_updates(provider, "test", {}, "en")
        assert result.get("target_roles") == ["Engineer"]

    async def test_empty_json_returns_empty(self):
        provider = AsyncMock()
        provider.generate = AsyncMock(return_value="{}")
        result = await extract_profile_updates(provider, "test", {}, "en")
        assert result == {}


# ── TestApplyProfileUpdates ───────────────────────────────────────────────────

class TestApplyProfileUpdates:

    def _mock_profile(self, **kwargs):
        p = MagicMock()
        p.skills = kwargs.get("skills", [])
        p.target_roles = kwargs.get("target_roles", [])
        p.avoid_roles = kwargs.get("avoid_roles", [])
        p.experience_level = kwargs.get("experience_level", None)
        p.salary_min = kwargs.get("salary_min", None)
        p.salary_target = kwargs.get("salary_target", None)
        p.remote_preference = kwargs.get("remote_preference", False)
        p.countries = kwargs.get("countries", [])
        p.cities = kwargs.get("cities", [])
        p.contract_types = kwargs.get("contract_types", [])
        p.languages = kwargs.get("languages", [])
        p.certifications = kwargs.get("certifications", [])
        p.raw_json = kwargs.get("raw_json", {})
        p.is_active = True
        return p

    async def test_creates_profile_when_none_exists(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        with patch(
            "app.services.profile_assistant_service.profile_service.get_active_profile",
            new=AsyncMock(return_value=None),
        ):
            await apply_profile_updates(db, uuid.uuid4(), {"skills": ["python"]})
        db.add.assert_called_once()
        db.commit.assert_called_once()

    async def test_merges_skills_with_existing(self):
        existing = self._mock_profile(skills=["java"])
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        with patch(
            "app.services.profile_assistant_service.profile_service.get_active_profile",
            new=AsyncMock(return_value=existing),
        ):
            await apply_profile_updates(db, uuid.uuid4(), {"skills": ["python"]})

        assert "java" in existing.skills
        assert "python" in existing.skills

    async def test_deduplicates_merged_list(self):
        existing = self._mock_profile(skills=["python"])
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        with patch(
            "app.services.profile_assistant_service.profile_service.get_active_profile",
            new=AsyncMock(return_value=existing),
        ):
            await apply_profile_updates(db, uuid.uuid4(), {"skills": ["python", "docker"]})

        assert existing.skills.count("python") == 1

    async def test_scalar_field_overwritten(self):
        existing = self._mock_profile(experience_level="junior")
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        with patch(
            "app.services.profile_assistant_service.profile_service.get_active_profile",
            new=AsyncMock(return_value=existing),
        ):
            await apply_profile_updates(db, uuid.uuid4(), {"experience_level": "senior"})

        assert existing.experience_level == "senior"

    async def test_extra_fields_go_to_raw_json(self):
        existing = self._mock_profile(raw_json={})
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        with patch(
            "app.services.profile_assistant_service.profile_service.get_active_profile",
            new=AsyncMock(return_value=existing),
        ):
            await apply_profile_updates(
                db, uuid.uuid4(), {"industries": ["Tech"], "opportunity_types": ["phd"]}
            )

        assert existing.raw_json.get("industries") == ["Tech"]
        assert existing.raw_json.get("opportunity_types") == ["phd"]

    async def test_extra_fields_merged_in_raw_json(self):
        existing = self._mock_profile(raw_json={"industries": ["Finance"]})
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        with patch(
            "app.services.profile_assistant_service.profile_service.get_active_profile",
            new=AsyncMock(return_value=existing),
        ):
            await apply_profile_updates(db, uuid.uuid4(), {"industries": ["Tech"]})

        assert "Finance" in existing.raw_json["industries"]
        assert "Tech" in existing.raw_json["industries"]

    async def test_invalid_updates_rejected_before_write(self):
        existing = self._mock_profile(experience_level="junior")
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        with patch(
            "app.services.profile_assistant_service.profile_service.get_active_profile",
            new=AsyncMock(return_value=existing),
        ):
            await apply_profile_updates(
                db, uuid.uuid4(), {"experience_level": "wizard"}
            )

        # Invalid level should be dropped — existing value unchanged
        assert existing.experience_level == "junior"
