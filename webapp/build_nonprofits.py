"""ThinkFree - ProPublica Nonprofit Explorer fetcher.

Many of the lobbying / industry groups shown in InfluenceWeb are real
501(c)(4)/(c)(6) nonprofits with public IRS Form 990 financials. This pulls
their EIN, revenue, expenses, assets, and latest filing from ProPublica's
Nonprofit Explorer API (no auth) and writes webapp/js/nonprofit_data.js.

Run:  ./tf_env/bin/python webapp/build_nonprofits.py

API: https://projects.propublica.org/nonprofits/api/v2  (GET only, no key)
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / "js" / "nonprofit_data.js"
BASE = "https://projects.propublica.org/nonprofits/api/v2"

# display name (as shown in the app) -> ProPublica search query
ORGS = {
    "Information Technology Industry Council": "Information Technology Industry Council",
    "Semiconductor Industry Assn": "Semiconductor Industry Association",
    "Internet & Television Assn": "NCTA The Internet Television Association",
    "PhRMA": "Pharmaceutical Research and Manufacturers of America",
    "American Hospital Assn": "American Hospital Association",
    "American Bankers Assn": "American Bankers Association",
    "Securities Industry & Fin. Markets Assn": "Securities Industry and Financial Markets Association",
    "American Petroleum Institute": "American Petroleum Institute",
    "Edison Electric Institute": "Edison Electric Institute",
    "Natl Assn of Manufacturers": "National Association of Manufacturers",
    "Natl Assn of Realtors": "National Association of Realtors",
    "Real Estate Roundtable": "Real Estate Roundtable",
    "Natl Retail Federation": "National Retail Federation",
    "Grocery Manufacturers Assn": "Consumer Brands Association",
    "American Chemistry Council": "American Chemistry Council",
    "Natl Mining Assn": "National Mining Association",
    "Business Roundtable": "Business Roundtable",
    "US Chamber of Commerce": "Chamber of Commerce of the United States",
    # advocacy 501(c)(4)s used as outside-spending groups
    "League of Conservation Voters": "League of Conservation Voters",
    "Americans for Prosperity": "Americans for Prosperity",
    "Club for Growth Action": "Club for Growth",
    "End Citizens United": "End Citizens United",
}

NTEE_MAJOR = {
    "A": "Arts & Culture", "B": "Education", "C": "Environment", "D": "Animals",
    "E": "Health", "F": "Mental Health", "G": "Disease/Disorders", "H": "Medical Research",
    "I": "Crime/Legal", "J": "Employment", "K": "Food/Agriculture", "L": "Housing",
    "M": "Public Safety", "N": "Recreation/Sports", "O": "Youth Development",
    "P": "Human Services", "Q": "International", "R": "Civil Rights/Advocacy",
    "S": "Community/Economic Dev.", "T": "Philanthropy", "U": "Science & Tech",
    "V": "Social Science", "W": "Public/Societal Benefit", "X": "Religion",
    "Y": "Mutual Benefit", "Z": "Unknown",
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ThinkFree/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def best_match(query):
    d = get(f"{BASE}/search.json?q={urllib.parse.quote(query)}")
    orgs = d.get("organizations") or []
    return orgs[0] if orgs else None


def latest_financials(ein):
    d = get(f"{BASE}/organizations/{ein}.json")
    org = d.get("organization", {}) or {}
    filings = d.get("filings_with_data") or []
    filings = sorted(filings, key=lambda f: f.get("tax_prd_yr") or 0, reverse=True)
    best = next((f for f in filings if f.get("totrevenue")), (filings[0] if filings else {}))
    return org, best


def money(n):
    if not n:
        return None
    a = abs(n)
    if a >= 1e9:
        return f"${a/1e9:.2f}B"
    if a >= 1e6:
        return f"${a/1e6:.1f}M"
    if a >= 1e3:
        return f"${a/1e3:.0f}K"
    return f"${a:,.0f}"


def main():
    out = {}
    print(f"Fetching {len(ORGS)} nonprofits from ProPublica...")
    for name, query in ORGS.items():
        try:
            org = best_match(query)
            if not org:
                print(f"  x {name}: no match"); continue
            ein = org.get("ein")
            full, fil = latest_financials(ein)
            ntee = (org.get("ntee_code") or full.get("ntee_code") or "")
            out[name] = {
                "ein": org.get("strein") or str(ein),
                "name": org.get("name") or full.get("name"),
                "city": org.get("city") or full.get("city"),
                "state": org.get("state") or full.get("state"),
                "ntee": ntee,
                "ntee_label": NTEE_MAJOR.get((ntee or " ")[0], ""),
                "revenue": fil.get("totrevenue"),
                "revenue_fmt": money(fil.get("totrevenue")),
                "expenses": fil.get("totfuncexpns"),
                "expenses_fmt": money(fil.get("totfuncexpns")),
                "assets": fil.get("totassetsend"),
                "assets_fmt": money(fil.get("totassetsend")),
                "year": fil.get("tax_prd_yr"),
                "url": f"https://projects.propublica.org/nonprofits/organizations/{ein}",
            }
            print(f"  + {name}: EIN {out[name]['ein']} | rev {out[name]['revenue_fmt']} ({out[name]['year']})")
            time.sleep(0.3)
        except Exception as e:  # noqa: BLE001
            print(f"  x {name}: {e}")

    data = {"source": "ProPublica Nonprofit Explorer (IRS Form 990)", "byName": out, "count": len(out)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// AUTO-GENERATED by webapp/build_nonprofits.py (ProPublica Nonprofit Explorer API)\n")
        f.write("window.NP_DATA = ")
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write(";\n")
    print(f"\nwrote {OUT} ({OUT.stat().st_size//1024} KB) - {len(out)} orgs")


if __name__ == "__main__":
    main()
