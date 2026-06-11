"""
Deterministic scoring engine — live demonstration.

No database, no network. Scores a set of realistic French AI/ML job listings
against Tanaz Piriaei's profile and prints a ranked table.

Run from backend/:
    PYTHONPATH=. python scripts/demo_scoring.py
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.scoring_service import ScoreBreakdown, score_job

# ── Tanaz's profile ───────────────────────────────────────────────────────────

PROFILE = {
    "skills": [
        "python", "machine learning", "deep learning", "pytorch", "tensorflow",
        "scikit-learn", "fastapi", "docker", "kubernetes", "llm", "rag",
        "langchain", "mlops", "airflow", "sql", "postgresql", "git",
    ],
    "experience_level": "mid",
    "salary_min": 42_000,
    "salary_target": 58_000,
    "remote_preference": True,
    "countries": ["france"],
    "cities": ["lyon", "paris", "grenoble", "bordeaux"],
    "contract_types": ["cdi", "cdd"],
}


# ── Sample jobs ───────────────────────────────────────────────────────────────

def _days_ago(n: int) -> str:
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
        "salary_min": 55_000,
        "salary_max": 70_000,
        "company_quality_score": 95,
        "published_at": _days_ago(1),
    },
    {
        "title": "MLOps Engineer",
        "company": "Renault Digital",
        "required_skills": ["python", "mlops", "kubernetes", "docker", "airflow"],
        "experience_level": "mid",
        "location": "Lyon, France",
        "remote": "hybrid",
        "contract_type": "cdi",
        "salary_min": 48_000,
        "salary_max": 58_000,
        "company_quality_score": 80,
        "published_at": _days_ago(3),
    },
    {
        "title": "Data Scientist — Computer Vision",
        "company": "Ubisoft Montréal",
        "required_skills": ["python", "pytorch", "deep learning", "tensorflow", "opencv"],
        "experience_level": "mid",
        "location": "Montréal, Canada",
        "remote": "hybrid",
        "contract_type": "cdi",
        "salary_min": 52_000,
        "salary_max": 66_000,
        "company_quality_score": 85,
        "published_at": _days_ago(2),
    },
    {
        "title": "AI Research Engineer",
        "company": "CEA List",
        "required_skills": ["python", "pytorch", "deep learning", "llm", "rag"],
        "experience_level": "senior",
        "location": "Grenoble, France",
        "remote": "hybrid",
        "contract_type": "cdi",
        "salary_min": 46_000,
        "salary_max": 55_000,
        "company_quality_score": 88,
        "published_at": _days_ago(5),
    },
    {
        "title": "Backend Developer (Python)",
        "company": "Fintech Startup",
        "required_skills": ["python", "fastapi", "postgresql", "docker"],
        "experience_level": "mid",
        "location": "Lyon, France",
        "remote": "none",
        "contract_type": "cdi",
        "salary_min": 38_000,
        "salary_max": 44_000,
        "company_quality_score": 55,
        "published_at": _days_ago(8),
    },
    {
        "title": "Senior ML Scientist",
        "company": "Google DeepMind",
        "required_skills": ["python", "pytorch", "tensorflow", "deep learning", "llm", "research"],
        "experience_level": "senior",
        "location": "London, UK",
        "remote": "hybrid",
        "contract_type": "cdi",
        "salary_min": 90_000,
        "salary_max": 130_000,
        "company_quality_score": 99,
        "published_at": _days_ago(0),
    },
    {
        "title": "Data Engineer",
        "company": "Decathlon Tech",
        "required_skills": ["python", "sql", "airflow", "spark", "docker"],
        "experience_level": "mid",
        "location": "Lille, France",
        "remote": "hybrid",
        "contract_type": "cdi",
        "salary_min": 40_000,
        "salary_max": 50_000,
        "company_quality_score": 72,
        "published_at": _days_ago(12),
    },
    {
        "title": "AI/ML Engineer — Full Remote",
        "company": "Hugging Face",
        "required_skills": ["python", "pytorch", "llm", "transformers", "fastapi"],
        "experience_level": "mid",
        "location": "Remote",
        "remote": "full",
        "contract_type": "cdi",
        "salary_min": 58_000,
        "salary_max": 72_000,
        "company_quality_score": 96,
        "published_at": _days_ago(2),
    },
    {
        "title": "Stage / Internship — NLP",
        "company": "Orange Labs",
        "required_skills": ["python", "pytorch", "nlp"],
        "experience_level": "junior",
        "location": "Paris, France",
        "remote": "hybrid",
        "contract_type": "stage",
        "salary_min": None,
        "salary_max": None,
        "company_quality_score": 70,
        "published_at": _days_ago(4),
    },
    {
        "title": "Freelance ML Consultant",
        "company": "Independent",
        "required_skills": ["python", "machine learning", "scikit-learn"],
        "experience_level": "senior",
        "location": "France",
        "remote": "full",
        "contract_type": "freelance",
        "salary_min": 70_000,
        "salary_max": 100_000,
        "company_quality_score": 40,
        "published_at": _days_ago(20),
    },
]


# ── Runner ────────────────────────────────────────────────────────────────────

def run() -> None:
    results = []
    for job in JOBS:
        breakdown, confidence = score_job(job, PROFILE)
        results.append((job, breakdown, confidence))

    results.sort(key=lambda x: x[1].total, reverse=True)

    print("\n" + "═" * 100)
    print("  DETERMINISTIC SCORING RESULTS — Tanaz Piriaei profile")
    print("═" * 100)
    print(
        f"  {'#':<3} {'Job title':<38} {'Company':<20} "
        f"{'Total':>5}  {'Skill':>5}  {'Exp':>4}  {'Loc':>4}  "
        f"{'Sal':>4}  {'Con':>4}  {'Co':>3}  {'Fr':>3}  "
        f"{'Conf':>5}  {'Flag'}"
    )
    print("─" * 100)

    for rank, (job, bd, conf) in enumerate(results, 1):
        flag = "⚑ review" if bd.needs_review else ""
        print(
            f"  {rank:<3} {job['title']:<38} {job['company']:<20} "
            f"{bd.total:>5}  {bd.skill_match:>5}  {bd.experience_match:>4}  "
            f"{bd.location_score:>4}  {bd.salary_score:>4}  {bd.contract_score:>4}  "
            f"{bd.company_score:>3}  {bd.freshness_score:>3}  "
            f"{conf:>4}%  {flag}"
        )

    print("─" * 100)
    print("  Weights: Skill/30  Exp/20  Loc/15  Salary/15  Contract/10  Company/5  Freshness/5")

    print("\n  TOP 3 BREAKDOWNS")
    print("─" * 60)
    for rank, (job, bd, conf) in enumerate(results[:3], 1):
        print(f"\n  #{rank} {job['title']} @ {job['company']}  →  {bd.total}/100")
        print(f"      Skills matched:   {bd.skill_match}/30")
        print(f"      Experience:       {bd.experience_match}/20")
        print(f"      Location:         {bd.location_score}/15")
        print(f"      Salary:           {bd.salary_score}/15")
        print(f"      Contract:         {bd.contract_score}/10")
        print(f"      Company quality:  {bd.company_score}/5")
        print(f"      Freshness:        {bd.freshness_score}/5")
        print(f"      Confidence:       {conf}%")
        if bd.needs_review:
            print(f"      ⚑ Flagged for review (high total but low skill extraction)")
    print()


if __name__ == "__main__":
    run()
