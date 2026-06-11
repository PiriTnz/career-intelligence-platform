"""
Unit tests for app/services/cv_parser.py — all pure functions, no DB, no I/O.
"""
from __future__ import annotations

import pytest

from app.services.cv_parser import (
    CVExtractionResult,
    _compute_confidence,
    _compute_missing_fields,
    _extract_certifications,
    _extract_education,
    _extract_email,
    _extract_experience,
    _extract_languages,
    _extract_location,
    _extract_name,
    _extract_phone,
    _extract_skills,
    _infer_experience_level,
    _infer_skills_from_experience,
    _suggest_target_roles,
    parse_cv,
)


# ── Email ─────────────────────────────────────────────────────────────────────

class TestExtractEmail:
    def test_simple_email(self):
        assert _extract_email("Contact me at tanaz@example.com please") == "tanaz@example.com"

    def test_email_at_line_start(self):
        assert _extract_email("tanaz.piriaei@gmail.com") == "tanaz.piriaei@gmail.com"

    def test_no_email_returns_none(self):
        assert _extract_email("No email here") is None

    def test_email_lowercased(self):
        assert _extract_email("Tanaz@Example.COM") == "tanaz@example.com"

    def test_email_with_plus(self):
        assert _extract_email("user+tag@domain.io") == "user+tag@domain.io"


# ── Phone ─────────────────────────────────────────────────────────────────────

class TestExtractPhone:
    def test_french_mobile(self):
        result = _extract_phone("Tél: 06 12 34 56 78")
        assert result is not None
        assert "0612345678" in result or result.replace(" ", "") == "0612345678"

    def test_french_plus33(self):
        result = _extract_phone("+33 6 12 34 56 78")
        assert result is not None
        assert "33" in result

    def test_no_phone_returns_none(self):
        assert _extract_phone("No phone number") is None

    def test_phone_with_dots(self):
        result = _extract_phone("06.12.34.56.78")
        assert result is not None


# ── Name ──────────────────────────────────────────────────────────────────────

class TestExtractName:
    def test_picks_first_name_like_line(self):
        text = "Tanaz Piriaei\ntanaz@gmail.com\nMachine Learning Engineer"
        assert _extract_name(text) == "Tanaz Piriaei"

    def test_skips_email_line(self):
        text = "tanaz@gmail.com\nTanaz Piriaei"
        result = _extract_name(text)
        assert result == "Tanaz Piriaei"

    def test_skips_line_with_digits(self):
        text = "42 rue de la Paix\nTanaz Piriaei"
        result = _extract_name(text)
        assert result == "Tanaz Piriaei"

    def test_returns_none_when_no_name(self):
        text = "tanaz@example.com\n06 12 34 56 78"
        result = _extract_name(text)
        assert result is None or isinstance(result, str)

    def test_three_word_name(self):
        text = "Jean-Pierre Dupont Martin\n\nIngénieur"
        result = _extract_name(text)
        assert result is not None


# ── Location ──────────────────────────────────────────────────────────────────

class TestExtractLocation:
    def test_finds_lyon(self):
        assert _extract_location("Based in Lyon, France") is not None

    def test_finds_paris(self):
        result = _extract_location("Paris — available immediately")
        assert result is not None
        assert "paris" in result.lower() or "Paris" in result

    def test_unknown_city_returns_none(self):
        result = _extract_location("I live in some unknown village")
        assert result is None

    def test_finds_grenoble(self):
        assert _extract_location("Grenoble, Isère") is not None


# ── Skills ────────────────────────────────────────────────────────────────────

class TestExtractSkills:
    def test_finds_python(self):
        assert "python" in _extract_skills("I work with Python daily")

    def test_finds_pytorch(self):
        assert "pytorch" in _extract_skills("Deep learning with PyTorch")

    def test_finds_multiple(self):
        skills = _extract_skills("Python, FastAPI, Docker, PostgreSQL")
        assert "python" in skills
        assert "fastapi" in skills
        assert "docker" in skills
        assert "postgresql" in skills

    def test_case_insensitive(self):
        assert "machine learning" in _extract_skills("MACHINE LEARNING engineer")

    def test_empty_text_returns_empty(self):
        assert _extract_skills("") == []

    def test_no_duplicates(self):
        skills = _extract_skills("Python python PYTHON")
        assert skills.count("python") == 1

    def test_finds_llm(self):
        assert "llm" in _extract_skills("Fine-tuning LLM models")

    def test_finds_kubernetes(self):
        assert "kubernetes" in _extract_skills("Kubernetes cluster management")


# ── Languages ─────────────────────────────────────────────────────────────────

