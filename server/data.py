"""data.py

Gated data endpoints. The large datasets that used to ship as public
webapp/js/*_data.js files now live in private_data/ (never web-served) and are
returned here only to a logged-in user. An anonymous visitor gets 401, so the
data cannot be scraped without an account.

Endpoint map:
  GET /api/data/bundle  -> all "core" datasets the dashboard needs up front
  GET /api/data/state   -> the large LegiScan + Open States datasets (lazy)
  GET /api/data/live     -> prices + news, rate-limited per tier, paused when the
                            market is closed for lower tiers (server-enforced)

Everything requires a valid session cookie via the current_user dependency.
"""
from __future__ import annotations

import datetime as dt
import json
import time
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Response

import config
import db
from auth import current_user

router = APIRouter(prefix="/api/data", tags=["data"])


def _effective_tier(user: dict) -> dict:
    """Resolve the user's tier from the DATABASE, not the signed token.

    The token carries the tier the user had at login; reading the live DB row
    here means an upgrade takes effect immediately and, more importantly, a
    downgrade (or a billing lapse) cannot be retained by replaying an older
    token that still says a higher tier. Falls back to the token's tier, then
    the default tier, if the row is somehow unavailable.
    """
    fresh = db.get_user(user["email"]) or {}
    key = fresh.get("tier") or user.get("tier") or config.DEFAULT_TIER
    return config.tier_for(key)


def _manifest() -> dict:
    path = config.PRIVATE_DATA_DIR / "manifest.json"
    if not path.exists():
        raise HTTPException(status_code=503, detail="Data not built yet. Run scripts/extract_data_to_json.py")
    return json.loads(path.read_text())


@lru_cache(maxsize=64)
def _load(global_name: str) -> str:
    """Read one dataset's JSON text from disk, cached in memory after first use.

    Returns the raw JSON string (not parsed) so we can hand it straight to the
    client without a parse/re-serialize round trip.

    Prefers a fresher copy written by the in-process background refresher to the
    persistent disk (e.g. ECONOMY), so the site serves the latest pull without a
    redeploy. The refresher clears this cache after each write. global_name is an
    internal manifest key, never request input, so the path join is not
    attacker-controllable.
    """
    fresh = config.DB_PATH.parent / "refresh" / f"{global_name}.json"
    if fresh.exists():
        try:
            return fresh.read_text()
        except OSError:
            pass
    path = config.PRIVATE_DATA_DIR / f"{global_name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Unknown dataset: {global_name}")
    return path.read_text()


def _bundle_json(names: list[str]) -> str:
    """Build a single JSON object mapping each global name to its dataset."""
    parts = [f"{json.dumps(name)}:{_load(name)}" for name in names]
    return "{" + ",".join(parts) + "}"


def _market_open(now: dt.datetime | None = None) -> bool:
    """US equity hours: Mon-Fri 09:30-16:00 America/New_York (DST-aware)."""
    try:
        from zoneinfo import ZoneInfo
        now = now or dt.datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return True  # if tz data is missing, do not block refreshes
    if now.weekday() >= 5:  # Saturday/Sunday
        return False
    minutes = now.hour * 60 + now.minute
    return 570 <= minutes < 960


# In-memory record of when each user last pulled /live, to enforce tier cadence.
# A real deployment behind multiple workers would move this to Redis; for a
# single-process beta this is sufficient and cannot be bypassed from the browser.
_last_live: dict[str, float] = {}


@router.get("/bundle")
def bundle(user: dict = Depends(current_user)):
    """Core datasets needed to render the app once the user is logged in."""
    m = _manifest()
    return Response(content=_bundle_json(m["core"]), media_type="application/json")


@router.get("/state")
def state(user: dict = Depends(current_user)):
    """Large LegiScan + Open States datasets, loaded lazily on first State view."""
    m = _manifest()
    return Response(content=_bundle_json(m["lazy"]), media_type="application/json")


@router.get("/tiers")
def tiers():
    """Public pricing catalogue for the upgrade UI.

    Unauthenticated on purpose: this is marketing/pricing metadata (names,
    cadence, prices), nothing account-specific or secret. It is the single
    source of truth the front-end renders, so client and server never drift.
    """
    return {"tiers": config.public_tiers(), "default": config.DEFAULT_TIER}


@router.get("/live")
def live(user: dict = Depends(current_user)):
    """Fresh prices + news, gated by the user's tier cadence and market hours."""
    tier = _effective_tier(user)   # authoritative tier from the DB, not the token
    refresh_min = tier["refresh_min"]

    # Lower tiers (slower than 30 min) make no fresh pull while the market is
    # closed; premium fast tiers keep updating after hours.
    if refresh_min > 30 and not _market_open():
        return {"paused": True, "reason": "market_closed"}

    # Enforce the per-tier cadence on the server so it cannot be sped up by
    # editing the browser. Return 429 with how long to wait.
    now = time.time()
    last = _last_live.get(user["email"], 0.0)
    wait = refresh_min * 60 - (now - last)
    if wait > 0:
        raise HTTPException(status_code=429, detail=f"Refresh available in {int(wait)}s", headers={"Retry-After": str(int(wait))})
    _last_live[user["email"]] = now

    m = _manifest()
    return Response(content=_bundle_json(m["live"]), media_type="application/json")
