#!/usr/bin/env python3
"""
ThinkFree Finance — Politician Trading Performance Calculator
Pre-computes estimated P&L for each congressional trade based on:
  - Disclosed dollar range midpoint (e.g. "$15,001 - $50,000" → ~$32,500)
  - Price on trade date vs current price (yfinance)
  - Aggregates by politician: total invested, estimated gain/loss, % return

Output: politician_performance.json

NOTE: Net worth data is not available via free public APIs.
      All figures are ESTIMATES based on disclosed minimum/maximum ranges.
      Actual amounts may differ significantly.

TROUBLESHOOTING MARKERS:
    [LOAD_TRADES]   — reading intelligence_output.json
    [PRICE_FETCH]   — fetching historical prices via yfinance
    [COMPUTE]       — calculating P&L per trade
    [AGGREGATE]     — rolling up by politician
    [SAVE]          — writing politician_performance.json
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR    = Path(__file__).parent
OUTPUT_FILE = BASE_DIR / "politician_performance.json"


def _parse_range_midpoint(range_str: str) -> float:
    """
    Parse disclosed dollar range to midpoint.
    Examples:
        "$1,001 - $15,000"       → 8,000.5
        "$50,001 - $100,000"     → 75,000.5
        "$1,000,001 - $5,000,000"→ 3,000,000.5
        "Over $5,000,000"        → 5,000,000
        "1001.0"                 → 1001.0   (raw number)
    """
    if not range_str:
        return 0.0

    s = str(range_str).replace(",", "").strip()

    # Plain number (some records store Amount not Range)
    try:
        return float(s)
    except ValueError:
        pass

    # "Over $X" → use X as floor
    over_match = re.search(r"over\s*\$?([\d.]+)", s, re.IGNORECASE)
    if over_match:
        return float(over_match.group(1))

    # "$X - $Y"
    parts = re.findall(r"\$?([\d.]+)", s)
    if len(parts) >= 2:
        lo, hi = float(parts[0]), float(parts[1])
        return (lo + hi) / 2
    if len(parts) == 1:
        return float(parts[0])

    return 0.0


def _build_ticker_history(tickers: list[str]) -> dict[str, "Any"]:
    """
    Download up to 5-year history for all tickers in ONE batch call per ticker.
    Returns dict: ticker → pd.Series (date index, close prices).
    One API call per ticker — eliminates per-trade-date calls that cause rate limits.
    """
    import pandas as pd  # noqa: PLC0415
    import yfinance as yf  # noqa: PLC0415
    import time as _time  # noqa: PLC0415

    history: dict[str, "pd.Series"] = {}
    for i, ticker in enumerate(tickers):
        try:
            df = yf.download(ticker, period="5y", interval="1d", progress=False, auto_adjust=True)
            if df is None or df.empty:
                history[ticker] = pd.Series(dtype=float)
                continue
            close = df["Close"]
            if hasattr(close, "squeeze"):
                close = close.squeeze()
            history[ticker] = close.dropna()
        except Exception:
            history[ticker] = pd.Series(dtype=float)

        # Rate-limit guard: 0.3s between calls keeps us well under yfinance limits
        if i % 10 == 9:
            _time.sleep(1.0)
        else:
            _time.sleep(0.3)

    return history


def _price_on_date(series: "Any", date_str: str) -> float | None:
    """Look up the price closest to date_str from a pre-fetched Series."""
    if series is None or series.empty:
        return None
    try:
        import pandas as pd  # noqa: PLC0415
        target = pd.Timestamp(date_str)
        # Find the nearest available trading day on or before the target
        available = series[series.index <= target]
        if available.empty:
            available = series   # if trade predates history, use earliest
        return float(available.iloc[-1])
    except Exception:
        return None


def main():
    # [LOAD_TRADES]
    intel_path = BASE_DIR / "GPT_Economy" / "Intelligence_layer (IN PROGRESS)" / "intelligence_output.json"
    if not intel_path.exists():
        print(f"[LOAD_TRADES] intelligence_output.json not found at {intel_path}")
        return

    with open(intel_path, "r", encoding="utf-8") as f:
        intel = json.load(f)

    trades = intel.get("housing_trades", [])
    print(f"[LOAD_TRADES] {len(trades)} trades loaded.")

    # Load party map
    party_path = BASE_DIR / "politician_parties.json"
    party_map: dict = {}
    if party_path.exists():
        with open(party_path, "r", encoding="utf-8") as f:
            party_map = json.load(f)

    recent_trades = [
        t for t in trades
        if t.get("Ticker", t.get("ticker", "")) and t.get("Representative", t.get("representative", ""))
    ]
    print(f"[LOAD_TRADES] {len(recent_trades)} trades (all-time).")

    # Collect unique tickers
    unique_tickers = sorted({
        t.get("Ticker", t.get("ticker", "")).upper()
        for t in recent_trades
        if t.get("Ticker", t.get("ticker", ""))
    })
    print(f"[PRICE_FETCH] Downloading 5-year history for {len(unique_tickers)} tickers "
          f"(one call per ticker — no rate limit issues)…")

    # ONE batch download per ticker — prices for all dates resolved in memory
    ticker_history = _build_ticker_history(unique_tickers)
    print(f"[PRICE_FETCH] Done. {sum(1 for s in ticker_history.values() if not s.empty)} tickers with data.")

    # [COMPUTE] Per-trade P&L — all lookups are in-memory now
    trade_records: list[dict] = []
    for t in recent_trades:
        ticker    = t.get("Ticker", t.get("ticker", "")).upper()
        rep       = t.get("Representative", t.get("representative", ""))
        tx        = t.get("Transaction", t.get("transaction", ""))
        date_str  = t.get("Date", t.get("TransactionDate", t.get("TradeDate", "")))
        range_str = t.get("Range", t.get("Amount", ""))
        chamber   = t.get("Chamber", "House")

        if not ticker or not rep or not date_str:
            continue

        series       = ticker_history.get(ticker)
        midpoint     = _parse_range_midpoint(range_str)
        price_then   = _price_on_date(series, date_str)
        price_now    = float(series.iloc[-1]) if series is not None and not series.empty else None

        pct_return   = None
        est_pnl      = None
        is_purchase  = "purchase" in tx.lower()
        is_sale      = "sale" in tx.lower()

        if price_then and price_now and price_then > 0 and midpoint > 0:
            raw_return = (price_now - price_then) / price_then
            if is_sale:
                raw_return = -raw_return   # sold → gains are inverted
            pct_return = round(raw_return * 100, 2)
            est_pnl    = round(midpoint * raw_return, 2)

        info = party_map.get(rep, {})
        trade_records.append({
            "politician":   rep,
            "party":        info.get("party", "Unknown"),
            "party_abbr":   info.get("party_abbr", "?"),
            "state":        info.get("state", ""),
            "chamber":      chamber,
            "ticker":       ticker,
            "transaction":  tx,
            "date":         date_str,
            "range_disclosed": range_str,
            "midpoint_est": round(midpoint, 2),
            "price_at_trade": round(price_then, 4) if price_then else None,
            "price_current":  round(price_now, 4) if price_now else None,
            "pct_return":     pct_return,
            "est_pnl":        est_pnl,
        })

    print(f"[COMPUTE] Computed P&L for {len(trade_records)} trades.")

    # [AGGREGATE] Roll up by politician
    from collections import defaultdict  # noqa: PLC0415
    pol_stats: dict[str, dict] = defaultdict(lambda: {
        "total_invested_est": 0.0,
        "total_est_pnl": 0.0,
        "trade_count": 0,
        "buy_count": 0,
        "sell_count": 0,
        "trades": [],
        "party": "Unknown",
        "party_abbr": "?",
        "state": "",
        "chamber": "",
    })

    for tr in trade_records:
        pol  = tr["politician"]
        stat = pol_stats[pol]
        stat["party"]      = tr["party"]
        stat["party_abbr"] = tr["party_abbr"]
        stat["state"]      = tr["state"]
        stat["chamber"]    = tr["chamber"]
        stat["trade_count"] += 1

        if "purchase" in tr["transaction"].lower():
            stat["buy_count"] += 1
        elif "sale" in tr["transaction"].lower():
            stat["sell_count"] += 1

        if tr["midpoint_est"] > 0:
            stat["total_invested_est"] += tr["midpoint_est"]
        if tr["est_pnl"] is not None:
            stat["total_est_pnl"] += tr["est_pnl"]

        stat["trades"].append(tr)

    # Build sorted summary table
    summary_rows = []
    for pol, stat in pol_stats.items():
        invested = stat["total_invested_est"]
        pnl      = stat["total_est_pnl"]
        pct      = (pnl / invested * 100) if invested > 0 else None
        summary_rows.append({
            "Politician":         pol,
            "Party":              stat["party"],
            "State":              stat["state"],
            "Chamber":            stat["chamber"],
            "Trades (6mo)":       stat["trade_count"],
            "Buys":               stat["buy_count"],
            "Sells":              stat["sell_count"],
            "Est. Total Traded":  round(invested, 2),
            "Est. P&L ($)":       round(pnl, 2),
            "Est. Return (%)":    round(pct, 2) if pct is not None else None,
        })

    summary_rows.sort(key=lambda x: x["Est. P&L ($)"], reverse=True)

    output = {
        "disclaimer": (
            "All figures are ESTIMATES based on the midpoint of publicly disclosed trade ranges. "
            "Actual amounts may differ significantly. Net worth data is not available via public APIs. "
            "This analysis identifies timing relationships only and does not imply wrongdoing."
        ),
        "generated_at":       datetime.utcnow().isoformat() + "Z",
        "politician_summary": summary_rows,
        "trade_detail":       trade_records,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[SAVE] Saved to {OUTPUT_FILE}")
    print(f"\nTop 5 estimated performers (all-time disclosed trades):")
    for r in summary_rows[:5]:
        pnl_str = f"${r['Est. P&L ($)']:+,.0f}" if r['Est. P&L ($)'] else "N/A"
        pct_str = f"{r['Est. Return (%)']:+.1f}%" if r['Est. Return (%)'] is not None else "N/A"
        print(f"  {r['Politician']} ({r['Party']}, {r['State']}) — "
              f"{r['Trades (6mo)']} trades | Est. P&L: {pnl_str} | Return: {pct_str}")


if __name__ == "__main__":
    main()
