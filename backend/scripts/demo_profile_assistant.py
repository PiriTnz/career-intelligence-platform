"""
Demo script: LLM Profile Assistant.

Shows the two-step assistant flow:
  1. POST /api/v1/profiles/assistant/message  — LLM extracts fields, returns proposed updates
  2. POST /api/v1/profiles/assistant/apply-updates — user confirms, fields written to profile

Also demonstrates:
  - GET  /api/v1/profiles/completeness
  - Multilingual input (English, French, Persian)
  - Graceful handling of unrelated messages

Usage:
    python scripts/demo_profile_assistant.py

Set BASE_URL, EMAIL, PASSWORD in environment or edit the defaults below.
No hardcoded user-specific data — uses a generic demo account.
"""
from __future__ import annotations

import json
import os
import sys
import textwrap
import time
import uuid

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
DEMO_EMAIL = os.getenv("DEMO_EMAIL", f"demo-assistant-{uuid.uuid4().hex[:8]}@example.com")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "DemoPassword123!")


def _require_requests():
    try:
        import requests
        return requests
    except ImportError:
        print("ERROR: 'requests' not installed. Run: pip install requests")
        sys.exit(1)


def _h(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def _pp(label: str, data: dict | list | int | str):
    print(f"\n{label}:")
    if isinstance(data, (dict, list)):
        print(textwrap.indent(json.dumps(data, indent=2, ensure_ascii=False), "  "))
    else:
        print(f"  {data}")


def _register(requests, email: str, password: str) -> str | None:
    r = requests.post(f"{BASE_URL}/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "name": "Profile Assistant Demo",
    })
    if r.status_code not in (200, 201):
        return None
    return r.json().get("access_token")


def _login(requests, email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/api/v1/auth/login", data={
        "username": email,
        "password": password,
    })
    if r.status_code != 200:
        print(f"Login failed: {r.status_code} — {r.text}")
        sys.exit(1)
    return r.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _message(requests, token: str, message: str, language: str = "en") -> dict:
    r = requests.post(
        f"{BASE_URL}/api/v1/profiles/assistant/message",
        headers=_auth_headers(token),
        json={"message": message, "language": language},
    )
    if r.status_code != 200:
        print(f"  ERROR {r.status_code}: {r.text}")
        return {}
    return r.json()


def _apply(requests, token: str, updates: dict) -> dict:
    r = requests.post(
        f"{BASE_URL}/api/v1/profiles/assistant/apply-updates",
        headers=_auth_headers(token),
        json={"updates": updates},
    )
    if r.status_code not in (200, 201):
        print(f"  ERROR {r.status_code}: {r.text}")
        return {}
    return r.json()


def _completeness(requests, token: str) -> dict:
    r = requests.get(
        f"{BASE_URL}/api/v1/profiles/completeness",
        headers=_auth_headers(token),
    )
    if r.status_code != 200:
        print(f"  ERROR {r.status_code}: {r.text}")
        return {}
    return r.json()


