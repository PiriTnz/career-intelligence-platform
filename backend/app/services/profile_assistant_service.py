"""
LLM Profile Assistant Service.

Extracts career profile fields from free-form user text (text or voice transcript).
All extracted data is validated before returning — no blind profile overwrites.

Design constraints:
  - LLM: extraction ONLY (natural language → structured fields)
  - Pydantic: all field validation (enums, ranges, types)
  - Deterministic: completeness scoring, next-question selection, translations
  - Two-step: /message proposes updates; /apply-updates writes them
  - Multilingual: English, French, Persian assistant messages
  - Generic: no user-specific data, roles, or locations hardcoded
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.profile import Profile
from app.llm.base import BaseLLMProvider
from app.schemas.profile_assistant import ExtractedProfileUpdate
from app.services import profile_service

logger = logging.getLogger(__name__)

# ── Completeness field definitions ────────────────────────────────────────────


@dataclass(frozen=True)
class _CompField:
    key: str
    label: str
    weight: int


COMPLETENESS_FIELDS: tuple[_CompField, ...] = (
    _CompField("skills",            "technical skills",                       20),
    _CompField("target_roles",      "target job roles",                       15),
    _CompField("experience_level",  "experience level",                       15),
    _CompField("location",          "preferred locations (city or country)",   10),
    _CompField("salary",            "salary expectations",                     10),
    _CompField("education",         "education history",                       10),
    _CompField("languages",         "languages spoken",                         5),
    _CompField("contract_types",    "preferred contract types",                 5),
    _CompField("certifications",    "certifications",                           5),
    _CompField("opportunity_types", "opportunity types of interest",            5),
)

COMPLETENESS_PRIORITY: list[str] = [
    "target_roles", "skills", "experience_level", "location",
    "salary", "languages", "contract_types", "education",
    "opportunity_types", "certifications",
]

# ── Multilingual messages ─────────────────────────────────────────────────────

_TRANSLATIONS: dict[str, dict] = {
    "en": {
        "fields_captured": "I've noted the following from your message: {fields}.",
        "no_update": "I couldn't find specific profile information in that message. Could you tell me more about your career goals?",
        "completeness": "Your profile is {pct}% complete.",
        "missing_hint": "To improve your profile, please share your {missing}.",
        "next_q": {
            "target_roles":      "What job roles or titles are you targeting?",
            "skills":            "What are your main technical or professional skills?",
            "experience_level":  "How many years of professional experience do you have?",
            "location":          "Which cities or countries are you open to working in?",
            "salary":            "What are your salary expectations (minimum and/or target)?",
            "languages":         "What languages do you speak professionally?",
            "contract_types":    "What type of contract are you looking for (permanent, freelance, etc.)?",
            "education":         "What is your highest level of education or degree?",
            "opportunity_types": "What types of opportunities interest you — employment, PhD, CIFRE, freelance?",
            "certifications":    "Do you have any professional certifications?",
        },
        "all_complete": "Your profile looks great! Is there anything else you'd like to add or update?",
    },
    "fr": {
        "fields_captured": "J'ai noté les informations suivantes de votre message : {fields}.",
        "no_update": "Je n'ai pas trouvé d'informations de profil spécifiques dans ce message. Pouvez-vous me parler de vos objectifs de carrière ?",
        "completeness": "Votre profil est complété à {pct}%.",
        "missing_hint": "Pour améliorer votre profil, partagez vos {missing}.",
        "next_q": {
            "target_roles":      "Quels postes ou titres de poste recherchez-vous ?",
            "skills":            "Quelles sont vos principales compétences techniques ou professionnelles ?",
            "experience_level":  "Combien d'années d'expérience professionnelle avez-vous ?",
            "location":          "Dans quelles villes ou pays souhaitez-vous travailler ?",
            "salary":            "Quelles sont vos attentes salariales (minimum et/ou cible) ?",
            "languages":         "Quelles langues parlez-vous professionnellement ?",
            "contract_types":    "Quel type de contrat recherchez-vous (CDI, freelance, etc.) ?",
            "education":         "Quel est votre niveau d'études ou votre diplôme le plus élevé ?",
            "opportunity_types": "Quels types d'opportunités vous intéressent — emploi, doctorat, CIFRE, freelance ?",
            "certifications":    "Avez-vous des certifications professionnelles ?",
        },
        "all_complete": "Votre profil est très complet ! Y a-t-il autre chose que vous souhaitez ajouter ou mettre à jour ?",
    },
    "fa": {
        "fields_captured": "اطلاعات زیر را از پیام شما یادداشت کردم: {fields}.",
        "no_update": "اطلاعات پروفایل خاصی در این پیام پیدا نکردم. می‌توانید بیشتر درباره اهداف شغلی خود توضیح دهید؟",
        "completeness": "پروفایل شما {pct}٪ کامل است.",
        "missing_hint": "برای بهبود پروفایل، لطفاً {missing} خود را به اشتراک بگذارید.",
        "next_q": {
            "target_roles":      "به دنبال چه سمت‌ها یا عنوان‌های شغلی هستید؟",
            "skills":            "مهارت‌های فنی یا حرفه‌ای اصلی شما چیست؟",
            "experience_level":  "چند سال تجربه حرفه‌ای دارید؟",
            "location":          "در چه شهرها یا کشورهایی حاضر به کار هستید؟",
            "salary":            "انتظارات حقوقی شما چیست (حداقل و/یا هدف)؟",
            "languages":         "به چه زبان‌هایی به‌صورت حرفه‌ای صحبت می‌کنید؟",
            "contract_types":    "به دنبال چه نوع قراردادی هستید (تمام‌وقت، فریلنس و غیره)؟",
            "education":         "بالاترین مدرک تحصیلی شما چیست؟",
            "opportunity_types": "به چه نوع فرصت‌هایی علاقه دارید — استخدام، دکترا، CIFRE، فریلنس؟",
            "certifications":    "آیا گواهینامه‌های حرفه‌ای دارید؟",
        },
        "all_complete": "پروفایل شما بسیار خوب به نظر می‌رسد! آیا چیز دیگری می‌خواهید اضافه یا به‌روزرسانی کنید؟",
    },
}

_FIELD_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "skills":            "skills",
        "target_roles":      "target roles",
        "experience_level":  "experience level",
        "salary_min":        "minimum salary",
        "salary_target":     "target salary",
        "remote_preference": "remote work preference",
        "countries":         "preferred countries",
        "cities":            "preferred cities",
        "contract_types":    "contract preferences",
        "languages":         "languages",
        "certifications":    "certifications",
        "industries":        "industries of interest",
        "opportunity_types": "opportunity types",
        "visa_work_auth":    "work authorization",
    },
    "fr": {
        "skills":            "compétences",
        "target_roles":      "postes cibles",
        "experience_level":  "niveau d'expérience",
        "salary_min":        "salaire minimum",
        "salary_target":     "salaire cible",
        "remote_preference": "préférence télétravail",
        "countries":         "pays préférés",
        "cities":            "villes préférées",
        "contract_types":    "types de contrat",
        "languages":         "langues",
        "certifications":    "certifications",
        "industries":        "secteurs d'intérêt",
        "opportunity_types": "types d'opportunités",
        "visa_work_auth":    "autorisation de travail",
    },
    "fa": {
        "skills":            "مهارت‌ها",
        "target_roles":      "سمت‌های هدف",
        "experience_level":  "سطح تجربه",
        "salary_min":        "حداقل حقوق",
        "salary_target":     "حقوق هدف",
        "remote_preference": "ترجیح دورکاری",
        "countries":         "کشورهای ترجیحی",
        "cities":            "شهرهای ترجیحی",
        "contract_types":    "نوع قرارداد",
        "languages":         "زبان‌ها",
        "certifications":    "گواهینامه‌ها",
        "industries":        "صنایع مورد علاقه",
        "opportunity_types": "نوع فرصت",
        "visa_work_auth":    "مجوز کار",
    },
}


# ── Completeness computation ──────────────────────────────────────────────────

@dataclass
class CompletenessResult:
    completeness: int
    missing_fields: list[str] = field(default_factory=list)
    field_scores: dict[str, int] = field(default_factory=dict)
    total_possible: int = 100


def _profile_has(profile: dict, key: str) -> bool:
    """Check whether a completeness dimension is satisfied."""
    raw = profile.get("raw_json") or {}
    if key == "location":
        return bool(profile.get("countries") or profile.get("cities"))
    if key == "salary":
        return bool(profile.get("salary_min") or profile.get("salary_target"))
    if key == "opportunity_types":
        return bool(raw.get("opportunity_types") or profile.get("opportunity_types"))
    if key == "education":
        val = profile.get("education")
        if isinstance(val, list):
            return len(val) > 0
        return bool(val)
    val = profile.get(key)
    if val is None:
        return False
    if isinstance(val, list):
        return len(val) > 0
    if isinstance(val, bool):
        return True
    return bool(val)


def compute_profile_completeness(profile: dict) -> CompletenessResult:
    """Compute 0-100 completeness score from a profile dict.

    Pure function — no I/O, no LLM.
    """
    total = 0
    missing: list[str] = []
    field_scores: dict[str, int] = {}

    for cf in COMPLETENESS_FIELDS:
        achieved = _profile_has(profile, cf.key)
        pts = cf.weight if achieved else 0
        total += pts
        field_scores[cf.key] = pts
        if not achieved:
            missing.append(cf.label)

    return CompletenessResult(
        completeness=min(total, 100),
        missing_fields=missing,
        field_scores=field_scores,
        total_possible=100,
    )


def profile_model_to_dict(profile: Profile) -> dict:
    """Convert a Profile SQLAlchemy model to a plain dict for completeness scoring."""
    return {
        "skills":           profile.skills or [],
        "target_roles":     profile.target_roles or [],
        "experience_level": profile.experience_level,
        "countries":        profile.countries or [],
        "cities":           profile.cities or [],
        "salary_min":       profile.salary_min,
        "salary_target":    profile.salary_target,
        "education":        profile.education or [],
        "languages":        profile.languages or [],
        "contract_types":   profile.contract_types or [],
        "certifications":   profile.certifications or [],
        "raw_json":         profile.raw_json or {},
    }


# ── Next question selection ───────────────────────────────────────────────────

def get_next_question(missing_labels: list[str], language: str) -> str:
    """Pick the highest-priority unanswered question in the requested language."""
    t = _TRANSLATIONS.get(language, _TRANSLATIONS["en"])
    next_q_map = t["next_q"]

    label_to_key = {cf.label: cf.key for cf in COMPLETENESS_FIELDS}
    missing_keys = [label_to_key.get(label) for label in missing_labels]
    missing_keys = [k for k in missing_keys if k is not None]

    for priority_key in COMPLETENESS_PRIORITY:
        if priority_key in missing_keys and priority_key in next_q_map:
            return next_q_map[priority_key]

    return t["all_complete"]


# ── Assistant message builder ─────────────────────────────────────────────────

def build_assistant_message(
    language: str,
    extracted: dict,
    missing_fields: list[str],
    completeness_pct: int,
) -> str:
    """Build the conversational response in the requested language.

    Pure function — fully deterministic, no LLM.
    """
    t = _TRANSLATIONS.get(language, _TRANSLATIONS["en"])
    labels = _FIELD_LABELS.get(language, _FIELD_LABELS["en"])
    parts: list[str] = []

    if extracted:
        field_names = [labels.get(k, k) for k in extracted]
        if field_names:
            parts.append(t["fields_captured"].format(fields=", ".join(field_names)))
        else:
            parts.append(t["no_update"])
    else:
        parts.append(t["no_update"])

    parts.append(t["completeness"].format(pct=completeness_pct))

    if missing_fields:
        parts.append(t["missing_hint"].format(missing=missing_fields[0]))

    return " ".join(parts)


# ── LLM extraction ────────────────────────────────────────────────────────────

def build_extraction_prompt(message: str, current_profile: dict, language: str) -> str:
    """Build the LLM prompt for structured profile extraction.

    Written in English for maximum model compatibility.
    The user message is passed verbatim — LLM handles multilingual input.
    """
    profile_context = ""
    if current_profile:
        skills = current_profile.get("skills", [])
        roles = current_profile.get("target_roles", [])
        exp = current_profile.get("experience_level")
        if any([skills, roles, exp]):
            profile_context = (
                f"\nCurrent profile (for context only — do NOT repeat existing values):\n"
                f"  Skills: {', '.join(skills[:10]) or 'none'}\n"
                f"  Target roles: {', '.join(roles[:5]) or 'none'}\n"
                f"  Experience level: {exp or 'unknown'}\n"
            )

    lang_hint = {
        "en": "The user is writing in English.",
        "fr": "The user is writing in French. Extract career information from French text.",
        "fa": "The user is writing in Persian/Farsi. Extract career information from Persian text.",
    }.get(language, "")

    return f"""You are a career profile extraction assistant. Extract structured career information from the user's message.
{lang_hint}
{profile_context}
User message: "{message}"

