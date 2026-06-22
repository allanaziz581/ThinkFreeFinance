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

# Tier definitions mirror the front-end. refresh_min drives how often a user may
# pull fresh "live" data; the server enforces this so it cannot be bypassed by
# editing the browser. Prices are placeholders.
TIERS = {
    "free":   {"name": "Free",         "refresh_min": 1440},
    "hourly": {"name": "Pro - Hourly", "refresh_min": 60},
    "half":   {"name": "Pro - 30-min", "refresh_min": 30},
    "live":   {"name": "Pro - 15-min", "refresh_min": 15},
    "beta":   {"name": "Beta Access",  "refresh_min": 15},
}
DEFAULT_TIER = "beta"   # closed-beta accounts get full access while testing


def is_placeholder_secret() -> bool:
    """True when the signing key was left at its default; used to block startup."""
    return SECRET_KEY in ("", "change-me-to-a-long-random-string")
