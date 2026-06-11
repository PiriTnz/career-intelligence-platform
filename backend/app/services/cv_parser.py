"""
Deterministic CV text parser — no LLM, no network calls.

Extracts structured data from raw CV text using regex and keyword matching.
All public functions are pure — testable without a DB connection.

Entry point: parse_cv(text) -> CVExtractionResult
PDF bytes -> text: extract_text_from_pdf(pdf_bytes) -> str
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class CVExtractionResult:
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location_raw: str | None = None
    experience_level: str | None = None

    skills: list[str] = field(default_factory=list)
    inferred_skills: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    education: list[dict] = field(default_factory=list)
    experience: list[dict] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    suggested_roles: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)

    extraction_confidence: int = 0  # 0-100


# ── Skill / knowledge vocabularies ───────────────────────────────────────────

SKILL_VOCAB: list[str] = [
    # Languages
    "python", "javascript", "typescript", "java", "c#", "c++", "c", "go",
    "rust", "scala", "r", "julia", "matlab", "bash", "shell", "sql",
    # Web
    "react", "vue", "angular", "next.js", "svelte", "html", "css", "fastapi",
    "django", "flask", "node.js", "express", "spring", "rails",
    # ML / AI
    "machine learning", "deep learning", "pytorch", "tensorflow", "keras",
    "scikit-learn", "xgboost", "lightgbm", "catboost", "pandas", "numpy",
    "scipy", "statsmodels", "nlp", "computer vision", "reinforcement learning",
    "transformers", "bert", "gpt", "llm", "rag", "langchain", "openai",
    "huggingface", "ollama", "vector database", "pinecone", "faiss", "chroma",
    # MLOps / DevOps
    "mlops", "airflow", "prefect", "dagster", "kubeflow", "mlflow",
    "dvc", "bentoml", "docker", "kubernetes", "helm", "terraform", "ansible",
    "ci/cd", "github actions", "gitlab ci", "jenkins", "argocd",
    # Cloud
    "aws", "gcp", "azure", "google cloud", "s3", "ec2", "lambda",
    "bigquery", "databricks", "snowflake", "dbt",
    # Data
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "kafka",
    "spark", "hadoop", "flink", "hive", "cassandra", "neo4j",
    # Other
    "git", "linux", "rest api", "graphql", "grpc", "microservices",
    "agile", "scrum", "jira",
]

# Longer phrases must come first so they match before their sub-strings
SKILL_VOCAB.sort(key=len, reverse=True)

HUMAN_LANGUAGES = {
    "french": "French", "français": "French", "anglais": "English",
    "english": "English", "spanish": "Spanish", "espagnol": "Spanish",
    "german": "German", "allemand": "German", "italian": "Italian",
    "italian": "Italian", "portuguese": "Portuguese",
    "portuguese": "Portuguese", "chinese": "Chinese",
    "mandarin": "Mandarin", "arabic": "Arabic", "arabe": "Arabic",
    "dutch": "Dutch", "japonais": "Japanese", "japanese": "Japanese",
}

FRENCH_CITIES = {
    "paris", "lyon", "marseille", "toulouse", "nice", "nantes", "strasbourg",
    "montpellier", "bordeaux", "lille", "rennes", "reims", "toulon",
    "saint-étienne", "grenoble", "dijon", "angers", "villeurbanne",
    "nîmes", "aix-en-provence", "clermont-ferrand", "brest", "tours",
    "amiens", "limoges", "metz", "besançon", "perpignan", "orléans",
    "mulhouse", "caen", "nancy", "rouen",
}

DEGREE_KEYWORDS = {
    "phd", "doctorat", "doctorate", "master", "m2", "m1", "msc", "m.sc",
    "meng", "m.eng", "mba", "licence", "bachelor", "bsc", "b.sc",
    "beng", "b.eng", "ingénieur", "diplôme d'ingénieur", "dut", "bts",
    "grande école", "prépa", "classes préparatoires",
}

CERT_PATTERNS = [
    r"aws\s+(?:certified|solutions\s+architect|developer|sysops|devops|cloud\s+practitioner)",
    r"google\s+cloud\s+(?:professional|associate)",
    r"microsoft\s+(?:certified|azure)",
    r"gcp\s+(?:professional|associate)",
    r"cka|ckad|cks",           # Kubernetes certs
    r"pmp|prince2|scrum\s+master|safe\s+agilist",
    r"tensorflow\s+developer",
    r"databricks\s+(?:certified|associate)",
    r"hashicorp\s+(?:terraform|vault)",
    r"cisco\s+(?:ccna|ccnp|ccie)",
]

# ── Role inference ────────────────────────────────────────────────────────────

_ROLE_REQUIREMENTS: list[tuple[str, set[str], int]] = [
    # (role_name, skill_pool, min_matches_needed)
    ("ML Engineer", {"python", "machine learning", "pytorch", "tensorflow",
                     "scikit-learn", "deep learning", "llm", "rag", "mlops"}, 3),
    ("LLM / RAG Engineer", {"llm", "rag", "langchain", "openai", "huggingface",
                             "transformers", "bert", "gpt", "vector database"}, 2),
    ("MLOps Engineer", {"mlops", "docker", "kubernetes", "airflow", "prefect",
                        "mlflow", "dvc", "ci/cd", "github actions"}, 2),
    ("Data Scientist", {"python", "scikit-learn", "pandas", "numpy",
                        "machine learning", "statistics", "r", "deep learning"}, 3),
    ("Data Engineer", {"python", "airflow", "spark", "kafka", "dbt",
                       "postgresql", "bigquery", "databricks", "snowflake"}, 2),
    ("AI Research Engineer", {"python", "pytorch", "deep learning", "transformers",
                               "llm", "rag", "nlp", "computer vision"}, 3),
    ("Backend Engineer", {"python", "fastapi", "django", "flask",
                          "postgresql", "redis", "docker", "rest api"}, 3),
    ("DevOps / Platform Engineer", {"docker", "kubernetes", "terraform", "ansible",
                                     "ci/cd", "linux", "aws", "gcp", "azure"}, 3),
    ("Full-Stack Developer", {"python", "javascript", "typescript", "react",
                               "fastapi", "postgresql", "docker"}, 3),
]

# Skills implied by job titles found in experience sections
_TITLE_SKILL_INFERENCE: list[tuple[re.Pattern, list[str]]] = [
    (re.compile(r"machine\s+learning|ml\s+engineer|ai\s+engineer", re.I),
     ["machine learning", "python"]),
    (re.compile(r"mlops|platform\s+engineer|devops", re.I),
     ["docker", "kubernetes", "ci/cd"]),
    (re.compile(r"data\s+scientist", re.I),
     ["python", "machine learning", "pandas"]),
    (re.compile(r"data\s+engineer", re.I),
     ["python", "sql", "airflow"]),
    (re.compile(r"backend|back.end|api\s+developer", re.I),
     ["rest api", "postgresql"]),
    (re.compile(r"devops|sre|infrastructure", re.I),
     ["linux", "docker", "ci/cd"]),
    (re.compile(r"nlp|natural\s+language", re.I),
     ["nlp", "python", "transformers"]),
]


# ── PDF → text ────────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract all text from a PDF. Returns '' if pypdf fails or is absent."""
    try:
        import pypdf  # type: ignore
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


