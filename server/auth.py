"""auth.py

Real, server-side authentication for the closed beta. This replaces the old
client-side localStorage gate (which anyone could bypass by editing the browser).

Security properties:
  - Passwords are hashed with bcrypt and never stored or logged in plaintext.
  - The session is a JWT signed with TF_SECRET_KEY and delivered in an httpOnly,
    Secure, SameSite cookie, so page JavaScript (and therefore an XSS payload)
    cannot read or steal it.
  - Sign-up requires the closed-beta invite key, compared in constant time.
  - The browser is never trusted for identity or tier; both come from the signed
    cookie and the server-side user record.
"""
from __future__ import annotations

import datetime as dt
import hmac
import json
import re
import sqlite3
import time
from collections import deque

import bcrypt
import jwt
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

import config
import db
import security

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "tf_session"
CSRF_COOKIE = "tf_csrf"
# Require a real-looking TLD (2+ letters) so "a@b" / "a@b.1" are rejected. This
# mirrors the browser-side check; both enforce format, not deliverability.
_EMAIL_RE = re.compile(r"^[^@\s]+@[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*\.[a-z]{2,}$", re.I)


# ----- brute-force rate limiting -----
#
# A simple in-memory limiter that blocks repeated failed logins (password
# guessing) and repeated signups (beta-key guessing). It records the timestamps
# of recent *failures* per key and refuses new attempts once a threshold is hit
# within a rolling window. A successful login clears that key's failures, so a
# legitimate user is never penalized.
#
# In-memory is sufficient for the single-process beta (same trade-off as the
# /api/data/live cadence tracker). It resets on restart and is per-process; a
# multi-worker deploy would move this to Redis. It is NOT bypassable from the
# browser, which is the point.

# Per (IP + email): stops hammering one account's password.
_LOGIN_MAX_FAILS = 5
_LOGIN_WINDOW = 15 * 60          # 15 minutes
# Per IP across all emails: stops spraying many accounts from one source.
_LOGIN_IP_MAX_FAILS = 20
_LOGIN_IP_WINDOW = 15 * 60
# Per IP: stops brute-forcing the closed-beta invite key via the signup form.
_SIGNUP_MAX_FAILS = 10
_SIGNUP_WINDOW = 60 * 60         # 1 hour

_fails: dict[str, deque] = {}


def _client_ip(request: Request) -> str:
    return security.client_ip(request, config.TRUSTED_PROXY_CIDRS)


def _check_locked(key: str, max_fails: int, window: int) -> None:
    """Raise 429 (with Retry-After) if `key` has hit `max_fails` within `window`."""
    now = time.time()
    dq = _fails.setdefault(key, deque())
    while dq and now - dq[0] > window:   # drop failures older than the window
        dq.popleft()
    if len(dq) >= max_fails:
        retry = int(window - (now - dq[0])) + 1
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Please wait a few minutes and try again.",
            headers={"Retry-After": str(retry)},
        )


def _record_fail(key: str) -> None:
    _fails.setdefault(key, deque()).append(time.time())


def _clear_fails(*keys: str) -> None:
    for key in keys:
        _fails.pop(key, None)


# ----- password hashing -----

