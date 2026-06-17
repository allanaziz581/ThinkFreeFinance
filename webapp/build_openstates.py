"""ThinkFree - Open States (Plural) legislator enrichment.

Secondary source that complements LegiScan (build_legiscan.py). Open States v3
provides clean, normalized legislator records WITH photos, email, and OpenStates
profile links for every state legislature. The front-end cross-references these
to the LegiScan roster by name to show faces + contact for accountability.

Open States v3 is rate-limited (1 req/sec, ~500/day on the free tier) and its
gateway 502s intermittently, so every call retries with backoff and the build
degrades gracefully: a state that can't be fetched is simply skipped, not fatal.

OPENSTATES_API_KEY is read from .env and never written to output or logs.
Writes webapp/js/openstates_data.js  (window.OPENSTATES_DATA).

Run:  ./tf_env/bin/python webapp/build_openstates.py
Docs: https://docs.openstates.org/api-v3/
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "js" / "openstates_data.js"
BASE = "https://v3.openstates.org/people"

PER_PAGE = 50          # v3 maximum
MAX_PAGES = 12         # safety cap (NH House alone is 400 members ~= 8 pages)
RATE = 1.15            # >= 1s between calls (free tier: 1 req/sec)
RETRIES = 4            # retries per request on 502 / 429 / transient errors

KEY = None
for _line in open(ROOT / ".env", encoding="utf-8"):
    if _line.startswith("OPENSTATES_API_KEY="):
        KEY = _line.strip().split("=", 1)[1]

# jurisdiction names accepted by the v3 API (full state names + DC)
STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia",
}

CHAMBER = {"upper": "Senate", "lower": "House", "legislature": "Legislature"}
PARTY = {"Democratic": "D", "Republican": "R", "Independent": "I"}


def fetch_page(jurisdiction, page):
    params = {"jurisdiction": jurisdiction, "per_page": PER_PAGE, "page": page, "apikey": KEY}
    url = BASE + "?" + urllib.parse.urlencode(params)
    last_err = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ThinkFree/1.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001  (502/429/timeouts are expected here)
            last_err = e
            time.sleep(RATE * (attempt + 2))  # linear backoff, respects rate limit
    raise last_err


def build_state(abbr):
    jurisdiction = STATE_NAMES[abbr]
    people, page, max_page = [], 1, 1
    while page <= max_page and page <= MAX_PAGES:
        d = fetch_page(jurisdiction, page)
        for p in d.get("results", []):
            role = p.get("current_role") or {}
            people.append({
                "name": p.get("name"),
                "party": PARTY.get(p.get("party"), p.get("party") or "?"),
                "chamber": CHAMBER.get(role.get("org_classification"), role.get("org_classification") or ""),
                "district": str(role.get("district") or ""),
                "image": p.get("image") or "",
                "email": p.get("email") or "",
                "openstates_url": p.get("openstates_url") or "",
            })
        max_page = (d.get("pagination") or {}).get("max_page", 1)
        page += 1
        time.sleep(RATE)
    return people


def main():
    if not KEY:
        print("ERROR: OPENSTATES_API_KEY missing from .env")
        return
    print(f"Enriching legislators from Open States for {len(STATE_NAMES)} jurisdictions...")
    out, skipped = {}, []
    for abbr in STATE_NAMES:
        try:
            people = build_state(abbr)
            if people:
                with_photo = sum(1 for p in people if p["image"])
                out[abbr] = {"name": STATE_NAMES[abbr], "legislators": people}
                print(f"  + {abbr} {STATE_NAMES[abbr][:16]:18} {len(people):>3} legislators ({with_photo} with photo)")
            else:
                skipped.append(abbr)
                print(f"  x {abbr}: empty")
        except Exception as e:  # noqa: BLE001
            skipped.append(abbr)
            print(f"  x {abbr}: {e} (Open States gateway likely down - skipped)")
        time.sleep(RATE)

    data = {
        "source": "Open States / Plural (openstates.org) API v3",
        "byState": out,
        "count": len(out),
        "skipped": skipped,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// AUTO-GENERATED by webapp/build_openstates.py (Open States v3). No API key stored here.\n")
        f.write("window.OPENSTATES_DATA = ")
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write(";\n")
    print(f"\nwrote {OUT} ({OUT.stat().st_size//1024} KB) - {len(out)} jurisdictions, {len(skipped)} skipped")


if __name__ == "__main__":
    main()
