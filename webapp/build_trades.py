"""ThinkFree - QuiverQuant live congressional-trades fetcher.

Replaces the previously-static congressional trade source with a live pull from
QuiverQuant's congress-trading feed, so the Political Watch screen's trade rows
refresh on their own (driven by the scheduler's `trades` job).

Data flow (unchanged downstream):
  build_trades.py  -> updates housing_trades in intelligence_output.json
  politician_performance.py -> adds estimated P&L  -> politician_performance.json
  build_data.py    -> recent_trades in data.js (window.TF_DATA)
  Political Watch / ticker modals read window.TF_DATA.recent_trades

Refresh latency (honest): congressional trades are governed by the STOCK Act,
which allows up to ~45 days between a transaction and its public disclosure.
QuiverQuant's /live feed updates as new disclosures are filed (roughly daily,
a few times a day at most). So "live" here means *as-soon-as-disclosed*, not
real-time trading. Hourly polling captures every new filing with margin.

QUIVERQUANT_API_KEY is read from .env and never written to output or logs.
Auth scheme: Authorization: Bearer <key>.
Run:  ./tf_env/bin/python webapp/build_trades.py
Docs: https://api.quiverquant.com/docs/
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INTEL = ROOT / "GPT_Economy" / "Intelligence_layer (IN PROGRESS)" / "intelligence_output.json"
COUNTS_OUT = ROOT / "congress_trade_counts.json"   # per-politician all-time/month counts + disclosure lag
# /bulk gives the FULL congressional-trading history (~110k+ rows) so per-politician
# trade counts are accurate; /live only returns the most-recent ~1000 (which was
# undercounting frequent traders like Pelosi to "2 trades").
API_URL = "https://api.quiverquant.com/beta/bulk/congresstrading"
MAX_ROWS = 2000          # keep the most-recent N disclosures for the P&L/detail layer
MAX_BYTES = 96 * 1024 * 1024   # bulk history is large; cap the read so a hostile body can't exhaust memory
TICKER_RE = re.compile(r"^[A-Z][A-Z.]{0,5}$")   # plausible equity tickers only

# Key from .env (never logged). Mirrors the pattern in build_prices.py.
KEY = ""
_env = ROOT / ".env"
if _env.exists():
    for _line in open(_env, encoding="utf-8"):
        if _line.startswith("QUIVERQUANT_API_KEY="):
            KEY = _line.strip().split("=", 1)[1]
            break
KEY = KEY or os.environ.get("QUIVERQUANT_API_KEY", "")


def fetch_live() -> list[dict]:
    if not KEY:
        print("[build_trades] QUIVERQUANT_API_KEY not set - skipping (trade data left unchanged).")
        return []
    req = urllib.request.Request(
        API_URL,
        headers={
            "Authorization": f"Bearer {KEY}",
            "Accept": "application/json",
            "User-Agent": "ThinkFree/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        body = r.read(MAX_BYTES + 1)        # bounded read: never buffer more than the cap
        if len(body) > MAX_BYTES:
            raise ValueError(f"QuiverQuant response exceeded {MAX_BYTES} bytes; refusing")
        payload = json.loads(body.decode())
    if not isinstance(payload, list):
        raise ValueError("QuiverQuant response was not a JSON array")
    return payload


def normalize(rows: list[dict]) -> list[dict]:
    """Map QuiverQuant rows to the housing_trades shape that
    politician_performance.py consumes, validating every field. Free-text fields
    (e.g. Description) are intentionally dropped - only structured, typed values
    flow downstream."""
    def party_abbr(p: str) -> str:
        p = (p or "").strip().lower()
        if p.startswith("r"): return "R"
        if p.startswith("d"): return "D"
        if p.startswith("i"): return "I"
        return ""

    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        # Accept both the /bulk schema (Name/Traded/Filed/Trade_Size_USD) and the
        # /live schema (Representative/TransactionDate/ReportDate/Range).
        ticker = str(row.get("Ticker", "") or "").strip().upper()
        rep = str(row.get("Name", "") or row.get("Representative", "") or "").strip()
        txn = str(row.get("Transaction", "") or "").strip()
        if not TICKER_RE.match(ticker) or not rep or not txn:
            continue
        txn_clean = "Sale" if "sale" in txn.lower() else ("Purchase" if "purchase" in txn.lower() or "buy" in txn.lower() else txn)
        chamber = "Senate" if str(row.get("Chamber", row.get("House", "")) or "").lower().startswith("s") else "House"
        size = str(row.get("Trade_Size_USD", "") or row.get("Amount", "") or "")
        out.append({
            "Representative": rep,
            "BioGuideID": str(row.get("BioGuideID", "") or ""),
            "Date": str(row.get("Traded", "") or row.get("TransactionDate", "") or row.get("Date", "") or "")[:10],
            "Ticker": ticker,
            "Transaction": txn_clean,
            "Range": str(row.get("Range", "") or ""),
            "Amount": size,
            "last_modified": str(row.get("Filed", "") or row.get("ReportDate", "") or "")[:10],
            "Chamber": chamber,
            "Party": party_abbr(row.get("Party", "")),
        })
    # Most-recent first by disclosure (ReportDate), then transaction date.
    out.sort(key=lambda t: (t["last_modified"], t["Date"]), reverse=True)
    return out


def _days_between(later: str, earlier: str) -> int | None:
    """Whole days between two YYYY-MM-DD strings, or None if unparseable."""
    try:
        a = datetime.strptime(later[:10], "%Y-%m-%d")
        b = datetime.strptime(earlier[:10], "%Y-%m-%d")
        d = (a - b).days
        return d if 0 <= d <= 400 else None
    except Exception:
        return None


def compute_counts(trades: list[dict], today: str) -> dict:
    """Per-politician all-time + past-30-day trade counts and average disclosure
    lag (days from transaction to disclosure) from the FULL history. These drive
    accurate trade counts and the transparency/integrity scores downstream."""
    cutoff = ""
    try:
        cutoff = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
    except Exception:
        cutoff = ""
    agg: dict[str, dict] = {}
    for t in trades:
        nm = t["Representative"]
        a = agg.setdefault(nm, {"all_time": 0, "past_month": 0, "_lags": [], "bioguide": t.get("BioGuideID", ""), "party": t.get("Party", "")})
        a["all_time"] += 1
        if cutoff and (t.get("Date") or "") >= cutoff:
            a["past_month"] += 1
        lag = _days_between(t.get("last_modified", ""), t.get("Date", ""))
        if lag is not None:
            a["_lags"].append(lag)
    out = {}
    for nm, a in agg.items():
        lags = a.pop("_lags")
        a["avg_disclosure_lag_days"] = round(sum(lags) / len(lags), 1) if lags else None
        out[nm] = a
    return out


def main() -> int:
    try:
        raw = fetch_live()
    except Exception as e:
        print(f"[build_trades] fetch failed: {type(e).__name__}: {str(e)[:140]}")
        return 1
    if not raw:
        return 0   # no key / empty -> leave existing data untouched (non-fatal)

    all_trades = normalize(raw)
    if not all_trades:
        print("[build_trades] no valid trades after normalization - leaving data unchanged.")
        return 1

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    counts = compute_counts(all_trades, today)
    detail = all_trades[:MAX_ROWS]   # recent slice for the P&L / detail layer

    # Per-politician counts file (consumed by build_data.py for accurate trade
    # counts + transparency/integrity scores).
    counts_doc = {"generated_at": datetime.now(timezone.utc).isoformat(),
                  "total_trades_all_time": len(all_trades),
                  "politicians": counts}
    ctmp = COUNTS_OUT.with_suffix(".json.tmp")
    ctmp.write_text(json.dumps(counts_doc, ensure_ascii=False), encoding="utf-8")
    ctmp.replace(COUNTS_OUT)

    # Preserve every other key in intelligence_output.json; replace only housing_trades.
    doc: dict = {}
    if INTEL.exists():
        try:
            doc = json.loads(INTEL.read_text(encoding="utf-8"))
            if not isinstance(doc, dict):
                doc = {}
        except Exception:
            doc = {}
    doc["housing_trades"] = detail

    INTEL.parent.mkdir(parents=True, exist_ok=True)
    tmp = INTEL.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    tmp.replace(INTEL)   # atomic swap

    top = sorted(counts.items(), key=lambda kv: kv[1]["all_time"], reverse=True)[:1]
    leader = f"{top[0][0]} {top[0][1]['all_time']} all-time" if top else "n/a"
    print(f"[build_trades] full history: {len(all_trades)} trades across {len(counts)} politicians "
          f"(top: {leader}); wrote {len(detail)} recent to housing_trades + counts to {COUNTS_OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