# ── Main entry point ──────────────────────────────────────────────────────────

def parse_cv(text: str) -> CVExtractionResult:
    """
    Parse raw CV text into structured data.
    Pure function — no I/O.
    """
    result = CVExtractionResult()
    if not text.strip():
        result.missing_fields = _ALL_REQUIRED_FIELDS[:]
        return result

    text_clean = _normalise_whitespace(text)

    result.email = _extract_email(text_clean)
    result.phone = _extract_phone(text_clean)
    result.full_name = _extract_name(text_clean)
    result.location_raw = _extract_location(text_clean)
    result.skills = _extract_skills(text_clean)
    result.languages = _extract_languages(text_clean)
    result.education = _extract_education(text_clean)
    result.experience = _extract_experience(text_clean)
    result.certifications = _extract_certifications(text_clean)

    result.inferred_skills = _infer_skills_from_experience(result.experience)
    result.experience_level = _infer_experience_level(result.experience)

    all_skills = list(dict.fromkeys(result.skills + result.inferred_skills))
    result.suggested_roles = _suggest_target_roles(set(all_skills))

    result.missing_fields = _compute_missing_fields(result)
    result.extraction_confidence = _compute_confidence(result)

    return result


# ── Field extractors ──────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

_PHONE_RES = [
    # French mobile: 06 12 34 56 78 / 0612345678 / +33612345678
    re.compile(r"(?:\+33|0033|0)[\s.\-]?[67](?:[\s.\-]?\d{2}){4}"),
    # French landline: 01-09
    re.compile(r"(?:\+33|0033|0)[\s.\-]?[1-9](?:[\s.\-]?\d{2}){4}"),
    # International generic: +XX XXX…
    re.compile(r"\+\d{1,3}[\s.\-]?\d{3,5}[\s.\-]?\d{3,5}[\s.\-]?\d{2,4}"),
]

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