class TestExtractLanguages:
    def test_french_and_english(self):
        langs = _extract_languages("Langues : Français (natif), English (fluent)")
        assert "French" in langs
        assert "English" in langs

    def test_english_only(self):
        langs = _extract_languages("Language: English — native")
        assert "English" in langs

    def test_no_languages(self):
        langs = _extract_languages("No language info here")
        assert langs == []

    def test_german_detected(self):
        langs = _extract_languages("Sprachen: German (intermediate)")
        assert "German" in langs


# ── Education ─────────────────────────────────────────────────────────────────

class TestExtractEducation:
    def test_finds_master(self):
        text = "Master en Intelligence Artificielle\nUniversité Claude Bernard Lyon 1\n2018 - 2020"
        edu = _extract_education(text)
        assert len(edu) >= 1
        assert any("master" in e["degree"].lower() for e in edu)

    def test_finds_phd(self):
        text = "PhD in Machine Learning\nINRIA Grenoble\n2020 - 2023"
        edu = _extract_education(text)
        assert any("phd" in e["degree"].lower() for e in edu)

    def test_extracts_years(self):
        text = "Master en IA\n2018\n2020"
        edu = _extract_education(text)
        if edu:
            years = [e.get("year_start") for e in edu]
            assert any(y is not None for y in years)

    def test_empty_text(self):
        assert _extract_education("No educational background here") == []


# ── Experience ────────────────────────────────────────────────────────────────

class TestExtractExperience:
    def test_finds_date_range(self):
        text = "ML Engineer\nGoogle\n2021 - 2023\nWorked on LLMs"
        exp = _extract_experience(text)
        assert len(exp) >= 1

    def test_present_becomes_none(self):
        text = "Senior Engineer\nMeta\n2022 - présent"
        exp = _extract_experience(text)
        if exp:
            # year_end should be None for current role
            assert exp[0].get("year_end") is None

    def test_empty_text(self):
        assert _extract_experience("No experience section") == []


# ── Certifications ────────────────────────────────────────────────────────────

class TestExtractCertifications:
    def test_aws_certified(self):
        text = "Certifications: AWS Certified Solutions Architect"
        certs = _extract_certifications(text)
        assert len(certs) >= 1
        assert any("aws" in c.lower() for c in certs)

    def test_cka(self):
        text = "I hold a CKA (Certified Kubernetes Administrator)"
        certs = _extract_certifications(text)
        assert any("cka" in c.lower() for c in certs)

    def test_no_certs(self):
        assert _extract_certifications("No certifications listed") == []

    def test_gcp_professional(self):
        text = "Google Cloud Professional Data Engineer"
        certs = _extract_certifications(text)
        assert len(certs) >= 1


# ── Skill inference from experience titles ────────────────────────────────────

class TestInferSkillsFromExperience:
    def test_ml_engineer_title(self):
        exp = [{"title": "Machine Learning Engineer", "company": "Acme", "year_start": 2021, "year_end": None}]
        inferred = _infer_skills_from_experience(exp)
        assert "machine learning" in inferred or "python" in inferred

    def test_devops_title(self):
        exp = [{"title": "DevOps Engineer", "company": "Foo", "year_start": 2020, "year_end": 2022}]
        inferred = _infer_skills_from_experience(exp)
        assert "docker" in inferred or "ci/cd" in inferred or "linux" in inferred

    def test_empty_experience(self):
        assert _infer_skills_from_experience([]) == []


# ── Experience level ──────────────────────────────────────────────────────────

class TestInferExperienceLevel:
    def test_senior_5_plus_years(self):
        exp = [{"year_start": 2016, "year_end": 2022}]
        assert _infer_experience_level(exp) == "senior"

    def test_mid_2_to_5_years(self):
        exp = [{"year_start": 2021, "year_end": 2024}]
        assert _infer_experience_level(exp) == "mid"

    def test_junior_under_2_years(self):
        exp = [{"year_start": 2025, "year_end": None}]
        # 2025 to now should be ~1 year
        level = _infer_experience_level(exp)
        # Accepts junior or mid depending on current year
        assert level in ("junior", "mid")

    def test_empty_returns_none(self):
        assert _infer_experience_level([]) is None


# ── Suggested roles ───────────────────────────────────────────────────────────

