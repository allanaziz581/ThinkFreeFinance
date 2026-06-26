"""security.py

Self-contained security primitives for the ThinkFree backend, implemented with
the Python standard library only (no new dependencies):

  - TOTP multi-factor auth (RFC 6238) + recovery codes
  - CSRF double-submit token helpers
  - Tamper-evident (hash-chained) audit-log hashing
  - Input sanitization
  - Role-based access control (RBAC) helpers

Keeping these in the stdlib avoids pulling extra packages into the install and
keeps the supply-chain surface small (a goal called out in the security review).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import struct
import time
from urllib.parse import quote


# --------------------------------------------------------------------------
# TOTP (RFC 6238) -- the time-based codes an authenticator app generates.
# --------------------------------------------------------------------------

def gen_totp_secret() -> str:
    """A new base32 TOTP secret (160 bits) to show the user once at enrollment."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _hotp(secret_b32: str, counter: int, digits: int = 6) -> str:
    key = base64.b32decode(secret_b32 + "=" * (-len(secret_b32) % 8), casefold=True)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def verify_totp(secret_b32: str, code: str, window: int = 1, step: int = 30) -> bool:
    """True if `code` matches the secret within +/- `window` time steps (clock skew)."""
    if not secret_b32 or not code:
        return False
    code = re.sub(r"\D", "", str(code))
    if len(code) != 6:
        return False
    counter = int(time.time() // step)
    for drift in range(-window, window + 1):
        if hmac.compare_digest(_hotp(secret_b32, counter + drift), code):
            return True
    return False


def provisioning_uri(secret_b32: str, email: str, issuer: str = "ThinkFree Finance") -> str:
    """otpauth:// URI for the QR/manual-entry step in an authenticator app."""
    label = quote(f"{issuer}:{email}")
    return f"otpauth://totp/{label}?secret={secret_b32}&issuer={quote(issuer)}&digits=6&period=30"


# --------------------------------------------------------------------------
# Recovery codes -- one-time backups if the authenticator device is lost.
# Stored only as sha256 hashes (like passwords): we never keep the plaintext.
# --------------------------------------------------------------------------

def gen_recovery_codes(n: int = 10) -> list[str]:
    return [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(n)]


def hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# CSRF -- double-submit token. A non-httpOnly cookie holds a random token; the
# client echoes it in an X-CSRF-Token header. A cross-site attacker can trigger
# a request but cannot read the cookie to set the matching header.
# --------------------------------------------------------------------------

def gen_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_ok(cookie_token: str | None, header_token: str | None) -> bool:
    if not cookie_token or not header_token:
        return False
    return hmac.compare_digest(cookie_token, header_token)


# --------------------------------------------------------------------------
# Audit log hashing -- each entry chains to the previous one's hash, so any
# later edit or deletion of a row breaks the chain (tamper-evident logging).
# --------------------------------------------------------------------------

def audit_hash(prev_hash: str, ts: int, email: str, action: str, detail: str) -> str:
    payload = f"{prev_hash}|{ts}|{email}|{action}|{detail}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Input sanitization -- strip control characters and cap length on any free
# text before it is stored or echoed (defense in depth alongside pydantic
# validation and the front-end's HTML escaping).
# --------------------------------------------------------------------------

_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(value, maxlen: int = 2000) -> str:
    if value is None:
        return ""
    return _CTRL_RE.sub("", str(value))[:maxlen].strip()


# --------------------------------------------------------------------------
# RBAC -- a simple ordered role hierarchy. Higher roles inherit lower ones.
# --------------------------------------------------------------------------

ROLES = {"user": 1, "analyst": 2, "admin": 3}


def role_at_least(role: str, required: str) -> bool:
    return ROLES.get(role or "user", 0) >= ROLES.get(required, 99)


def new_session_id() -> str:
    return secrets.token_urlsafe(18)
