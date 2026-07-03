#!/usr/bin/env python3
"""
ThinkFree Finance, QuantLib Metrics Engine (Phase 8 Enhancement)

Uses QuantLib to compute risk-adjusted opportunity metrics:
  1. Annualized historical volatility from price history
  2. Historical frequency of a 5% monthly move (fraction of past rolling 21-day windows
     over ~5 years). Replaces the old Black-Scholes N(d2) risk-neutral probability, which
     is not a real-world probability and is no longer reported.
  3. Lognormal expected price E[S_T] = spot * exp(r * T)
  4. Value at Risk (VaR) at 95% confidence (parametric and historical)

Kelly position sizing is computed internally but is NOT reported to users anywhere.
Falls back to numpy-only equivalents if QuantLib has issues.

Falls back to numpy-only equivalents if QuantLib has issues.

Output: quantlib_metrics.json, merged into opportunity_scores.json by controller.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, date
from pathlib import Path
from typing import Any

import numpy as np

try:
    import QuantLib as ql
    _QL_AVAILABLE = True
except ImportError:
    _QL_AVAILABLE = False

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False

BASE_DIR    = Path(__file__).parent
OUTPUT_PATH = BASE_DIR / "quantlib_metrics.json"

from constants import RISK_FREE_RATE, KELLY_CAP  # single shared risk-free rate (^IRX)

LOOKBACK_DAYS  = 252      # 1 trading year
TARGET_HORIZON = 21       # 1 calendar month (~21 trading days)


# ── Volatility ─────────────────────────────────────────────────────────────────

def compute_annualized_vol(prices: list[float]) -> float:
    """Annualized historical volatility from daily log returns."""
    if len(prices) < 10:
        return 0.30  # default 30% vol if insufficient data
    arr    = np.array(prices, dtype=float)
    log_r  = np.diff(np.log(arr))
    log_r  = log_r[np.isfinite(log_r)]
    if len(log_r) < 5:
        return 0.30
    return float(np.std(log_r, ddof=1) * math.sqrt(252))


# ── Black-Scholes probability of profit ────────────────────────────────────────

def historical_move_frequency(
    prices: list[float],
    horizon_days: int = TARGET_HORIZON,
    threshold: float = 0.05,
    direction: str = "up",
) -> tuple[float | None, int]:
    """Empirical fraction of past rolling `horizon_days` windows that met the threshold.

    direction 'up':   window return >= +threshold
    direction 'down': window return <= -threshold

    This is a plain historical count over the supplied series (intended to be 5+ years),
    NOT a model. It replaces the Black-Scholes N(d2) risk-neutral probability, which is an
    option-pricing artifact (it prices under the risk-neutral measure at the risk-free
    drift) and is not the real-world chance of a move. Returns (frequency, n_windows);
    frequency is None when there are too few windows. No confidence interval is produced.
    """
    s = [float(p) for p in prices]
    n = len(s)
    if n <= horizon_days:
        return (None, 0)
    hits = 0
    total = 0
    for i in range(n - horizon_days):
        if s[i] <= 0:
            continue
        r = s[i + horizon_days] / s[i] - 1.0
        total += 1
        if direction == "up" and r >= threshold:
            hits += 1
        elif direction == "down" and r <= -threshold:
            hits += 1
    if total == 0:
        return (None, 0)
    return (hits / total, total)


def bs_prob_above_target(
    spot: float,
    target: float,
    vol: float,
    risk_free: float = RISK_FREE_RATE,
    time_years: float = TARGET_HORIZON / 252,
) -> float:
    """DEPRECATED, NOT displayed. Risk-neutral N(d2) probability that price exceeds
    `target` at expiry. This is an option-pricing artifact under the risk-neutral measure,
    not a real-world probability, so it is no longer surfaced to users anywhere. Kept only
    so nothing that still imports it breaks; use historical_move_frequency() instead.
    """
    if spot <= 0 or target <= 0 or vol <= 0 or time_years <= 0:
        return 0.5

    if _QL_AVAILABLE:
        try:
            today = ql.Date.todaysDate()
            expiry = today + int(time_years * 365)
            ql.Settings.instance().evaluationDate = today

            spot_h   = ql.SimpleQuote(spot)
            vol_h    = ql.SimpleQuote(vol)
            rate_h   = ql.SimpleQuote(risk_free)
            div_h    = ql.SimpleQuote(0.0)

            day_count = ql.Actual365Fixed()
            calendar  = ql.UnitedStates(ql.UnitedStates.NYSE)

            spot_ts = ql.QuoteHandle(spot_h)
            vol_ts  = ql.BlackVolTermStructureHandle(
                ql.BlackConstantVol(today, calendar, ql.QuoteHandle(vol_h), day_count)
            )
            rate_ts = ql.YieldTermStructureHandle(
                ql.FlatForward(today, ql.QuoteHandle(rate_h), day_count)
            )
            div_ts  = ql.YieldTermStructureHandle(
                ql.FlatForward(today, ql.QuoteHandle(div_h), day_count)
            )

            process = ql.BlackScholesMertonProcess(spot_ts, div_ts, rate_ts, vol_ts)
            payoff  = ql.PlainVanillaPayoff(ql.Option.Call, target)
            exercise = ql.EuropeanExercise(expiry)
            option  = ql.VanillaOption(payoff, exercise)
            engine  = ql.AnalyticEuropeanEngine(process)
            option.setPricingEngine(engine)

            # N(d2) = risk-neutral probability of S_T > K
            d1 = (math.log(spot / target) + (risk_free + 0.5 * vol**2) * time_years) / (vol * math.sqrt(time_years))
            d2 = d1 - vol * math.sqrt(time_years)
            from scipy.special import ndtr
            return float(ndtr(d2))

        except Exception:
            pass

    # Numpy fallback
    d1 = (math.log(spot / target) + (risk_free + 0.5 * vol**2) * time_years) / (vol * math.sqrt(time_years))
    d2 = d1 - vol * math.sqrt(time_years)
    return float(_norm_cdf(d2))


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# ── VaR ────────────────────────────────────────────────────────────────────────

def compute_var_95(prices: list[float]) -> float:
    """Daily 95% PARAMETRIC Value at Risk (fraction of position), under the NORMAL
    assumption: 1.645 * daily_vol. Normal VaR understates fat left tails; pair it
    with historical_var_95() below, and label it as the normal assumption in output."""
    vol = compute_annualized_vol(prices)
    daily_vol = vol / math.sqrt(252)
    return round(1.645 * daily_vol, 4)


def historical_var_95(prices: list[float]) -> float:
    """Daily 95% HISTORICAL-SIMULATION VaR (fraction of position): the empirical 5th
    percentile of actual daily returns, reported as a positive loss magnitude. Makes
    no distributional assumption, so it captures fat tails the parametric VaR misses."""
    if len(prices) < 10:
        return 0.025
    arr = np.array(prices, dtype=float)
    rets = np.diff(arr) / arr[:-1]
    rets = rets[np.isfinite(rets)]
    if len(rets) < 5:
        return 0.025
    q05 = float(np.percentile(rets, 5))     # 5th percentile of returns (a loss)
    return round(abs(min(q05, 0.0)), 4)


# ── Expected return under lognormal ────────────────────────────────────────────

def expected_return_lognormal(
    spot: float,
    vol: float,
    risk_free: float = RISK_FREE_RATE,
    horizon_years: float = TARGET_HORIZON / 252,
) -> float:
    """Expected (MEAN) price under the risk-neutral lognormal model: E[S_T] = S*exp(r*T).

    The old code returned S*exp((r - 0.5*vol^2)*T), which is the MEDIAN (the drift of
    log S), not the mean. For high vol that median falls below spot even when r > 0,
    which injected a spurious downward / SELL bias into the expected-return figure.
    The arithmetic mean of a lognormal is S*exp(r*T); the -0.5*vol^2 term cancels.
    """
    if spot <= 0 or vol <= 0:
        return spot
    return spot * math.exp(risk_free * horizon_years)


def median_price_path_lognormal(
    spot: float,
    vol: float,
    risk_free: float = RISK_FREE_RATE,
    horizon_years: float = TARGET_HORIZON / 252,
) -> float:
    """The MEDIAN lognormal path: S*exp((r - 0.5*vol^2)*T). Kept explicitly labeled
    for anywhere that genuinely wants the median rather than the mean."""
    if spot <= 0 or vol <= 0:
        return spot
    return spot * math.exp((risk_free - 0.5 * vol ** 2) * horizon_years)


# ── Kelly criterion ─────────────────────────────────────────────────────────────

def _kelly_raw(prices: list[float], risk_free: float = RISK_FREE_RATE) -> float:
    """Full continuous Kelly fraction f* = (mu - r) / sigma^2 from historical log
    returns. No fraction and no cap; those are applied by kelly_fraction()."""
    if len(prices) < 10:
        return 0.0
    import numpy as _np
    log_rets = _np.diff(_np.log(prices))
    mu_annual    = float(_np.mean(log_rets)) * 252
    sigma_annual = float(_np.std(log_rets, ddof=1)) * math.sqrt(252)
    if sigma_annual <= 0:
        return 0.0
    return (mu_annual - risk_free) / (sigma_annual ** 2)


def kelly_fraction(prices: list[float], risk_free: float = RISK_FREE_RATE) -> float:
    """Reported QUARTER-Kelly: the full f* is divided by 4 FIRST, then capped at
    KELLY_CAP. The old code did min(cap, f*), which is NOT quarter-Kelly: a full f*
    of 0.8 was reported as the 0.25 cap instead of 0.8/4 = 0.20. Quarter-Kelly is the
    conservative sizing convention, so scale then cap.
    """
    f_quarter = max(0.0, _kelly_raw(prices, risk_free) / 4.0)
    return min(KELLY_CAP, f_quarter)


# ── Fetch prices ───────────────────────────────────────────────────────────────

def fetch_recent_prices(ticker: str, days: int = LOOKBACK_DAYS) -> list[float]:
    if not _YF_AVAILABLE:
        return []
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty:
            return []
        close = df["Close"]
        if hasattr(close, "squeeze"):
            close = close.squeeze()
        prices = [float(p) for p in close.dropna().tolist()]
        return prices[-days:]
    except Exception:
        return []


def fetch_history(ticker: str, period: str = "5y") -> list[float]:
    """Full daily close series over `period` (default 5 years) for the historical-frequency
    calculation, which needs a long real-world sample rather than the 1-year vol window."""
    if not _YF_AVAILABLE:
        return []
    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty:
            return []
        close = df["Close"]
        if hasattr(close, "squeeze"):
            close = close.squeeze()
        return [float(p) for p in close.dropna().tolist()]
    except Exception:
        return []


# ── Per-ticker QuantLib metrics ────────────────────────────────────────────────

def compute_ticker_metrics(ticker: str, signal: dict) -> dict:
    prices = fetch_recent_prices(ticker)

    if len(prices) >= 10:
        spot    = prices[-1]
        vol     = compute_annualized_vol(prices)
        var_95  = compute_var_95(prices)
        exp_price = expected_return_lognormal(spot, vol)
        exp_return_pct = ((exp_price / spot) - 1) * 100 if spot > 0 else 0.0
    else:
        spot, vol, var_95 = 0.0, 0.30, 0.025
        exp_return_pct = 0.0

    # Real-world historical frequency over 5 years (NOT the N(d2) risk-neutral prob).
    history = fetch_history(ticker, period="5y")
    freq_up, n_up = historical_move_frequency(history, TARGET_HORIZON, 0.05, "up")
    freq_down, _  = historical_move_frequency(history, TARGET_HORIZON, 0.05, "down")
    lookback_years = round(len(history) / 252, 1) if history else 0.0

    final_sig = signal.get("final_signal", "HOLD")

    return {
        "ticker":                  ticker,
        "current_price":           round(spot, 2),
        "annualized_volatility":   round(vol * 100, 1),         # as %
        "var_95_daily":            round(var_95 * 100, 2),       # as % of position
        # Historical frequency of a >= +/-5% move over a 1-month (21 trading day) window.
        "hist_freq_up_5pct_1mo":   round(freq_up * 100, 1) if freq_up is not None else None,
        "hist_freq_down_5pct_1mo": round(freq_down * 100, 1) if freq_down is not None else None,
        "hist_lookback_years":     lookback_years,
        "hist_windows_counted":    n_up,
        "expected_return_1mo_pct": round(exp_return_pct, 2),
        "technical_signal":        final_sig,
        "plain_english": _plain_english_ql(ticker, final_sig, vol, freq_up, var_95, lookback_years),
        "disclaimer": "QuantLib metrics are theoretical estimates, not guaranteed outcomes. Not investment advice.",
    }


def _plain_english_ql(
    ticker: str, signal: str, vol: float, freq_up: float | None, var_95: float, lookback_years: float
) -> str:
    vol_pct  = vol * 100
    var_pct  = var_95 * 100
    vol_label = "low" if vol_pct < 20 else ("moderate" if vol_pct < 40 else "high")

    if freq_up is not None and lookback_years >= 1:
        freq_txt = (
            f"Over the past {lookback_years:.0f} years, {freq_up * 100:.0f}% of 1-month periods "
            f"gained 5% or more."
        )
    else:
        freq_txt = "Not enough price history to measure how often a 5% monthly gain occurred."

    if signal == "BUY":
        return (
            f"{ticker} has {vol_label} volatility ({vol_pct:.1f}%/yr). {freq_txt} "
            f"Daily loss risk at 95% confidence: {var_pct:.1f}% of position."
        )
    elif signal == "SELL":
        return (
            f"{ticker} shows technical weakness with {vol_label} volatility ({vol_pct:.1f}%/yr). "
            f"{freq_txt} Daily loss risk at 95% confidence: {var_pct:.1f}% of position."
        )
    else:
        return (
            f"{ticker} signals are mixed. Volatility: {vol_pct:.1f}%/yr ({vol_label}). "
            f"{freq_txt} No strong directional conviction."
        )


# ── Main ───────────────────────────────────────────────────────────────────────

def run_quantlib_metrics() -> dict:
    print("=== ThinkFree, QuantLib Metrics Engine ===")
    print(f"  QuantLib available: {_QL_AVAILABLE}")

    signals_path = BASE_DIR / "Module_2_Technical_Analysis" / "signal_output_phase3.json"
    signals: list[dict] = []
    try:
        with open(signals_path, "r", encoding="utf-8") as f:
            signals = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"  Warning: {signals_path} not found. Running with empty signals.")

    # Focus on BUY and SELL signals only (top 15)
    prioritized = sorted(
        [s for s in signals if s.get("final_signal") in ("BUY", "SELL")],
        key=lambda x: abs(x.get("confidence_score", 0)),
        reverse=True,
    )[:15]

    if not prioritized:
        print("  No BUY/SELL signals found, sampling first 10 signals.")
        prioritized = signals[:10]

    print(f"  Computing QuantLib metrics for {len(prioritized)} tickers...")

    results = []
    for sig in prioritized:
        ticker = sig.get("ticker", "")
        if not ticker:
            continue
        print(f"    → {ticker} ({sig.get('final_signal', '?')})", end="", flush=True)
        metrics = compute_ticker_metrics(ticker, sig)
        results.append(metrics)
        print(f"  vol={metrics['annualized_volatility']}%  hist P(+5%/1mo)={metrics['hist_freq_up_5pct_1mo']}%")

    output = {
        "generated_at":       datetime.utcnow().isoformat() + "Z",
        "quantlib_version":   ql.__version__ if _QL_AVAILABLE else "unavailable",
        "risk_free_rate_used": RISK_FREE_RATE,
        "horizon_trading_days": TARGET_HORIZON,
        "ticker_metrics":     results,
        "methodology": (
            "Volatility is computed from 252-day log returns. "
            "The chance of a 5% monthly move is the HISTORICAL FREQUENCY: the fraction of "
            "past rolling 21-trading-day windows (over roughly 5 years) that gained or lost "
            "5% or more. It is a real-world count, not the Black-Scholes N(d2) risk-neutral "
            "probability, which is no longer reported. "
            "VaR is parametric at 95% confidence using annualized vol / sqrt(252). "
            "Position-sizing (Kelly) figures are not reported. "
            "All figures are theoretical estimates, not guarantees. Not investment advice."
        ),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nQuantLib metrics saved to {OUTPUT_PATH}")
    print(f"  Tickers analyzed: {len(results)}")
    return output


if __name__ == "__main__":
    run_quantlib_metrics()
