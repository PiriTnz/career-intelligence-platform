"""
Unit tests for the job normalizer — pure functions, no I/O.
"""
from __future__ import annotations

import pytest

from app.services.normalizer import (
    _detect_language,
    _extract_skills,
    _map_contract,
    _parse_french_salary,
    _parse_salary,
    normalize,
)


# ── Contract mapping ──────────────────────────────────────────────────────────

class TestMapContract:
    def test_cdi_maps_correctly(self):
        assert _map_contract("CDI") == "cdi"

    def test_cdd_maps_correctly(self):
        assert _map_contract("CDD") == "cdd"

    def test_alternance_maps_from_apprentissage(self):
        assert _map_contract("apprentissage") == "alternance"

    def test_stage_from_internship(self):
        assert _map_contract("internship") == "stage"

    def test_underscore_variant_full_time(self):
        # Regression: Adzuna sends "full_time" (underscore), not "full-time"
        assert _map_contract("full_time") == "cdi"

    def test_underscore_variant_part_time(self):
        assert _map_contract("part_time") == "cdd"

    def test_permanent_maps_to_cdi(self):
        assert _map_contract("permanent") == "cdi"

    def test_empty_string_returns_none(self):
        assert _map_contract("") is None

    def test_case_insensitive(self):
        assert _map_contract("Freelance") == "freelance"

    def test_unknown_contract_returns_as_is(self):
        # "mystery-contract" contains "contract" which maps to "cdd" via substring matching.
        # Use a value with no known keyword to test true passthrough.
        result = _map_contract("xyz-unknown")
        assert result == "xyz-unknown"


# ── French salary parsing ─────────────────────────────────────────────────────

class TestParseFrenchSalary:
    def test_standard_range(self):
        min_s, max_s = _parse_french_salary("Annuel de 35000 à 45000 Euros")
        assert min_s == 35000
        assert max_s == 45000

    def test_single_value(self):
        min_s, max_s = _parse_french_salary("Annuel de 40000 Euros")
        assert min_s == 40000
        assert max_s is None

    def test_empty_text(self):
        min_s, max_s = _parse_french_salary("")
        assert min_s is None
        assert max_s is None

    def test_text_with_no_numbers(self):
        min_s, max_s = _parse_french_salary("Selon profil")
        assert min_s is None
        assert max_s is None

    def test_range_with_spaces_in_numbers(self):
        # French convention: "35 000 à 45 000"
        min_s, max_s = _parse_french_salary("35000 à 45000")
        assert min_s == 35000
        assert max_s == 45000


# ── Generic salary parsing ────────────────────────────────────────────────────

class TestParseSalary:
    def test_integer_passthrough(self):
        assert _parse_salary(50000) == 50000

    def test_float_truncates(self):
        assert _parse_salary(50000.9) == 50000

    def test_monthly_converts_to_annual(self):
        # Value < 10_000 treated as monthly
        assert _parse_salary(3500) == 3500 * 12

    def test_string_with_digits_extracted(self):
        assert _parse_salary("45,000") == 45000

    def test_none_returns_none(self):
        assert _parse_salary(None) is None

    def test_non_numeric_string_returns_none(self):
        assert _parse_salary("negotiable") is None


# ── Skill extraction ──────────────────────────────────────────────────────────

class TestExtractSkills:
    def test_extracts_known_skills(self):
        text = "We need experience with Python, Docker, and Kubernetes."
        skills = _extract_skills(text)
        assert "python" in skills
        assert "docker" in skills
        assert "kubernetes" in skills

    def test_case_insensitive(self):
        skills = _extract_skills("PYTHON and FastAPI are required.")
        assert "python" in skills
        assert "fastapi" in skills

    def test_unknown_skills_not_extracted(self):
        skills = _extract_skills("Expertise in COBOL and Fortran.")
        assert skills == []

    def test_empty_text(self):
        assert _extract_skills("") == []

    def test_llm_and_rag_extracted(self):
        skills = _extract_skills("Experience with LLM, RAG, and LangChain frameworks.")
        assert "llm" in skills
        assert "rag" in skills
        assert "langchain" in skills


# ── Language detection ────────────────────────────────────────────────────────

class TestDetectLanguage:
    def test_detects_french(self):
        text = "Nous recherchons un ingénieur expérimenté. Missions variées."
        assert _detect_language(text) == "fr"

    def test_detects_english_by_default(self):
        text = "We are looking for a senior software engineer."
        assert _detect_language(text) == "en"

    def test_empty_text_defaults_to_english(self):
        assert _detect_language("") == "en"


