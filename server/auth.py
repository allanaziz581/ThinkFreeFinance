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
import re
import time
from collections import deque

import bcrypt
import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

import config
import db

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "tf_session"
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
    """Best-effort client IP. Honors the first X-Forwarded-For hop set by the
    host's proxy (Render/Railway/Cloudflare), falling back to the socket peer."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


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

def _make_token(email: str, tier: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": email,
        "tier": tier,
        "iat": now,
        "exp": now + dt.timedelta(seconds=config.SESSION_TTL_SECONDS),
    }
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


class ProfileBody(BaseModel):
    age: str | None = None
    experience: str | None = None
    goal: str | None = None
    timeline: str | None = None
    emotional: str | None = None


def _public_user(user: dict) -> dict:
    """Strip the password hash before sending an account back to the browser."""
    return {
        "email": user["email"],
        "name": user["name"],
        "tier": user["tier"],
        "tier_name": config.TIERS.get(user["tier"], {}).get("name", user["tier"]),
        "a11y": user["a11y"],
        "profile": user["profile"],
    }


# ----- endpoints -----

@router.post("/signup")
def signup(body: SignupBody, request: Request, response: Response):
    # Throttle signups per IP so the closed-beta invite key cannot be brute-forced.
    sk = f"signup:{_client_ip(request)}"
    _check_locked(sk, _SIGNUP_MAX_FAILS, _SIGNUP_WINDOW)
    # Constant-time compare so the beta key cannot be guessed by timing.
    if not hmac.compare_digest(body.beta_key.strip(), config.BETA_KEY):
        _record_fail(sk)
        raise HTTPException(status_code=403, detail="Invalid beta invite key")
    if not body.consent:
        raise HTTPException(status_code=400, detail="You must confirm you meet the age requirement")
    email = body.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email")
    if db.get_user(email):
        raise HTTPException(status_code=409, detail="An account with that email already exists")
    created = dt.date.today().isoformat()
    db.create_user(email, body.name.strip(), hash_password(body.password), config.DEFAULT_TIER, created)
    token = _make_token(email, config.DEFAULT_TIER)
    _set_session_cookie(response, token)
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
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    _clear_fails(k_user, k_ip)   # a real login wipes the failure counters
    token = _make_token(email, user["tier"])
    _set_session_cookie(response, token)
    return {"user": _public_user(user)}


@router.post("/logout")
def logout(response: Response, tf_session: str | None = Cookie(default=None)):
    # Best-effort revocation: bump the account's token-validity epoch so every
    # outstanding token (including a copy an attacker may hold) is invalidated
    # now, not just at expiry. Then clear the cookie on this browser.
    if tf_session:
        try:
            payload = jwt.decode(tf_session, config.SECRET_KEY, algorithms=["HS256"])
            email = payload.get("sub", "")
            if email and db.get_user(email):
                db.update_token_valid_after(email, int(time.time()))
        except jwt.PyJWTError:
            pass
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    """Return the current account, or 401 if not logged in (used on page load)."""
    return {"user": _public_user(user)}


@router.post("/profile")
def save_profile(body: ProfileBody, user: dict = Depends(current_user)):
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
    return {"user": _public_user(db.get_user(user["email"]))}


@router.post("/a11y")
def save_a11y(on: bool, user: dict = Depends(current_user)):
    db.update_a11y(user["email"], on)
    return {"ok": True}
