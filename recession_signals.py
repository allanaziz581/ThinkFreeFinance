#!/usr/bin/env python3
"""
ThinkFree Finance — Recession Signals Engine (Phase 13)

Downloads publicly available macro indicators and produces a plain-English
recession risk score from 0 (no risk) to 10 (very high risk).

Indicators used:
  - Yield curve: 10-year vs 3-month Treasury spread (via yfinance)
  - VIX: market stress/fear index (via yfinance)
  - FRED data: unemployment rate, GDP growth (requires FRED_API_KEY in .env)

Output: recession_signals_output.json
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
OUTPUT_PATH = BASE_DIR / "recession_signals_output.json"


# ------------------------------------------------------------------
# Data fetchers
# ------------------------------------------------------------------

def fetch_yield_curve() -> dict:
    """Return 10yr yield, 3mo yield, and the spread between them."""
    try:
        raw = yf.download(["^TNX", "^IRX"], period="3mo", interval="1d", progress=False)
        if raw.empty:
            return {"ten_year": None, "three_month": None, "spread": None, "inverted": False}

        close = raw["Close"] if "Close" in raw.columns else raw.xs("Close", axis=1, level=0)
        if isinstance(close, pd.Series):
            close = close.to_frame()

        ten_yr = float(close["^TNX"].dropna().iloc[-1]) if "^TNX" in close.columns else None
        three_mo = float(close["^IRX"].dropna().iloc[-1]) if "^IRX" in close.columns else None

        if ten_yr is None or three_mo is None:
            return {"ten_year": ten_yr, "three_month": three_mo, "spread": None, "inverted": False}

        spread = ten_yr - three_mo
        return {
            "ten_year": round(ten_yr, 3),
            "three_month": round(three_mo, 3),
            "spread": round(spread, 3),
            "inverted": spread < 0,
        }
    except Exception as e:
        print(f"[WARN] Yield curve fetch failed: {e}")
        return {"ten_year": None, "three_month": None, "spread": None, "inverted": False}


def fetch_vix() -> dict:
    """Return current VIX level and a stress category."""
    try:
        vix_data = yf.download("^VIX", period="5d", interval="1d", progress=False)
        if vix_data.empty:
            return {"vix": None, "stress_level": "Unknown"}

        close = vix_data["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        vix = float(close.dropna().iloc[-1])

        if vix < 15:
            stress = "Low — markets are calm"
        elif vix < 20:
            stress = "Normal — typical market conditions"
        elif vix < 30:
            stress = "Elevated — investors are nervous"
        elif vix < 40:
            stress = "High — significant market stress"
        else:
            stress = "Extreme — market panic conditions"

        return {"vix": round(vix, 2), "stress_level": stress}
    except Exception as e:
        print(f"[WARN] VIX fetch failed: {e}")
        return {"vix": None, "stress_level": "Unknown"}


def _fetch_fred_csv(series_id: str) -> "pd.Series | None":
    """Fetch a FRED series from the public CSV endpoint (no API key needed)."""
    import io
    import requests as _req
    import pandas as pd
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        resp = _req.get(url, timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        # FRED CSV columns: observation_date, <SERIES_ID>
        df.columns = ["date", "value"]
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df["value"].dropna()
    except Exception as e:
        print(f"[WARN] FRED CSV {series_id}: {e}")
        return None


def fetch_fred_indicators() -> dict:
    """Fetch unemployment and GDP — uses public FRED CSV first, API key as fallback."""
    # Try public CSV (no key needed)
    try:
        unrate_series = _fetch_fred_csv("UNRATE")
        gdp_series    = _fetch_fred_csv("A191RL1Q225SBEA")

        unemployment = float(unrate_series.iloc[-1]) if unrate_series is not None and len(unrate_series) >= 1 else None
        unemp_prev   = float(unrate_series.iloc[-2]) if unrate_series is not None and len(unrate_series) >= 2 else None
        unemp_rising = (unemployment > unemp_prev) if (unemployment and unemp_prev) else False

        gdp_growth   = float(gdp_series.iloc[-1]) if gdp_series is not None and len(gdp_series) >= 1 else None
        gdp_negative = (gdp_growth is not None and gdp_growth < 0)

        if unemployment is not None:
            return {
                "available": True,
                "unemployment_rate": unemployment,
                "unemployment_rising": unemp_rising,
                "gdp_growth": gdp_growth,
                "gdp_negative": gdp_negative,
            }
    except Exception as e:
        print(f"[WARN] Public FRED CSV fetch failed: {e}")

    # Try API key if available
    fred_key = os.getenv("FRED_API_KEY", "")
    if fred_key:
        try:
            from fredapi import Fred
            fred = Fred(api_key=fred_key)
            unrate = fred.get_series("UNRATE", limit=3)
            unemployment = float(unrate.iloc[-1]) if not unrate.empty else None
            unemp_prev = float(unrate.iloc[-2]) if len(unrate) >= 2 else None
            unemp_rising = (unemployment > unemp_prev) if (unemployment and unemp_prev) else False
            gdp = fred.get_series("A191RL1Q225SBEA", limit=4)
            gdp_growth = float(gdp.iloc[-1]) if not gdp.empty else None
            gdp_negative = (gdp_growth is not None and gdp_growth < 0)
            return {
                "available": True,
                "unemployment_rate": unemployment,
                "unemployment_rising": unemp_rising,
                "gdp_growth": gdp_growth,
                "gdp_negative": gdp_negative,
            }
        except Exception as e:
            print(f"[WARN] FRED API fetch failed: {e}")

    return {"available": False, "unemployment_rate": None, "gdp_growth": None}


# ------------------------------------------------------------------
# Scoring
# ------------------------------------------------------------------

def compute_recession_score(yield_curve: dict, vix_data: dict, fred: dict) -> dict:
    """
    Score recession risk 0–10 based on available indicators.
    Each indicator contributes points toward the total.
    """
    score = 0.0
    max_possible = 0.0
    factors = []

    def clamp(x, lo=0.0, hi=1.0):
        return max(lo, min(hi, x))

    # ── Yield curve (up to 4 pts — strongest predictor) ───────────────
    # Graduated: deeply inverted is worst, but a flattening / recently
    # un-inverted curve (low positive spread) still carries real risk and
    # should NOT score zero. Healthy = spread comfortably above ~1.3%.
    if yield_curve.get("spread") is not None:
        max_possible += 4
        spread = yield_curve["spread"]
        if yield_curve.get("inverted"):
            curve_score = min(4.0, 4.0 * (abs(spread) / 1.5))
            score += curve_score
            factors.append(
                f"The yield curve is INVERTED (spread: {spread:.2f}%). "
                "Short-term borrowing costs more than long-term — historically one "
                "of the most reliable early warning signs of a recession."
            )
        else:
            # Risk decays from 1.0 at spread=0 to 0.0 at spread>=1.3
            curve_risk = clamp((1.3 - spread) / 1.3)
            curve_score = round(4.0 * curve_risk, 2)
            score += curve_score
            if spread < 0.5:
                factors.append(
                    f"The yield curve is very flat (spread: {spread:.2f}%). "
                    "Borrowing costs are nearly equal for short and long-term debt — "
                    "a warning sign worth watching."
                )
            elif spread < 1.0:
                factors.append(
                    f"The yield curve is flattening (spread: {spread:.2f}%). "
                    "It is positive but historically narrow — when a curve steepens "
                    "back up after an inversion, recessions have often followed."
                )
            else:
                factors.append(
                    f"The yield curve is normal (spread: {spread:.2f}%). "
                    "Long-term borrowing costs more than short-term, which is healthy."
                )

    # ── VIX (up to 3 pts) — graduated, no hard cliff at 20 ────────────
    if vix_data.get("vix") is not None:
        max_possible += 3
        vix = vix_data["vix"]
        # 0 risk at/below 14, full risk at/above 40
        vix_risk = clamp((vix - 14) / (40 - 14))
        score += round(3.0 * vix_risk, 2)
        if vix >= 30:
            factors.append(f"Market fear (VIX: {vix}) is very high — significant investor anxiety.")
        elif vix >= 20:
            factors.append(f"Market anxiety (VIX: {vix}) is elevated.")
        elif vix >= 16:
            factors.append(f"Market volatility (VIX: {vix}) is creeping above its calm baseline.")
        else:
            factors.append(f"Markets are calm (VIX: {vix}) — no major fear signals.")

    # ── FRED indicators (up to 3 pts if available) ────────────────────
    if fred.get("available"):
        max_possible += 3
        unemp = fred.get("unemployment_rate")
        unemp_rising = fred.get("unemployment_rising", False)
        gdp = fred.get("gdp_growth")
        gdp_neg = fred.get("gdp_negative", False)

        # GDP: stall-speed matters, not just negative. Trend growth ~2.2%.
        # Risk: 0 at >=2.5%, scales up below that, max below 0.
        if gdp is not None:
            if gdp_neg:
                score += 1.5
                factors.append(
                    f"GDP growth is negative ({gdp}%) — the economy actually shrank. "
                    "Two quarters of this officially defines a recession."
                )
            else:
                gdp_risk = clamp((2.5 - gdp) / 2.5)  # 1.6% -> 0.36
                score += round(1.5 * gdp_risk, 2)
                if gdp < 2.0:
                    factors.append(
                        f"GDP growth is {gdp}% — below the ~2% trend. Sustained "
                        "'stall speed' growth has historically preceded recessions."
                    )
                else:
                    factors.append(f"GDP growth is {gdp}% — at or above trend, which is healthy.")

        # Unemployment: graduated. Rising matters even below 5% (Sahm-style).
        if unemp is not None:
            if unemp_rising and unemp > 5.0:
                score += 1.5
                factors.append(
                    f"Unemployment is rising and sits at {unemp}%. When businesses "
                    "start laying people off, spending slows and recessions deepen."
                )
            elif unemp_rising:
                score += 0.75
                factors.append(
                    f"Unemployment ({unemp}%) is ticking up. Even small sustained "
                    "increases off the lows are an early recession signal."
                )
            else:
                # Level-based floor: above ~4.5% adds mild risk even if flat.
                level_risk = clamp((unemp - 4.5) / 2.0)
                score += round(0.75 * level_risk, 2)
                factors.append(f"Unemployment ({unemp}%) is stable.")
    else:
        factors.append(
            "FRED economic data (unemployment, GDP) not available. "
            "Add a free FRED_API_KEY to .env for a more complete score."
        )

    # Normalize to 0–10
    if max_possible > 0:
        normalized = round((score / max_possible) * 10, 1)
    else:
        normalized = 0.0

    # Label
    if normalized <= 2:
        label = "Low"
        plain = "The economy shows no significant recession warning signs right now."
    elif normalized <= 4:
        label = "Moderate"
        plain = "There are some warning signs but no imminent recession signal. Worth keeping an eye on."
    elif normalized <= 6:
        label = "Elevated"
        plain = "Multiple warning signs are flashing. The economy may be slowing down more than usual."
    elif normalized <= 8:
        label = "High"
        plain = "Strong recession indicators present. Historically, conditions like these have preceded downturns."
    else:
        label = "Very High"
        plain = "Almost all recession warning signals are active. The risk of a serious economic slowdown is significant."

    return {
        "score": normalized,
        "max_score": 10,
        "label": label,
        "plain_english_summary": plain,
        "factors": factors,
    }


# ------------------------------------------------------------------
# Life impact translation
# ------------------------------------------------------------------

def explain_real_world_impact(score: float, yield_inverted: bool, vix: float | None) -> dict:
    """Translate recession risk into plain-English personal finance impacts."""
    if score <= 3:
        return {
            "mortgages": "No immediate concern. Fixed rates are relatively stable.",
            "credit_cards": "No major rate changes expected in the near term.",
            "jobs": "Job market remains relatively healthy.",
            "groceries_gas": "No recession-driven price pressure detected.",
            "savings": "A good time to build your emergency fund — always valuable regardless of conditions.",
        }
    elif score <= 6:
        return {
            "mortgages": (
                "If you have a variable-rate mortgage, be aware that rate uncertainty is elevated. "
                "Consider whether locking into a fixed rate makes sense for your situation."
            ),
            "credit_cards": (
                "Credit card interest rates tend to stay high during uncertain periods. "
                "Paying down high-interest debt is a smart defensive move."
            ),
            "jobs": (
                "Some sectors may start slowing hiring. Job security varies widely by industry. "
                "Healthcare, utilities, and essential services tend to be more stable."
            ),
            "groceries_gas": (
                "Economic slowdowns can cut both ways — sometimes prices fall as demand drops, "
                "but supply disruptions can keep them elevated. No clear direction right now."
            ),
            "savings": (
                "Building 3-6 months of emergency savings becomes more important as uncertainty rises. "
                "High-yield savings accounts and short-term CDs are worth considering."
            ),
        }
    else:
        return {
            "mortgages": (
                "Recession conditions can sometimes lead to rate cuts (which help) or tighter lending standards (which hurt). "
                "If you have variable-rate debt, talk to your lender about your options."
            ),
            "credit_cards": (
                "In serious downturns, credit becomes harder to get and more expensive. "
                "Reducing reliance on credit cards and building cash reserves is advisable."
            ),
            "jobs": (
                "Layoffs typically accelerate in high-risk recession environments. "
                "Updating your resume and expanding your professional network is always a good idea during uncertain times."
            ),
            "groceries_gas": (
                "Severe recessions often cause sharp swings in commodity prices. "
                "Energy costs can fall significantly if demand drops, but food prices are stickier."
            ),
            "savings": (
                "Cash is king in a recession. Building your emergency fund now, before conditions worsen, "
                "gives you the most options and the most security."
            ),
        }


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def run_recession_signals() -> dict:
    print("=== ThinkFree — Recession Signals Engine ===")
    print("Fetching yield curve data...")
    yield_curve = fetch_yield_curve()

    print("Fetching VIX (market fear index)...")
    vix_data = fetch_vix()

    print("Fetching FRED economic indicators...")
    fred = fetch_fred_indicators()

    print("Computing recession risk score...")
    score_data = compute_recession_score(yield_curve, vix_data, fred)

    real_world = explain_real_world_impact(
        score=score_data["score"],
        yield_inverted=yield_curve.get("inverted", False),
        vix=vix_data.get("vix"),
    )

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "recession_risk": score_data,
        "raw_indicators": {
            "yield_curve": yield_curve,
            "vix": vix_data,
            "fred": fred,
        },
        "real_world_impact": real_world,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nRecession Risk Score: {score_data['score']}/10 — {score_data['label']}")
    print(f"{score_data['plain_english_summary']}")
    print(f"\nSaved to: {OUTPUT_PATH}")

    return output


if __name__ == "__main__":
    run_recession_signals()
