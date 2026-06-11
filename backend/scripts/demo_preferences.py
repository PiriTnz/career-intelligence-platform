"""
Feedback Learning Agent — live demonstration.

Simulates a job hunt timeline: Tanaz views/saves/applies to AI jobs,
gets interviews for LLM roles, rejects Java/data-engineering jobs.
Shows how the preference profile evolves and re-ranks recommendations.

Run from backend/:
    PYTHONPATH=. python scripts/demo_preferences.py
"""
from __future__ import annotations

from app.services.matching_engine import match
from app.services.preference_service import (
    PreferenceProfile,
    blend_scores,
    compute_preference_score,
)
from app.services.scoring_service import score_job

# ── Simulated feedback timeline ───────────────────────────────────────────────
# (job, list of events) — events listed in order

FEEDBACK_TIMELINE = [
    # Strong positive: LLM / RAG jobs
    {
        "title": "LLM Engineer — Generative AI",
        "company_name": "Hugging Face",
        "required_skills": ["python", "pytorch", "llm", "rag", "langchain", "fastapi"],
        "experience_level": "mid",
        "location": "Remote",
        "remote": "full",
        "contract_type": "cdi",
        "salary_min": 58000,
        "salary_max": 72000,
        "company_quality_score": 96,
        "published_at": None,
        "language": "en",
    },
    {
        "title": "ML Engineer — LLM & RAG",
        "company_name": "Mistral AI",
        "required_skills": ["python", "pytorch", "llm", "rag", "fastapi", "docker"],
        "experience_level": "mid",
        "location": "Paris, France",
        "remote": "full",
        "contract_type": "cdi",
        "salary_min": 55000,
        "salary_max": 70000,
        "company_quality_score": 95,
        "published_at": None,
        "language": "fr",
    },
    # Mild positive: MLOps
    {
        "title": "MLOps Engineer",
        "company_name": "Renault Digital",
        "required_skills": ["python", "mlops", "kubernetes", "docker", "airflow"],
        "experience_level": "mid",
        "location": "Lyon, France",
        "remote": "hybrid",
        "contract_type": "cdi",
        "salary_min": 48000,
        "salary_max": 58000,
        "company_quality_score": 80,
        "published_at": None,
        "language": "fr",
    },
    # Rejected: wrong stack
    {
        "title": "Java Backend Engineer",
        "company_name": "Legacy Corp",
        "required_skills": ["java", "spring", "oracle", "hibernate"],
        "experience_level": "mid",
        "location": "Strasbourg, France",
        "remote": "none",
        "contract_type": "cdi",
        "salary_min": 35000,
        "salary_max": 42000,
        "company_quality_score": 40,
        "published_at": None,
        "language": "fr",
    },
    # Rejected: wrong domain
    {
        "title": "Data Engineer",
        "company_name": "Decathlon Tech",
        "required_skills": ["python", "sql", "airflow", "spark", "docker"],
        "experience_level": "mid",
        "location": "Lille, France",
        "remote": "hybrid",
        "contract_type": "cdi",
        "salary_min": 40000,
        "salary_max": 50000,
        "company_quality_score": 72,
        "published_at": None,
        "language": "fr",
    },
]

# Events: (job_index, event_type)
EVENTS = [
    # Viewed many jobs — no signal
    (0, "viewed"), (1, "viewed"), (2, "viewed"), (3, "viewed"), (4, "viewed"),
    # Saved LLM jobs
    (0, "saved"), (1, "saved"),
    # Applied to LLM + MLOps
    (0, "applied"), (1, "applied"), (2, "applied"),
    # Got interviews at LLM companies
    (0, "interview"), (1, "interview"),
    # Rejected Java and data engineering
    (3, "rejected"), (4, "rejected"),
]

# ── Jobs to recommend ─────────────────────────────────────────────────────────