Extract ONLY fields that are explicitly mentioned. Do NOT infer or guess.
Return a JSON object with these fields (include only what is present):

{{
  "target_roles": ["list", "of", "job", "titles"],
  "skills": ["lowercase", "skill", "names"],
  "experience_level": "junior|mid|senior",
  "years_experience": 3,
  "salary_min": 40000,
  "salary_target": 55000,
  "remote_preference": true,
  "countries": ["Country Names"],
  "cities": ["City Names"],
  "contract_types": ["cdi", "cdd", "freelance", "stage", "alternance", "cifre"],
  "languages": ["Language Names"],
  "certifications": ["cert names"],
  "industries": ["industry sectors"],
  "opportunity_types": ["employment", "phd", "cifre", "freelance", "internship"],
  "visa_work_auth": "e.g. EU citizen, requires visa, work permit holder"
}}

Rules:
- experience_level: use years to determine — 0-2 years = junior, 3-5 = mid, 5+ = senior
- salary: annual EUR amount. If monthly is given, multiply by 12
- skills: lowercase (python, docker, react, etc.)
- Return empty JSON {{}} if no career information found
- Return ONLY valid JSON, no markdown, no explanation"""


def _parse_llm_json(raw: str) -> dict:
    """Parse JSON from LLM response, stripping markdown code fences if present."""
    if not raw or not raw.strip():
        return {}
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    try:
        result = json.loads(text)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, ValueError):
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                return result if isinstance(result, dict) else {}
            except (json.JSONDecodeError, ValueError):
                pass
        logger.warning("Could not parse LLM JSON response: %.100s", raw)
        return {}


def validate_extracted_updates(raw: dict) -> tuple[dict, list[str]]:
    """Validate raw LLM output through ExtractedProfileUpdate schema.

    Returns (validated_clean_dict, list_of_rejected_field_names).
    Invalid fields are silently dropped — never reach the profile.
    """
    try:
        parsed = ExtractedProfileUpdate.model_validate(raw)
        clean = parsed.to_clean_dict()
        rejected = [k for k in raw if k not in parsed.model_fields]
        return clean, rejected
    except Exception as exc:
        logger.warning("validate_extracted_updates failed: %s", exc)
        return {}, list(raw.keys())


async def extract_profile_updates(
    provider: BaseLLMProvider,
    message: str,
    current_profile: dict,
    language: str = "en",
) -> dict:
    """Use LLM to extract structured profile updates from a user message.

    Returns a validated dict of fields to update — empty dict if LLM fails.
    Never raises — caller always gets a dict.
    """
    prompt = build_extraction_prompt(message, current_profile, language)
    try:
        raw_response = await provider.generate(prompt, max_tokens=500)
    except Exception as exc:
        logger.error("LLM extraction failed: %s", exc)
        return {}

    raw_json = _parse_llm_json(raw_response)
    if not raw_json:
        return {}

    validated, rejected = validate_extracted_updates(raw_json)
    if rejected:
        logger.debug("Dropped unknown/invalid fields from LLM output: %s", rejected)
    return validated


# ── Profile update application ────────────────────────────────────────────────

_LIST_FIELDS = frozenset({
    "target_roles", "avoid_roles", "skills", "countries",
    "cities", "contract_types", "languages", "certifications",
})

_EXTRA_FIELDS = frozenset({"industries", "opportunity_types", "visa_work_auth"})

_PROFILE_STD_FIELDS = frozenset({
    "target_roles", "avoid_roles", "skills", "experience_level",
    "salary_min", "salary_target", "remote_preference",
    "countries", "cities", "contract_types", "languages", "certifications",
})


async def apply_profile_updates(
    db: AsyncSession,
    user_id: uuid.UUID,
    updates: dict,
) -> Profile:
    """Apply validated profile updates to the user's active profile.

    List fields are MERGED (union, deduplicated). Scalar fields are overwritten.
    Extra fields (industries, opportunity_types, visa_work_auth) go into raw_json.
    Creates a new profile if the user has none.
    """
    validated, _ = validate_extracted_updates(updates)

    std_updates = {k: v for k, v in validated.items() if k in _PROFILE_STD_FIELDS}
    extra_updates = {k: v for k, v in validated.items() if k in _EXTRA_FIELDS}

    profile = await profile_service.get_active_profile(db, user_id)

    if profile is None:
        profile = Profile(
            user_id=user_id,
            version=1,
            target_roles=std_updates.get("target_roles", []),
            avoid_roles=std_updates.get("avoid_roles", []),
            skills=std_updates.get("skills", []),
            experience_level=std_updates.get("experience_level"),
            salary_min=std_updates.get("salary_min"),
            salary_target=std_updates.get("salary_target"),
            remote_preference=std_updates.get("remote_preference", False),
            countries=std_updates.get("countries", []),
            cities=std_updates.get("cities", []),
            contract_types=std_updates.get("contract_types", []),
            languages=std_updates.get("languages", []),
            certifications=std_updates.get("certifications", []),
            raw_json=extra_updates if extra_updates else None,
            is_active=True,
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        return profile

    # Separate list fields from scalar fields
    list_updates = {k: v for k, v in std_updates.items() if k in _LIST_FIELDS}
    scalar_updates = {k: v for k, v in std_updates.items() if k not in _LIST_FIELDS}

    # Merge list fields (union, deduplicate, preserve order)
    for fname, new_vals in list_updates.items():
        if isinstance(new_vals, list):
            existing = list(getattr(profile, fname, None) or [])
            merged = list(dict.fromkeys(existing + new_vals))
            setattr(profile, fname, merged)

    # Overwrite scalar fields
    for fname, val in scalar_updates.items():
        if val is not None:
            setattr(profile, fname, val)

    # Merge extra fields into raw_json
    if extra_updates:
        raw_json = dict(profile.raw_json or {})
        for k, new_val in extra_updates.items():
            if isinstance(new_val, list) and isinstance(raw_json.get(k), list):
                raw_json[k] = list(dict.fromkeys(raw_json[k] + new_val))
            else:
                raw_json[k] = new_val
        profile.raw_json = raw_json

    await db.commit()
    await db.refresh(profile)
    return profile
