#!/usr/bin/env python3
"""
ThinkFree Finance , Politician Trading Performance Calculator
Pre-computes estimated P&L for each congressional trade based on:
  - Disclosed dollar range midpoint (e.g. "$15,001 - $50,000" → ~$32,500)
  - Price on trade date vs current price (yfinance)
  - Aggregates by politician: total invested, estimated gain/loss, % return

Output: politician_performance.json

NOTE: Net worth data is not available via free public APIs.
      All figures are ESTIMATES based on disclosed minimum/maximum ranges.
      Actual amounts may differ significantly.

TROUBLESHOOTING MARKERS:
    [LOAD_TRADES]   , reading intelligence_output.json
    [PRICE_FETCH]   , fetching historical prices via yfinance
    [COMPUTE]       , calculating P&L per trade
    [AGGREGATE]     , rolling up by politician
    [SAVE]          , writing politician_performance.json
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR    = Path(__file__).parent
OUTPUT_FILE = BASE_DIR / "politician_performance.json"


def parse_range_bounds(range_str) -> tuple[float, float]:
    """Parse a disclosed dollar range into (low, high) bounds, not a single midpoint.

    Disclosures are ranges ("$15,001 - $50,000"); collapsing to the midpoint hides the
    uncertainty. We keep both ends so per-politician totals can be reported as a range.
        "$1,001 - $15,000"        -> (1001.0, 15000.0)
        "Over $5,000,000"         -> (5000000.0, 5000000.0)  (floor, open-ended above)
        "1001.0"                  -> (1001.0, 1001.0)
    """
    if not range_str:
        return (0.0, 0.0)
    s = str(range_str).replace(",", "").strip()
    try:
        v = float(s)
        return (v, v)
    except ValueError:
        pass
    over_match = re.search(r"over\s*\$?([\d.]+)", s, re.IGNORECASE)
    if over_match:
        v = float(over_match.group(1))
        return (v, v)
    parts = re.findall(r"\$?([\d.]+)", s)
    if len(parts) >= 2:
        return (float(parts[0]), float(parts[1]))
    if len(parts) == 1:
        return (float(parts[0]), float(parts[0]))
    return (0.0, 0.0)


def _parse_range_midpoint(range_str) -> float:
    """Midpoint of the disclosed range (kept for display only, never for ranking)."""
    lo, hi = parse_range_bounds(range_str)
    return (lo + hi) / 2.0


def simple_return(then: float | None, now: float | None) -> float | None:
    """Fractional price return, or None if inputs are missing/degenerate."""
    if then is None or now is None or then <= 0:
        return None
    return now / then - 1.0


def excess_vs_benchmark(stock_then, stock_now, bench_then, bench_now) -> float | None:
    """Stock return minus the benchmark (SPY) return over the SAME window.

    A raw buy-and-hold return flatters everyone in a rising market; the honest measure of
    a trade is how it did RELATIVE to simply holding the broad market over the identical
    window. Returns a fraction (0.05 == +5 percentage points of excess), or None.
    """
    s = simple_return(stock_then, stock_now)
    b = simple_return(bench_then, bench_now)
    if s is None or b is None:
        return None
    return s - b


def sell_framing(price_at_sale, price_now) -> dict:
    """Frame a SALE by what happened AFTER it, never as realized buy-side P&L.

    If the stock rose after they sold, they forewent that gain; if it fell, they avoided
    that loss. This is reported separately and is never summed into buy P&L.
    """
    r = simple_return(price_at_sale, price_now)
    if r is None:
        return {"stance": "unknown", "return_since_sale_pct": None}
    stance = "forewent_gain" if r >= 0 else "avoided_loss"
    return {"stance": stance, "return_since_sale_pct": round(r * 100, 2)}


def _build_ticker_history(tickers: list[str]) -> dict[str, "Any"]:
    """
    Download up to 5-year history for all tickers in ONE batch call per ticker.
    Returns dict: ticker → pd.Series (date index, close prices).
    One API call per ticker , eliminates per-trade-date calls that cause rate limits.
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

    # Collect unique tickers. SPY is always included: it is the benchmark every trade is
    # measured against over its own window.
    unique_tickers = sorted({
        t.get("Ticker", t.get("ticker", "")).upper()
        for t in recent_trades
        if t.get("Ticker", t.get("ticker", ""))
    } | {"SPY"})
    print(f"[PRICE_FETCH] Downloading 5-year history for {len(unique_tickers)} tickers "
          f"(one call per ticker , no rate limit issues)…")

    # ONE batch download per ticker , prices for all dates resolved in memory
    ticker_history = _build_ticker_history(unique_tickers)
    print(f"[PRICE_FETCH] Done. {sum(1 for s in ticker_history.values() if not s.empty)} tickers with data.")

    spy_series = ticker_history.get("SPY")
    spy_now = float(spy_series.iloc[-1]) if spy_series is not None and not spy_series.empty else None

    # [COMPUTE] Per-trade excess return vs SPY , all lookups are in-memory now.
    # BUYS carry an excess-return and a P&L RANGE (from the disclosed range bounds).
    # SALES are framed separately (forewent gain / avoided loss) and never enter P&L.
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
        lo, hi       = parse_range_bounds(range_str)
        price_then   = _price_on_date(series, date_str)
        price_now    = float(series.iloc[-1]) if series is not None and not series.empty else None
        spy_then     = _price_on_date(spy_series, date_str)

        is_sale      = "sale" in tx.lower()
        is_purchase  = "purchase" in tx.lower()

        # Excess return vs SPY over the SAME window (fraction), directionless by side.
        excess = excess_vs_benchmark(price_then, price_now, spy_then, spy_now)
        stock_ret = simple_return(price_then, price_now)

        info = party_map.get(rep, {})
        rec = {
            "politician":   rep,
            "party":        info.get("party", "Unknown"),
            "party_abbr":   info.get("party_abbr", "?"),
            "state":        info.get("state", ""),
            "chamber":      chamber,
            "ticker":       ticker,
            "transaction":  tx,
            "side":         "SELL" if is_sale else ("BUY" if is_purchase else "OTHER"),
            "date":         date_str,
            "range_disclosed": range_str,
            "range_low":    round(lo, 2),
            "range_high":   round(hi, 2),
            "midpoint_est": round((lo + hi) / 2.0, 2),
            "price_at_trade": round(price_then, 4) if price_then else None,
            "price_current":  round(price_now, 4) if price_now else None,
            "stock_return_pct": round(stock_ret * 100, 2) if stock_ret is not None else None,
            "excess_return_vs_spy_pct": round(excess * 100, 2) if excess is not None else None,
        }

        if is_sale:
            # Frame by what happened after the sale; NOT summed into buy P&L.
            rec["sell_frame"] = sell_framing(price_then, price_now)
            rec["pnl_low"] = None
            rec["pnl_high"] = None
        else:
            # Buy-side dollar P&L is a RANGE from the disclosed bounds, not a point.
            if stock_ret is not None and hi > 0:
                rec["pnl_low"] = round(lo * stock_ret, 2)
                rec["pnl_high"] = round(hi * stock_ret, 2)
            else:
                rec["pnl_low"] = None
                rec["pnl_high"] = None

        # Backward-compatible keys for existing consumers (webapp/build_data.py, iOS).
        # These now carry HONEST values: the displayed return is market-adjusted (excess
        # vs SPY), and sells carry no P&L (None) so they are never shown as buy-side gains.
        rec["pct_return"] = rec["excess_return_vs_spy_pct"]
        if is_sale:
            rec["est_pnl"] = None
        else:
            rec["est_pnl"] = round((lo + hi) / 2.0 * stock_ret, 2) if stock_ret is not None else None

        trade_records.append(rec)

    print(f"[COMPUTE] Computed excess-vs-SPY for {len(trade_records)} trades.")

    # [AGGREGATE] Roll up by politician. Buys and sells are kept in separate buckets.
    from collections import defaultdict  # noqa: PLC0415
    pol_stats: dict[str, dict] = defaultdict(lambda: {
        "invested_low": 0.0, "invested_high": 0.0,
        "buy_pnl_low": 0.0, "buy_pnl_high": 0.0,
        "buy_excess_returns": [],       # for ranking (mean excess vs SPY)
        "sell_return_since_pct": [],    # framing only, separate from P&L
        "trade_count": 0, "buy_count": 0, "sell_count": 0,
        "trades": [],
        "party": "Unknown", "party_abbr": "?", "state": "", "chamber": "",
    })

    for tr in trade_records:
        stat = pol_stats[tr["politician"]]
        stat["party"]      = tr["party"]
        stat["party_abbr"] = tr["party_abbr"]
        stat["state"]      = tr["state"]
        stat["chamber"]    = tr["chamber"]
        stat["trade_count"] += 1
        stat["trades"].append(tr)

        if tr["side"] == "BUY":
            stat["buy_count"] += 1
            stat["invested_low"]  += tr["range_low"]
            stat["invested_high"] += tr["range_high"]
            if tr["pnl_low"] is not None:
                stat["buy_pnl_low"]  += tr["pnl_low"]
                stat["buy_pnl_high"] += tr["pnl_high"]
            if tr["excess_return_vs_spy_pct"] is not None:
                stat["buy_excess_returns"].append(tr["excess_return_vs_spy_pct"])
        elif tr["side"] == "SELL":
            stat["sell_count"] += 1
            frame = tr.get("sell_frame", {})
            if frame.get("return_since_sale_pct") is not None:
                stat["sell_return_since_pct"].append(frame["return_since_sale_pct"])

    # Build summary table. Ranking is by MEAN buy excess return vs SPY, not dollar P&L.
    summary_rows = []
    for pol, stat in pol_stats.items():
        excess_list = stat["buy_excess_returns"]
        mean_excess = round(sum(excess_list) / len(excess_list), 2) if excess_list else None
        sells = stat["sell_return_since_pct"]
        mean_sell_since = round(sum(sells) / len(sells), 2) if sells else None
        summary_rows.append({
            "Politician":       pol,
            "Party":            stat["party"],
            "State":            stat["state"],
            "Chamber":          stat["chamber"],
            "Trades":           stat["trade_count"],
            "Buys":             stat["buy_count"],
            "Sells":            stat["sell_count"],
            # Disclosed dollars as a RANGE, never a single midpoint point-estimate.
            "Buy Invested Range ($)": [round(stat["invested_low"], 2), round(stat["invested_high"], 2)],
            "Buy P&L Range ($)":      [round(stat["buy_pnl_low"], 2), round(stat["buy_pnl_high"], 2)],
            "Mean Buy Excess vs SPY (%)": mean_excess,
            # Sells reported separately; their after-sale move is NOT summed into P&L.
            "Mean Stock Move Since Sell (%)": mean_sell_since,
        })

    # Rank on excess vs SPY (skill relative to the market), not raw dollar P&L.
    summary_rows.sort(
        key=lambda x: (x["Mean Buy Excess vs SPY (%)"] is not None, x["Mean Buy Excess vs SPY (%)"] or 0.0),
        reverse=True,
    )

    output = {
        "disclaimer": (
            "All dollar figures are ESTIMATES reported as a RANGE from the low and high ends "
            "of publicly disclosed trade ranges (never a single midpoint). Performance is the "
            "trade's EXCESS return versus SPY over the identical window, not a raw return. "
            "SELL disclosures are framed by what the stock did after the sale (gain forewent "
            "or loss avoided) and are never added to buy-side P&L. Net worth data is not "
            "available via public APIs. This analysis identifies timing relationships only and "
            "does not imply wrongdoing."
        ),
        "benchmark": "SPY",
        "generated_at":       datetime.utcnow().isoformat() + "Z",
        "politician_summary": summary_rows,
        "trade_detail":       trade_records,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[SAVE] Saved to {OUTPUT_FILE}")
    print(f"\nTop 5 by mean buy excess return vs SPY (all-time disclosed trades):")
    for r in summary_rows[:5]:
        ex = r["Mean Buy Excess vs SPY (%)"]
        ex_str = f"{ex:+.1f}%" if ex is not None else "N/A"
        inv = r["Buy Invested Range ($)"]
        pnl = r["Buy P&L Range ($)"]
        print(f"  {r['Politician']} ({r['Party']}, {r['State']}) , "
              f"{r['Buys']} buys | Excess vs SPY: {ex_str} | "
              f"Invested ${inv[0]:,.0f}-${inv[1]:,.0f} | P&L ${pnl[0]:,.0f} to ${pnl[1]:,.0f}")


if __name__ == "__main__":
    main()
