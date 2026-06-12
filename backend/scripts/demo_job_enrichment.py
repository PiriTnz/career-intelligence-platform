#!/usr/bin/env python
"""
Demo: Job-Aware Profile Enrichment Agent

Simulates a full enrichment flow entirely in-process — no DB, no API call.

Profile  : Python, Docker
Job req  : Python, Docker, Terraform, Azure, MLflow, Leadership
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from app.services.enrichment_service import (
    analyze_requirements,
    classify_answer,
    generate_questions,
)


# ── Simulated data ─────────────────────────────────────────────────────────────

PROFILE_SKILLS = ["Python", "Docker"]

JOB_REQUIREMENTS = ["Python", "Docker", "Terraform", "Azure", "MLflow", "Leadership"]

# KB = empty (fresh user)
KNOWLEDGE_BASE = []

# Simulated user answers
SIMULATED_ANSWERS = {
    "q-0": "Yes, I use Terraform in my homelab — I have a GitHub repo with IaC configs",
    "q-1": "No, I have never worked with Azure at all",
    "q-2": "I built an MLflow tracking server for my university thesis on time-series forecasting",
    "q-3": "Yes, I led a 3-person team on a client project at my internship last summer",
}


def _sep(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print('─' * 60)


def main() -> None:
    _sep("1. REQUIREMENT ANALYSIS")
    gaps = analyze_requirements(JOB_REQUIREMENTS, PROFILE_SKILLS, KNOWLEDGE_BASE)
    for g in gaps:
        icon = {"already_verified": "✅", "partially_verified": "🔶", "unknown": "❓"}[g.classification]
        bridge = f" (via {g.via_skill}, {g.via_family})" if g.via_skill else ""
        print(f"  {icon} {g.requirement:15s}  [{g.classification}]{bridge}")

    _sep("2. QUESTION GENERATION")
    questions = generate_questions(gaps)
    print(f"  Skipped {len(gaps) - len(questions)} already-verified skills")
    print(f"  Generated {len(questions)} questions:\n")
    for q in questions:
        print(f"  [{q.id}] ({q.question_type})")
        print(f"        Req: {q.requirement}")
        print(f"        Q:   {q.question}\n")

    _sep("3. ANSWER CLASSIFICATION")
    classified: list[dict] = []
    for q in questions:
        raw = SIMULATED_ANSWERS.get(q.id, "No, I haven't used this.")
        etype, suggested = classify_answer(raw)
        classified.append({
            "question_id": q.id,
            "requirement": q.requirement,
            "answer": raw,
            "evidence_type": etype,
            "suggested_status": suggested,
        })
        icon = {"verified": "✅", "learning": "📚", "rejected": "❌"}[suggested]
        print(f"  {icon} {q.requirement:12s}  {etype:12s}  → {suggested}")
        print(f"        \"{raw[:80]}\"")

    _sep("4. CONFIRMATION STEP (simulated: accept all verified, skip rejected)")
    confirmed_skills: list[str] = []
    rejected_skills: list[str] = []

    for item in classified:
        if item["suggested_status"] == "rejected":
            rejected_skills.append(item["requirement"])
        else:
            confirmed_skills.append(item["requirement"])

    print(f"\n  Confirmed ({len(confirmed_skills)}): {confirmed_skills}")
    print(f"  Rejected  ({len(rejected_skills)}): {rejected_skills}")
    print("\n  NOTE: rejected items are NEVER added to skill_evidence — no fabrication.")

    _sep("5. PROFILE ENRICHMENT RESULT")
    original = set(s.lower() for s in PROFILE_SKILLS)
    enriched = set(s.lower() for s in confirmed_skills)
    final_skills = sorted(original | enriched)

    print(f"\n  Before enrichment : {sorted(original)}")
    print(f"  After enrichment  : {final_skills}")
    print(f"\n  New skills added  : {sorted(enriched - original)}")
    print(f"  Gaps remaining    : {[s.lower() for s in rejected_skills]}")

    _sep("6. READINESS CHANGE (illustrative)")
    before = round(len(original) / len(JOB_REQUIREMENTS) * 100)
    after = round(len(final_skills) / len(JOB_REQUIREMENTS) * 100)
    bar_before = "█" * (before // 5) + "░" * (20 - before // 5)
    bar_after = "█" * (after // 5) + "░" * (20 - after // 5)
    print(f"\n  Before: [{bar_before}] {before}%")
    print(f"  After:  [{bar_after}] {after}%")
    print(f"\n  Improvement: +{after - before}pp")

    print("\n  All done. Run `alembic upgrade head` then start the API to use the live endpoints.\n")


if __name__ == "__main__":
    main()