def main():
    requests = _require_requests()

    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║          LLM Profile Assistant — Demo Script             ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"\nBase URL : {BASE_URL}")
    print(f"Demo user: {DEMO_EMAIL}")

    # ── Auth ──────────────────────────────────────────────────────────────
    _h("1. Authentication")
    token = _register(requests, DEMO_EMAIL, DEMO_PASSWORD)
    if token is None:
        print("Registration skipped (user may exist) — logging in...")
        token = _login(requests, DEMO_EMAIL, DEMO_PASSWORD)
    else:
        print("Demo user registered and logged in.")

    # ── Baseline completeness (new profile = 0%) ──────────────────────────
    _h("2. Baseline Profile Completeness")
    comp = _completeness(requests, token)
    _pp("Completeness", comp.get("completeness", "n/a"))
    _pp("Missing fields", comp.get("missing_fields", []))

    # ── Round 1: English — skills and roles ───────────────────────────────
    _h("3. Message 1 — English (skills + roles)")
    msg1 = "I'm a data engineer with expertise in Python, Apache Spark, and dbt. I'm targeting senior data engineering roles."
    print(f"\nUser: \"{msg1}\"")
    resp1 = _message(requests, token, msg1, "en")
    _pp("Assistant says", resp1.get("assistant_message", ""))
    _pp("Proposed updates", resp1.get("updated_profile_fields", {}))
    _pp("Completeness after extraction", resp1.get("profile_completeness", 0))
    _pp("Next question", resp1.get("next_question", ""))

    # Apply round 1 updates
    if resp1.get("updated_profile_fields"):
        print("\n  → Applying round 1 updates...")
        profile1 = _apply(requests, token, resp1["updated_profile_fields"])
        if profile1:
            print(f"  ✓ Profile updated (v{profile1.get('version', '?')})")

    time.sleep(0.5)

    # ── Round 2: French — salary and location ─────────────────────────────
    _h("4. Message 2 — French (salary + location)")
    msg2 = "Je cherche un CDI à Paris ou Lyon avec un salaire entre 55 000 et 75 000 euros par an. Je suis ouvert au télétravail partiel."
    print(f"\nUser (fr): \"{msg2}\"")
    resp2 = _message(requests, token, msg2, "fr")
    _pp("Assistant says", resp2.get("assistant_message", ""))
    _pp("Proposed updates", resp2.get("updated_profile_fields", {}))
    _pp("Completeness", resp2.get("profile_completeness", 0))

    if resp2.get("updated_profile_fields"):
        print("\n  → Applying round 2 updates...")
        profile2 = _apply(requests, token, resp2["updated_profile_fields"])
        if profile2:
            print(f"  ✓ Profile updated (v{profile2.get('version', '?')})")

    time.sleep(0.5)

    # ── Round 3: Persian — experience ─────────────────────────────────────
    _h("5. Message 3 — Persian (experience level)")
    msg3 = "من ۶ سال تجربه در مهندسی داده دارم و به فرصت‌های شغلی و همچنین دکترا علاقه‌مند هستم."
    print(f"\nUser (fa): \"{msg3}\"")
    resp3 = _message(requests, token, msg3, "fa")
    _pp("Assistant says", resp3.get("assistant_message", ""))
    _pp("Proposed updates", resp3.get("updated_profile_fields", {}))
    _pp("Completeness", resp3.get("profile_completeness", 0))

    if resp3.get("updated_profile_fields"):
        print("\n  → Applying round 3 updates...")
        profile3 = _apply(requests, token, resp3["updated_profile_fields"])
        if profile3:
            print(f"  ✓ Profile updated (v{profile3.get('version', '?')})")

    time.sleep(0.5)

    # ── Round 4: Unrelated message (graceful no-op) ───────────────────────
    _h("6. Message 4 — Unrelated (assistant handles gracefully)")
    msg4 = "What's the weather like today in Paris?"
    print(f"\nUser: \"{msg4}\"")
    resp4 = _message(requests, token, msg4, "en")
    _pp("Assistant says", resp4.get("assistant_message", ""))
    _pp("Proposed updates", resp4.get("updated_profile_fields", {}))
    assert resp4.get("updated_profile_fields") == {} or resp4.get("updated_profile_fields") is None, \
        "Expected no updates for unrelated message"
    print("  ✓ No profile fields proposed for unrelated message")

    # ── Final completeness check ──────────────────────────────────────────
    _h("7. Final Profile Completeness")
    final_comp = _completeness(requests, token)
    _pp("Overall completeness", f"{final_comp.get('completeness', 0)}%")
    _pp("Remaining missing fields", final_comp.get("missing_fields", []))
    _pp("Field scores", final_comp.get("field_scores", {}))

    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║                      Demo Complete                       ║")
    print("╚══════════════════════════════════════════════════════════╝\n")


if __name__ == "__main__":
    main()
