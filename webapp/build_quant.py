"""ThinkFree - QuantLib + Technical-Analysis engine for the webapp.

This is the quantitative HEART of the Predictive Market Signals engine. It reuses
the real QuantLib model from quantlib_metrics.py (annualized volatility, 95% VaR,
lognormal expected return) plus the 5-year HISTORICAL FREQUENCY of a 5% monthly move
(replacing the old risk-neutral N(d2) probability and Kelly sizing) AND computes
real technical indicators (RSI, MACD, SMA-50/200 crossovers) with the `ta` library
on live yfinance price history, then writes webapp/js/quant_data.js
(window.QUANT_DATA) so predictions.js uses real math instead of proxies.

Run:  ./tf_env/bin/python webapp/build_quant.py [TICKER ...]
      (no args -> the Predictive Market Signals candidate tickers)
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import ta

ROOT = Path(__file__).resolve().parent.parent
JS = Path(__file__).resolve().parent / "js"
OUT = JS / "quant_data.js"
sys.path.insert(0, str(ROOT))
from quantlib_metrics import (  # reuse the real QuantLib math, single source of truth
    fetch_recent_prices, fetch_history, compute_annualized_vol, compute_var_95,
    historical_move_frequency, expected_return_lognormal, RISK_FREE_RATE, TARGET_HORIZON,
)


def _load(fname, marker):
    t = (JS / fname).read_text(encoding="utf-8")
    return json.loads(t.split(marker, 1)[1].rstrip().rstrip(";").strip())


def candidates(n=22):
    d = _load("data.js", "window.TF_DATA =")
    px = set(_load("prices_data.js", "window.PRICES_DATA =").get("byTicker", {}))
    act = Counter()
    for x in d.get("news", []):
        if x.get("symbol"):
            act[x["symbol"]] += 1
    for t in d.get("recent_trades", []):
        if t.get("ticker"):
            act[t["ticker"]] += 0.5
    return [tk for tk, _ in act.most_common() if tk in px and tk.isalpha() and tk.isupper()][:n]


def sharpe(prices):
    r = np.diff(np.log(prices))
    sd = r.std(ddof=1)
    if not sd:
        return 0.0
    return round(float((r.mean() * 252 - RISK_FREE_RATE) / (sd * math.sqrt(252))), 2)


def ta_block(prices):
    s = pd.Series(prices)
    try:
        rsi = float(ta.momentum.RSIIndicator(s).rsi().iloc[-1])
        macd = ta.trend.MACD(s)
        macd_v = float(macd.macd().iloc[-1])
        macd_sig = float(macd.macd_signal().iloc[-1])
        sma50 = float(s.rolling(50).mean().iloc[-1])
        sma200 = float(s.rolling(200).mean().iloc[-1]) if len(s) >= 200 else None
    except Exception:
        return {}
    rsi_sig = "oversold" if rsi < 30 else "overbought" if rsi > 70 else "neutral"
    macd_cross = "bullish" if macd_v > macd_sig else "bearish"
    trend = ("golden" if sma50 > sma200 else "death") if sma200 else "n/a"
    score = 50
    score += 12 if rsi_sig == "oversold" else -12 if rsi_sig == "overbought" else 0
    score += 14 if macd_cross == "bullish" else -14
    score += 14 if trend == "golden" else -14 if trend == "death" else 0
    score = max(5, min(95, score))
    return {
        "rsi": round(rsi, 1), "rsi_signal": rsi_sig,
        "macd": round(macd_v, 3), "macd_signal_line": round(macd_sig, 3), "macd_cross": macd_cross,
        "sma50": round(sma50, 2), "sma200": round(sma200, 2) if sma200 else None, "trend": trend,
        "ta_score": score, "ta_signal": "BUY" if score >= 60 else "SELL" if score <= 40 else "HOLD",
    }


def main():
    tickers = [t.upper() for t in sys.argv[1:]] or candidates()
    print(f"QuantLib + TA for {len(tickers)} tickers...")
    out = {}
    for tk in tickers:
        prices = fetch_recent_prices(tk)
        if len(prices) < 30:
            print(f"  x {tk}: insufficient history")
            continue
        spot = prices[-1]
        vol = compute_annualized_vol(prices)
        # Real-world 5-year historical frequency of a 5% monthly move (no N(d2), no Kelly).
        history = fetch_history(tk, period="5y")
        freq_up, n_win = historical_move_frequency(history, TARGET_HORIZON, 0.05, "up")
        freq_down, _   = historical_move_frequency(history, TARGET_HORIZON, 0.05, "down")
        rec = {
            "price": round(spot, 2),
            "volatility": round(vol * 100, 1),
            "var95": round(compute_var_95(prices) * 100, 2),
            "hist_up_5pct_1mo": round(freq_up * 100, 1) if freq_up is not None else None,
            "hist_down_5pct_1mo": round(freq_down * 100, 1) if freq_down is not None else None,
            "hist_lookback_years": round(len(history) / 252, 1) if history else 0.0,
            "hist_windows": n_win,
            "exp_return_1mo": round(((expected_return_lognormal(spot, vol) / spot) - 1) * 100, 2),
            "sharpe": sharpe(prices),
        }
        rec.update(ta_block(prices))
        # Direction comes from the technical signal. The QuantLib block quantifies
        # RISK and probability, not direction: the lognormal expected return is the
        # risk-neutral carry (spot*exp(r*T)), identical for every stock, so it carries
        # no directional information. The old code derived ql_signal from the sign of
        # that term, which (with the former median bug) forced high-vol names to SELL.
        rec["ql_signal"] = rec.get("ta_signal", "HOLD")
        out[tk] = rec
        print(f"  + {tk:6} vol {rec['volatility']}% | hist +5%/1mo {rec['hist_up_5pct_1mo']}% | VaR {rec['var95']}% | RSI {rec.get('rsi')} | {rec.get('ta_signal')}/{rec['ql_signal']}")

    data = {"source": "QuantLib (volatility/VaR/lognormal) + 5yr historical frequency + ta technical indicators on yfinance history", "byTicker": out, "count": len(out)}
    OUT.write_text("// AUTO-GENERATED by webapp/build_quant.py (QuantLib + ta). No API keys.\nwindow.QUANT_DATA = " + json.dumps(data) + ";\n", encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB) - {len(out)} tickers")


if __name__ == "__main__":
    main()
