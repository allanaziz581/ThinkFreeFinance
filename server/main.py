"""main.py

The ThinkFree backend entry point. It does three jobs:

  1. Serves the static front-end shell (HTML/CSS/JS) - but NOT the datasets,
     the Python source, or anything in private_data/.
  2. Mounts the auth and data API routers (real login + gated data).
  3. Adds security headers on every response and blocks direct access to the
     files that used to leak everything (the *_data.js bundles).

Run locally:
  python3 -m venv server/.venv
  server/.venv/bin/pip install -r server/requirements.txt
  cp server/.env.example server/.env   # then edit TF_SECRET_KEY etc.
  server/.venv/bin/uvicorn main:app --app-dir server --reload --port 8000
"""
from __future__ import annotations

import time
from collections import deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

import config
import db
import auth
import data

# Refuse to boot with the placeholder signing key, so a misconfigured production
# deploy fails loudly instead of running with a guessable secret.
if config.PRODUCTION and config.is_placeholder_secret():
    raise RuntimeError("TF_SECRET_KEY is unset/placeholder. Set a strong secret before running in production.")

app = FastAPI(title="ThinkFree Finance", docs_url=None, redoc_url=None, openapi_url=None)

config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
db.init_db()

# Seed an admin account on first boot so the deployed site is immediately usable.
# Idempotent: does nothing if TF_ADMIN_EMAIL / TF_ADMIN_PASSWORD are unset or the
# account already exists. With a persistent disk this runs once and then sticks.
def _seed_admin() -> None:
    email = config._get("TF_ADMIN_EMAIL", "").strip().lower()
    pw = config._get("TF_ADMIN_PASSWORD", "")
    if not email or not pw or db.get_user(email):
        return
    import datetime
    db.create_user(email, "Admin", auth.hash_password(pw), "beta", datetime.date.today().isoformat())
    try:
        db.set_role(email, "admin")
    except Exception:
        # Never log the email or password; a generic signal is enough to flag a
        # seeded-but-not-admin misconfiguration without leaking the credential.
        print("[seed] admin role assignment failed; seeded account exists without admin role")


_seed_admin()


# Closed-beta invite codes (single-use). These are NOT secrets: each code lets one
# person create one account, then is consumed. Seeded idempotently on boot, so they
# persist on the /var/data disk and survive redeploys; INSERT OR IGNORE means a code
# already redeemed is never reset back to unused.
_INVITE_SEED = [
    ("THINKFREE-ETHAN-KL7S", "ethan"),
    ("THINKFREE-GABE-XRNH", "gabe"),
    ("THINKFREE-MORRIGAN-ZNKN", "morrigan"),
    ("THINKFREE-NICOLE-9KLN", "nicole"),
    ("THINKFREE-LENA-XAF6", "lena"),
    ("THINKFREE-ELI-FVN9", "eli"),
    # A dedicated verification code so the signup flow can be tested end to end on
    # the live service without burning one of the six real invitee codes.
    ("THINKFREE-VERIFY-9AGH", "verify"),
]


def _seed_invites() -> None:
    import datetime
    today = datetime.date.today().isoformat()
    for code, name in _INVITE_SEED:
        try:
            db.seed_invite_code(code, name, today)
        except Exception:
            print("[seed] invite-code seed failed for one code; continuing")


_seed_invites()
app.include_router(auth.router)
app.include_router(data.router)
import billing  # noqa: E402  (subscription/billing seam, stubbed, no live payments)
app.include_router(billing.router)

# CORS. With the recommended single-server setup the front-end and API share one
# origin, so the browser never makes a cross-origin call and this is inert (belt
# and suspenders). If you ever serve the front-end from a different domain, set
# TF_ALLOWED_ORIGINS to that exact origin: credentialed CORS requires an explicit
# allow-list (never "*") because the session travels in a cookie.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# Filenames that must never be served directly (they hold the bulk data). Even if
# copies still exist under webapp/js during the migration, the server 404s them so
# the data is only reachable through the authenticated /api/data/* endpoints.
_BLOCKED_SUFFIXES = ("_data.js", "news_intel.js", "member_bills.js")

# Coarse global per-IP request throttle: a baseline against floods, scraping, and
# credential-stuffing bursts that sit underneath the precise per-endpoint limits
# in auth.py. In-memory and per-process (single-worker beta); a multi-worker or
# higher-scale deploy puts the real DDoS/WAF layer at the edge (Cloudflare) and
# moves this to Redis. Generous enough that a normal SPA session never trips it.
_GLOBAL_MAX = 240            # requests
_GLOBAL_WINDOW = 60          # per 60 seconds
_ip_hits: dict[str, deque] = {}


def _throttled(ip: str) -> bool:
    now = time.time()
    dq = _ip_hits.setdefault(ip, deque())
    while dq and now - dq[0] > _GLOBAL_WINDOW:
        dq.popleft()
    if len(dq) >= _GLOBAL_MAX:
        return True
    dq.append(now)
    return False


@app.middleware("http")
async def security_and_blocklist(request: Request, call_next):
    path = request.url.path

    # Global flood protection (skip the health probe so the LB is never throttled).
    if path != "/healthz":
        ip = request.headers.get("x-forwarded-for", "")
        ip = ip.split(",")[0].strip() if ip else (request.client.host if request.client else "unknown")
        if _throttled(ip):
            return JSONResponse({"detail": "Too many requests"}, status_code=429,
                                headers={"Retry-After": str(_GLOBAL_WINDOW)})

    # 0) In production, force HTTPS. Behind a TLS-terminating host (Render/Railway/
    #    Cloudflare) the original scheme arrives in X-Forwarded-Proto; if it is
    #    plain http, redirect to the https URL. We default to "https" when the
    #    header is absent so we never loop on a direct https hit, and we exempt the
    #    health check so the load balancer's probe is never redirected.
    if config.PRODUCTION and path != "/healthz":
        proto = request.headers.get("x-forwarded-proto", "https").split(",")[0].strip()
        if proto == "http":
            return RedirectResponse(str(request.url.replace(scheme="https")), status_code=308)

    # 1) Never serve the raw dataset files, regardless of where they sit on disk.
    if path.startswith("/js/") and path.endswith(_BLOCKED_SUFFIXES):
        return JSONResponse({"detail": "Not found"}, status_code=404)

    response = await call_next(request)

    # 2) Apply hardening headers to every response.
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # Scripts only from our own origin; inline styles are allowed because the UI
    # uses many style="" attributes. Images may come from data: URIs and https.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; connect-src 'self' https://dns.google; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
    )
    if config.PRODUCTION:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Static assets: the UI's CSS and logic JS (the data files are blocked above).
app.mount("/css", StaticFiles(directory=config.WEBAPP_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=config.WEBAPP_DIR / "js"), name="js")


@app.get("/healthz")
def healthz():
    """Simple liveness check for the host/load balancer."""
    return {"ok": True}


@app.get("/api/healthz")
def api_healthz():
    """Same liveness check under /api. The front-end's boot.js probes this exact
    path to decide server vs static mode, so it must answer ok in server mode."""
    return {"ok": True}


@app.get("/")
def index():
    """Serve the app shell. The shell contains no data and no secrets; it fetches
    everything from the gated /api/* endpoints after the user logs in."""
    return FileResponse(config.WEBAPP_DIR / "index.html")