def hash_password(plain: str) -> str:
    """Hash a password with bcrypt (includes a per-password random salt)."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time bcrypt verification; returns False on any malformed hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ----- session tokens (JWT) -----

def _make_token(email: str, tier: str, sid: str | None = None) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": email,
        "tier": tier,
        "iat": now,
        "exp": now + dt.timedelta(seconds=config.SESSION_TTL_SECONDS),
    }
    if sid:
        payload["sid"] = sid   # ties the token to a row in the session registry
    return jwt.encode(payload, config.SECRET_KEY, algorithm="HS256")


def _set_session_cookie(response: Response, token: str) -> None:
    # httpOnly: JS cannot read it. secure: only sent over HTTPS (prod). samesite
    # lax: sent on top-level navigations but not cross-site POSTs (CSRF defense).
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=config.SESSION_TTL_SECONDS,
        httponly=True,
        secure=config.PRODUCTION,
        samesite="lax",
        path="/",
    )


def _set_csrf_cookie(response: Response) -> str:
    """Issue a fresh CSRF token in a NON-httpOnly cookie so the page JS can read
    it and echo it back in the X-CSRF-Token header (double-submit). Returns the
    token for convenience. SameSite=lax + this header together defend mutations."""
    token = security.gen_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        max_age=config.SESSION_TTL_SECONDS,
        httponly=False,
        secure=config.PRODUCTION,
        samesite="lax",
        path="/",
    )
    return token


def require_csrf(x_csrf_token: str | None = Header(default=None),
                 tf_csrf: str | None = Cookie(default=None)) -> None:
    """Dependency for state-changing endpoints: the X-CSRF-Token header must match
    the tf_csrf cookie. A cross-site attacker can forge a request but cannot read
    the cookie to set the matching header."""
    if not security.csrf_ok(tf_csrf, x_csrf_token):
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid")


def _audit(request: Request, email: str | None, action: str, detail: str = "") -> None:
    """Append a tamper-evident audit entry. Best-effort: never breaks a request."""
    try:
        db.audit_append(int(time.time()), email, action,
                        security.sanitize_text(detail, 500), _client_ip(request),
                        security.audit_hash)
    except Exception:
        pass


def current_user(tf_session: str | None = Cookie(default=None)) -> dict:
    """FastAPI dependency: resolve the logged-in account from the session cookie.

    Raises 401 if the cookie is missing, invalid, expired, or the user is gone.
    Use this on every endpoint that returns private data.
    """
    if not tf_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(tf_session, config.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    user = db.get_user(payload.get("sub", ""))
    if not user:
        raise HTTPException(status_code=401, detail="Account not found")
    # Reject tokens issued before the account's validity epoch (set on logout),
    # so a logged-out or stolen-then-revoked cookie stops working immediately.
    if int(payload.get("iat", 0)) < int(user.get("token_valid_after", 0)):
        raise HTTPException(status_code=401, detail="Session revoked")
    # Per-device revocation: if the token carries a session id, that session must
    # still be active (lets a user log out one device without ending all of them).
    sid = payload.get("sid")
    if sid:
        if not db.session_active(sid):
            raise HTTPException(status_code=401, detail="Session revoked")
        try:
            db.touch_session(sid, int(time.time()))
        except Exception:
            pass
        user["sid"] = sid
    return user


# ----- request bodies -----

class SignupBody(BaseModel):
    beta_key: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=80)
    email: str
    password: str = Field(min_length=8, max_length=200)
    # Age-requirement attestation collected on the signup form (18+, or 13+ with
    # parental permission). Enforced server-side so it cannot be skipped.
    consent: bool = False


class LoginBody(BaseModel):
    email: str
    password: str
    otp: str | None = None          # 6-digit TOTP code, if MFA is enabled
    recovery: str | None = None     # a one-time recovery code, as a fallback


class ProfileBody(BaseModel):
    age: str | None = None
    experience: str | None = None
    goal: str | None = None
    timeline: str | None = None
    emotional: str | None = None


def _public_user(user: dict) -> dict:
    """Strip secrets (password hash, MFA secret, recovery codes) before sending an
    account back to the browser."""
    _tier = config.tier_for(user["tier"])
    return {
        "email": user["email"],
        "name": user["name"],
        "tier": user["tier"],
        "tier_name": _tier["name"],
        "refresh_min": _tier["refresh_min"],
        "price_display": _tier.get("price_display", ""),
        "a11y": user["a11y"],
        "profile": user["profile"],
        "role": user.get("role", "user"),
        "mfa_enabled": bool(user.get("mfa_enabled", 0)),
    }


def require_role(required: str):
    """Build a dependency that enforces a minimum RBAC role (least privilege)."""
    def _dep(user: dict = Depends(current_user)) -> dict:
        if not security.role_at_least(user.get("role", "user"), required):
            raise HTTPException(status_code=403, detail="Insufficient privileges")
        return user
    return _dep


def _device_of(request: Request) -> str:
    return security.sanitize_text(request.headers.get("user-agent", "Unknown device"), 180)


# ----- endpoints -----

@router.post("/signup")
def signup(body: SignupBody, request: Request, response: Response):
    # Throttle signups per IP so the closed-beta invite key cannot be brute-forced.
    sk = f"signup:{_client_ip(request)}"
    _check_locked(sk, _SIGNUP_MAX_FAILS, _SIGNUP_WINDOW)
    # Single-use invite code. The signup form still calls this field `beta_key`,
    # but it is now matched against the invite_codes table (one account per code)
    # instead of a single shared key. The code is atomically consumed below, after
    # the remaining checks pass.
    code = (body.beta_key or "").strip()
    inv = db.get_invite_code(code)
    if not inv:
        _record_fail(sk)
        raise HTTPException(status_code=403, detail="Invalid invite code")
    if inv.get("used"):
        _record_fail(sk)
        raise HTTPException(status_code=403, detail="That invite code has already been used")
    if not body.consent:
        raise HTTPException(status_code=400, detail="You must confirm you meet the age requirement")
    email = body.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email")
    if db.get_user(email):
        raise HTTPException(status_code=409, detail="An account with that email already exists")
    # Atomically claim the code (single-use, race-safe). If a concurrent request
    # claimed it first, reject this one.
    if not db.consume_invite_code(code, email):
        _record_fail(sk)
        raise HTTPException(status_code=403, detail="That invite code has already been used")
    created = dt.date.today().isoformat()
    # An invite code is a closed-beta invitation, so the new account gets the beta
    # tier (full access) rather than the limited self-serve free tier.
    invite_tier = "beta"
    try:
        db.create_user(email, body.name.strip(), hash_password(body.password), invite_tier, created)
    except sqlite3.IntegrityError:
        # Email taken in the race between the check above and this insert: free the
        # code so it can be retried, and report the real cause.
        db.release_invite_code(code)
        raise HTTPException(status_code=409, detail="An account with that email already exists")
    except Exception:
        # Any other creation failure (e.g. a transient DB error) must also free the
        # code, but should not be mislabeled as a duplicate email.
        db.release_invite_code(code)
        raise HTTPException(status_code=500, detail="Could not create account. Please try again.")
    sid = security.new_session_id()
    db.create_session(sid, email, _device_of(request), _client_ip(request), int(time.time()))
    _set_session_cookie(response, _make_token(email, invite_tier, sid))
    _set_csrf_cookie(response)
    _audit(request, email, "signup", f"account created via invite {code.upper()}")
    return {"user": _public_user(db.get_user(email))}


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response):
    email = body.email.strip().lower()
    ip = _client_ip(request)
    # Two limits: a tight one per (IP + account) to stop hammering one password,
    # and a looser per-IP one to stop spraying many accounts from one source.
    k_user, k_ip = f"login:{ip}:{email}", f"login_ip:{ip}"
    _check_locked(k_user, _LOGIN_MAX_FAILS, _LOGIN_WINDOW)
    _check_locked(k_ip, _LOGIN_IP_MAX_FAILS, _LOGIN_IP_WINDOW)
    user = db.get_user(email)
    # Same generic error whether the email or the password is wrong, so we do not
    # reveal which accounts exist.
    if not user or not verify_password(body.password, user["pass_hash"]):
        _record_fail(k_user)
        _record_fail(k_ip)
        _audit(request, email, "login_fail", "bad password")
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    # Second factor, when the account has MFA enabled.
    if user.get("mfa_enabled"):
        if not body.otp and not body.recovery:
            # Password was correct but a code is needed: tell the client to prompt.
            return {"mfa_required": True}
        ok = bool(body.otp) and security.verify_totp(user.get("mfa_secret") or "", body.otp)
        if not ok and body.recovery:
            ok = _consume_recovery(email, user, body.recovery)
        if not ok:
            _record_fail(k_user)
            _record_fail(k_ip)
            _audit(request, email, "mfa_fail", "bad code")
            raise HTTPException(status_code=401, detail="Invalid authentication code")

    _clear_fails(k_user, k_ip)   # a real login wipes the failure counters
    sid = security.new_session_id()
    db.create_session(sid, email, _device_of(request), _client_ip(request), int(time.time()))
    _set_session_cookie(response, _make_token(email, user["tier"], sid))
    _set_csrf_cookie(response)
    _audit(request, email, "login", "ok")
    return {"user": _public_user(user)}


def _consume_recovery(email: str, user: dict, code: str) -> bool:
    """Check and burn a one-time recovery code (stored only as sha256 hashes)."""
    return db.consume_recovery_code(email, security.hash_code(code))


@router.post("/logout")
def logout(response: Response, tf_session: str | None = Cookie(default=None)):
    # Best-effort revocation: bump the account's token-validity epoch so every
    # outstanding token (including a copy an attacker may hold) is invalidated
    # now, not just at expiry. Then clear the cookie on this browser.
    if tf_session:
        try:
            payload = jwt.decode(tf_session, config.SECRET_KEY, algorithms=["HS256"])
            email = payload.get("sub", "")
            sid = payload.get("sid")
            # Revoke just this device's session if we can; otherwise fall back to
            # the account-wide epoch bump (also revokes any token without a sid).
            if sid:
                db.revoke_session(email, sid)
            elif email and db.get_user(email):
                db.update_token_valid_after(email, int(time.time()))
        except jwt.PyJWTError:
            pass
    response.delete_cookie(COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    """Return the current account, or 401 if not logged in (used on page load)."""
    return {"user": _public_user(user)}


@router.post("/profile")
def save_profile(body: ProfileBody, request: Request, user: dict = Depends(current_user),
                 _csrf: None = Depends(require_csrf)):
    # Hard floor at 13 (ThinkFree is unavailable to children under 13), enforced
    # server-side so the browser check can't be bypassed.
    try:
        age = int(body.age) if body.age is not None else 0
    except (TypeError, ValueError):
        age = 0
    if age < 13:
        raise HTTPException(status_code=400, detail="You must be at least 13 years old to use ThinkFree")
    if age > 120:
        raise HTTPException(status_code=400, detail="Enter a valid age")
    db.update_profile(user["email"], body.model_dump())
    _audit(request, user["email"], "profile_update", "")
    return {"user": _public_user(db.get_user(user["email"]))}


@router.post("/a11y")
def save_a11y(on: bool, user: dict = Depends(current_user), _csrf: None = Depends(require_csrf)):
    db.update_a11y(user["email"], on)
    return {"ok": True}


# ----- MFA (TOTP) enrollment -----

class MfaEnableBody(BaseModel):
    code: str = Field(min_length=6, max_length=8)


@router.post("/mfa/setup")
def mfa_setup(request: Request, user: dict = Depends(current_user), _csrf: None = Depends(require_csrf)):
    """Begin MFA enrollment: generate a secret + recovery codes, store the pending
    secret, and return the otpauth URI and the plaintext recovery codes ONCE."""
    secret = security.gen_totp_secret()
    recovery = security.gen_recovery_codes()
    if not db.begin_mfa_setup(user["email"], secret,
                              json.dumps([security.hash_code(c) for c in recovery])):
        raise HTTPException(status_code=409, detail="MFA is already enabled. Disable it using your current code before setting up a replacement.")
    _audit(request, user["email"], "mfa_setup", "secret issued")
    return {
        "secret": secret,
        "otpauth_uri": security.provisioning_uri(secret, user["email"]),
        "recovery_codes": recovery,   # shown once; only hashes are stored
    }


@router.post("/mfa/enable")
def mfa_enable(body: MfaEnableBody, request: Request, user: dict = Depends(current_user),
               _csrf: None = Depends(require_csrf)):
    """Confirm enrollment by verifying a code against the pending secret."""
    fresh = db.get_user(user["email"])
    if not fresh or not fresh.get("mfa_secret"):
        raise HTTPException(status_code=400, detail="Start MFA setup first")
    factor_key = f"mfa:{user['email']}"
    _check_locked(factor_key, _LOGIN_MAX_FAILS, _LOGIN_WINDOW)
    if not security.verify_totp(fresh["mfa_secret"], body.code):
        _record_fail(factor_key)
        raise HTTPException(status_code=400, detail="That code is not valid. Try again.")
    if not db.confirm_mfa_setup(user["email"], fresh["mfa_secret"]):
        raise HTTPException(status_code=409, detail="MFA setup changed. Start again.")
    _clear_fails(factor_key)
    _audit(request, user["email"], "mfa_enabled", "")
    return {"ok": True, "mfa_enabled": True}


@router.post("/mfa/disable")
def mfa_disable(body: MfaEnableBody, request: Request, user: dict = Depends(current_user),
                _csrf: None = Depends(require_csrf)):
    """Disable MFA. Requires a valid current code so a hijacked session cannot
    silently turn it off."""
    fresh = db.get_user(user["email"])
    if not fresh or not fresh.get("mfa_enabled"):
        return {"ok": True, "mfa_enabled": False}
    factor_key = f"mfa:{user['email']}"
    _check_locked(factor_key, _LOGIN_MAX_FAILS, _LOGIN_WINDOW)
    if not security.verify_totp(fresh.get("mfa_secret") or "", body.code):
        _record_fail(factor_key)
        raise HTTPException(status_code=400, detail="That code is not valid.")
    db.disable_mfa(user["email"])
    _clear_fails(factor_key)
    _audit(request, user["email"], "mfa_disabled", "")
    return {"ok": True, "mfa_enabled": False}


# ----- session / device management -----

class SidBody(BaseModel):
    sid: str = Field(min_length=1, max_length=80)


@router.get("/sessions")
def sessions(user: dict = Depends(current_user)):
    """List the user's active devices, marking which one is the current session."""
    out = db.list_sessions(user["email"])
    for s in out:
        s["current"] = (s["sid"] == user.get("sid"))
    return {"sessions": out}


