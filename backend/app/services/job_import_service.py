"""
Fetch and parse a job posting from a URL.

Parse priority:
  1. JSON-LD <script type="application/ld+json"> with @type JobPosting
  2. OpenGraph / meta tags
  3. Heuristic extraction from visible text
"""
import json
import logging
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.services import normalizer

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; JobHunterBot/1.0; +https://github.com/job-hunter)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
_TIMEOUT = 15.0


async def fetch_and_parse(url: str) -> dict:
    """
    Fetch *url* and return a normalised job dict compatible with
    ``normalizer.normalize(raw, "import")``.

    Raises ``ValueError`` on fetch failure or unrecognisable page.
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT) as client:
        try:
            resp = await client.get(url, headers=_HEADERS)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ValueError(f"HTTP {exc.response.status_code} fetching URL") from exc
        except httpx.RequestError as exc:
            raise ValueError(f"Could not reach URL: {exc}") from exc

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # Try strategies in order
    data = _try_json_ld(soup) or _try_meta_tags(soup, url) or _try_heuristic(soup, url)

    if not data.get("title"):
        raise ValueError("Could not extract a job title from the page.")

    # Ensure URL is always set to the canonical URL
    data.setdefault("url", url)
    data["url"] = url
    data.setdefault("source", "import")

    # Run through the generic normaliser path to fill missing fields
    return normalizer.normalize(data, "import")


# ── Strategy 1: JSON-LD ───────────────────────────────────────────────────────

def _try_json_ld(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            obj = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        # Handle @graph arrays
        items = obj if isinstance(obj, list) else [obj]
        for item in items:
            if isinstance(item, dict) and item.get("@type") in ("JobPosting", "JobListing"):
                return _extract_from_json_ld(item)

    return None


def _extract_from_json_ld(item: dict) -> dict:
    salary = item.get("baseSalary", {})
    salary_value = salary.get("value", {}) if isinstance(salary, dict) else {}
    sal_min = _int_or_none(salary_value.get("minValue") if isinstance(salary_value, dict) else salary_value)
    sal_max = _int_or_none(salary_value.get("maxValue") if isinstance(salary_value, dict) else None)

    location_obj = item.get("jobLocation", {})
    address = location_obj.get("address", {}) if isinstance(location_obj, dict) else {}
    location_str = None
    if isinstance(address, dict):
        parts = [address.get("addressLocality"), address.get("addressRegion"), address.get("addressCountry")]
        location_str = ", ".join(p for p in parts if p) or None
    elif isinstance(address, str):
        location_str = address

    remote_str = "none"
    job_location_type = item.get("jobLocationType", "")
    if "remote" in str(job_location_type).lower():
        remote_str = "full"

    employer = item.get("hiringOrganization", {})
    company = employer.get("name", "") if isinstance(employer, dict) else str(employer)

    skills_raw = item.get("skills", "") or ""
    skills = [s.strip() for s in re.split(r"[,;]+", skills_raw) if s.strip()] if skills_raw else []

    return {
        "title": item.get("title") or item.get("name") or "",
        "company_name": company,
        "description": _strip_html(item.get("description", "")),
        "location": location_str,
        "remote": remote_str,
        "salary_min": sal_min,
        "salary_max": sal_max,
        "salary_currency": "EUR",
        "contract_type": _map_employment_type(item.get("employmentType", "")),
        "required_skills": skills,
        "published_at": item.get("datePosted"),
        "source": "import",
    }


# ── Strategy 2: OpenGraph / meta tags ────────────────────────────────────────

def _try_meta_tags(soup: BeautifulSoup, url: str) -> dict | None:
    def _meta(name: str) -> str:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        return (tag.get("content") or "") if tag else ""

    title = (
        _meta("og:title")
        or _meta("twitter:title")
        or (soup.title.string if soup.title else "")
    ).strip()

    if not title:
        return None

    description = (
        _meta("og:description")
        or _meta("description")
        or _meta("twitter:description")
    ).strip()

    company = _meta("og:site_name").strip() or _domain_as_company(url)

    return {
        "title": title,
        "company_name": company,
        "description": description or None,
        "location": None,
        "remote": "none",
        "salary_min": None,
        "salary_max": None,
        "salary_currency": "EUR",
        "contract_type": None,
        "required_skills": [],
        "source": "import",
    }


# ── Strategy 3: heuristic ─────────────────────────────────────────────────────

def _try_heuristic(soup: BeautifulSoup, url: str) -> dict | None:
    # Best title guess: h1 or first heading
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    if not title:
        return None

    # Grab body text for skills extraction
    body_text = soup.get_text(separator=" ", strip=True)[:8000]

    return {
        "title": title,
        "company_name": _domain_as_company(url),
        "description": body_text[:5000] or None,
        "location": None,
        "remote": "none",
        "salary_min": None,
        "salary_max": None,
        "salary_currency": "EUR",
        "contract_type": None,
        "required_skills": [],
        "source": "import",
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    return BeautifulSoup(text, "html.parser").get_text(separator=" ", strip=True)


def _int_or_none(value) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _domain_as_company(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
        parts = host.split(".")
        # drop www. prefix and TLD
        meaningful = [p for p in parts if p not in ("www", "com", "fr", "io", "net", "org", "co")]
        return meaningful[0].capitalize() if meaningful else host
    except Exception:
        return "Unknown"


_EMPLOYMENT_TYPE_MAP = {
    "full_time": "cdi",
    "fulltime": "cdi",
    "full-time": "cdi",
    "part_time": "temps-partiel",
    "parttime": "temps-partiel",
    "part-time": "temps-partiel",
    "temporary": "cdd",
    "contract": "freelance",
    "intern": "stage",
    "internship": "stage",
    "volunteer": "benevole",
}


def _map_employment_type(raw: str) -> str | None:
    if not raw:
        return None
    key = str(raw).lower().replace(" ", "_")
    # JSON-LD can be a list
    if isinstance(raw, list):
        key = str(raw[0]).lower().replace(" ", "_")
    return _EMPLOYMENT_TYPE_MAP.get(key)
