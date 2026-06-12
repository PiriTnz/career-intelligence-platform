"""
Opportunity Discovery Agent — in-memory demonstration.

Shows how the agent scores and ranks diverse opportunity types
(employment, PhD, CIFRE, freelance, internship) against a generic
user profile with learned preferences.

Generic: no user-specific data hardcoded. Profile and preferences
are parameterized and could represent any user.

Run from backend/:
    PYTHONPATH=. python scripts/demo_opportunities.py
"""
from __future__ import annotations

from app.services.matching_engine import match
from app.services.opportunity_discovery_service import (
    OPP_EVENT_WEIGHTS,
    _compute_explicit_pref_score,
    _compute_type_feedback_score,
    blend_opportunity_scores,
    compute_opportunity_preference_score,
)
from app.services.preference_service import PreferenceProfile, blend_scores, compute_preference_score
from app.services.scoring_service import score_job

# ── Generic user profile ──────────────────────────────────────────────────────
# Represents any user — all values driven by profile fields, not hardcoded identity.

PROFILE = {
    "skills": [
        "python", "machine learning", "deep learning", "pytorch", "tensorflow",
        "scikit-learn", "fastapi", "docker", "kubernetes", "llm", "rag",
        "langchain", "mlops", "sql", "postgresql", "git", "research",
    ],
    "target_roles": ["ML Engineer", "Research Engineer", "AI Engineer", "Data Scientist"],
    "experience_level": "mid",
    "salary_min": 35_000,
    "salary_target": 55_000,
    "remote_preference": True,
    "countries": ["france"],
    "cities": ["paris", "lyon", "bordeaux", "toulouse", "grenoble"],
    "contract_types": ["cdi", "cifre", "phd", "cdd"],
    "languages": ["French", "English"],
}

# ── Opportunity catalog ────────────────────────────────────────────────────────
# Generic: represents opportunities from any source or sector.

OPPORTUNITIES = [
    {
        "title": "Research Engineer — Natural Language Processing",
        "company": "AI Research Institute",
        "location": "Paris, France",
        "remote": "hybrid",
        "opportunity_type": "employment",
        "industry": "research",
        "sector": "nlp",
        "contract_type": "cdi",
        "salary_min": 52_000,
        "salary_max": 68_000,
        "required_skills": ["python", "pytorch", "nlp", "llm", "fastapi"],
        "experience_level": "mid",
        "language": "en",
    },
    {
        "title": "PhD — Machine Learning for Climate Modeling",
        "company": "National Research Centre",
        "location": "Grenoble, France",
        "remote": "hybrid",
        "opportunity_type": "phd",
        "industry": "research",
        "sector": "climate",
        "contract_type": "phd",
        "salary_min": 18_000,
        "salary_max": 22_000,
        "required_skills": ["python", "machine learning", "deep learning", "pytorch"],
        "experience_level": "junior",
        "language": "en",
    },
    {
        "title": "CIFRE PhD — AI-Driven Industrial Optimization",
        "company": "Industrial Corp & University Lab",
        "location": "Lyon, France",
        "remote": "hybrid",
        "opportunity_type": "cifre",
        "industry": "manufacturing",
        "sector": "industrial ai",
        "contract_type": "cifre",
        "salary_min": 25_000,
        "salary_max": 30_000,
        "required_skills": ["python", "machine learning", "pytorch", "mlops", "docker"],
        "experience_level": "junior",
        "language": "fr",
    },
    {
        "title": "ML Freelance Mission — RAG System Design",
        "company": "Tech Startup",
        "location": "Remote",
        "remote": "full",
        "opportunity_type": "freelance",
        "industry": "technology",
        "sector": "generative ai",
        "contract_type": "freelance",
        "salary_min": 400,
        "salary_max": 600,
        "required_skills": ["python", "rag", "langchain", "llm", "fastapi"],
        "experience_level": "mid",
        "language": "en",
    },
    {
        "title": "ML Engineering Internship — Computer Vision",
        "company": "Autonomous Systems Lab",
        "location": "Toulouse, France",
        "remote": "hybrid",
        "opportunity_type": "internship",
        "industry": "aerospace",
        "sector": "computer vision",
        "contract_type": "stage",
        "salary_min": 14_000,
        "salary_max": 18_000,
        "required_skills": ["python", "deep learning", "pytorch", "opencv"],
        "experience_level": "junior",
        "language": "fr",
    },
    {
        "title": "Senior Data Scientist — Retail Analytics",
        "company": "Retail Analytics Corp",
        "location": "Bordeaux, France",
        "remote": "none",
        "opportunity_type": "employment",
        "industry": "retail",
        "sector": "analytics",
        "contract_type": "cdi",
        "salary_min": 58_000,
        "salary_max": 72_000,
        "required_skills": ["python", "sql", "scikit-learn", "spark", "tableau"],
        "experience_level": "senior",
        "language": "fr",
    },
    {
        "title": "Research Engineer — Robotics & Reinforcement Learning",
        "company": "Robotics Institute",
        "location": "Paris, France",
        "remote": "hybrid",
        "opportunity_type": "employment",
        "industry": "research",
        "sector": "robotics",
        "contract_type": "cdi",
        "salary_min": 48_000,
        "salary_max": 62_000,
        "required_skills": ["python", "pytorch", "reinforcement learning", "ros", "docker"],
        "experience_level": "mid",
        "language": "en",
    },
]