# Match "YYYY – YYYY" or "YYYY – présent/present/current/now"
# group 1: start year, group 2: end year or "present" keyword (may be None)
_DATE_RANGE_RE = re.compile(
    r"(20\d{2}|19\d{2})"
    r"[\s\-–—/]+"
    r"(20\d{2}|19\d{2}|présent|present|aujourd'hui|current|now)?",
    re.I,
)

_SECTION_RE = re.compile(
    r"^[ \t]*("
    r"compétences?(?: techniques?| clés?)?|technical skills?|skills?|stack|technologies"
    r"|expériences?(?: professionnelles?)?|professional experience|work experience|experience|parcours professionnel"
    r"|formation|éducation|education|studies|diplômes?"
    r"|certifications?|formations? complémentaires?|prix|awards"
    r"|langues?|languages?"
    r")[ \t]*:?[ \t]*$",
    re.I | re.M,
)


def _normalise_whitespace(text: str) -> str:
    # Collapse multiple blank lines; strip trailing spaces
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_email(text: str) -> str | None:
    m = _EMAIL_RE.search(text)
    return m.group(0).lower() if m else None


def _extract_phone(text: str) -> str | None:
    for pat in _PHONE_RES:
        m = pat.search(text)
        if m:
            raw = m.group(0).strip()
            # Normalize: remove decorative separators except leading +
            digits = re.sub(r"[\s.\-]", "", raw)
            return digits
    return None


def _extract_name(text: str) -> str | None:
    """
    The name is usually in the first 5 non-empty lines.
    Heuristic: pick the shortest line that looks like a person's name
    (2-4 words, no digits, not an email, not a section header).
    """
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()][:8]
    name_re = re.compile(r"^[A-ZÀ-Ÿa-zà-ÿ\-']{2,}(?:\s+[A-ZÀ-Ÿa-zà-ÿ\-']{2,}){1,3}$")
    for line in lines:
        if _EMAIL_RE.search(line):
            continue
        if any(pat.search(line) for pat in _PHONE_RES):
            continue
        if re.search(r"\d", line):
            continue
        if len(line) > 60:
            continue
        if name_re.match(line):
            # Avoid section headers (all upper-case words look different from names)
            words = line.split()
            # A name usually has at least one mixed-case or title-case word
            if any(w[0].isupper() for w in words):
                return line
    return None