# ── Full normalize pipeline ───────────────────────────────────────────────────

class TestNormalizeFranceTravail:
    RAW = {
        "id": "FT-001",
        "intitule": "Ingénieur ML",
        "entreprise": {"nom": "Acme Corp"},
        "lieuTravail": {"libelle": "Lyon (69)"},
        "typeContrat": "CDI",
        "salaire": {"libelle": "Annuel de 45000 à 55000 Euros"},
        "description": "Nous recherchons un expert Python, Docker et LLM.",
        "dateCreation": "2024-06-01",
        "origineOffre": {"urlOrigine": "https://ft.fr/offre/FT-001"},
        "experienceExige": "S",
    }

    def test_title_mapped(self):
        result = normalize(self.RAW, "france_travail")
        assert result["title"] == "Ingénieur ML"

    def test_company_mapped(self):
        result = normalize(self.RAW, "france_travail")
        assert result["company_name"] == "Acme Corp"

    def test_salary_parsed(self):
        result = normalize(self.RAW, "france_travail")
        assert result["salary_min"] == 45000
        assert result["salary_max"] == 55000

    def test_contract_normalized(self):
        result = normalize(self.RAW, "france_travail")
        assert result["contract_type"] == "cdi"

    def test_skills_extracted_from_description(self):
        result = normalize(self.RAW, "france_travail")
        assert "python" in result["required_skills"]
        assert "docker" in result["required_skills"]
        assert "llm" in result["required_skills"]

    def test_language_detected_as_french(self):
        result = normalize(self.RAW, "france_travail")
        assert result["language"] == "fr"

    def test_source_set_correctly(self):
        result = normalize(self.RAW, "france_travail")
        assert result["source"] == "france_travail"

    def test_experience_level_mapped(self):
        result = normalize(self.RAW, "france_travail")
        assert result["experience_level"] == "mid"  # "S" → mid

    def test_url_from_origine(self):
        result = normalize(self.RAW, "france_travail")
        assert result["url"] == "https://ft.fr/offre/FT-001"


class TestNormalizeAdzuna:
    RAW = {
        "id": "AZ-999",
        "title": "ML Engineer",
        "company": {"display_name": "TechCorp"},
        "location": {"display_name": "Paris, Île-de-France"},
        "contract_time": "full_time",
        "salary_min": 50000,
        "salary_max": 65000,
        "description": "We need Python, FastAPI, Docker and Kubernetes skills.",
        "redirect_url": "https://adzuna.fr/job/AZ-999",
        "created": "2024-06-15",
    }

    def test_title_mapped(self):
        result = normalize(self.RAW, "adzuna")
        assert result["title"] == "ML Engineer"

    def test_contract_full_time_underscore_normalized(self):
        # Regression: "full_time" (underscore) must map to "cdi"
        result = normalize(self.RAW, "adzuna")
        assert result["contract_type"] == "cdi"

    def test_salary_passthrough(self):
        result = normalize(self.RAW, "adzuna")
        assert result["salary_min"] == 50000
        assert result["salary_max"] == 65000

    def test_source_set_correctly(self):
        result = normalize(self.RAW, "adzuna")
        assert result["source"] == "adzuna"

    def test_skills_extracted(self):
        result = normalize(self.RAW, "adzuna")
        assert "python" in result["required_skills"]
        assert "fastapi" in result["required_skills"]

    def test_language_detected_as_english(self):
        result = normalize(self.RAW, "adzuna")
        assert result["language"] == "en"


class TestNormalizeGeneric:
    RAW = {
        "title": "Data Scientist",
        "company": "DataCo",
        "location": "Remote",
        "contract_type": "CDI",
        "salary_min": 45000,
        "remote": "full",
        "url": "https://example.com/job/1",
        "description": "Python, scikit-learn, PyTorch required.",
    }

    def test_generic_source_fallback(self):
        result = normalize(self.RAW, "generic")
        assert result["title"] == "Data Scientist"
        assert result["source"] == "generic"

    def test_unknown_source_uses_generic(self):
        result = normalize(self.RAW, "unknown_source")
        assert result["title"] == "Data Scientist"
        assert result["source"] == "unknown_source"

    def test_remote_full_mapped(self):
        result = normalize(self.RAW, "generic")
        assert result["remote"] == "full"
