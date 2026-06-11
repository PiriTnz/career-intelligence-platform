"""
Profile-aware matching engine — live demonstration.

No database, no network. Runs 10 realistic French AI/ML jobs through
both the scoring engine and the matching engine against Tanaz's profile,
then prints a combined ranked table.

Run from backend/:
    PYTHONPATH=. python scripts/demo_matching.py
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.matching_engine import match
from app.services.scoring_service import score_job

# ── Tanaz's profile ───────────────────────────────────────────────────────────

PROFILE = {
    "skills": [
        "python", "machine learning", "deep learning", "pytorch", "tensorflow",
        "scikit-learn", "fastapi", "docker", "kubernetes", "llm", "rag",
        "langchain", "mlops", "airflow", "sql", "postgresql", "git",
    ],
    "target_roles": ["ML Engineer", "LLM Engineer", "MLOps Engineer", "AI Research Engineer"],
    "experience_level": "mid",
    "salary_min": 42_000,
    "salary_target": 58_000,
    "remote_preference": True,
    "countries": ["france"],
    "cities": ["lyon", "paris", "grenoble", "bordeaux"],
    "contract_types": ["cdi", "cdd"],
    "languages": ["French", "English"],
}


def _ago(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()


JOBS = [
    {
        "title": "ML Engineer — LLM & RAG",
        "company": "Mistral AI",
        "required_skills": ["python", "pytorch", "llm", "rag", "fastapi", "docker"],
        "experience_level": "mid",
        "location": "Paris, France",
        "remote": "full",
        "contract_type": "cdi",
        "salary_min": 55_000, "salary_max": 70_000,
        "company_quality_score": 95,
        "published_at": _ago(1),
        "language": "fr",
    },
    {
        "title": "MLOps Engineer",
        "company": "Renault Digital",
        "required_skills": ["python", "mlops", "kubernetes", "docker", "airflow"],
        "experience_level": "mid",
        "location": "Lyon, France",
        "remote": "hybrid",
        "contract_type": "cdi",
        "salary_min": 48_000, "salary_max": 58_000,
        "company_quality_score": 80,
        "published_at": _ago(3),
        "language": "fr",
    },
    {
        "title": "Data Scientist — Computer Vision",
        "company": "Ubisoft",
        "required_skills": ["python", "pytorch", "deep learning", "tensorflow", "opencv"],
        "experience_level": "mid",
        "location": "Lyon, France",
        "remote": "hybrid",
        "contract_type": "cdi",
        "salary_min": 52_000, "salary_max": 66_000,
        "company_quality_score": 85,
        "published_at": _ago(2),
        "language": "en",
    },
    {
        "title": "AI Research Engineer",
        "company": "CEA List",
        "required_skills": ["python", "pytorch", "deep learning", "llm", "rag"],
        "experience_level": "senior",
        "location": "Grenoble, France",
        "remote": "hybrid",
        "contract_type": "cdi",
        "salary_min": 46_000, "salary_max": 55_000,
        "company_quality_score": 88,
        "published_at": _ago(5),
        "language": "fr",
    },
    {
        "title": "LLM Engineer — Generative AI",
        "company": "Hugging Face",
        "required_skills": ["python", "pytorch", "llm", "rag", "langchain", "fastapi"],
        "experience_level": "mid",
        "location": "Remote",
        "remote": "full",
        "contract_type": "cdi",
        "salary_min": 58_000, "salary_max": 72_000,
        "company_quality_score": 96,
        "published_at": _ago(2),
        "language": "en",
    },
    {
        "title": "Backend Developer (Python)",
        "company": "Fintech Startup",
        "required_skills": ["python", "fastapi", "postgresql", "docker"],
        "experience_level": "mid",
        "location": "Lyon, France",
        "remote": "none",
        "contract_type": "cdi",
        "salary_min": 38_000, "salary_max": 44_000,
        "company_quality_score": 55,
        "published_at": _ago(8),
        "language": "fr",
    },
    {
        "title": "Senior ML Scientist",
        "company": "Google DeepMind",
        "required_skills": ["python", "pytorch", "tensorflow", "deep learning", "llm", "research"],
        "experience_level": "senior",
        "location": "London, UK",
        "remote": "hybrid",
        "contract_type": "cdi",
        "salary_min": 90_000, "salary_max": 130_000,
        "company_quality_score": 99,
        "published_at": _ago(0),
        "language": "en",
    },
    {
        "title": "Data Engineer",
        "company": "Decathlon Tech",
        "required_skills": ["python", "sql", "airflow", "spark", "docker"],
        "experience_level": "mid",
        "location": "Lille, France",
        "remote": "hybrid",
        "contract_type": "cdi",
        "salary_min": 40_000, "salary_max": 50_000,
        "company_quality_score": 72,
        "published_at": _ago(12),
        "language": "fr",
    },
    {
        "title": "Stage NLP — 6 mois",
        "company": "Orange Labs",
        "required_skills": ["python", "pytorch", "nlp"],
        "experience_level": "junior",
        "location": "Paris, France",
        "remote": "hybrid",
        "contract_type": "stage",
        "salary_min": None, "salary_max": None,
        "company_quality_score": 70,
        "published_at": _ago(4),
        "language": "fr",
    },
    {
        "title": "Java Backend Engineer",
        "company": "Legacy Corp",
        "required_skills": ["java", "spring", "oracle", "hibernate"],
        "experience_level": "mid",
        "location": "Strasbourg, France",
        "remote": "none",
        "contract_type": "cdi",
        "salary_min": 35_000, "salary_max": 42_000,
        "company_quality_score": 40,
        "published_at": _ago(20),
        "language": "fr",
    },
]


def run() -> None:
    results = []
    for job in JOBS:
        breakdown, confidence = score_job(job, PROFILE)
        mr = match(job, PROFILE)
        results.append((job, breakdown, confidence, mr))

    results.sort(key=lambda x: x[1].total, reverse=True)

    W = 122
    print("\n" + "═" * W)
    print("  PROFILE-AWARE MATCHING + SCORING — Tanaz Piriaei (mid ML/AI, Lyon, France)")
    print("═" * W)
    print(
        f"  {'#':<3} {'Job title':<35} {'Company':<18} "
        f"{'Score':>5}  {'Skl':>3} {'Exp':>3} {'Loc':>3} {'Sal':>3} {'Con':>3}  "
        f"{'Skill%':>6}  {'Role%':>5}  {'Fit%':>4}  "
        f"{'Matched / Missing skills'}"
    )
    print("─" * W)

    for rank, (job, bd, conf, mr) in enumerate(results, 1):
        flag = " ⚑" if bd.needs_review else ""
        matched_str = ", ".join(mr.matched_skills[:4]) or "–"
        missing_str = (", ".join(mr.missing_skills[:3]) + ("…" if len(mr.missing_skills) > 3 else "")) or "–"
        skills_col = f"{matched_str}  /  ✗{missing_str}"

        print(
            f"  {rank:<3} {job['title']:<35} {job['company']:<18} "
            f"{bd.total:>5}  {bd.skill_match:>3} {bd.experience_match:>3} "
            f"{bd.location_score:>3} {bd.salary_score:>3} {bd.contract_score:>3}  "
            f"{mr.skill_match_percentage:>5.0f}%  {mr.role_match_percentage:>4.0f}%  "
            f"{mr.overall_fit:>3.0f}%  "
            f"{skills_col}{flag}"
        )

    print("─" * W)
    print("  Score dims (max): Skill/30  Exp/20  Loc/15  Salary/15  Contract/10  Company/5  Freshness/5")
    print("  Fit dims (weight): Skill×40%  Role×20%  Location×15%  Salary×10%  Contract×10%  Language×5%")

    print("\n  TOP 3 DETAILED MATCH BREAKDOWN")
    print("─" * 70)
    for rank, (job, bd, conf, mr) in enumerate(results[:3], 1):
        gap_str = {0: "exact match", 1: "+1 overqualified", -1: "−1 underqualified",
                   2: "+2 overqualified", -2: "−2 underqualified"}.get(mr.experience_gap, str(mr.experience_gap))
        print(f"\n  #{rank}  {job['title']} @ {job['company']}")
        print(f"        Total score:    {bd.total}/100  |  Fit: {mr.overall_fit:.0f}%  |  Confidence: {conf}%")
        print(f"        Skill match:    {mr.skill_match_percentage:.0f}%  (matched: {', '.join(mr.matched_skills) or '–'})")
        if mr.missing_skills:
            print(f"        Missing skills: {', '.join(mr.missing_skills)}")
        print(f"        Role match:     {mr.role_match_percentage:.0f}%  (best: {mr.best_matching_role or '–'})")
        print(f"        Location:       {'✓' if mr.location_match else '✗'}  Remote: {'✓' if mr.remote_match else '✗'}  Contract: {'✓' if mr.contract_match else '✗'}  Language: {'✓' if mr.language_match else '✗'}")
        print(f"        Salary OK:      {'✓' if mr.salary_ok else '✗'}  Experience gap: {gap_str}")
    print()


if __name__ == "__main__":
    run()
