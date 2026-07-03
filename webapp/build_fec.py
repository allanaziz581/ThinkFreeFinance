"""ThinkFree - OpenFEC (Federal Election Commission) fetcher.

Pulls real campaign-finance data for the politicians tracked in ThinkFree:
total receipts, money from individuals vs. PACs, disbursements, cash on hand,
and top contributors by employer. Writes webapp/js/fec_data.js.

API key is read from .env (FEC_API_KEY) and never written to output or logs.

Run:  ./tf_env/bin/python webapp/build_fec.py
Docs: https://api.open.fec.gov/developers/  (repo: github.com/fecgov/fec)
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "js" / "fec_data.js"
BASE = "https://api.open.fec.gov/v1/"
TOP_EMPLOYER_LIMIT = 30   # fetch top-contributor breakdown for the N biggest names

KEY = None
for _line in open(ROOT / ".env", encoding="utf-8"):
    if _line.startswith("FEC_API_KEY="):
        KEY = _line.strip().split("=", 1)[1]


def get(path, **params):
    params["api_key"] = KEY
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "ThinkFree/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


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


def politicians():
    d = json.load(open(ROOT / "politician_performance.json", encoding="utf-8"))
    return d.get("politician_summary", [])


def find_candidate(name, chamber, state):
    office = "H" if str(chamber).lower().startswith("h") else ("S" if str(chamber).lower().startswith("s") else None)
    try:
        params = {"q": name, "per_page": 10}
        if office:
            params["office"] = office
        d = get("candidates/search/", **params)
    except Exception as e:  # noqa: BLE001
        print(f"     search error for {name}: {e}")
        return None
    res = d.get("results") or []
    st = STATE_ABBR.get(state, "")
    # prefer state match, then has committee, then most recent filing
    res.sort(key=lambda c: (st and c.get("state") == st, bool(c.get("principal_committees")), c.get("last_file_date") or ""), reverse=True)
    return res[0] if res else None


STATE_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO",
    "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
    "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}


def main():
    if not KEY:
        print("ERROR: FEC_API_KEY missing from .env")
        return
    pols = politicians()
    print(f"Fetching FEC data for {len(pols)} politicians...")
    out = {}
    ranked = sorted(pols, key=lambda p: p.get("Mean Buy Excess vs SPY (%)") or 0, reverse=True)
    top_names = {p.get("Politician") for p in ranked[:TOP_EMPLOYER_LIMIT]}

    for p in pols:
        name = p.get("Politician", "")
        try:
            cand = find_candidate(name, p.get("Chamber"), p.get("State"))
            if not cand:
                print(f"  x {name}: no FEC candidate"); continue
            cid = cand.get("candidate_id")
            rec = {
                "candidate_id": cid,
                "fec_name": cand.get("name"),
                "party": cand.get("party"),
                "office": cand.get("office_full"),
                "url": f"https://www.fec.gov/data/candidate/{cid}/",
            }
            # totals (latest cycle)
            try:
                t = get(f"candidate/{cid}/totals/", per_page=1, sort="-cycle")
                tot = (t.get("results") or [{}])[0]
                rec.update({
                    "cycle": tot.get("cycle"),
                    "receipts": tot.get("receipts"), "receipts_fmt": money(tot.get("receipts")),
                    "from_individuals": tot.get("individual_contributions"), "from_individuals_fmt": money(tot.get("individual_contributions")),
                    "from_pacs": tot.get("other_political_committee_contributions"), "from_pacs_fmt": money(tot.get("other_political_committee_contributions")),
                    "disbursements": tot.get("disbursements"), "disbursements_fmt": money(tot.get("disbursements")),
                    "cash": tot.get("last_cash_on_hand_end_period"), "cash_fmt": money(tot.get("last_cash_on_hand_end_period")),
                })
            except Exception:
                pass
            # top contributors by employer (only for biggest names, to limit calls)
            if name in top_names and cand.get("principal_committees"):
                cm = cand["principal_committees"][0].get("committee_id")
                cyc = rec.get("cycle")
                try:
                    emp = get("schedules/schedule_a/by_employer/", committee_id=cm, cycle=cyc, per_page=8, sort="-total")
                    rec["top_employers"] = [{"employer": e.get("employer"), "total_fmt": money(e.get("total"))}
                                            for e in (emp.get("results") or []) if e.get("employer")]
                except Exception:
                    pass
            out[name] = rec
            print(f"  + {name}: {cid} | receipts {rec.get('receipts_fmt')} | PAC {rec.get('from_pacs_fmt')} ({rec.get('cycle')})")
            time.sleep(0.25)
        except Exception as e:  # noqa: BLE001
            print(f"  x {name}: {e}")

    data = {"source": "OpenFEC (Federal Election Commission)", "byName": out, "count": len(out)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// AUTO-GENERATED by webapp/build_fec.py (OpenFEC API). No API key stored here.\n")
        f.write("window.FEC_DATA = ")
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write(";\n")
    print(f"\nwrote {OUT} ({OUT.stat().st_size//1024} KB) - {len(out)} politicians")


if __name__ == "__main__":
    main()