CANDIDATE_JOBS = [
    {
        "title": "Senior LLM Engineer",
        "company_name": "Mistral AI",
        "required_skills": ["python", "pytorch", "llm", "rag", "langchain"],
        "experience_level": "senior",
        "location": "Paris, France",
        "remote": "full",
        "contract_type": "cdi",
        "salary_min": 70000,
        "salary_max": 90000,
        "company_quality_score": 95,
        "published_at": None,
        "language": "fr",
    },
    {
        "title": "ML Research Engineer — NLP",
        "company_name": "Aleph Alpha",
        "required_skills": ["python", "pytorch", "nlp", "llm", "research"],
        "experience_level": "mid",
        "location": "Remote",
        "remote": "full",
        "contract_type": "cdi",
        "salary_min": 60000,
        "salary_max": 75000,
        "company_quality_score": 88,
        "published_at": None,
        "language": "en",
    },
    {
        "title": "MLOps Platform Engineer",
        "company_name": "Scaleway",
        "required_skills": ["python", "kubernetes", "docker", "mlops", "airflow"],
        "experience_level": "mid",
        "location": "Lyon, France",
        "remote": "hybrid",
        "contract_type": "cdi",
        "salary_min": 50000,
        "salary_max": 62000,
        "company_quality_score": 75,
        "published_at": None,
        "language": "fr",
    },
    {
        "title": "Data Engineer — Streaming",
        "company_name": "BNP Paribas",
        "required_skills": ["python", "spark", "kafka", "sql", "airflow"],
        "experience_level": "mid",
        "location": "Paris, France",
        "remote": "hybrid",
        "contract_type": "cdi",
        "salary_min": 48000,
        "salary_max": 60000,
        "company_quality_score": 65,
        "published_at": None,
        "language": "fr",
    },
    {
        "title": "Java Senior Developer",
        "company_name": "Capgemini",
        "required_skills": ["java", "spring", "microservices", "docker"],
        "experience_level": "senior",
        "location": "Lyon, France",
        "remote": "none",
        "contract_type": "cdi",
        "salary_min": 52000,
        "salary_max": 65000,
        "company_quality_score": 60,
        "published_at": None,
        "language": "fr",
    },
    {
        "title": "AI Engineer — Computer Vision",
        "company_name": "Prophesee",
        "required_skills": ["python", "pytorch", "deep learning", "opencv", "c++"],
        "experience_level": "mid",
        "location": "Paris, France",
        "remote": "hybrid",
        "contract_type": "cdi",
        "salary_min": 55000,
        "salary_max": 68000,
        "company_quality_score": 80,
        "published_at": None,
        "language": "fr",
    },
]

PROFILE = {
    "skills": [
        "python", "machine learning", "deep learning", "pytorch", "tensorflow",
        "scikit-learn", "fastapi", "docker", "kubernetes", "llm", "rag",
        "langchain", "mlops", "airflow", "sql", "postgresql", "git",
    ],
    "target_roles": ["ML Engineer", "LLM Engineer", "MLOps Engineer", "AI Research Engineer"],
    "experience_level": "mid",
    "salary_min": 42000,
    "salary_target": 58000,
    "remote_preference": True,
    "countries": ["france"],
    "cities": ["lyon", "paris", "grenoble"],
    "contract_types": ["cdi", "cdd"],
    "languages": ["French", "English"],
}


def _build_preference_profile() -> PreferenceProfile:
    """Build preference profile from simulated events."""
    from collections import defaultdict
    from app.services.preference_service import EVENT_WEIGHTS, _extract_family

    skill_aff: dict[str, float] = defaultdict(float)
    location_aff: dict[str, float] = defaultdict(float)
    company_aff: dict[str, float] = defaultdict(float)
    contract_aff: dict[str, float] = defaultdict(float)
    family_aff: dict[str, float] = defaultdict(float)
    signal_breakdown: dict[str, int] = defaultdict(int)

    for job_idx, event_type in EVENTS:
        signal_breakdown[event_type] += 1
        weight = EVENT_WEIGHTS.get(event_type, 0.0)
        if weight == 0.0:
            continue
        job = FEEDBACK_TIMELINE[job_idx]
        for skill in job.get("required_skills", []):
            skill_aff[skill.lower()] += weight
        if job.get("location"):
            city = job["location"].split(",")[0].strip().lower()
            if city and city != "remote":
                location_aff[city] += weight
        if job.get("company_name"):
            company_aff[job["company_name"].lower()] += weight
        if job.get("contract_type"):
            contract_aff[job["contract_type"].lower()] += weight
        family = _extract_family(job.get("title"))
        if family:
            family_aff[family] += weight

    def _top(d, n):
        return sorted(
            [(k, round(v, 1)) for k, v in d.items() if v > 0],
            key=lambda x: x[1], reverse=True,
        )[:n]

    return PreferenceProfile(
        preferred_skills=_top(skill_aff, 20),
        preferred_locations=_top(location_aff, 10),
        preferred_companies=_top(company_aff, 10),
        preferred_contract_types=_top(contract_aff, 5),
        preferred_job_families=_top(family_aff, 10),
        total_events=len(EVENTS),
        signal_breakdown=dict(signal_breakdown),
    )