# ── Simulated feedback on past opportunities ───────────────────────────────────
# Events: (opportunity_index, event_type)

FEEDBACK_EVENTS = [
    # Positive: NLP research and CIFRE
    (0, "saved"), (0, "applied"), (0, "interview"),
    (2, "saved"), (2, "applied"),
    # Mild positive: PhD
    (1, "saved"), (1, "interested"),
    # Viewed only: freelance (no signal)
    (3, "viewed"),
    # Rejected: internship
    (4, "rejected"),
]

# ── Explicit opportunity preferences (user-configured) ───────────────────────

EXPLICIT_PREFERENCES = {
    "preferred_opportunity_types": ["employment", "cifre", "phd"],
    "preferred_industries": ["research", "technology"],
    "preferred_sectors": [],  # no sector preference
    "preferred_locations": ["paris", "lyon", "grenoble"],
    "preferred_contract_types": ["cdi", "cifre"],
    "keywords": ["machine learning", "ai"],
}


# ── Build job-feedback-based preference profile ───────────────────────────────

def _build_feedback_prefs() -> PreferenceProfile:
    from collections import defaultdict
    from app.services.preference_service import EVENT_WEIGHTS, _extract_family

    skill_aff: dict[str, float] = defaultdict(float)
    location_aff: dict[str, float] = defaultdict(float)
    company_aff: dict[str, float] = defaultdict(float)
    contract_aff: dict[str, float] = defaultdict(float)
    family_aff: dict[str, float] = defaultdict(float)
    signal_breakdown: dict[str, int] = defaultdict(int)

    # Map opportunity feedback events to equivalent job feedback weights
    # (interview weight shared across both agents)
    opp_to_job_weight = {
        "interview": 3.0, "applied": 2.0, "interested": 1.5,
        "saved": 1.0, "viewed": 0.0, "rejected": -2.0,
    }

    for opp_idx, event_type in FEEDBACK_EVENTS:
        signal_breakdown[event_type] += 1
        weight = opp_to_job_weight.get(event_type, 0.0)
        if weight == 0.0:
            continue
        opp = OPPORTUNITIES[opp_idx]
        for skill in opp.get("required_skills", []):
            skill_aff[skill.lower()] += weight
        if opp.get("location") and opp["location"] != "Remote":
            city = opp["location"].split(",")[0].strip().lower()
            if city:
                location_aff[city] += weight
        if opp.get("company"):
            company_aff[opp["company"].lower()] += weight
        if opp.get("contract_type"):
            contract_aff[opp["contract_type"].lower()] += weight
        family = _extract_family(opp.get("title"))
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
        total_events=len(FEEDBACK_EVENTS),
        signal_breakdown=dict(signal_breakdown),
    )


def _build_type_affinities() -> dict[str, float]:
    """Compute type affinities from feedback events (mirrors get_opportunity_type_affinities)."""
    from collections import defaultdict
    aff: dict[str, float] = defaultdict(float)
    weights = {
        "interview": 3.0, "applied": 2.0, "interested": 1.5,
        "saved": 1.0, "viewed": 0.0, "rejected": -2.0,
    }
    for opp_idx, event_type in FEEDBACK_EVENTS:
        w = weights.get(event_type, 0.0)
        if w != 0.0:
            opp_type = OPPORTUNITIES[opp_idx].get("opportunity_type", "employment")
            aff[opp_type] += w
    return dict(aff)


