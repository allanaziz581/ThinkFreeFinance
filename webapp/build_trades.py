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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INTEL = ROOT / "GPT_Economy" / "Intelligence_layer (IN PROGRESS)" / "intelligence_output.json"
API_URL = "https://api.quiverquant.com/beta/live/congresstrading"
MAX_ROWS = 1500          # keep the most-recent N disclosures (UI shows "recent")
MAX_BYTES = 32 * 1024 * 1024   # cap the response read so a hostile/huge body can't exhaust memory
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
    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("Ticker", "") or "").strip().upper()
        rep = str(row.get("Representative", "") or "").strip()
        txn = str(row.get("Transaction", "") or "").strip()
        if not TICKER_RE.match(ticker) or not rep or not txn:
            continue
        # Normalize Sale Partial / Sale Full etc. to a clean verb the UI regex reads.
        txn_clean = "Sale" if "sale" in txn.lower() else ("Purchase" if "purchase" in txn.lower() or "buy" in txn.lower() else txn)
        chamber = "Senate" if str(row.get("House", "")).lower().startswith("s") else "House"
        out.append({
            "Representative": rep,
            "BioGuideID": str(row.get("BioGuideID", "") or ""),
            "Date": str(row.get("TransactionDate", "") or row.get("Date", "") or ""),
            "Ticker": ticker,
            "Transaction": txn_clean,
            "Range": str(row.get("Range", "") or ""),
            "Amount": str(row.get("Amount", "") or ""),
            "last_modified": str(row.get("ReportDate", "") or ""),
            "Chamber": chamber,
            "Party": str(row.get("Party", "") or ""),
        })
    # Most-recent first by disclosure (ReportDate), then transaction date.
    out.sort(key=lambda t: (t["last_modified"], t["Date"]), reverse=True)
    return out[:MAX_ROWS]


def main() -> int:
    try:
        raw = fetch_live()
    except Exception as e:
        print(f"[build_trades] fetch failed: {type(e).__name__}: {str(e)[:140]}")
        return 1
    if not raw:
        return 0   # no key / empty -> leave existing data untouched (non-fatal)

    trades = normalize(raw)
    if not trades:
        print("[build_trades] no valid trades after normalization - leaving data unchanged.")
        return 1

    # Preserve every other key in intelligence_output.json; replace only housing_trades.
    doc: dict = {}
    if INTEL.exists():
        try:
            doc = json.loads(INTEL.read_text(encoding="utf-8"))
            if not isinstance(doc, dict):
                doc = {}
        except Exception:
            doc = {}
    doc["housing_trades"] = trades

    INTEL.parent.mkdir(parents=True, exist_ok=True)
    tmp = INTEL.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    tmp.replace(INTEL)   # atomic swap

    newest_txn = max((t["Date"] for t in trades if t["Date"]), default="?")
    newest_rep = max((t["last_modified"] for t in trades if t["last_modified"]), default="?")
    print(f"[build_trades] wrote {len(trades)} live trades to intelligence_output.json "
          f"(newest txn {newest_txn}, newest disclosure {newest_rep})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
