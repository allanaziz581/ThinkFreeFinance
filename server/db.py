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
        # Section 5 additions: RBAC role, MFA secret + enabled flag, recovery-code
        # hashes (JSON list). Added via migration so existing beta DBs upgrade in place.
        for name, ddl in (
            ("role", "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'"),
            ("mfa_secret", "ALTER TABLE users ADD COLUMN mfa_secret TEXT"),
            ("mfa_enabled", "ALTER TABLE users ADD COLUMN mfa_enabled INTEGER NOT NULL DEFAULT 0"),
            ("recovery_codes", "ALTER TABLE users ADD COLUMN recovery_codes TEXT"),
        ):
            if name not in cols:
                conn.execute(ddl)

        # Session registry: one row per logged-in device, so a user can list and
        # revoke individual devices ("log out everywhere else") and the server can
        # invalidate a single stolen session without revoking all of them.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                sid       TEXT PRIMARY KEY,
                email     TEXT NOT NULL,
                device    TEXT,
                ip        TEXT,
                created   INTEGER NOT NULL,
                last_seen INTEGER NOT NULL,
                revoked   INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # Tamper-evident audit log: each row chains to the previous row's hash, so
        # editing or deleting any row breaks the chain (verify_audit_chain detects it).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts        INTEGER NOT NULL,
                email     TEXT,
                action    TEXT NOT NULL,
                detail    TEXT,
                ip        TEXT,
                prev_hash TEXT NOT NULL,
                row_hash  TEXT NOT NULL
            )
            """
        )
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


# ----- RBAC role -----

def set_role(email: str, role: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE users SET role = ? WHERE email = ?", (role, email.lower()))
        conn.commit()


# ----- Subscription tier -----

def set_tier(email: str, tier: str) -> None:
    """Change an account's subscription tier. SERVER-SIDE ONLY.

    The only legitimate callers are (a) an admin tool and (b) the billing webhook
    after a verified payment event. There is deliberately NO request path that
    lets the browser set its own tier — entitlement can never be self-escalated.
    """
    with _connect() as conn:
        conn.execute("UPDATE users SET tier = ? WHERE email = ?", (tier, email.lower()))
        conn.commit()


# ----- MFA (TOTP) -----

def set_mfa_secret(email: str, secret: str | None, recovery_json: str | None) -> None:
    """Store a pending TOTP secret (not yet enabled) and hashed recovery codes."""
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET mfa_secret = ?, recovery_codes = ? WHERE email = ?",
            (secret, recovery_json, email.lower()),
        )
        conn.commit()


def set_mfa_enabled(email: str, enabled: bool) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET mfa_enabled = ? WHERE email = ?",
            (1 if enabled else 0, email.lower()),
        )
        conn.commit()


def set_recovery_codes(email: str, recovery_json: str | None) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET recovery_codes = ? WHERE email = ?",
            (recovery_json, email.lower()),
        )
        conn.commit()


# ----- session registry -----

def create_session(sid: str, email: str, device: str, ip: str, now: int) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (sid, email, device, ip, created, last_seen, revoked) "
            "VALUES (?, ?, ?, ?, ?, ?, 0)",
            (sid, email.lower(), device, ip, now, now),
        )
        conn.commit()


def session_active(sid: str) -> bool:
    """True if the session exists and has not been revoked (device logout)."""
    if not sid:
        return False
    with _connect() as conn:
        row = conn.execute("SELECT revoked FROM sessions WHERE sid = ?", (sid,)).fetchone()
    return bool(row) and not row["revoked"]


def touch_session(sid: str, now: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE sessions SET last_seen = ? WHERE sid = ?", (now, sid))
        conn.commit()


def list_sessions(email: str) -> list:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT sid, device, ip, created, last_seen, revoked FROM sessions "
            "WHERE email = ? AND revoked = 0 ORDER BY last_seen DESC",
            (email.lower(),),
        ).fetchall()
    return [dict(r) for r in rows]


def revoke_session(email: str, sid: str) -> bool:
    """Revoke one device's session. Scoped to the owner so users can only end
    their own sessions (object-ownership check)."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE sessions SET revoked = 1 WHERE sid = ? AND email = ?",
            (sid, email.lower()),
        )
        conn.commit()
        return cur.rowcount > 0


