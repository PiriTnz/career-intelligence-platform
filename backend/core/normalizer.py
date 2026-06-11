"""
Normalizer — maps raw job data from any source to unified schema.
Each source has its own mapper function.
"""
from datetime import datetime
from typing import Optional
import re


UNIFIED_SCHEMA = {
    "title": "",
    "company": "",
    "location": "",
    "contract_type": "",   # alternance, cdi, cdd, stage, freelance
    "salary_min": None,
    "salary_max": None,
    "remote": "none",      # none, hybrid, full
    "required_skills": [],
    "experience_level": "",
    "language": "fr",
    "url": "",
    "source": "",
    "published_at": None,
    "description": "",
}

CONTRACT_MAP = {
    "alternance": "alternance",
    "apprentissage": "alternance",
    "cdi": "cdi",
    "cdd": "cdd",
    "stage": "stage",
    "internship": "stage",
    "freelance": "freelance",
    "full-time": "cdi",
    "part-time": "cdd",
}

SKILL_KEYWORDS = [
    "python", "javascript", "typescript", "java", "c#", "c++", "go", "rust",
    "react", "vue", "angular", "fastapi", "django", "flask", "node",
    "docker", "kubernetes", "terraform", "ansible", "aws", "gcp", "azure",
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "llm", "rag", "langchain", "ollama", "openai", "huggingface",
    "machine learning", "deep learning", "pytorch", "tensorflow",
    "devops", "ci/cd", "github actions", "jenkins", "linux",
    "mcp", "agent", "n8n", "airflow",
]


def normalize(raw: dict, source: str) -> dict:
    mappers = {
        "indeed": _from_indeed,
        "wttj": _from_wttj,
        "hellowork": _from_hellowork,
        "generic": _from_generic,
    }
    mapper = mappers.get(source, _from_generic)
    job = mapper(raw)
    job["source"] = source
    job["required_skills"] = _extract_skills(job.get("description", ""))
    job["language"] = _detect_language(job.get("description", ""))
    return job


def _from_indeed(raw: dict) -> dict:
    return {
        **UNIFIED_SCHEMA,
        "title": raw.get("title", ""),
        "company": raw.get("company", ""),
        "location": raw.get("formattedLocation", ""),
        "contract_type": _map_contract(raw.get("jobType", "")),
        "salary_min": _parse_salary(raw.get("salaryMin")),
        "salary_max": _parse_salary(raw.get("salaryMax")),
        "remote": _map_remote(raw.get("remoteWork", "")),
        "url": raw.get("url", ""),
        "description": raw.get("snippet", "") + " " + raw.get("description", ""),
        "published_at": _parse_date(raw.get("date")),
    }


def _from_wttj(raw: dict) -> dict:
    contract_raw = raw.get("contract_type", {})
    contract = contract_raw.get("name", "") if isinstance(contract_raw, dict) else contract_raw
    office = raw.get("office", {})
    location = office.get("city", "") if isinstance(office, dict) else ""
    return {
        **UNIFIED_SCHEMA,
        "title": raw.get("name", ""),
        "company": raw.get("organization", {}).get("name", "") if isinstance(raw.get("organization"), dict) else "",
        "location": location,
        "contract_type": _map_contract(contract),
        "remote": _map_remote(raw.get("remote", "")),
        "url": f"https://www.welcometothejungle.com/jobs/{raw.get('slug', '')}",
        "description": raw.get("description", ""),
        "published_at": _parse_date(raw.get("published_at")),
    }


def _from_hellowork(raw: dict) -> dict:
    return {
        **UNIFIED_SCHEMA,
        "title": raw.get("title", ""),
        "company": raw.get("company", ""),
        "location": raw.get("city", ""),
        "contract_type": _map_contract(raw.get("contract", "")),
        "salary_min": _parse_salary(raw.get("salary_min")),
        "salary_max": _parse_salary(raw.get("salary_max")),
        "url": raw.get("url", ""),
        "description": raw.get("description", ""),
        "published_at": _parse_date(raw.get("date")),
    }


def _from_generic(raw: dict) -> dict:
    return {
        **UNIFIED_SCHEMA,
        "title": raw.get("title", ""),
        "company": raw.get("company", raw.get("company_name", "")),
        "location": raw.get("location", ""),
        "contract_type": _map_contract(raw.get("contract_type", raw.get("type", ""))),
        "salary_min": _parse_salary(raw.get("salary_min")),
        "salary_max": _parse_salary(raw.get("salary_max")),
        "remote": _map_remote(raw.get("remote", "")),
        "url": raw.get("url", ""),
        "description": raw.get("description", ""),
        "published_at": _parse_date(raw.get("published_at", raw.get("date"))),
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _map_contract(raw: str) -> str:
    if not raw:
        return ""
    key = raw.lower().strip()
    for k, v in CONTRACT_MAP.items():
        if k in key:
            return v
    return key


def _map_remote(raw: str) -> str:
    if not raw:
        return "none"
    raw = raw.lower()
    if "full" in raw or "100" in raw or "remote" in raw:
        return "full"
    if "hybrid" in raw or "télétravail partiel" in raw:
        return "hybrid"
    return "none"


def _parse_salary(value) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def _parse_date(value) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _extract_skills(text: str) -> list[str]:
    text_lower = text.lower()
    return [s for s in SKILL_KEYWORDS if s in text_lower]


def _detect_language(text: str) -> str:
    fr_markers = ["nous recherchons", "poste", "entreprise", "expérience", "compétences"]
    if any(m in text.lower() for m in fr_markers):
        return "fr"
    return "en"