@router.post("/sessions/revoke")
def revoke_one(body: SidBody, request: Request, user: dict = Depends(current_user),
               _csrf: None = Depends(require_csrf)):
    """Log out a single device (ownership-scoped to the caller)."""
    ok = db.revoke_session(user["email"], body.sid)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    _audit(request, user["email"], "session_revoke", body.sid)
    return {"ok": True}


@router.post("/logout-all")
def logout_all(request: Request, user: dict = Depends(current_user), _csrf: None = Depends(require_csrf)):
    """Log out every other device, keeping the current session active."""
    db.revoke_all_sessions(user["email"], keep_sid=user.get("sid"))
    _audit(request, user["email"], "logout_all", "")
    return {"ok": True}


@router.post("/refresh")
def refresh(request: Request, response: Response, user: dict = Depends(current_user),
            _csrf: None = Depends(require_csrf)):
    """Slide the session forward: re-issue the cookie (and CSRF token) for the
    same active session, extending its expiry without a fresh login."""
    sid = user.get("sid") or security.new_session_id()
    if not db.session_active(sid):
        db.create_session(sid, user["email"], _device_of(request), _client_ip(request), int(time.time()))
    _set_session_cookie(response, _make_token(user["email"], user["tier"], sid))
    _set_csrf_cookie(response)
    return {"ok": True}