def _extract_location(text: str) -> str | None:
    # Search header lines in document order (first 10 non-empty lines).
    # A city in line 4 wins over a city in line 14, regardless of name length.
    header_lines = [ln for ln in text.split("\n") if ln.strip()][:10]
    for line in header_lines:
        line_lower = line.lower()
        for city in sorted(FRENCH_CITIES, key=len, reverse=True):
            if re.search(r"\b" + re.escape(city) + r"\b", line_lower):
                m = re.search(re.escape(city), line_lower)
                return line[m.start(): m.end()].title() if m else city.title()

    # Full-text fallback — iterate cities by length so longer names win
    text_lower = text.lower()
    for city in sorted(FRENCH_CITIES, key=len, reverse=True):
        if re.search(r"\b" + re.escape(city) + r"\b", text_lower):
            m = re.search(re.escape(city), text_lower)
            return text[m.start(): m.end()].title() if m else city.title()

    # Postal-code fallback
    m = re.search(r"\b([A-ZÀ-Ÿa-zà-ÿ\- ]+),?\s*((?:0[1-9]|[1-8]\d|9[0-5])\d{3})\b", text)
    if m:
        return f"{m.group(1).strip()}, {m.group(2)}"
    return None


def _extract_skills(text: str) -> list[str]:
    """
    Two-pass extraction:
    1. If a Skills section exists, parse it word-by-word (dense listing).
    2. Scan the whole text for known skill keywords.
    """
    found: dict[str, bool] = {}
    text_lower = text.lower()

    # Pass 1 — known vocab anywhere in text
    for skill in SKILL_VOCAB:
        pat = re.compile(r"(?<![a-z])" + re.escape(skill) + r"(?![a-z])", re.I)
        if pat.search(text_lower):
            found[skill] = True

    return sorted(found.keys())


def _extract_languages(text: str) -> list[str]:
    found: set[str] = set()
    text_lower = text.lower()
    for keyword, canonical in HUMAN_LANGUAGES.items():
        # Accept: "French (native)", "anglais : courant", etc.
        if re.search(r"\b" + re.escape(keyword) + r"\b", text_lower):
            found.add(canonical)
    return sorted(found)


def _extract_education(text: str) -> list[dict]:
    """
    Return list of {degree, institution, year_start, year_end} dicts.
    Looks for degree keywords within ±3 lines of a year range.
    """
    entries: list[dict] = []
    lines = text.split("\n")

    for i, line in enumerate(lines):
        line_lower = line.lower()
        matched_degree = next(
            (kw for kw in DEGREE_KEYWORDS if re.search(r"\b" + re.escape(kw) + r"\b", line_lower)),
            None,
        )
        if matched_degree is None:
            continue

        # Collect context: ±2 lines
        context_lines = lines[max(0, i - 1): min(len(lines), i + 3)]
        context = " ".join(context_lines)

        years = _YEAR_RE.findall(context)
        entry: dict = {
            "degree": line.strip(),
            "institution": None,
            "year_start": int(years[0]) if years else None,
            "year_end": int(years[1]) if len(years) >= 2 else None,
        }

        # Try to pull institution from adjacent lines
        for adj in context_lines:
            adj_stripped = adj.strip()
            if adj_stripped and adj_stripped != line.strip() and len(adj_stripped) > 3:
                if not _YEAR_RE.search(adj_stripped) and not re.search(r"\d{2,}", adj_stripped):
                    entry["institution"] = adj_stripped
                    break

        entries.append(entry)

    # Deduplicate by degree text
    seen: set[str] = set()
    deduped = []
    for e in entries:
        key = e["degree"].lower()[:40]
        if key not in seen:
            seen.add(key)
            deduped.append(e)
    return deduped


