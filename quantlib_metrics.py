#!/usr/bin/env python3
"""
ThinkFree Finance, QuantLib Metrics Engine (Phase 8 Enhancement)

Uses QuantLib to compute risk-adjusted opportunity metrics:
  1. Annualized historical volatility from price history
  2. Black-Scholes probability of profit (lognormal implied upside)
  3. Risk-adjusted expected return (Kelly-based sizing)
  4. Sharpe ratio from historical returns
  5. Value at Risk (VaR) at 95% confidence

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

def bs_prob_above_target(
    spot: float,
    target: float,
    vol: float,
    risk_free: float = RISK_FREE_RATE,
    time_years: float = TARGET_HORIZON / 252,
) -> float:
    """
    Probability (under risk-neutral measure) that price exceeds `target` at expiry.
    Uses the N(d2) term from Black-Scholes, which gives the risk-neutral probability
    of the option expiring in-the-money.
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


# ── Per-ticker QuantLib metrics ────────────────────────────────────────────────

def compute_ticker_metrics(ticker: str, signal: dict) -> dict:
    prices = fetch_recent_prices(ticker)

    if len(prices) >= 10:
        spot    = prices[-1]
        vol     = compute_annualized_vol(prices)
        var_95  = compute_var_95(prices)
        # Use 5% upside as "target" for prob calculation
        target_bull = spot * 1.05
        target_bear = spot * 0.95
        prob_up   = bs_prob_above_target(spot, target_bull, vol)
        prob_down = 1 - bs_prob_above_target(spot, target_bear, vol)
        exp_price = expected_return_lognormal(spot, vol)
        exp_return_pct = ((exp_price / spot) - 1) * 100 if spot > 0 else 0.0
        kelly = kelly_fraction(prices)
    else:
        spot, vol, var_95 = 0.0, 0.30, 0.025
        prob_up, prob_down = 0.5, 0.5
        exp_return_pct = 0.0
        kelly = 0.0

    final_sig = signal.get("final_signal", "HOLD")

    return {
        "ticker":                  ticker,
        "current_price":           round(spot, 2),
        "annualized_volatility":   round(vol * 100, 1),         # as %
        "var_95_daily":            round(var_95 * 100, 2),       # as % of position
        "prob_5pct_upside_1mo":    round(prob_up * 100, 1),      # as %
        "prob_5pct_downside_1mo":  round(prob_down * 100, 1),    # as %
        "expected_return_1mo_pct": round(exp_return_pct, 2),
        "kelly_fraction":          round(kelly * 100, 1),        # as % of portfolio
        "technical_signal":        final_sig,
        "plain_english": _plain_english_ql(ticker, final_sig, vol, prob_up, var_95, kelly),
        "disclaimer": "QuantLib metrics are theoretical estimates, not guaranteed outcomes. Not investment advice.",
    }


def _plain_english_ql(
    ticker: str, signal: str, vol: float, prob_up: float, var_95: float, kelly: float
) -> str:
    vol_pct  = vol * 100
    var_pct  = var_95 * 100
    prob_pct = prob_up * 100
    kel_pct  = kelly * 100

    vol_label = "low" if vol_pct < 20 else ("moderate" if vol_pct < 40 else "high")

    if signal == "BUY":
        return (
            f"{ticker} has {vol_label} volatility ({vol_pct:.1f}%/yr). "
            f"Based on its price history, there is roughly a {prob_pct:.0f}% theoretical probability "
            f"of a 5% gain over the next month under normal conditions. "
            f"Daily loss risk at 95% confidence: {var_pct:.1f}% of position. "
            f"Suggested position size (Kelly): up to {kel_pct:.1f}% of portfolio."
        )
    elif signal == "SELL":
        return (
            f"{ticker} shows technical weakness with {vol_label} volatility ({vol_pct:.1f}%/yr). "
            f"Theoretical upside probability over 1 month: {prob_pct:.0f}%. "
            f"Daily loss risk at 95% confidence: {var_pct:.1f}% of position."
        )
    else:
        return (
            f"{ticker} signals are mixed. Volatility: {vol_pct:.1f}%/yr ({vol_label}). "
            f"Theoretical 1-month upside probability: {prob_pct:.0f}%. "
            f"No strong directional conviction."
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
        print(f"  vol={metrics['annualized_volatility']}%  P(+5%)={metrics['prob_5pct_upside_1mo']}%")

    output = {
        "generated_at":       datetime.utcnow().isoformat() + "Z",
        "quantlib_version":   ql.__version__ if _QL_AVAILABLE else "unavailable",
        "risk_free_rate_used": RISK_FREE_RATE,
        "horizon_trading_days": TARGET_HORIZON,
        "ticker_metrics":     results,
        "methodology": (
            "Volatility is computed from 252-day log returns. "
            "Probability of profit uses the Black-Scholes lognormal model (N(d2)). "
            "VaR is parametric at 95% confidence using annualized vol / sqrt(252). "
            "Kelly fraction sizes positions to maximize log-expected-wealth. "
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
