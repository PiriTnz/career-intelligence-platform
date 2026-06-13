"""
Demo: Application Tracker — full lifecycle walk-through.

Shows the complete journey from job discovery to offer using the new
8-stage pipeline: recommended → preparing → ready_to_apply → applied
→ follow_up → interview → offer.

Runs in-process (no server required). Uses real service logic with
mocked database.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.db.models import Application, ApplicationTimeline, Job
from app.schemas.application import VALID_TRANSITIONS, ApplicationMetrics

# ── fake DB state ─────────────────────────────────────────────────────────────

TIMELINE: list[dict] = []


def _make_job(title: str, company: str) -> MagicMock:
    job = MagicMock(spec=Job)
    job.id = uuid.uuid4()
    job.title = title
    job.company_name = company
    job.location = "Sydney"
    job.remote = "hybrid"
    return job


def _make_app(job_id: uuid.UUID, user_id: uuid.UUID) -> MagicMock:
    now = datetime.now(timezone.utc)
    app = MagicMock(spec=Application)
    app.id = uuid.uuid4()
    app.user_id = user_id
    app.job_id = job_id
    app.status = "recommended"
    app.applied_at = None
    app.follow_up_at = None
    app.interview_at = None
    app.offer_at = None
    app.rejected_at = None
    app.notes = None
    app.created_at = now
    app.updated_at = now
    return app


_TIMESTAMP_MAP = {
    "applied":   "applied_at",
    "follow_up": "follow_up_at",
    "interview": "interview_at",
    "offer":     "offer_at",
    "rejected":  "rejected_at",
}


def advance(app: MagicMock, new_status: str, notes: str | None = None) -> None:
    allowed = VALID_TRANSITIONS.get(app.status, [])
    if new_status not in allowed:
        raise ValueError(f"Invalid: {app.status!r} → {new_status!r}  (allowed: {allowed})")
    app.status = new_status
    ts_field = _TIMESTAMP_MAP.get(new_status)
    if ts_field and getattr(app, ts_field) is None:
        setattr(app, ts_field, datetime.now(timezone.utc))
    if notes:
        app.notes = notes
    TIMELINE.append({"status": new_status, "notes": notes})


# ── demo ──────────────────────────────────────────────────────────────────────

def divider(title: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print("─" * 60)


def show_app(app: MagicMock, job: MagicMock) -> None:
    print(f"  Job:     {job.title} @ {job.company_name}")
    print(f"  Status:  {app.status}")
    if app.applied_at:
        print(f"  Applied: {app.applied_at.strftime('%Y-%m-%d %H:%M UTC')}")
    if app.follow_up_at:
        print(f"  Follow-up: {app.follow_up_at.strftime('%Y-%m-%d %H:%M UTC')}")
    if app.interview_at:
        print(f"  Interview: {app.interview_at.strftime('%Y-%m-%d %H:%M UTC')}")
    if app.offer_at:
        print(f"  Offer:   {app.offer_at.strftime('%Y-%m-%d %H:%M UTC')}")
    if app.notes:
        print(f"  Notes:   {app.notes}")


def show_timeline() -> None:
    print("\n  Timeline:")
    for i, entry in enumerate(TIMELINE, 1):
        note = f" — {entry['notes']}" if entry["notes"] else ""
        print(f"    {i}. {entry['status']}{note}")


def show_transition_map() -> None:
    print("\n  Valid transitions:")
    for src, targets in VALID_TRANSITIONS.items():
        arrow = " → " + ", ".join(targets) if targets else " (terminal)"
        print(f"    {src}{arrow}")


def demo_offer_path() -> None:
    """Happy path: recommended → offer."""
    user_id = uuid.uuid4()
    job = _make_job("Senior ML Engineer", "DeepMind Sydney")
    app = _make_app(job.id, user_id)

    divider("1. Job Discovered")
    show_app(app, job)

    divider("2. User starts preparing CV")
    advance(app, "preparing", "Workspace created — CV draft in progress")
    show_app(app, job)

    divider("3. CV and cover letter ready — marked ready_to_apply")
    advance(app, "ready_to_apply", "Score: 87 — strong match on Python/TF/GCP")
    show_app(app, job)

    divider("4. Application submitted externally by user")
    advance(app, "applied", "Applied via LinkedIn Easy Apply")
    show_app(app, job)

    divider("5. Two weeks later — following up")
    advance(app, "follow_up", "No reply after 14 days — sent follow-up email")
    show_app(app, job)

    divider("6. Interview scheduled")
    advance(app, "interview", "Technical interview — Thursday 10am AEST")
    show_app(app, job)

    divider("7. Offer received!")
    advance(app, "offer", "$185k + equity — accepting")
    show_app(app, job)

    show_timeline()


def demo_rejection_path() -> None:
    """Sad path: recommended → rejected."""
    global TIMELINE
    TIMELINE = []

    user_id = uuid.uuid4()
    job = _make_job("Staff Engineer", "Big Tech Co")
    app = _make_app(job.id, user_id)

    divider("Rejection path: preparing → rejected")
    advance(app, "preparing")
    advance(app, "ready_to_apply")
    advance(app, "applied")
    advance(app, "rejected", "Position closed — no role available")
    show_app(app, job)
    show_timeline()


def demo_invalid_transition() -> None:
    """Guard rail: can't jump from recommended → applied."""
    global TIMELINE
    TIMELINE = []

    user_id = uuid.uuid4()
    job = _make_job("Data Scientist", "Startup Inc")
    app = _make_app(job.id, user_id)

    print("\n  Testing guard rails...")
    try:
        advance(app, "applied")  # skip preparing + ready_to_apply
        print("  ERROR: Should have raised ValueError")
    except ValueError as e:
        print(f"  Correctly blocked: {e}")

    try:
        advance(app, "offer")  # skip everything
        print("  ERROR: Should have raised ValueError")
    except ValueError as e:
        print(f"  Correctly blocked: {e}")


