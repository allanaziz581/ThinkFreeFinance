"""Shared quant constants for the ThinkFree pipeline.

Single source of truth for the risk-free rate (previously 0.05 in some modules and
0.0 in others). The rate is the 13-week U.S. Treasury bill yield (^IRX), which is
quoted in PERCENT, so it is divided by 100 to get a decimal.

Callers that want a live rate call risk_free_from_irx() and pass the result down;
RISK_FREE_RATE is the shared default used everywhere so no module invents its own.
"""
from __future__ import annotations

# Shared default risk-free rate (decimal). Refreshed from ^IRX by risk_free_from_irx().
RISK_FREE_RATE = 0.05

# Quarter-Kelly is the reported sizing: full continuous f* is divided by 4, then
# capped. Kept here so every module that references Kelly uses one number.
KELLY_CAP = 0.25


def risk_free_from_irx(default: float = RISK_FREE_RATE) -> float:
    """13-week T-bill yield (^IRX) as a decimal, e.g. 5.2 percent -> 0.052.

    ^IRX is quoted in percent, so we divide by 100. Returns `default` on any
    failure or an out-of-range value. Network call; not run at import time.
    """
    try:
        import yfinance as yf
        hist = yf.download("^IRX", period="5d", interval="1d", progress=False, auto_adjust=False)
        if hist is None or hist.empty:
            return default
        close = hist["Close"]
        if hasattr(close, "squeeze"):
            close = close.squeeze()
        val = float(close.dropna().iloc[-1])
        r = val / 100.0
        if 0.0 <= r <= 0.10:
            return round(r, 4)
    except Exception:
        pass
    return default