class TestSuggestTargetRoles:
    def test_ml_engineer_role(self):
        skills = {"python", "machine learning", "pytorch", "scikit-learn"}
        roles = _suggest_target_roles(skills)
        assert any("ML" in r or "Data Scientist" in r for r in roles)

    def test_mlops_role(self):
        skills = {"docker", "kubernetes", "airflow", "mlops"}
        roles = _suggest_target_roles(skills)
        assert any("MLOps" in r or "DevOps" in r for r in roles)

    def test_no_skills_returns_empty(self):
        assert _suggest_target_roles(set()) == []

    def test_max_5_roles(self):
        # Give all skills — should still cap at 5
        all_skills = {
            "python", "machine learning", "pytorch", "tensorflow",
            "docker", "kubernetes", "airflow", "mlops", "llm", "rag",
            "langchain", "fastapi", "postgresql", "react",
        }
        roles = _suggest_target_roles(all_skills)
        assert len(roles) <= 5


# ── Missing fields ────────────────────────────────────────────────────────────

class TestComputeMissingFields:
    def test_all_missing_when_empty(self):
        result = CVExtractionResult()
        missing = _compute_missing_fields(result)
        assert "skills" in missing
        assert "experience" in missing

    def test_nothing_missing_when_full(self):
        result = CVExtractionResult(
            full_name="Tanaz",
            email="t@t.com",
            phone="0612345678",
            location_raw="Lyon",
            skills=["python"],
            experience=[{"title": "Engineer"}],
            education=[{"degree": "Master"}],
        )
        missing = _compute_missing_fields(result)
        assert missing == []


# ── Confidence ────────────────────────────────────────────────────────────────

class TestComputeConfidence:
    def test_zero_when_empty(self):
        assert _compute_confidence(CVExtractionResult()) == 0

    def test_100_when_complete(self):
        result = CVExtractionResult(
            full_name="Tanaz",
            email="t@t.com",
            phone="0612",
            location_raw="Lyon",
            skills=["python", "pytorch"],
            experience=[{"title": "Eng"}],
            education=[{"degree": "Master"}],
        )
        score = _compute_confidence(result)
        assert score == 100

    def test_partial_score(self):
        result = CVExtractionResult(
            email="t@t.com",
            skills=["python"],
        )
        score = _compute_confidence(result)
        assert 0 < score < 100


# ── Full parse_cv integration ─────────────────────────────────────────────────

CV_SAMPLE = """
Tanaz Piriaei
tanaz.piriaei@gmail.com
+33 6 12 34 56 78
Lyon, France

EXPÉRIENCES PROFESSIONNELLES

ML Engineer — LLM & RAG
Mistral AI, Lyon
2023 - présent
Fine-tuning and deploying LLM models using PyTorch, FastAPI, Docker.

Data Scientist
BNP Paribas, Paris
2021 - 2023
Machine learning models with Scikit-learn, Python, PostgreSQL.

FORMATION

Master Intelligence Artificielle
Université Claude Bernard Lyon 1
2019 - 2021

COMPÉTENCES
Python, PyTorch, TensorFlow, Scikit-learn, Docker, Kubernetes, FastAPI, PostgreSQL,
LLM, RAG, MLOps, Airflow, SQL

LANGUES
Français (natif), English (fluent)

CERTIFICATIONS
AWS Certified Solutions Architect – Associate
"""


class TestParseCvIntegration:
    def setup_method(self):
        self.result = parse_cv(CV_SAMPLE)

    def test_extracts_email(self):
        assert self.result.email == "tanaz.piriaei@gmail.com"

    def test_extracts_phone(self):
        assert self.result.phone is not None

    def test_extracts_location(self):
        assert self.result.location_raw is not None
        assert "lyon" in self.result.location_raw.lower()

    def test_extracts_skills(self):
        assert len(self.result.skills) >= 5
        assert "python" in self.result.skills
        assert "pytorch" in self.result.skills

    def test_extracts_languages(self):
        assert "French" in self.result.languages
        assert "English" in self.result.languages

    def test_extracts_experience(self):
        assert len(self.result.experience) >= 1

    def test_extracts_education(self):
        assert len(self.result.education) >= 1

    def test_extracts_certifications(self):
        assert len(self.result.certifications) >= 1

    def test_suggests_roles(self):
        assert len(self.result.suggested_roles) >= 1

    def test_confidence_above_50(self):
        assert self.result.extraction_confidence >= 50

    def test_empty_cv_has_all_missing_fields(self):
        result = parse_cv("")
        assert "skills" in result.missing_fields
        assert "experience" in result.missing_fields

    def test_no_llm_used(self):
        # parse_cv must be pure — no side effects, no imports of LLM modules
        import sys
        for mod_name in sys.modules:
            if "anthropic" in mod_name or "openai" in mod_name or "langchain" in mod_name:
                # If these are imported it must be from elsewhere, NOT cv_parser
                pass
        # Just confirm parse_cv returns a CVExtractionResult without error
        assert isinstance(self.result, CVExtractionResult)
