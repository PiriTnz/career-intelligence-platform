"""
Map raw job JSON from any source to the unified normalized schema.
No I/O — pure functions, fully testable.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

UNIFIED_SCHEMA: dict[str, Any] = {
    "title": "",
    "company_name": "",
    "location": None,
    "contract_type": None,
    "salary_min": None,
    "salary_max": None,
    "salary_currency": "EUR",
    "remote": "none",
    "required_skills": [],
    "experience_level": None,
    "language": "fr",
    "url": "",
    "source": "",
    "source_id": None,
    "published_at": None,
    "description": "",
}

CONTRACT_MAP = {
    "cdi": "cdi",
    "cdd": "cdd",
    "alternance": "alternance",
    "apprentissage": "alternance",
    "stage": "stage",
    "internship": "stage",
    "freelance": "freelance",
    "interim": "interim",
    "mis": "interim",
    "full-time": "cdi",
    "part-time": "cdd",
    "permanent": "cdi",
    "contract": "cdd",
}

SKILL_KEYWORDS = [
    "python", "javascript", "typescript", "java", "c#", "c++", "go", "rust",
    "react", "vue", "angular", "fastapi", "django", "flask", "node",
    "docker", "kubernetes", "terraform", "ansible", "aws", "gcp", "azure",
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "llm", "rag", "langchain", "ollama", "openai", "huggingface",
    "machine learning", "deep learning", "pytorch", "tensorflow", "scikit-learn",
    "devops", "ci/cd", "github actions", "jenkins", "linux",
    "mlops", "airflow", "kafka", "spark", "dbt",
    "bert", "gpt", "transformers", "vector database",
]

FR_MARKERS = [
    "nous recherchons", "poste", "entreprise", "expérience",
    "compétences", "missions", "profil", "requis",
]


def normalize(raw: dict, source: str) -> dict:
    """Entry point — dispatches to the right mapper, then enriches."""
    mappers = {
        "france_travail": _from_france_travail,
        "adzuna": _from_adzuna,
        "generic": _from_generic,
    }
    job = mappers.get(source, _from_generic)(raw)
    job["source"] = source
    job["required_skills"] = _extract_skills(job.get("description") or "")
    job["language"] = _detect_language(job.get("description") or "")
    return job


# ── Source mappers ────────────────────────────────────────────────────────────

def _from_france_travail(raw: dict) -> dict:
    lieu = raw.get("lieuTravail") or {}
    entreprise = raw.get("entreprise") or {}
    salaire = raw.get("salaire") or {}
    origine = raw.get("origineOffre") or {}

    # Parse salary from French text like "Annuel de 35000 à 45000 Euros"
    sal_min, sal_max = _parse_french_salary(salaire.get("libelle", ""))

    return {
        **UNIFIED_SCHEMA,
        "source_id": raw.get("id", ""),
        "title": raw.get("intitule", ""),
        "company_name": entreprise.get("nom", "Entreprise non précisée"),
        "location": lieu.get("libelle", ""),
        "contract_type": _map_contract(raw.get("typeContrat", "")),
        "salary_min": sal_min,
        "salary_max": sal_max,
        "remote": _map_remote_france_travail(raw),
        "url": origine.get("urlOrigine", f"https://www.francetravail.fr/offres/recherche/detail/{raw.get('id', '')}"),
        "description": raw.get("description", ""),
        "published_at": _parse_date(raw.get("dateCreation")),
        "experience_level": _map_experience_france_travail(raw.get("experienceExige", "")),
    }


def _from_adzuna(raw: dict) -> dict:
    location = raw.get("location") or {}
    company = raw.get("company") or {}
    return {
        **UNIFIED_SCHEMA,
        "source_id": str(raw.get("id", "")),
        "title": raw.get("title", ""),
        "company_name": company.get("display_name", ""),
        "location": location.get("display_name", ""),
        "contract_type": _map_contract(raw.get("contract_time", "")),
        "salary_min": _parse_salary(raw.get("salary_min")),
        "salary_max": _parse_salary(raw.get("salary_max")),
        "remote": _map_remote_adzuna(raw),
        "url": raw.get("redirect_url", ""),
        "description": raw.get("description", ""),
        "published_at": _parse_date(raw.get("created")),
    }


def _from_generic(raw: dict) -> dict:
    return {
        **UNIFIED_SCHEMA,
        "source_id": str(raw.get("id", raw.get("source_id", ""))),
        "title": raw.get("title", ""),
        "company_name": raw.get("company", raw.get("company_name", "")),
        "location": raw.get("location", ""),
        "contract_type": _map_contract(raw.get("contract_type", raw.get("type", ""))),
        "salary_min": _parse_salary(raw.get("salary_min")),
        "salary_max": _parse_salary(raw.get("salary_max")),
        "remote": _map_remote_generic(raw.get("remote", "")),
        "url": raw.get("url", ""),
        "description": raw.get("description", ""),
        "published_at": _parse_date(raw.get("published_at", raw.get("date"))),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _map_contract(raw: str) -> str | None:
    if not raw:
        return None
    key = raw.lower().strip().replace("_", "-")
    for k, v in CONTRACT_MAP.items():
        if k in key:
            return v
    return key or None


def _map_remote_france_travail(raw: dict) -> str:
    # France Travail uses "teletravailPossible" boolean
    if raw.get("teletravailPossible"):
        return "hybrid"
    # Some listings embed "télétravail" in the description
    desc = (raw.get("description") or "").lower()
    if "full remote" in desc or "100% télétravail" in desc or "full remote" in desc:
        return "full"
    if "télétravail" in desc or "teletravail" in desc:
        return "hybrid"
    return "none"


def _map_remote_adzuna(raw: dict) -> str:
    flags = (raw.get("tags") or [])
    desc = (raw.get("description") or "").lower()
    if any(t.get("label") == "remote" for t in flags):
        return "full"
    if "hybrid" in desc or "hybride" in desc:
        return "hybrid"
    if "remote" in desc or "télétravail" in desc:
        return "hybrid"
    return "none"


def _map_remote_generic(raw: str) -> str:
    if not raw:
        return "none"
    raw = raw.lower()
    if "full" in raw or "100" in raw:
        return "full"
    if "hybrid" in raw or "télétravail" in raw:
        return "hybrid"
    return "none"


def _map_experience_france_travail(code: str) -> str | None:
    mapping = {"D": "junior", "S": "mid", "E": "senior"}
    return mapping.get(code.upper() if code else "")


def _parse_salary(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        v = int(value)
        # Convert monthly to annual if suspiciously small
        return v * 12 if v < 10_000 else v
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def _parse_french_salary(text: str) -> tuple[int | None, int | None]:
    """Parse 'Annuel de 35000 à 45000 Euros' → (35000, 45000)."""
    numbers = re.findall(r"\d[\d\s]*\d|\d+", text.replace(" ", "").replace(" ", ""))
    values = [int(n.replace(" ", "")) for n in numbers if n.strip()]
    if len(values) >= 2:
        return values[0], values[1]
    if len(values) == 1:
        return values[0], None
    return None, None


def _parse_date(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)[:19]  # strip sub-second precision


def _extract_skills(text: str) -> list[str]:
    text_lower = text.lower()
    return [s for s in SKILL_KEYWORDS if s in text_lower]


def _detect_language(text: str) -> str:
    if any(m in text.lower() for m in FR_MARKERS):
        return "fr"
    return "en"