def _extract_experience(text: str) -> list[dict]:
    """
    Return list of {title, company, year_start, year_end} dicts.
    Identifies job entries by date-range patterns.
    """
    entries: list[dict] = []
    lines = text.split("\n")

    for i, line in enumerate(lines):
        range_match = _DATE_RANGE_RE.search(line)
        if range_match is None:
            continue

        yr_start = range_match.group(1)
        yr_end_raw = range_match.group(2)

        # year_end = None when "présent/current/now"
        if yr_end_raw and re.match(r"(présent|present|aujourd|current|now)", yr_end_raw, re.I):
            yr_end = None
        else:
            yr_end = int(yr_end_raw) if yr_end_raw and yr_end_raw.isdigit() else None

        # Job title and company usually appear in adjacent lines
        title: str | None = None
        company: str | None = None

        for offset in [-2, -1, 1, 2]:
            adj_idx = i + offset
            if 0 <= adj_idx < len(lines):
                adj = lines[adj_idx].strip()
                if not adj or len(adj) < 3:
                    continue
                if _DATE_RANGE_RE.search(adj):
                    continue
                if title is None:
                    title = adj
                elif company is None and adj != title:
                    company = adj
                if title and company:
                    break

        if title:
            entries.append({
                "title": title,
                "company": company,
                "year_start": int(yr_start) if yr_start and yr_start.isdigit() else None,
                "year_end": yr_end,
            })

    # Deduplicate
    seen: set[str] = set()
    deduped = []
    for e in entries:
        key = (e.get("title", ""), e.get("year_start"))
        k = str(key)
        if k not in seen:
            seen.add(k)
            deduped.append(e)
    return deduped[:15]  # cap to prevent noise


def _extract_certifications(text: str) -> list[str]:
    found: list[str] = []
    text_lower = text.lower()
    for pattern in CERT_PATTERNS:
        for m in re.finditer(pattern, text_lower, re.I):
            cert = m.group(0).strip()
            if cert not in found:
                found.append(cert)
    return found


# ── Inference & enrichment ────────────────────────────────────────────────────

def _infer_skills_from_experience(experience: list[dict]) -> list[str]:
    inferred: set[str] = set()
    for entry in experience:
        title = (entry.get("title") or "").lower()
        for pattern, skills in _TITLE_SKILL_INFERENCE:
            if pattern.search(title):
                inferred.update(skills)
    return sorted(inferred)


def _infer_experience_level(experience: list[dict]) -> str | None:
    if not experience:
        return None
    # Total years = sum of each role's duration
    import datetime
    current_year = datetime.date.today().year
    total_years = 0
    for entry in experience:
        start = entry.get("year_start") or 0
        end = entry.get("year_end") or current_year
        if start and start >= 1990:
            total_years += max(0, end - start)
    if total_years == 0:
        return None
    if total_years < 2:
        return "junior"
    if total_years < 5:
        return "mid"
    return "senior"


def _suggest_target_roles(skills: set[str]) -> list[str]:
    suggestions: list[tuple[str, int]] = []
    for role, pool, threshold in _ROLE_REQUIREMENTS:
        matches = len(skills & pool)
        if matches >= threshold:
            suggestions.append((role, matches))
    # Sort by match count descending, return top 5
    suggestions.sort(key=lambda x: x[1], reverse=True)
    return [role for role, _ in suggestions[:5]]


_ALL_REQUIRED_FIELDS = [
    "full_name", "email", "phone", "location",
    "skills", "experience", "education",
]


def _compute_missing_fields(result: CVExtractionResult) -> list[str]:
    missing = []
    if not result.full_name:
        missing.append("full_name")
    if not result.email:
        missing.append("email")
    if not result.phone:
        missing.append("phone")
    if not result.location_raw:
        missing.append("location")
    if not result.skills:
        missing.append("skills")
    if not result.experience:
        missing.append("experience")
    if not result.education:
        missing.append("education")
    return missing


def _compute_confidence(result: CVExtractionResult) -> int:
    """
    Weighted confidence score 0-100 based on how many fields were extracted.
    """
    weights = {
        "full_name": 15,
        "email": 15,
        "skills": 25,
        "experience": 20,
        "education": 15,
        "phone": 5,
        "location_raw": 5,
    }
    score = 0
    for field, weight in weights.items():
        value = getattr(result, field)
        if value:
            score += weight
    return min(score, 100)