def run() -> None:
    feedback_prefs = _build_feedback_prefs()
    type_affinities = _build_type_affinities()

    W = 145
    print("\n" + "═" * W)
    print("  OPPORTUNITY DISCOVERY AGENT — demonstration")
    print("  Generic multi-user platform: results driven by profile + preferences, no hardcoded identity")
    print("═" * W)

    # ── Feedback summary ──────────────────────────────────────────────────────
    print("\n  LEARNED PREFERENCE PROFILE (from opportunity feedback)")
    print("─" * 60)
    bd = feedback_prefs.signal_breakdown
    print(f"  Total events: {feedback_prefs.total_events}")
    print(f"  Signals: interview×{bd.get('interview',0)} | applied×{bd.get('applied',0)} "
          f"| interested×{bd.get('interested',0)} | saved×{bd.get('saved',0)} "
          f"| viewed×{bd.get('viewed',0)} | rejected×{bd.get('rejected',0)}")

    if feedback_prefs.preferred_skills:
        print(f"\n  Top skills (affinity):")
        for name, aff in feedback_prefs.preferred_skills[:8]:
            bar = "█" * int(aff)
            print(f"    {name:<20} {bar} {aff:.1f}")

    print(f"\n  Type affinities from feedback: " +
          ", ".join(f"{t}({v:+.1f})" for t, v in sorted(type_affinities.items(), key=lambda x: x[1], reverse=True)))
    print(f"\n  Explicit preferences: types={EXPLICIT_PREFERENCES['preferred_opportunity_types']} "
          f"| industries={EXPLICIT_PREFERENCES['preferred_industries']}")

    # ── Scored results ────────────────────────────────────────────────────────
    print("\n" + "─" * W)
    print("  SCORED OPPORTUNITIES (profile_weight=0.70, preference_weight=0.30)")
    print("─" * W)
    header = (
        f"  {'#':<3} {'Opportunity title':<46} {'Type':<12} "
        f"{'Prof':>4} {'Pref':>5} {'Final':>5}  {'Industry':<20} {'Notes'}"
    )
    print(header)
    print("─" * W)

    results = []
    for opp in OPPORTUNITIES:
        score_dict = {
            "title": opp["title"],
            "company_name": opp.get("company", ""),
            "required_skills": opp.get("required_skills", []),
            "experience_level": opp.get("experience_level"),
            "location": opp.get("location"),
            "remote": opp.get("remote", "none"),
            "contract_type": opp.get("contract_type"),
            "salary_min": opp.get("salary_min"),
            "salary_max": opp.get("salary_max"),
            "published_at": None,
            "company_quality_score": 50,
            "language": opp.get("language", "en"),
            "opportunity_type": opp.get("opportunity_type"),
            "industry": opp.get("industry"),
            "sector": opp.get("sector"),
        }

        bd_score, _ = score_job(score_dict, PROFILE)
        pref_score = compute_opportunity_preference_score(
            score_dict, feedback_prefs, EXPLICIT_PREFERENCES, type_affinities
        )
        has_prefs = feedback_prefs.has_preferences or bool(EXPLICIT_PREFERENCES)
        final = blend_opportunity_scores(
            bd_score.total, pref_score,
            profile_weight=0.70, preference_weight=0.30,
            has_preferences=has_prefs,
        )
        results.append((opp, bd_score.total, pref_score, final))

    results.sort(key=lambda x: x[3], reverse=True)
    baseline = {opp["title"]: bd for opp, bd, _, _ in sorted(results, key=lambda x: x[1], reverse=True)}

    for rank, (opp, prof_score, pref_score, final) in enumerate(results, 1):
        notes = ""
        if pref_score > 65:
            notes = "↑ pref boost"
        elif pref_score < 35:
            notes = "↓ pref penalty"
        opp_type = opp.get("opportunity_type", "employment")
        industry = opp.get("industry", "")
        print(
            f"  {rank:<3} {opp['title'][:45]:<46} {opp_type:<12} "
            f"{prof_score:>4}  {pref_score:>4.0f}  {final:>5}  {industry:<20} {notes}"
        )

    print("─" * W)
    print("  Columns: Prof=profile score (deterministic, 0–100) | Pref=preference score (0–100)")
    print("  Final = 0.70 × Prof + 0.30 × Pref (configurable via profile_weight / preference_weight)")

    # ── Score comparison: with vs. without preferences ─────────────────────────
    print("\n  RANKING IMPACT — top-3 preference movers")
    print("─" * 70)
    sorted_no_pref = sorted(results, key=lambda x: x[1], reverse=True)
    rank_no_pref = {r[0]["title"]: i + 1 for i, r in enumerate(sorted_no_pref)}

    movers = sorted(results, key=lambda x: abs(x[3] - x[1]), reverse=True)[:3]
    for opp, prof_score, pref_score, final in movers:
        rank_after = next(i + 1 for i, r in enumerate(results) if r[0]["title"] == opp["title"])
        rank_before = rank_no_pref[opp["title"]]
        delta = final - prof_score
        print(f"\n  {opp['title']}")
        print(f"    Type: {opp.get('opportunity_type')} | Industry: {opp.get('industry')}")
        print(f"    Profile score:    {prof_score}/100  (rank #{rank_before} without preferences)")
        print(f"    Preference score: {pref_score:.0f}/100")
        print(f"    Final score:      {final}/100  (rank #{rank_after} with preferences)  Δ{delta:+d}")

    # ── Opportunity types found ────────────────────────────────────────────────
    print(f"\n  OPPORTUNITY TYPES IN CATALOG: "
          + ", ".join(sorted({opp["opportunity_type"] for opp in OPPORTUNITIES})))
    print()


if __name__ == "__main__":
    run()
