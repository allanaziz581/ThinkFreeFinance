#!/usr/bin/env python3
"""
ThinkFree Finance , Congress.gov Bills Intelligence
Phase 6.5 supplement: fetches recently enacted laws and pending bills, then
correlates them with congressional stock trades by keyword matching
company names, sectors, and policy topics within a 6-month window.

TROUBLESHOOTING MARKERS:
    [FETCH_LAWS]    , pulling enacted laws from /v3/law/119
    [FETCH_BILLS]   , pulling recent pending bills from /v3/bill/119
    [CORRELATE]     , matching bills to trader tickers via keyword map
    [SAVE]          , writing congress_bills.json
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_DIR     = Path(__file__).parent
OUTPUT_FILE  = BASE_DIR / "congress_bills.json"

CONGRESS_API_KEY = os.getenv("CONGRESS_API_KEY", "")
CURRENT_CONGRESS = 119   # 119th Congress: Jan 2025 - Jan 2027
LOOKBACK_DAYS    = 180
BASE_URL         = "https://api.congress.gov/v3"

DISCLAIMER = (
    "This analysis identifies timing relationships between publicly available "
    "government disclosures and market events. It does not imply or allege "
    "wrongdoing of any kind."
)

# ── Keyword map: ticker → terms to look for in bill titles/text ───────────────
# Covers the most common congressional trade tickers
TICKER_KEYWORDS: dict[str, list[str]] = {
    # Tech
    "AAPL":  ["apple", "smartphone", "app store", "antitrust", "digital market", "tech"],
    "MSFT":  ["microsoft", "cloud", "azure", "software", "artificial intelligence", "AI"],
    "GOOGL": ["google", "alphabet", "search", "antitrust", "advertising", "AI"],
    "GOOG":  ["google", "alphabet", "search", "antitrust"],
    "NVDA":  ["nvidia", "semiconductor", "chip", "AI", "artificial intelligence", "GPU"],
    "META":  ["meta", "facebook", "social media", "instagram", "AI", "privacy"],
    "AMZN":  ["amazon", "cloud", "AWS", "e-commerce", "marketplace", "antitrust"],
    "TSLA":  ["tesla", "electric vehicle", "EV", "battery", "autonomous", "self-driving"],
    "INTC":  ["intel", "semiconductor", "chip", "manufacturing", "CHIPS act"],
    "AMD":   ["AMD", "semiconductor", "chip", "AI", "GPU"],
    "QCOM":  ["qualcomm", "wireless", "5G", "semiconductor", "telecom"],
    "AMAT":  ["applied materials", "semiconductor", "chip", "manufacturing"],
    "MU":    ["micron", "memory", "semiconductor", "DRAM", "chip"],
    "DELL":  ["dell", "computer", "technology", "data center"],
    "ORCL":  ["oracle", "database", "cloud", "software"],
    "ADBE":  ["adobe", "software", "creative", "AI"],
    "NOW":   ["servicenow", "software", "cloud", "enterprise"],
    "PLTR":  ["palantir", "data analytics", "defense", "AI", "government contract"],
    "COIN":  ["coinbase", "cryptocurrency", "crypto", "bitcoin", "digital asset"],
    # Telecom
    "T":     ["AT&T", "telecom", "telecommunications", "wireless", "broadband", "spectrum"],
    "VZ":    ["verizon", "telecom", "wireless", "broadband", "5G"],
    "CMCSA": ["comcast", "broadband", "cable", "media", "telecom"],
    # Finance
    "JPM":   ["jpmorgan", "bank", "banking", "financial regulation", "credit"],
    "BAC":   ["bank of america", "banking", "financial"],
    "GS":    ["goldman sachs", "investment bank", "financial"],
    "MS":    ["morgan stanley", "investment bank", "wealth management"],
    "WFC":   ["wells fargo", "banking", "mortgage", "consumer finance"],
    "BLK":   ["blackrock", "asset management", "ETF", "investment"],
    "V":     ["visa", "payment", "credit card", "financial transaction"],
    "MA":    ["mastercard", "payment", "credit card", "financial transaction"],
    "PYPL":  ["paypal", "digital payment", "fintech"],
    "SQ":    ["block", "square", "payment", "fintech", "bitcoin"],
    "COF":   ["capital one", "credit card", "banking", "consumer finance"],
    "AXP":   ["american express", "credit card", "payment", "travel"],
    # Health Care
    "JNJ":   ["johnson", "pharmaceutical", "drug", "medical device", "health"],
    "UNH":   ["unitedhealthy", "health insurance", "medicare", "medicaid", "ACA"],
    "LLY":   ["eli lilly", "pharmaceutical", "drug", "GLP-1", "obesity", "diabetes"],
    "MRK":   ["merck", "pharmaceutical", "vaccine", "drug pricing"],
    "ABBV":  ["abbvie", "pharmaceutical", "biologic", "rheumatoid"],
    "PFE":   ["pfizer", "pharmaceutical", "vaccine", "drug pricing"],
    "GILD":  ["gilead", "antiviral", "HIV", "drug"],
    "AMGN":  ["amgen", "biologic", "biosimilar", "pharmaceutical"],
    "BIIB":  ["biogen", "alzheimer", "neurological", "drug"],
    "REGN":  ["regeneron", "biologic", "drug", "pharmaceutical"],
    "CVS":   ["CVS", "pharmacy", "health care", "insurance"],
    "CI":    ["cigna", "health insurance", "pharmacy benefit"],
    "HUM":   ["humana", "medicare", "health insurance"],
    "ABT":   ["abbott", "medical device", "diagnostic"],
    "TMO":   ["thermo fisher", "life science", "laboratory"],
    "ALGN":  ["align technology", "dental", "orthodontic", "medical device"],
    # Energy
    "XOM":   ["exxon", "oil", "gas", "energy", "fossil fuel", "refinery", "LNG"],
    "CVX":   ["chevron", "oil", "gas", "energy", "petroleum"],
    "NEE":   ["nextera", "solar", "wind", "renewable energy", "clean energy"],
    "DUK":   ["duke energy", "utility", "electricity", "nuclear", "clean energy"],
    "SO":    ["southern company", "utility", "electricity", "nuclear"],
    # Industrials / Defense
    "LMT":   ["lockheed", "defense", "military", "fighter jet", "missile", "pentagon"],
    "RTX":   ["raytheon", "defense", "aerospace", "military", "missile"],
    "BA":    ["boeing", "aerospace", "defense", "airline", "aircraft"],
    "GE":    ["GE aerospace", "engine", "defense", "aerospace"],
    "HON":   ["honeywell", "aerospace", "industrial", "defense"],
    "CAT":   ["caterpillar", "infrastructure", "construction", "heavy equipment"],
    "DE":    ["deere", "agriculture", "farming", "equipment"],
    "UPS":   ["UPS", "shipping", "logistics", "supply chain", "postal"],
    # Consumer
    "AMZN":  ["amazon", "e-commerce", "retail", "cloud"],
    "WMT":   ["walmart", "retail", "grocery", "supply chain"],
    "HD":    ["home depot", "housing", "construction", "retail"],
    "LOW":   ["lowe's", "housing", "construction", "retail"],
    "MCD":   ["mcdonald's", "fast food", "restaurant", "franchise"],
    "SBUX":  ["starbucks", "coffee", "restaurant", "franchise"],
    "NKE":   ["nike", "athletic", "apparel", "trade", "tariff"],
    "TGT":   ["target", "retail", "consumer"],
    "F":     ["ford", "automobile", "electric vehicle", "EV", "trade", "tariff"],
    "GM":    ["general motors", "automobile", "EV", "trade", "tariff"],
    "TSLA":  ["tesla", "EV", "electric vehicle", "battery", "charging"],
    # Real Estate
    "AMT":   ["american tower", "wireless", "5G", "tower", "spectrum"],
    "PLD":   ["prologis", "warehouse", "logistics", "real estate"],
    "CCI":   ["crown castle", "wireless", "tower", "5G"],
    # Communication / Media
    "DIS":   ["disney", "streaming", "media", "copyright", "entertainment"],
    "NFLX":  ["netflix", "streaming", "media", "broadband"],
    # Consumer Staples
    "PG":    ["procter & gamble", "consumer products", "household"],
    "KO":    ["coca-cola", "beverage", "sugar", "tariff"],
    "PEP":   ["pepsi", "beverage", "food", "snack"],
    "COST":  ["costco", "retail", "membership", "wholesale"],
}

# Sector-level keywords , catches bills affecting a whole sector
SECTOR_KEYWORDS: dict[str, list[str]] = {
    "Technology":             ["artificial intelligence", "AI", "semiconductor", "chip", "CHIPS", "tech", "cybersecurity", "data privacy", "broadband"],
    "Health Care":            ["drug pricing", "pharmaceutical", "medicare", "medicaid", "ACA", "Affordable Care", "prescription", "health insurance", "FDA"],
    "Financials":             ["bank", "banking", "credit", "consumer financial", "CFPB", "securities", "crypto", "digital asset", "fintech", "investment"],
    "Energy":                 ["oil", "gas", "fossil fuel", "clean energy", "renewable", "solar", "wind", "nuclear", "climate", "carbon", "LNG", "pipeline"],
    "Industrials":            ["defense", "military", "infrastructure", "manufacturing", "supply chain", "NDAA", "pentagon", "aerospace"],
    "Consumer Discretionary": ["tariff", "trade", "automobile", "EV", "retail", "e-commerce", "housing"],
    "Consumer Staples":       ["food safety", "FDA", "agriculture", "nutrition", "farm bill", "import"],
    "Communication Services": ["broadband", "spectrum", "media", "telecommunications", "net neutrality", "social media"],
    "Real Estate":            ["housing", "mortgage", "zoning", "rent", "FHFA", "Fannie Mae", "Freddie Mac"],
    "Utilities":              ["electricity", "grid", "nuclear", "clean energy", "utility", "power"],
}


def _headers() -> dict:
    return {}   # Congress.gov uses api_key as query param, not header


def _paginated_get(endpoint: str, params: dict, max_items: int = 250) -> list[dict]:
    """Fetch up to max_items records, handling pagination."""
    items: list[dict] = []
    offset = 0
    limit  = min(250, max_items)

    while len(items) < max_items:
        p = {**params, "limit": limit, "offset": offset, "format": "json", "api_key": CONGRESS_API_KEY}
        try:
            r = requests.get(f"{BASE_URL}{endpoint}", params=p, timeout=20)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            print(f"[FETCH] Error at offset {offset}: {exc}")
            break

        # Congress.gov uses 'bills' or 'laws' as the list key
        batch = data.get("bills", data.get("laws", []))
        if not batch:
            break
        items.extend(batch)
        offset += len(batch)
        total  = data.get("pagination", {}).get("count", 0)
        if offset >= total or len(batch) < limit:
            break

    return items[:max_items]


def fetch_enacted_laws(since_days: int = LOOKBACK_DAYS) -> list[dict]:
    """[FETCH_LAWS] Pull recently enacted laws from /v3/law/{congress}."""
    print(f"[FETCH_LAWS] Fetching enacted laws from {CURRENT_CONGRESS}th Congress (last {since_days} days)…")
    laws = _paginated_get(f"/law/{CURRENT_CONGRESS}", params={}, max_items=500)
    print(f"[FETCH_LAWS] Got {len(laws)} enacted laws total.")

    # Filter to lookback window
    cutoff = datetime.utcnow() - timedelta(days=since_days)
    filtered = []
    for law in laws:
        action = law.get("latestAction") or {}
        date_str = action.get("actionDate", "")
        try:
            if datetime.fromisoformat(date_str) >= cutoff:
                filtered.append(law)
        except Exception:
            filtered.append(law)   # include if date missing

    print(f"[FETCH_LAWS] {len(filtered)} laws in the last {since_days} days.")
    return filtered


def fetch_recent_bills(since_days: int = LOOKBACK_DAYS) -> list[dict]:
    """[FETCH_BILLS] Pull recently updated pending bills from /v3/bill/{congress}."""
    print(f"[FETCH_BILLS] Fetching recent bills from {CURRENT_CONGRESS}th Congress…")
    since = (datetime.utcnow() - timedelta(days=since_days)).strftime("%Y-%m-%dT00:00:00Z")
    bills = _paginated_get(
        f"/bill/{CURRENT_CONGRESS}",
        params={"sort": "updateDate+desc", "fromDateTime": since},
        max_items=500,
    )
    print(f"[FETCH_BILLS] Got {len(bills)} recent bills.")
    return bills


def _text_matches(title: str, action_text: str, keywords: list[str]) -> bool:
    combined = (title + " " + action_text).lower()
    return any(kw.lower() in combined for kw in keywords)


def correlate_bills_to_tickers(
    all_bills: list[dict],
    trades: list[dict],
) -> list[dict]:
    """
    [CORRELATE] For each bill, find which congressional trades involve tickers
    whose company or sector keywords appear in the bill title or action text.
    Returns a list of correlation records.
    """
    print(f"[CORRELATE] Correlating {len(all_bills)} bills against {len(trades)} trades…")

    # Load party lookup (built by congress_bills.py fetch step)
    party_path = BASE_DIR / "politician_parties.json"
    party_map: dict[str, dict] = {}
    if party_path.exists():
        with open(party_path, "r", encoding="utf-8") as _f:
            party_map = json.load(_f)

    # Build ticker → list of full trade records (preserving politician name, party, chamber, transaction)
    ticker_trades: dict[str, list[dict]] = {}
    for t in trades:
        tkr  = t.get("Ticker", t.get("ticker", "")).upper()
        if not tkr:
            continue
        name = t.get("Representative", t.get("representative", "Unknown"))
        info = party_map.get(name, {})
        ticker_trades.setdefault(tkr, []).append({
            "date":        t.get("Date", t.get("TransactionDate", t.get("TradeDate", ""))),
            "politician":  name,
            "party":       info.get("party", "Unknown"),
            "party_abbr":  info.get("party_abbr", "?"),
            "state":       info.get("state", ""),
            "chamber":     t.get("Chamber", "House"),
            "transaction": t.get("Transaction", t.get("transaction", "")),
            "amount":      t.get("Range", t.get("Amount", "")),
        })

    results: list[dict] = []

    for bill in all_bills:
        action = bill.get("latestAction") or {}
        bill_date_str = action.get("actionDate", "")
        try:
            bill_dt = datetime.fromisoformat(bill_date_str)
        except Exception:
            bill_dt = None

        title       = bill.get("title", "") or ""
        action_text = action.get("text", "") or ""
        bill_type   = bill.get("type", "")
        bill_num    = bill.get("number", "")
        congress    = bill.get("congress", CURRENT_CONGRESS)
        is_enacted  = bill.get("isLaw", False) or bill_type in ("", None)

        matched_tickers: list[str] = []
        matched_sectors: list[str] = []

        # Match by ticker keywords
        for tkr, kws in TICKER_KEYWORDS.items():
            if tkr in ticker_trades and _text_matches(title, action_text, kws):
                matched_tickers.append(tkr)

        # Match by sector keywords
        for sector, kws in SECTOR_KEYWORDS.items():
            if _text_matches(title, action_text, kws):
                matched_sectors.append(sector)

        if not matched_tickers and not matched_sectors:
            continue

        # Find trades within ±90 days of the bill's action date, include politician name
        correlated_trades: list[dict] = []
        seen: set[str] = set()   # deduplicate politician+ticker combos
        for tkr in matched_tickers:
            for tr in ticker_trades.get(tkr, []):
                try:
                    td = datetime.fromisoformat(tr["date"])
                except Exception:
                    continue
                if bill_dt and abs((td - bill_dt).days) <= 90:
                    key = f"{tr['politician']}|{tkr}|{tr['date']}"
                    if key in seen:
                        continue
                    seen.add(key)
                    correlated_trades.append({
                        "politician":  tr["politician"],
                        "party":       tr.get("party", "Unknown"),
                        "party_abbr":  tr.get("party_abbr", "?"),
                        "state":       tr.get("state", ""),
                        "chamber":     tr["chamber"],
                        "transaction": tr["transaction"],
                        "ticker":      tkr,
                        "trade_date":  tr["date"],
                        "amount":      tr["amount"],
                        "days_delta":  (td - bill_dt).days if bill_dt else None,
                    })

        results.append({
            "bill_id":          f"{bill_type}{bill_num}-{congress}" if bill_type else f"Law-{congress}",
            "title":            title,
            "action_date":      bill_date_str,
            "action_text":      action_text[:300],
            "is_enacted":       is_enacted,
            "matched_tickers":  sorted(set(matched_tickers)),
            "matched_sectors":  sorted(set(matched_sectors)),
            "correlated_trades": correlated_trades[:20],
        })

    results.sort(key=lambda x: x.get("action_date", ""), reverse=True)
    print(f"[CORRELATE] Found {len(results)} bills with ticker/sector correlations.")
    return results


def main():
    if not CONGRESS_API_KEY:
        raise RuntimeError("CONGRESS_API_KEY not set. Add it to your .env file.")

    laws  = fetch_enacted_laws(LOOKBACK_DAYS)
    bills = fetch_recent_bills(LOOKBACK_DAYS)
    all_bills = laws + bills   # enacted laws get priority via sort

    # Load congressional trades for correlation
    intel_path = BASE_DIR / "GPT_Economy" / "Intelligence_layer (IN PROGRESS)" / "intelligence_output.json"
    trades: list[dict] = []
    if intel_path.exists():
        with open(intel_path, "r", encoding="utf-8") as f:
            intel = json.load(f)
        trades = intel.get("housing_trades", [])
        print(f"[CORRELATE] Loaded {len(trades)} congressional trades for correlation.")
    else:
        print("[CORRELATE] intelligence_output.json not found , correlating bills only.")

    correlations = correlate_bills_to_tickers(all_bills, trades)

    output = {
        "disclaimer":     DISCLAIMER,
        "generated_at":   datetime.utcnow().isoformat() + "Z",
        "congress":       CURRENT_CONGRESS,
        "lookback_days":  LOOKBACK_DAYS,
        "enacted_laws":   len(laws),
        "recent_bills":   len(bills),
        "correlations":   correlations,
        "raw_laws":       [
            {
                "title":       b.get("title", ""),
                "action_date": (b.get("latestAction") or {}).get("actionDate", ""),
                "action_text": (b.get("latestAction") or {}).get("text", "")[:200],
                "type":        b.get("type", "Law"),
                "number":      b.get("number", ""),
            }
            for b in laws
        ],
    }

    # [SAVE]
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[SAVE] Saved to {OUTPUT_FILE}")
    print(f"\nSummary:")
    print(f"  Enacted laws fetched:   {len(laws)}")
    print(f"  Recent bills fetched:   {len(bills)}")
    print(f"  Correlated bill events: {len(correlations)}")

    # Preview top 5 correlations
    if correlations:
        print("\nTop correlated bills:")
        for c in correlations[:5]:
            tickers = ", ".join(c["matched_tickers"]) or ","
            sectors = ", ".join(c["matched_sectors"]) or ","
            print(f"  [{c['action_date']}] {c['title'][:80]}")
            print(f"    Tickers: {tickers}  |  Sectors: {sectors}")
            for tr in c["correlated_trades"][:3]:
                delta = tr.get("days_delta", 0)
                direction = "before" if delta < 0 else "after"
                print(f"    → {tr['politician']} ({tr['chamber']}) {tr['transaction']} {tr['ticker']} "
                      f"on {tr['trade_date']} ({abs(delta)} days {direction} bill)")


if __name__ == "__main__":
    main()
