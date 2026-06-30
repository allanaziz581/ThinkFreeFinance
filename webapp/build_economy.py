"""ThinkFree - Economic / Cost-of-Living tracker builder.

Pulls a broad set of consumer-facing economic indicators and frames every one
against a fixed JANUARY 2025 baseline (the reference the dashboard anchors on),
plus a trailing year-over-year change, so a reader can see "what has this cost
done since the start of 2025, and over the last 12 months."

Single source path: the FRED API (FRED_API_KEY). FRED mirrors the underlying
BLS CPI component and average-price (APU) series, the University of Michigan
sentiment/expectations series, Freddie Mac mortgage rates, Census/HUD home
prices and the Federal Reserve credit series, so one typed fetch covers every
category. The `source` field on each indicator names the true originating
agency. Any series that fails to fetch is OMITTED, never faked.

Writes webapp/js/economy_data.js (window.ECONOMY). FRED_API_KEY is read from
.env and never written to output or logs.
Run: ./tf_env/bin/python webapp/build_economy.py
Docs: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "js" / "economy_data.js"
FRED_OBS = "https://api.stlouisfed.org/fred/series/observations"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
BASELINE = "2025-01-01"        # the Jan 2025 reference line the cards measure from
OBS_START = "2021-01-01"       # enough history for a clean chart + baseline + YoY
MAX_BYTES = 8 * 1024 * 1024
UA = {"User-Agent": "ThinkFree/1.0"}


def _env(name: str) -> str:
    try:
        for line in open(ROOT / ".env", encoding="utf-8"):
            if line.startswith(name + "="):
                return line.strip().split("=", 1)[1]
    except OSError:
        pass
    return os.environ.get(name, "")


FRED_KEY = _env("FRED_API_KEY")

# direction: "price" -> a rise is bad for households (red); "good" -> a rise is
# good (green, e.g. wages, jobs, sentiment). is_rate -> headline is a level
# change in percentage points, not a percent change (rates, ratios).
# fmt tuple: (prefix, scale, decimals, suffix). value is multiplied by scale.
IDX = ("", 1, 1, "")
RATE = ("", 1, 2, "%")
USD2 = ("$", 1, 2, "")

CATALOG = [
    ("Food & Groceries", [
        ("CUSR0000SAF11",  "Groceries (Food at Home)", "BLS CPI",          "price", False, IDX),
        ("APU0000708111",  "Eggs, Grade A (dozen)",    "BLS Average Price", "price", False, USD2),
        ("APU0000709112",  "Milk, Whole (gallon)",     "BLS Average Price", "price", False, USD2),
        ("APU0000702111",  "Bread, White (lb)",        "BLS Average Price", "price", False, USD2),
        ("APU0000703112",  "Ground Beef (lb)",         "BLS Average Price", "price", False, USD2),
        ("APU0000706111",  "Chicken (lb)",             "BLS Average Price", "price", False, USD2),
        ("APU0000717311",  "Coffee (lb)",              "BLS Average Price", "price", False, USD2),
        ("CUSR0000SEFV",   "Dining Out (Food Away)",   "BLS CPI",          "price", False, IDX),
    ]),
    ("Housing & Utilities", [
        ("CUSR0000SEHA",   "Rent of Primary Residence", "BLS CPI",         "price", False, IDX),
        ("CUSR0000SAH1",   "Shelter (All)",             "BLS CPI",         "price", False, IDX),
        ("APU000072610",   "Electricity (per kWh)",     "BLS Average Price","price", False, ("$", 1, 3, "/kWh")),
        ("CUSR0000SEHF02", "Utility (Piped) Gas",       "BLS CPI",         "price", False, IDX),
        ("CUSR0000SEHG",   "Water & Sewer / Trash",     "BLS CPI",         "price", False, IDX),
    ]),
    ("Transportation & Gas", [
        ("GASREGW",        "Gas, Regular (per gallon)", "EIA via FRED",    "price", False, ("$", 1, 2, "/gal")),
        ("CUSR0000SETA01", "New Vehicles",              "BLS CPI",         "price", False, IDX),
        ("CUSR0000SETA02", "Used Cars & Trucks",        "BLS CPI",         "price", False, IDX),
        ("CUSR0000SETG01", "Airline Fares",             "BLS CPI",         "price", False, IDX),
        ("CUSR0000SETD",   "Vehicle Maintenance",       "BLS CPI",         "price", False, IDX),
    ]),
    ("Healthcare", [
        ("CPIMEDSL",       "Medical Care (All)",        "BLS CPI",         "price", False, IDX),
        ("CUSR0000SEMC",   "Medical Care Services",     "BLS CPI",         "price", False, IDX),
        ("CUSR0000SAM1",   "Medical Commodities (Drugs)","BLS CPI",        "price", False, IDX),
        ("CUSR0000SEMD",   "Hospital Services",         "BLS CPI",         "price", False, IDX),
    ]),
    ("Education", [
        ("CUSR0000SEEB",   "College Tuition & Fees",    "BLS CPI",         "price", False, IDX),
        ("CUUR0000SEEA",   "Educational Books",         "BLS CPI",         "price", False, IDX),
    ]),
    ("Personal & Clothing", [
        ("CPIAPPSL",       "Apparel (All)",             "BLS CPI",         "price", False, IDX),
        ("CUSR0000SAG1",   "Personal Care & Services",  "BLS CPI",         "price", False, IDX),
    ]),
    ("Housing Metrics", [
        ("MORTGAGE30US",   "30-Year Mortgage Rate",     "Freddie Mac",     "price", True,  RATE),
        ("MSPUS",          "Median Home Sale Price",    "Census / HUD",    "price", False, ("$", 1, 0, "")),
        ("CSUSHPISA",      "Home Price Index (Case-Shiller)", "S&P / FRED","price", False, IDX),
        ("HOUST",          "Housing Starts",            "Census",          "good",  False, ("", 0.001, 2, "M")),
        ("EXHOSLUSM495S",  "Existing Home Sales",       "NAR / FRED",      "good",  False, ("", 0.001, 2, "M")),
    ]),
    ("Jobs & Employment", [
        ("UNRATE",         "Unemployment Rate",         "BLS",             "good",  True,  RATE),
        ("PAYEMS",         "Nonfarm Payrolls",          "BLS",             "good",  False, ("", 0.001, 2, "M")),
        ("CIVPART",        "Labor Force Participation",  "BLS",            "good",  True,  RATE),
        ("JTSJOL",         "Job Openings",              "BLS JOLTS",       "good",  False, ("", 0.001, 2, "M")),
        ("CES0500000003",  "Avg Hourly Earnings",       "BLS",             "good",  False, USD2),
        ("ICSA",           "Initial Jobless Claims",    "DOL",             "good",  True,  ("", 0.001, 0, "K")),
    ]),
    ("Consumer Sentiment", [
        ("UMCSENT",        "Consumer Sentiment (UMich)", "U. of Michigan", "good",  False, IDX),
    ]),
    ("Spending & Retail", [
        ("RSAFS",          "Retail Sales",              "Census",          "good",  False, ("$", 0.001, 1, "B")),
        ("PCE",            "Personal Consumption (PCE)", "BEA",            "good",  False, ("$", 0.001, 2, "T")),
        ("PCEC96",         "Real PCE",                  "BEA",             "good",  False, ("$", 0.001, 2, "T")),
    ]),
    ("Income", [
        ("DSPIC96",        "Real Disposable Income",    "BEA",             "good",  False, ("$", 0.001, 2, "T")),
        ("PI",             "Personal Income",           "BEA",             "good",  False, ("$", 0.001, 2, "T")),
        ("LES1252881600Q", "Real Median Weekly Earnings","BLS",            "good",  False, ("$", 1, 0, "")),
    ]),
    ("Consumer Debt", [
        ("TOTALSL",        "Total Consumer Credit",     "Federal Reserve", "price", False, ("$", 0.001, 2, "T")),
        ("TERMCBCCALLNS",  "Credit Card APR",           "Federal Reserve", "price", True,  RATE),
        ("TDSP",           "Household Debt Service Ratio","Federal Reserve","price", True,  RATE),
        ("DRCCLACBS",      "Credit Card Delinquency Rate","Federal Reserve","price",True,  RATE),
    ]),
    ("Auto Sales", [
        ("TOTALSA",        "Total Vehicle Sales",       "BEA",             "good",  False, ("", 1, 1, "M")),
        ("TERMCBAUTO48NS", "Auto Loan Rate (48mo)",     "Federal Reserve", "price", True,  RATE),
    ]),
    ("Inflation Expectations", [
        ("MICH",           "1-Year Inflation Expectation","U. of Michigan","price", True,  RATE),
        ("T5YIE",          "5-Year Breakeven Inflation", "FRED / Treasury","price", True,  RATE),
        ("T10YIE",         "10-Year Breakeven Inflation","FRED / Treasury","price", True,  RATE),
        ("CPIAUCSL",       "CPI, All Items",            "BLS",             "price", False, IDX),
        ("CPILFESL",       "Core CPI",                  "BLS",             "price", False, IDX),
    ]),
]


def _http(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("response too large")
    return body


def fetch_series(series_id: str) -> list[list]:
    """Return [[YYYY-MM-DD, float], ...] ascending, or [] on failure. Tries the
    keyed JSON API first, then the public CSV endpoint as a fallback."""
    if FRED_KEY:
        q = urllib.parse.urlencode({
            "series_id": series_id, "api_key": FRED_KEY, "file_type": "json",
            "observation_start": OBS_START, "sort_order": "asc",
        })
        try:
            doc = json.loads(_http(f"{FRED_OBS}?{q}").decode())
            obs = doc.get("observations", [])
            out = []
            for o in obs:
                v = o.get("value", ".")
                if v in (".", "", None):
                    continue
                try:
                    out.append([o["date"][:10], float(v)])
                except (ValueError, KeyError):
                    continue
            # With a valid key, an empty result means the series id is invalid;
            # return it (the caller omits it) rather than hammering the slow CSV.
            return out
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            return []
    # No key: public CSV (no key). Columns: observation_date, <id>.
    try:
        text = _http(FRED_CSV + urllib.parse.quote(series_id)).decode()
        out = []
        for ln in text.splitlines()[1:]:
            parts = ln.split(",")
            if len(parts) < 2 or parts[1] in (".", ""):
                continue
            d = parts[0][:10]
            if d < OBS_START:
                continue
            try:
                out.append([d, float(parts[1])])
            except ValueError:
                continue
        return out
    except (urllib.error.URLError, OSError, ValueError):
        return []


def _nearest(series: list[list], target: str) -> list | None:
    """Observation whose date is closest to target (YYYY-MM-DD)."""
    if not series:
        return None
    try:
        t = datetime.strptime(target, "%Y-%m-%d")
    except ValueError:
        return None
    best, best_gap = None, 10 ** 9
    for d, v in series:
        try:
            gap = abs((datetime.strptime(d, "%Y-%m-%d") - t).days)
        except ValueError:
            continue
        if gap < best_gap:
            best, best_gap = [d, v], gap
    return best


def _fmt(value: float, spec) -> str:
    pre, scale, dec, suf = spec
    return f"{pre}{value * scale:,.{dec}f}{suf}"


def build_indicator(meta: tuple) -> dict | None:
    sid, name, source, direction, is_rate, spec = meta
    series = fetch_series(sid)
    if len(series) < 2:
        print(f"  skip {sid} ({name}): no data")
        return None

    cur = series[-1]
    base = _nearest(series, BASELINE)
    # year before the current observation
    try:
        cy = datetime.strptime(cur[0], "%Y-%m-%d")
        yoy_target = cy.replace(year=cy.year - 1).strftime("%Y-%m-%d")
    except ValueError:
        yoy_target = None
    yoy = _nearest(series, yoy_target) if yoy_target else None

    def pct(a, b):
        return round((a - b) / b * 100, 1) if b not in (0, None) else None

    since_pct = pct(cur[1], base[1]) if base else None
    since_abs = round(cur[1] - base[1], 2) if base else None
    yoy_pct = pct(cur[1], yoy[1]) if yoy else None
    yoy_abs = round(cur[1] - yoy[1], 2) if yoy else None

    # downsample to <= 60 points for a clean chart while keeping the endpoints
    step = max(1, len(series) // 60)
    chart = series[::step]
    if chart[-1] != cur:
        chart.append(cur)

    return {
        "id": sid, "name": name, "source": source, "direction": direction,
        "is_rate": is_rate, "unit": spec[3],
        "current": round(cur[1], 4), "current_fmt": _fmt(cur[1], spec), "current_date": cur[0],
        "baseline": round(base[1], 4) if base else None,
        "baseline_fmt": _fmt(base[1], spec) if base else None,
        "baseline_date": base[0] if base else None,
        "since_baseline_pct": since_pct, "since_baseline_abs": since_abs,
        "yoy_pct": yoy_pct, "yoy_abs": yoy_abs,
        "series": chart,
    }


def build_doc() -> "tuple[dict | None, list[str]]":
    """Pull every catalog series from FRED and return (window.ECONOMY doc, skipped).
    Pure compute + network, no file IO, so the FastAPI service's in-process
    refresher can call it directly to get the freshest economy data without a
    rebuild or a git commit. Returns (None, skipped) if nothing could be sourced."""
    categories = []
    missing = []
    for cat_name, items in CATALOG:
        built = []
        for meta in items:
            ind = build_indicator(meta)
            if ind:
                built.append(ind)
            else:
                missing.append(f"{meta[1]} ({meta[0]})")
        if built:
            categories.append({"name": cat_name, "indicators": built})
    if not categories:
        return None, missing
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_label": "Jan 2025",
        "baseline_date": BASELINE,
        "source_note": ("Indicators are sourced from the Federal Reserve Economic Data (FRED) service, "
                        "which mirrors the originating agency series (BLS, BEA, Census, Freddie Mac, "
                        "University of Michigan, Federal Reserve). Each card names its origin. "
                        "Changes are measured against a fixed January 2025 baseline."),
        "categories": categories,
    }
    return doc, missing


def main() -> int:
    if not FRED_KEY:
        print("[economy] FRED_API_KEY not set; using public CSV fallback (slower, may rate-limit).")
    doc, missing = build_doc()
    if doc is None:
        print("[economy] no indicators sourced; leaving existing data unchanged.")
        return 1
    categories = doc["categories"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".js.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("// AUTO-GENERATED by webapp/build_economy.py - do not edit by hand.\n")
        f.write("window.ECONOMY = ")
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    tmp.replace(OUT)
    total = sum(len(c["indicators"]) for c in categories)
    print(f"[economy] wrote {total} indicators across {len(categories)} categories.")
    print(f"[economy] sourced: {total}; missing/skipped: {len(missing)}")
    if missing:
        print("[economy] skipped: " + "; ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
