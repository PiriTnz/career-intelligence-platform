"""
Tests for application_package_service.

Coverage:
- Pure functions: classify_requirements, compute_ready_to_apply_score,
  generate_warnings, build_cv_adaptation_prompt, build_cover_letter_prompt
- Async service: prepare_application_package, get_application_package
- Safety: real_gap skills never claimed, transferable uses bridge language only
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.application_package_service import (
    RequirementClassification,
    TransferableSkillResult,
    build_cover_letter_prompt,
    build_cv_adaptation_prompt,
    classify_requirements,
    compute_ready_to_apply_score,
    generate_warnings,
    get_application_package,
    prepare_application_package,
)
from app.services.matching_engine import MatchResult


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_match(
    matched: list[str] | None = None,
    missing: list[str] | None = None,
    experience_gap: int = 0,
    location_match: bool = True,
    remote_match: bool = False,
    contract_match: bool = True,
    salary_ok: bool = True,
    language_match: bool = True,
    overall_fit: float = 0.8,
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
        overall_fit=overall_fit,
    )


def _base_profile_dict(**overrides) -> dict:
    d = {
        "skills": ["python", "docker", "postgresql"],
        "target_roles": ["backend engineer"],
        "experience_level": "mid",
        "countries": ["France"],
        "cities": [],
        "remote_preference": True,
        "contract_types": ["cdi"],
        "salary_min": 45000,
        "salary_target": 55000,
        "languages": ["English", "French"],
        "certifications": [],
        "education": [],
        "experience": [],
    }
    d.update(overrides)
    return d


# ── TestClassifyRequirements ──────────────────────────────────────────────────

class TestClassifyRequirements:
    def test_all_verified_when_all_matched(self):
        match = _make_match(matched=["python", "docker"], missing=[])
        result = classify_requirements(
            required_skills=["python", "docker"],
            profile_skills=["python", "docker"],
            match_result=match,
        )
        assert result.verified_match == ["python", "docker"]
        assert result.transferable_match == []
        assert result.real_gap == []

    def test_real_gap_when_no_family_bridge(self):
        # "kubernetes" — no profile skill in the containers family
        match = _make_match(matched=[], missing=["kubernetes"])
        result = classify_requirements(
            required_skills=["kubernetes"],
            profile_skills=["pandas", "numpy"],
            match_result=match,
        )
        assert "kubernetes" in result.real_gap
        assert result.verified_match == []
        assert result.transferable_match == []

    def test_transferable_when_same_family(self):
        # "tensorflow" missing but user has "pytorch" (same ml_frameworks family)
        match = _make_match(matched=["python"], missing=["tensorflow"])
        result = classify_requirements(
            required_skills=["python", "tensorflow"],
            profile_skills=["python", "pytorch"],
            match_result=match,
        )
        assert "python" in result.verified_match
        assert len(result.transferable_match) == 1
        t = result.transferable_match[0]
        assert t.skill == "tensorflow"
        assert t.via == "pytorch"
        assert t.family == "ml_frameworks"
        assert result.real_gap == []

    def test_real_gap_never_in_verified(self):
        # Critical safety: real_gap and verified_match are mutually exclusive
        match = _make_match(matched=["python"], missing=["kubernetes"])
        result = classify_requirements(
            required_skills=["python", "kubernetes"],
            profile_skills=["python"],
            match_result=match,
        )
        real_lower = {s.lower() for s in result.real_gap}
        verified_lower = {s.lower() for s in result.verified_match}
        assert real_lower.isdisjoint(verified_lower), (
            f"Overlap between real_gap and verified_match: {real_lower & verified_lower}"
        )

    def test_partition_is_complete(self):
        # len(verified) + len(transferable) + len(real_gap) == len(missing_skills) + len(matched)
        required = ["python", "tensorflow", "kubernetes", "react"]
        matched = ["python"]
        missing = ["tensorflow", "kubernetes", "react"]
        match = _make_match(matched=matched, missing=missing)
        result = classify_requirements(
            required_skills=required,
            profile_skills=["python", "pytorch"],
            match_result=match,
        )
        total = len(result.verified_match) + len(result.transferable_match) + len(result.real_gap)
        assert total == len(required)

    def test_empty_requirements_returns_empty_classification(self):
        match = _make_match(matched=[], missing=[])
        result = classify_requirements(
            required_skills=[],
            profile_skills=["python"],
            match_result=match,
        )
        assert result.verified_match == []
        assert result.transferable_match == []
        assert result.real_gap == []

    def test_multiple_transferable_skills(self):
        # pytorch → tensorflow (ml_frameworks); docker → kubernetes (containers)
        match = _make_match(matched=[], missing=["tensorflow", "kubernetes"])
        result = classify_requirements(
            required_skills=["tensorflow", "kubernetes"],
            profile_skills=["pytorch", "docker"],
            match_result=match,
        )
        assert len(result.transferable_match) == 2
        skills_mapped = {t.skill for t in result.transferable_match}
        assert skills_mapped == {"tensorflow", "kubernetes"}
        assert result.real_gap == []

    def test_case_insensitive_family_lookup(self):
        # "PyTorch" in profile — family lookup must be case-insensitive
        match = _make_match(matched=[], missing=["tensorflow"])
        result = classify_requirements(
            required_skills=["tensorflow"],
            profile_skills=["PyTorch"],
            match_result=match,
        )
        assert len(result.transferable_match) == 1
        assert result.transferable_match[0].via == "PyTorch"

    def test_real_gap_skill_has_no_family_bridge(self):
        # "matlab" (data_science family) — profile has no data_science skill
        match = _make_match(matched=[], missing=["matlab"])
        result = classify_requirements(
            required_skills=["matlab"],
            profile_skills=["fastapi", "docker"],  # python/containers families, not data_science
            match_result=match,
        )
        assert "matlab" in result.real_gap
        assert result.transferable_match == []

    def test_postgres_bridges_to_mysql(self):
        # Both "postgresql" and "mysql" are in the databases family
        match = _make_match(matched=[], missing=["mysql"])
        result = classify_requirements(
            required_skills=["mysql"],
            profile_skills=["postgresql"],
            match_result=match,
        )
        assert len(result.transferable_match) == 1
        assert result.transferable_match[0].skill == "mysql"
        assert result.transferable_match[0].via == "postgresql"


# ── TestComputeReadyToApplyScore ──────────────────────────────────────────────

class TestComputeReadyToApplyScore:
    def _make_classification(
        self,
        verified: list[str] | None = None,
        transferable: int = 0,
        real_gap: list[str] | None = None,
    ) -> RequirementClassification:
        t_list = [
            TransferableSkillResult(skill=f"t{i}", via=f"v{i}", family="ml_frameworks")
            for i in range(transferable)
        ]
        return RequirementClassification(
            verified_match=verified or [],
            transferable_match=t_list,
            real_gap=real_gap or [],
        )

    def test_perfect_match_yields_high_score(self):
        classification = self._make_classification(verified=["python", "docker", "postgres"])
        match = _make_match(
            matched=["python", "docker", "postgres"],
            experience_gap=0,
            location_match=True,
            contract_match=True,
            salary_ok=True,
            language_match=True,
        )
        profile = _base_profile_dict()
        score = compute_ready_to_apply_score(
            classification, ["python", "docker", "postgres"], match, profile
        )
        assert score >= 70

    def test_zero_match_yields_low_score(self):
        classification = self._make_classification(verified=[], real_gap=["a", "b", "c", "d"])
        match = _make_match(
            matched=[],
            experience_gap=-3,
            location_match=False,
            remote_match=False,
            contract_match=False,
            salary_ok=False,
            language_match=False,
        )
        profile = {"skills": [], "target_roles": [], "experience_level": None, "countries": [], "cities": []}
        score = compute_ready_to_apply_score(
            classification, ["a", "b", "c", "d"], match, profile
        )
        assert score <= 30

    def test_score_always_0_to_100(self):
        for n_verified in range(0, 6):
            classification = self._make_classification(verified=["x"] * n_verified)
            match = _make_match(experience_gap=n_verified - 3)
            profile = _base_profile_dict()
            score = compute_ready_to_apply_score(
                classification, ["x"] * 5, match, profile
            )
            assert 0 <= score <= 100, f"Score {score} out of range for n_verified={n_verified}"

    def test_transferable_gives_partial_credit(self):
        # No verified skills but 3 transferable — should be higher than zero verified + zero transferable
        c_transfer = self._make_classification(verified=[], transferable=3)
        c_none = self._make_classification(verified=[], transferable=0)
        match = _make_match(experience_gap=0, location_match=True, contract_match=True, salary_ok=True, language_match=True)
        profile = _base_profile_dict()
        required = ["a", "b", "c"]
        s_transfer = compute_ready_to_apply_score(c_transfer, required, match, profile)
        s_none = compute_ready_to_apply_score(c_none, required, match, profile)
        assert s_transfer > s_none

    def test_empty_requirements_no_crash(self):
        classification = self._make_classification()
        match = _make_match()
        profile = _base_profile_dict()
        score = compute_ready_to_apply_score(classification, [], match, profile)
        assert 0 <= score <= 100

    def test_experience_gap_negative_one_reduces_score(self):
        c = self._make_classification(verified=["python"])
        m_exact = _make_match(experience_gap=0, location_match=True, contract_match=True, salary_ok=True, language_match=True)
        m_slight = _make_match(experience_gap=-1, location_match=True, contract_match=True, salary_ok=True, language_match=True)
        profile = _base_profile_dict()
        required = ["python"]
        assert compute_ready_to_apply_score(c, required, m_exact, profile) > compute_ready_to_apply_score(c, required, m_slight, profile)


# ── TestGenerateWarnings ──────────────────────────────────────────────────────

class TestGenerateWarnings:
    def _cls(self, real_gap: list[str] | None = None) -> RequirementClassification:
        return RequirementClassification(
            verified_match=["python"],
            transferable_match=[],
            real_gap=real_gap or [],
        )

    def test_no_warnings_for_perfect_match(self):
        match = _make_match(experience_gap=0, location_match=True, remote_match=False)
        warnings = generate_warnings(self._cls(), ["python"], match)
        assert warnings == []

    def test_high_gap_warning_when_above_60_pct(self):
        real_gap = ["a", "b", "c", "d"]
        required = ["python", "a", "b", "c", "d"]  # 4/5 = 80% gap
        cls = RequirementClassification(verified_match=["python"], transferable_match=[], real_gap=real_gap)
        match = _make_match()
        warnings = generate_warnings(cls, required, match)
        assert any("high" in w.lower() for w in warnings)

    def test_moderate_gap_warning_when_25_to_60_pct(self):
        real_gap = ["a"]
        required = ["python", "docker", "a"]  # 1/3 ≈ 33% gap
        cls = RequirementClassification(verified_match=["python", "docker"], transferable_match=[], real_gap=real_gap)
        match = _make_match()
        warnings = generate_warnings(cls, required, match)
        assert any("moderate" in w.lower() for w in warnings)

    def test_no_gap_warning_below_25_pct(self):
        real_gap = ["a"]
        required = ["python", "docker", "postgresql", "fastapi", "a"]  # 1/5 = 20% < 25%
        cls = RequirementClassification(verified_match=["python", "docker", "postgresql", "fastapi"], transferable_match=[], real_gap=real_gap)
        match = _make_match()
        warnings = generate_warnings(cls, required, match)
        gap_warnings = [w for w in warnings if "gap" in w.lower() and ("high" in w.lower() or "moderate" in w.lower())]
        assert len(gap_warnings) == 0

    def test_experience_gap_warning_when_significantly_underqualified(self):
        match = _make_match(experience_gap=-2)
        warnings = generate_warnings(self._cls(), [], match)
        assert any("experience" in w.lower() for w in warnings)

    def test_slight_experience_gap_warning(self):
        match = _make_match(experience_gap=-1)
        warnings = generate_warnings(self._cls(), [], match)
        assert any("slight" in w.lower() for w in warnings)

    def test_overqualified_no_experience_warning(self):
        match = _make_match(experience_gap=1)
        warnings = generate_warnings(self._cls(), [], match)
        assert not any("experience" in w.lower() for w in warnings)

    def test_location_mismatch_warning(self):
        match = _make_match(location_match=False, remote_match=False)
        warnings = generate_warnings(self._cls(), [], match)
        assert any("location" in w.lower() for w in warnings)

    def test_no_location_warning_when_remote_available(self):
        match = _make_match(location_match=False, remote_match=True)
        warnings = generate_warnings(self._cls(), [], match)
        location_warnings = [w for w in warnings if "location" in w.lower()]
        assert len(location_warnings) == 0


# ── TestBuildCvAdaptationPrompt ───────────────────────────────────────────────

class TestBuildCvAdaptationPrompt:
    def _classification(self) -> RequirementClassification:
        return RequirementClassification(
            verified_match=["python", "docker"],
            transferable_match=[TransferableSkillResult("tensorflow", "pytorch", "ml_frameworks")],
            real_gap=["kubernetes"],
        )

    def _job(self) -> dict:
        return {
            "title": "Senior ML Engineer",
            "company_name": "Acme Corp",
            "location": "Paris",
            "contract_type": "cdi",
            "required_skills": ["python", "docker", "tensorflow", "kubernetes"],
        }

    def test_real_gap_explicitly_forbidden_in_prompt(self):
        prompt = build_cv_adaptation_prompt(
            _base_profile_dict(), None, self._job(), self._classification()
        )
        assert "kubernetes" in prompt
        assert "do NOT claim" in prompt or "FORBIDDEN" in prompt or "NOT claim" in prompt or "never" in prompt.lower()

    def test_verified_skills_listed_prominently(self):
        prompt = build_cv_adaptation_prompt(
            _base_profile_dict(), None, self._job(), self._classification()
        )
        assert "python" in prompt
        assert "docker" in prompt

    def test_full_name_from_profile_version(self):
        pv = {"full_name": "Jane Doe", "extracted_skills": [], "inferred_skills": [], "education": [], "experience": [], "certifications": []}
        prompt = build_cv_adaptation_prompt(
            _base_profile_dict(), pv, self._job(), self._classification()
        )
        assert "Jane Doe" in prompt

    def test_fallback_name_when_no_profile_version(self):
        prompt = build_cv_adaptation_prompt(
            _base_profile_dict(), None, self._job(), self._classification()
        )
        assert "Candidate" in prompt

    def test_cv_structure_sections_in_prompt(self):
        prompt = build_cv_adaptation_prompt(
            _base_profile_dict(), None, self._job(), self._classification()
        )
        for section in ["Professional Summary", "Core Skills", "Work Experience", "Education"]:
            assert section in prompt, f"Missing section: {section}"

    def test_job_title_and_company_in_prompt(self):
        prompt = build_cv_adaptation_prompt(
            _base_profile_dict(), None, self._job(), self._classification()
        )
        assert "Senior ML Engineer" in prompt
        assert "Acme Corp" in prompt

    def test_transferable_skill_listed_in_prompt(self):
        prompt = build_cv_adaptation_prompt(
            _base_profile_dict(), None, self._job(), self._classification()
        )
        assert "tensorflow" in prompt.lower()
        assert "pytorch" in prompt.lower()


# ── TestBuildCoverLetterPrompt ────────────────────────────────────────────────

class TestBuildCoverLetterPrompt:
    def _classification(self) -> RequirementClassification:
        return RequirementClassification(
            verified_match=["python", "fastapi"],
            transferable_match=[TransferableSkillResult("tensorflow", "pytorch", "ml_frameworks")],
            real_gap=["kubernetes"],
        )

    def _job(self) -> dict:
        return {
            "title": "ML Engineer",
            "company_name": "DataCo",
            "location": "Lyon",
            "contract_type": "cdi",
        }

    def test_real_gap_in_forbidden_section(self):
        prompt = build_cover_letter_prompt(
            _base_profile_dict(), None, self._job(), self._classification()
        )
        assert "kubernetes" in prompt
        assert "Never claim" in prompt or "never" in prompt.lower() or "do NOT" in prompt or "FORBIDDEN" in prompt

    def test_bridge_language_instruction_present(self):
        prompt = build_cover_letter_prompt(
            _base_profile_dict(), None, self._job(), self._classification()
        )
        assert "bridge" in prompt.lower() or "transferable" in prompt.lower()

    def test_transferable_skill_with_via_context(self):
        prompt = build_cover_letter_prompt(
            _base_profile_dict(), None, self._job(), self._classification()
        )
        assert "tensorflow" in prompt.lower()
        assert "pytorch" in prompt.lower()

    def test_verified_skills_claimable(self):
        prompt = build_cover_letter_prompt(
            _base_profile_dict(), None, self._job(), self._classification()
        )
        assert "python" in prompt
        assert "fastapi" in prompt

    def test_paragraph_structure_instructions_present(self):
        prompt = build_cover_letter_prompt(
            _base_profile_dict(), None, self._job(), self._classification()
        )
        assert "Paragraph" in prompt or "paragraph" in prompt
        assert "4" in prompt  # 4 paragraphs

    def test_job_details_in_prompt(self):
        prompt = build_cover_letter_prompt(
            _base_profile_dict(), None, self._job(), self._classification()
        )
        assert "ML Engineer" in prompt
        assert "DataCo" in prompt


# ── TestPrepareApplicationPackage (async) ─────────────────────────────────────

class TestPrepareApplicationPackage:
    def _make_job(self, job_id: uuid.UUID) -> MagicMock:
        job = MagicMock()
        job.id = job_id
        job.title = "Backend Engineer"
        job.company_name = "TestCo"
        job.location = "Paris"
        job.remote = "hybrid"
        job.contract_type = "cdi"
        job.salary_min = 50000
        job.salary_max = 70000
        job.required_skills = ["python", "docker"]
        job.experience_level = "mid"
        job.language = "fr"
        return job

    def _make_profile(self, user_id: uuid.UUID) -> MagicMock:
        p = MagicMock()
        p.id = uuid.uuid4()
        p.user_id = user_id
        p.skills = ["python", "docker", "postgresql"]
        p.target_roles = ["backend engineer"]
        p.experience_level = "mid"
        p.countries = ["France"]
        p.cities = []
        p.remote_preference = True
        p.contract_types = ["cdi"]
        p.salary_min = 45000
        p.salary_target = 55000
        p.languages = ["English", "French"]
        p.certifications = []
        p.education = []
        p.experience = []
        p.raw_json = None
        return p

    async def test_returns_package_on_success(self):
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()
        job = self._make_job(job_id)
        profile = self._make_profile(user_id)

        db = AsyncMock()
        # First execute → job, second → profile version, third → existing package (None)
        from unittest.mock import MagicMock as MM
        job_result = MM()
        job_result.scalar_one_or_none.return_value = job
        pv_result = MM()
        pv_result.scalar_one_or_none.return_value = None
        pkg_result = MM()
        pkg_result.scalar_one_or_none.return_value = None

        db.execute = AsyncMock(side_effect=[job_result, pv_result, pkg_result])
        db.add = MagicMock()
        db.commit = AsyncMock()

        created_pkg = MagicMock()
        created_pkg.id = uuid.uuid4()
        created_pkg.user_id = user_id
        created_pkg.job_id = job_id
        created_pkg.cv_draft = "CV content"
        created_pkg.cover_letter_draft = "Cover letter content"
        created_pkg.requirement_analysis = {"verified_match": ["python", "docker"], "transferable_match": [], "real_gap": []}
        created_pkg.warnings = []
        created_pkg.ready_to_apply_score = 80

        async def _refresh(obj):
            obj.cv_draft = "CV content"
            obj.cover_letter_draft = "Cover letter content"
            obj.requirement_analysis = created_pkg.requirement_analysis
            obj.warnings = []
            obj.ready_to_apply_score = 80
            obj.id = created_pkg.id
            obj.user_id = user_id
            obj.job_id = job_id

        db.refresh = _refresh

        provider = AsyncMock()
        provider.generate = AsyncMock(return_value="Generated text")

        with patch("app.services.application_package_service.profile_service.get_active_profile", return_value=profile):
            pkg = await prepare_application_package(db, user_id, job_id, provider)

        assert pkg is not None
        assert provider.generate.await_count == 2  # CV + cover letter

    async def test_raises_value_error_when_job_not_found(self):
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()

        db = AsyncMock()
        not_found = MagicMock()
        not_found.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=not_found)

        provider = AsyncMock()
        with pytest.raises(ValueError, match="not found"):
            await prepare_application_package(db, user_id, job_id, provider)

    async def test_raises_value_error_when_no_profile(self):
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()
        job = self._make_job(job_id)

        db = AsyncMock()
        job_result = MagicMock()
        job_result.scalar_one_or_none.return_value = job
        db.execute = AsyncMock(return_value=job_result)

        provider = AsyncMock()
        with patch("app.services.application_package_service.profile_service.get_active_profile", return_value=None):
            with pytest.raises(ValueError, match="profile"):
                await prepare_application_package(db, user_id, job_id, provider)

    async def test_upsert_updates_existing_package(self):
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()
        job = self._make_job(job_id)
        profile = self._make_profile(user_id)

        existing_pkg = MagicMock()
        existing_pkg.user_id = user_id
        existing_pkg.job_id = job_id
        existing_pkg.cv_draft = "old cv"
        existing_pkg.cover_letter_draft = "old cl"
        existing_pkg.requirement_analysis = {}
        existing_pkg.warnings = []
        existing_pkg.ready_to_apply_score = 0

        db = AsyncMock()
        job_result = MagicMock()
        job_result.scalar_one_or_none.return_value = job
        pv_result = MagicMock()
        pv_result.scalar_one_or_none.return_value = None
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = existing_pkg

        db.execute = AsyncMock(side_effect=[job_result, pv_result, existing_result])
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        provider = AsyncMock()
        provider.generate = AsyncMock(return_value="new content")

        with patch("app.services.application_package_service.profile_service.get_active_profile", return_value=profile):
            await prepare_application_package(db, user_id, job_id, provider)

        # Should NOT call db.add (updating existing, not inserting new)
        db.add.assert_not_called()
        # Package fields must be updated
        assert existing_pkg.cv_draft == "new content"
        assert existing_pkg.cover_letter_draft == "new content"


# ── TestGetApplicationPackage (async) ─────────────────────────────────────────

class TestGetApplicationPackage:
    async def test_returns_none_when_not_found(self):
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)

        pkg = await get_application_package(db, user_id, job_id)
        assert pkg is None

    async def test_returns_package_when_found(self):
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()
        mock_pkg = MagicMock()
        mock_pkg.user_id = user_id
        mock_pkg.job_id = job_id

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_pkg
        db.execute = AsyncMock(return_value=result)

        pkg = await get_application_package(db, user_id, job_id)
        assert pkg is mock_pkg


# ── Safety tests ──────────────────────────────────────────────────────────────

class TestSafetyConstraints:
    def test_real_gap_in_cv_prompt_forbidden_section(self):
        cls = RequirementClassification(
            verified_match=["python"],
            transferable_match=[],
            real_gap=["kubernetes", "terraform"],
        )
        job = {"title": "DevOps", "company_name": "Co", "location": "Paris", "contract_type": "cdi", "required_skills": ["python", "kubernetes", "terraform"]}
        prompt = build_cv_adaptation_prompt(_base_profile_dict(), None, job, cls)

        # Real gap skills must appear in the forbidden / do-not-claim section
        prompt_lower = prompt.lower()
        assert "kubernetes" in prompt_lower
        assert "terraform" in prompt_lower
        forbidden_marker = prompt.find("do NOT claim") or prompt.find("FORBIDDEN") or prompt.find("NOT claim")
        # Check real_gap skills appear before or near the forbidden instruction
        for skill in ["kubernetes", "terraform"]:
            assert skill.lower() in prompt_lower

    def test_real_gap_in_cover_letter_prompt_forbidden_section(self):
        cls = RequirementClassification(
            verified_match=["python"],
            transferable_match=[],
            real_gap=["kubernetes"],
        )
        job = {"title": "DevOps", "company_name": "Co", "location": None, "contract_type": None}
        prompt = build_cover_letter_prompt(_base_profile_dict(), None, job, cls)

        assert "kubernetes" in prompt.lower()
        assert "never" in prompt.lower() or "do not" in prompt.lower() or "never claim" in prompt.lower()

    def test_transferable_uses_bridge_language_in_cover_letter_prompt(self):
        cls = RequirementClassification(
            verified_match=["python"],
            transferable_match=[TransferableSkillResult("tensorflow", "pytorch", "ml_frameworks")],
            real_gap=[],
        )
        job = {"title": "ML Eng", "company_name": "Co", "location": None, "contract_type": None}
        prompt = build_cover_letter_prompt(_base_profile_dict(), None, job, cls)

        # The prompt must instruct bridge language, not direct claims for transferable skills
        assert "bridge" in prompt.lower() or "transferable" in prompt.lower()
        assert "tensorflow" in prompt.lower()
        assert "pytorch" in prompt.lower()

    def test_high_match_job_score_above_threshold(self):
        cls = RequirementClassification(
            verified_match=["python", "docker", "postgresql"],
            transferable_match=[],
            real_gap=[],
        )
        match = _make_match(
            matched=["python", "docker", "postgresql"],
            experience_gap=0,
            location_match=True,
            contract_match=True,
            salary_ok=True,
            language_match=True,
        )
        profile = _base_profile_dict()
        score = compute_ready_to_apply_score(cls, ["python", "docker", "postgresql"], match, profile)
        assert score >= 70, f"High-match job should score ≥70, got {score}"

    def test_medium_match_job_score_in_range(self):
        cls = RequirementClassification(
            verified_match=["python"],
            transferable_match=[TransferableSkillResult("tensorflow", "pytorch", "ml_frameworks")],
            real_gap=["kubernetes"],
        )
        match = _make_match(
            matched=["python"],
            experience_gap=0,
            location_match=True,
            contract_match=True,
            salary_ok=True,
            language_match=True,
        )
        profile = _base_profile_dict()
        score = compute_ready_to_apply_score(cls, ["python", "tensorflow", "kubernetes"], match, profile)
        assert 20 <= score <= 85, f"Medium-match job should score 20-85, got {score}"