# ----- data governance: export + account deletion -----

class DeleteBody(BaseModel):
    confirm: str = Field(min_length=1)


@router.get("/account/export")
def account_export(request: Request, user: dict = Depends(current_user)):
    """GDPR-style export of everything stored about the caller."""
    _audit(request, user["email"], "data_export", "")
    return db.export_user(user["email"])


@router.post("/account/delete")
def account_delete(body: DeleteBody, request: Request, response: Response,
                   user: dict = Depends(current_user), _csrf: None = Depends(require_csrf)):
    """Permanently delete the caller's account. Requires typing DELETE to confirm."""
    if body.confirm.strip().upper() != "DELETE":
        raise HTTPException(status_code=400, detail='Type "DELETE" to confirm account deletion')
    email = user["email"]
    _audit(request, email, "account_delete", "user requested deletion")
    db.delete_user(email)
    response.delete_cookie(COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"ok": True}


# ----- admin: audit access (RBAC, least privilege) -----

@router.get("/admin/audit")
def admin_audit(limit: int = 200, user: dict = Depends(require_role("admin"))):
    """Tamper-evident audit tail, admin only. Reports whether the chain verifies."""
    return {
        "chain_valid": db.verify_audit_chain(security.audit_hash),
        "entries": db.audit_tail(min(max(int(limit), 1), 1000)),
    }
