"""config.py

Central settings for the ThinkFree backend, loaded once from server/.env (or from
real environment variables in production). Nothing secret is hard-coded here; every
sensitive value comes from the environment so it never lands in the repo or in any
file the browser can download.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Resolve important directories relative to this file so the server runs the same
# way no matter what the current working directory is when it starts.
SERVER_DIR = Path(__file__).resolve().parent           # .../ThinkFree-main/server
ROOT_DIR = SERVER_DIR.parent                            # .../ThinkFree-main
WEBAPP_DIR = ROOT_DIR / "webapp"                        # static front-end shell
PRIVATE_DATA_DIR = ROOT_DIR / "private_data"            # built JSON, never web-served
DB_PATH = SERVER_DIR / "users.db"                       # sqlite user store (gitignored)

# Load server/.env if present. In production the platform injects real env vars and
# this file is absent, which is fine: load_dotenv() simply does nothing.
load_dotenv(SERVER_DIR / ".env")


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


# Secret used to sign session tokens. We refuse to start with the placeholder so a
# misconfigured deploy fails loudly instead of shipping a guessable signing key.
SECRET_KEY = _get("TF_SECRET_KEY", "change-me-to-a-long-random-string")

# Closed-beta invite key required to create an account.
BETA_KEY = _get("TF_BETA_KEY", "THINKFREE-BETA-2026")

# Production flag flips on Secure cookies and HSTS. Keep it off for local http.
PRODUCTION = _get("TF_PRODUCTION", "0") == "1"

# Origins allowed to call the API from a browser (same-origin by default).
ALLOWED_ORIGINS = [o.strip() for o in _get("TF_ALLOWED_ORIGINS", "http://localhost:8000").split(",") if o.strip()]

# Session lifetime (how long a login stays valid) in seconds.
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60   # 7 days

# ---------------------------------------------------------------------------
# Tier catalogue — THE single source of truth for refresh cadence + pricing.
# ---------------------------------------------------------------------------
# The front-end fetches this via GET /api/data/tiers instead of hard-coding its
# own copy, so cadence and price never drift between client and server.
#
#   refresh_min   how often the user may pull fresh "live" data. ENFORCED
#                 server-side in data.py /live (429 until the window elapses) so
#                 it cannot be sped up by editing the browser.
#   price_usd     monthly price as a number (0 = free). Drives billing later.
#   price_display human-readable price string for the UI.
#   entitlements  capability flags the front-end and server can branch on.
#   public        True = shown in the upgrade options; False = internal/granted
#                 tier (e.g. closed-beta) not offered for self-serve purchase.
#   order         display ordering in the plan picker.
#
# IMPORTANT: tier *keys* are persisted on user rows and inside signed tokens, so
# keys are stable across pricing changes — only the values are tuned. To add a
# brand-new tier, add a new key here; do not rename an existing one.
TIERS = {
    "free": {
        "name": "Free", "refresh_min": 1440, "price_usd": 0, "price_display": "$0",
        "blurb": "Daily market briefing", "order": 0, "public": True,
        "entitlements": {"after_hours": False, "live_prices": True, "news": True},
    },
    "hourly": {
        "name": "Pro · Hourly", "refresh_min": 60, "price_usd": 9, "price_display": "$9/mo",
        "blurb": "Fresh prices every hour", "order": 1, "public": True,
        "entitlements": {"after_hours": False, "live_prices": True, "news": True},
    },
    "half": {
        "name": "Pro · 30-min", "refresh_min": 30, "price_usd": 19, "price_display": "$19/mo",
        "blurb": "Refreshes every 30 minutes, including after hours", "order": 2, "public": True,
        "entitlements": {"after_hours": True, "live_prices": True, "news": True},
    },
    # NOTE: key kept as "live" (already persisted on existing accounts); cadence
    # retuned from 15→5 min and renamed to the 5-minute product tier.
    "live": {
        "name": "Pro · 5-min", "refresh_min": 5, "price_usd": 39, "price_display": "$39/mo",
        "blurb": "Fastest feed — every 5 minutes, including after hours", "order": 3, "public": True,
        "entitlements": {"after_hours": True, "live_prices": True, "news": True},
    },
    # Internal tier granted to closed-beta testers: top speed, never sold.
    "beta": {
        "name": "Beta Access", "refresh_min": 5, "price_usd": 0, "price_display": "Free (beta)",
        "blurb": "Full 5-minute access during the closed beta", "order": 99, "public": False,
        "entitlements": {"after_hours": True, "live_prices": True, "news": True},
    },
}
DEFAULT_TIER = "free"   # new self-serve accounts start on the free daily tier


def tier_for(key: str) -> dict:
    """Resolve a tier dict by key, falling back to the default tier if unknown."""
    return TIERS.get(key, TIERS[DEFAULT_TIER])


def public_tiers() -> list[dict]:
    """The purchasable tier catalogue (id + metadata), ordered for the UI.

    Excludes internal tiers (public=False) and never exposes anything secret —
    this is plain marketing/pricing metadata safe to serve unauthenticated.
    """
    out = []
    for key, t in TIERS.items():
        if not t.get("public"):
            continue
        out.append({
            "id": key,
            "name": t["name"],
            "refresh_min": t["refresh_min"],
            "price_usd": t["price_usd"],
            "price_display": t["price_display"],
            "blurb": t["blurb"],
            "entitlements": t["entitlements"],
            "order": t["order"],
        })
    return sorted(out, key=lambda x: x["order"])


def is_placeholder_secret() -> bool:
    """True when the signing key was left at its default; used to block startup."""
    return SECRET_KEY in ("", "change-me-to-a-long-random-string")