def run() -> None:
    prefs = _build_preference_profile()

    W = 130
    print("\n" + "═" * W)
    print("  FEEDBACK LEARNING AGENT — Tanaz Piriaei (mid ML/AI, Lyon)")
    print("═" * W)

    # ── Preference profile ─────────────────────────────────────────────────────
    print("\n  LEARNED PREFERENCE PROFILE")
    print("─" * 60)
    print(f"  Total events: {prefs.total_events}")
    bd = prefs.signal_breakdown
    print(f"  Signals: interview×{bd.get('interview',0)} | applied×{bd.get('applied',0)} "
          f"| saved×{bd.get('saved',0)} | viewed×{bd.get('viewed',0)} | rejected×{bd.get('rejected',0)}")

    print(f"\n  Top skills (affinity):")
    for name, aff in prefs.preferred_skills[:8]:
        bar = "█" * int(aff)
        print(f"    {name:<20} {bar} {aff:.1f}")

    print(f"\n  Locations:       {', '.join(f'{n}({a:.0f})' for n, a in prefs.preferred_locations)}")
    print(f"  Companies:       {', '.join(f'{n}({a:.0f})' for n, a in prefs.preferred_companies[:5])}")
    print(f"  Contract types:  {', '.join(f'{n}({a:.0f})' for n, a in prefs.preferred_contract_types)}")
    print(f"  Job families:    {', '.join(f'{n}({a:.0f})' for n, a in prefs.preferred_job_families[:5])}")

    # ── Ranked recommendations ─────────────────────────────────────────────────
    print("\n" + "─" * W)
    print("  PREFERENCE-AWARE RECOMMENDATIONS")
    print("─" * W)
    print(
        f"  {'#':<3} {'Job title':<38} {'Company':<18} "
        f"{'Prof':>4} {'Pref':>4} {'Final':>5}  {'Δ':>4}  "
        f"{'Notes'}"
    )
    print("─" * W)

    # Build no-prefs baseline
    no_prefs = PreferenceProfile()

    results = []
    for job in CANDIDATE_JOBS:
        bd_score, _ = score_job(job, PROFILE)
        pref_score = compute_preference_score(job, prefs)
        final = blend_scores(bd_score.total, pref_score, has_preferences=prefs.has_preferences)
        baseline = bd_score.total  # no-prefs = profile score
        delta = final - baseline
        results.append((job, bd_score.total, pref_score, final, delta))

    results_no_pref = sorted(results, key=lambda x: x[1], reverse=True)
    results_with_pref = sorted(results, key=lambda x: x[3], reverse=True)

    rank_before = {r[0]["title"]: i + 1 for i, r in enumerate(results_no_pref)}

    for rank, (job, prof_score, pref_score, final, delta) in enumerate(results_with_pref, 1):
        rank_chg = rank_before[job["title"]] - rank
        chg_str = f"+{rank_chg}" if rank_chg > 0 else str(rank_chg) if rank_chg < 0 else " ="
        notes = ""
        if pref_score > 65:
            notes = "↑ preference boost"
        elif pref_score < 35:
            notes = "↓ preference penalty"
        print(
            f"  {rank:<3} {job['title']:<38} {job['company_name']:<18} "
            f"{prof_score:>4}  {pref_score:>4.0f}  {final:>5}  {delta:>+4}  {chg_str} {notes}"
        )

    print("─" * W)
    print("  Columns: Prof=profile score (deterministic) | Pref=preference score | "
          "Final=0.70×Prof + 0.30×Pref | Δ=final-prof | Rank change from no-feedback baseline")

    # ── Ranking impact example ────────────────────────────────────────────────
    print("\n  RANKING IMPACT DETAIL — top-3 movers")
    print("─" * 70)
    for job, prof_score, pref_score, final, delta in sorted(results, key=lambda x: abs(x[4]), reverse=True)[:3]:
        print(f"\n  {job['title']} @ {job['company_name']}")
        print(f"    Profile score:    {prof_score}/100")
        print(f"    Preference score: {pref_score:.0f}/100")
        print(f"    Final score:      {final}/100  (Δ{delta:+d})")
        top_skills = [s for s in job.get("required_skills", [])
                      if any(s == p for p, _ in prefs.preferred_skills)]
        bad_skills = [s for s in job.get("required_skills", [])
                      if any(s == p and a < 0 for p, a in
                             [(p, a) for p, a in [("java", -2.0), ("spring", -2.0),
                                                   ("oracle", -2.0), ("hibernate", -2.0),
                                                   ("spark", -2.0), ("kafka", -2.0)]])]
        if top_skills:
            print(f"    Preferred skills matched: {', '.join(top_skills)}")

    print()


if __name__ == "__main__":
    run()
