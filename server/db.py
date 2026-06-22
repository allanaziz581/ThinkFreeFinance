"""db.py

A tiny SQLite-backed user store. SQLite (Python standard library, no extra
dependency) is plenty for a closed beta and keeps accounts on the server where
the browser can never read them. If the beta grows, this module is the single
place to swap in Postgres without touching the rest of the app.

Each account row holds: email (primary key), display name, a bcrypt password
hash (never the plaintext), tier, an accessibility flag, the behavioral-profile
JSON, and the creation date.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Optional

from config import DB_PATH


def _connect() -> sqlite3.Connection:
    # check_same_thread=False lets the connection be used across FastAPI's worker
    # threads; we open a short-lived connection per call to stay simple and safe.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the users table on first run. Safe to call every startup."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                email             TEXT PRIMARY KEY,
                name              TEXT NOT NULL,
                pass_hash         TEXT NOT NULL,
                tier              TEXT NOT NULL,
                a11y              INTEGER NOT NULL DEFAULT 0,
                profile           TEXT,
                created           TEXT NOT NULL,
                token_valid_after INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # Migrate databases created before token_valid_after existed: any session
        # token issued at/after this unix time is valid; logout bumps it to "now"
        # to revoke all outstanding tokens for that account.
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "token_valid_after" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN token_valid_after INTEGER NOT NULL DEFAULT 0")
        conn.commit()


def get_user(email: str) -> Optional[dict]:
    """Return the account row for an email, or None. Profile JSON is decoded."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
    if not row:
        return None
    user = dict(row)
    user["a11y"] = bool(user["a11y"])
    user["profile"] = json.loads(user["profile"]) if user["profile"] else None
    return user


def create_user(email: str, name: str, pass_hash: str, tier: str, created: str) -> None:
    """Insert a new account. Raises sqlite3.IntegrityError if the email exists."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO users (email, name, pass_hash, tier, a11y, profile, created) "
            "VALUES (?, ?, ?, ?, 0, NULL, ?)",
            (email.lower(), name, pass_hash, tier, created),
        )
        conn.commit()


def update_profile(email: str, profile: Optional[dict]) -> None:
    """Persist the behavioral-quiz profile for an account."""
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET profile = ? WHERE email = ?",
            (json.dumps(profile) if profile is not None else None, email.lower()),
        )
        conn.commit()


def update_a11y(email: str, a11y: bool) -> None:
    """Persist the accessibility-mode preference for an account."""
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET a11y = ? WHERE email = ?",
            (1 if a11y else 0, email.lower()),
        )
        conn.commit()


def update_token_valid_after(email: str, ts: int) -> None:
    """Set the account's token-validity epoch (unix seconds). Any session token
    issued before `ts` is then rejected by current_user — used on logout to
    revoke outstanding cookies immediately rather than waiting for expiry."""
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET token_valid_after = ? WHERE email = ?",
            (int(ts), email.lower()),
        )
        conn.commit()
