"""ThinkFree - Company relationship fetcher (RELATIONSHIPS ONLY).

Pulls real federal LOBBYING relationships from the Senate LDA API (free) for each
tracked company: which lobbying firms it hires, which lobbyists, which issue areas
and bills it lobbies on, and how much it spends. This is purely the relationship
graph -- who is connected to whom and how -- nothing else.

Writes webapp/js/relationships_data.js (window.RELATIONSHIPS).
Run:  ./tf_env/bin/python webapp/build_relationships.py [--year 2024] [--limit N]
Source: https://lda.senate.gov/api/  (anonymous: ~15 requests/min)
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

JS = Path(__file__).resolve().parent / "js"
OUT = JS / "relationships_data.js"
LDA = "https://lda.senate.gov/api/v1/filings/"
SLEEP = 4.2            # anonymous LDA limit ~15/min
GENERIC = re.compile(r"\b(inc|corp|corporation|company|co|ltd|plc|holdings?|group|the|&)\b\.?", re.I)
BILL_RE = re.compile(r"\b([HS]\.?\s?(?:R\.?|J\.?\s?Res\.?|Con\.?\s?Res\.?|Res\.?)?\s?\d{1,5})\b")


def load_window(fname, marker):
    t = (JS / fname).read_text(encoding="utf-8")
    return json.loads(t.split(marker, 1)[1].rstrip().rstrip(";").strip())


def search_name(name):
    """A distinctive client-name search term for the LDA API."""
    n = GENERIC.sub("", name or "").strip().strip(",").strip()
    return n or name


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ThinkFree/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_company(name, year):
    url = LDA + "?" + urllib.parse.urlencode({"client_name": search_name(name), "filing_year": year, "page_size": 25})
    try:
        d = get(url)
    except Exception as e:  # noqa: BLE001
        return None, str(e)
    results = d.get("results", [])
    firms, lobbyists, issues, bills = Counter(), set(), Counter(), set()
    spend = 0.0
    for f in results:
        reg = (f.get("registrant") or {}).get("name")
        if reg:
            firms[reg] += 1
        for k in ("income", "expenses"):
            try:
                spend += float(f.get(k) or 0)
            except (TypeError, ValueError):
                pass
        for a in (f.get("lobbying_activities") or []):
            iss = a.get("general_issue_code_display")
            if iss:
                issues[iss] += 1
            for l in (a.get("lobbyists") or []):
                lob = l.get("lobbyist") or {}
                nm = ((lob.get("first_name") or "") + " " + (lob.get("last_name") or "")).strip()
                if nm:
                    lobbyists.add(nm.title())
            for b in BILL_RE.findall(a.get("description", "") or ""):
                bills.add(re.sub(r"\s+", " ", b).upper())
    return {
        "client": (results[0].get("client") or {}).get("name") if results else search_name(name),
        "filings": d.get("count", len(results)),
        "spend_fmt": _money(spend),
        "firms": [f for f, _ in firms.most_common(12)],
        "lobbyists": sorted(lobbyists)[:16],
        "issues": [i for i, _ in issues.most_common(12)],
        "bills": sorted(bills)[:20],
    }, None


def _money(n):
    if not n:
        return None
    if n >= 1e6:
        return f"${n/1e6:.1f}M"
    if n >= 1e3:
        return f"${n/1e3:.0f}K"
    return f"${n:,.0f}"


def main():
    year = 2024
    limit = None
    if "--year" in sys.argv:
        year = int(sys.argv[sys.argv.index("--year") + 1])
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    iw = load_window("influence_data.js", "window.IW_DATA =").get("companies", {})
    px = load_window("prices_data.js", "window.PRICES_DATA =").get("byTicker", {}) if (JS / "prices_data.js").exists() else {}
    sp = load_window("sp500_data.js", "window.SP500 =").get("byTicker", {}) if (JS / "sp500_data.js").exists() else {}
    # every company across all datasets, with a usable name for the LDA client search
    nm = {}
    for tk, c in sp.items():
        nm[tk] = c.get("name") or tk
    for tk, c in px.items():
        if c.get("name"):
            nm[tk] = c["name"]
    for tk, c in iw.items():
        if c.get("name"):
            nm[tk] = c["name"]
    names = nm
    tickers = sorted(nm)
    if limit:
        tickers = tickers[:limit]
    print(f"Fetching lobbying relationships for {len(tickers)} companies (year {year})...")

    out = {}
    for tk in tickers:
        name = names[tk]
        rec, err = fetch_company(name, year)
        if err:
            print(f"  x {tk} ({name[:20]}): {err}")
        elif rec and (rec["firms"] or rec["filings"]):
            out[tk] = rec
            print(f"  + {tk:6} {name[:22]:24} {rec['filings']:>3} filings | {len(rec['firms'])} firms | {len(rec['issues'])} issues | {len(rec['bills'])} bills | {rec['spend_fmt'] or '-'}")
        else:
            print(f"  - {tk}: no lobbying on record")
        time.sleep(SLEEP)

    data = {"source": "U.S. Senate Lobbying Disclosure Act (LDA) database", "year": year,
            "disclaimer": "Public federal lobbying disclosures. Describes relationships only; does not imply wrongdoing.",
            "byTicker": out, "count": len(out)}
    OUT.write_text("// AUTO-GENERATED by webapp/build_relationships.py (Senate LDA). No API keys.\nwindow.RELATIONSHIPS = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"\nwrote {OUT} ({OUT.stat().st_size // 1024} KB) - {len(out)} companies")


if __name__ == "__main__":
    main()