def demo_metrics() -> None:
    """Show what the metrics endpoint would return for a realistic portfolio."""
    divider("Portfolio Metrics (simulated)")

    # Simulate a realistic job search portfolio
    pipeline = {
        "recommended":   12,
        "preparing":      4,
        "ready_to_apply": 3,
        "applied":        8,
        "follow_up":      2,
        "interview":      2,
        "offer":          1,
        "rejected":       5,
    }
    total = sum(pipeline.values())
    metrics = ApplicationMetrics(total=total, **pipeline)

    print(f"\n  Total applications: {metrics.total}")
    print(f"  Recommended (not yet acting): {metrics.recommended}")
    print(f"  Preparing:                    {metrics.preparing}")
    print(f"  Ready to apply:               {metrics.ready_to_apply}  ← action queue")
    print(f"  Applied (awaiting response):  {metrics.applied}")
    print(f"  Follow-up sent:               {metrics.follow_up}")
    print(f"  Interviewing:                 {metrics.interview}")
    print(f"  Offers:                       {metrics.offer}")
    print(f"  Rejected:                     {metrics.rejected}")
    conversion = round(metrics.offer / metrics.applied * 100, 1) if metrics.applied else 0
    print(f"\n  Offer rate:   {conversion}%  ({metrics.offer}/{metrics.applied} applied)")
    interview_rate = round(metrics.interview / metrics.applied * 100, 1) if metrics.applied else 0
    print(f"  Interview rate: {interview_rate}%  ({metrics.interview}/{metrics.applied} applied)")


def main() -> None:
    print("=" * 60)
    print("  APPLICATION TRACKER — LIFECYCLE DEMO")
    print("=" * 60)

    divider("Valid Transition Map")
    show_transition_map()

    divider("SCENARIO A — Full offer path")
    demo_offer_path()

    divider("SCENARIO B — Rejection path")
    demo_rejection_path()

    divider("SCENARIO C — Guard rails (invalid transitions)")
    demo_invalid_transition()

    demo_metrics()

    print("\n" + "=" * 60)
    print("  Demo complete — no automation, no auto-apply.")
    print("  Every status change requires explicit user action.")
    print("=" * 60)


if __name__ == "__main__":
    main()