def revoke_all_sessions(email: str, keep_sid: str | None = None) -> None:
    with _connect() as conn:
        if keep_sid:
            conn.execute(
                "UPDATE sessions SET revoked = 1 WHERE email = ? AND sid != ?",
                (email.lower(), keep_sid),
            )
        else:
            conn.execute("UPDATE sessions SET revoked = 1 WHERE email = ?", (email.lower(),))
        conn.commit()


# ----- tamper-evident audit log -----

def _last_audit_hash(conn) -> str:
    row = conn.execute("SELECT row_hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    return row["row_hash"] if row else "genesis"


def audit_append(ts: int, email: str | None, action: str, detail: str, ip: str, hash_fn) -> None:
    """Append a hash-chained audit entry. hash_fn(prev, ts, email, action, detail)
    is injected from security.py to keep the crypto in one place."""
    with _connect() as conn:
        prev = _last_audit_hash(conn)
        row_hash = hash_fn(prev, ts, email or "", action, detail)
        conn.execute(
            "INSERT INTO audit_log (ts, email, action, detail, ip, prev_hash, row_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, email, action, detail, ip, prev, row_hash),
        )
        conn.commit()


def audit_tail(limit: int = 200) -> list:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, ts, email, action, detail, ip, prev_hash, row_hash "
            "FROM audit_log ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [dict(r) for r in rows]


def verify_audit_chain(hash_fn) -> bool:
    """Recompute every row's hash in order; returns False if the chain is broken
    (i.e. a row was edited or deleted) -- the tamper-evidence check."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT ts, email, action, detail, prev_hash, row_hash FROM audit_log ORDER BY id ASC"
        ).fetchall()
    prev = "genesis"
    for r in rows:
        if r["prev_hash"] != prev:
            return False
        expect = hash_fn(prev, r["ts"], r["email"] or "", r["action"], r["detail"] or "")
        if expect != r["row_hash"]:
            return False
        prev = r["row_hash"]
    return True


# ----- data governance: export & account deletion -----

def export_user(email: str) -> dict:
    """Gather everything stored about a user for a GDPR-style data export."""
    e = email.lower()
    with _connect() as conn:
        urow = conn.execute("SELECT * FROM users WHERE email = ?", (e,)).fetchone()
        sess = conn.execute("SELECT sid, device, ip, created, last_seen, revoked FROM sessions WHERE email = ?", (e,)).fetchall()
        audit = conn.execute("SELECT id, ts, action, detail, ip FROM audit_log WHERE email = ?", (e,)).fetchall()
    user = dict(urow) if urow else {}
    user.pop("pass_hash", None)        # never export the password hash
    user.pop("mfa_secret", None)       # nor the live MFA secret
    user.pop("recovery_codes", None)   # nor recovery-code hashes
    if user.get("profile"):
        try:
            user["profile"] = json.loads(user["profile"])
        except Exception:
            pass
    return {"account": user, "sessions": [dict(r) for r in sess], "activity": [dict(r) for r in audit]}


def delete_user(email: str) -> None:
    """Account-deletion workflow: remove the user record and all their sessions.

    Audit-log rows are intentionally left untouched: they form a tamper-evident
    hash chain (mutating them would break it), and security event logs are
    retained as a legitimate-interest security record. They contain only the
    email and the action taken, never profile data, passwords, or MFA secrets."""
    e = email.lower()
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE email = ?", (e,))
        conn.execute("DELETE FROM users WHERE email = ?", (e,))
        conn.commit()
