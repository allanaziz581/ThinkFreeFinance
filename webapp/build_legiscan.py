"""ThinkFree - LegiScan state-legislature fetcher (State Accountability Layer).

Pulls real state-legislative activity for all 50 states + DC from the LegiScan
Public API: the current session per state, the full bill master list (with a
session-wide status breakdown), the legislator roster + party/chamber
composition, and a deep dive on the most recently-active economically-relevant
bills (sponsors + roll-call vote summaries).

Bills are tagged with ThinkFree economic topics (taxes, housing, wages, health,
energy, education, etc.) so the front-end can translate statehouse activity into
"how this affects your rent / paycheck / groceries."

LEGISCAN_API_KEY is read from .env and never written to output or logs.
Writes webapp/js/legiscan_data.js  (window.LEGISCAN_DATA).

Public API budget: 30,000 queries/month. This run spends ~51*3 + deep-dives
(~400 total), well within budget.

Run:  ./tf_env/bin/python webapp/build_legiscan.py
Docs: https://legiscan.com/gaits/documentation/legiscan
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "js" / "legiscan_data.js"
BASE = "https://api.legiscan.com/"

RELEVANT_CAP = 40      # max economically-relevant bills stored per state
DEEP_DIVE = 6          # top-N recent relevant bills to fetch sponsors+votes for
SLEEP = 0.3            # polite delay between API calls

KEY = None
for _line in open(ROOT / ".env", encoding="utf-8"):
    if _line.startswith("LEGISCAN_API_KEY="):
        KEY = _line.strip().split("=", 1)[1]

STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
]

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

# LegiScan bill status codes -> human label
STATUS = {0: "N/A", 1: "Introduced", 2: "Engrossed", 3: "Enrolled",
          4: "Passed", 5: "Vetoed", 6: "Failed"}

# ThinkFree economic topic -> trigger keywords (matched in bill title/description)
TOPICS = {
    "Taxes": ["tax", "taxation", "revenue", "levy", "tax credit", "exemption"],
    "Budget": ["appropriat", "budget", "spending", "fund transfer", "general fund"],
    "Housing": ["housing", "rent", "tenant", "landlord", "eviction", "mortgage", "property tax", "homeowner", "affordable hous", "zoning"],
    "Wages & Labor": ["minimum wage", "wage", "labor", "employ", "overtime", "worker", "union", "paid leave", "workforce"],
    "Healthcare": ["health", "medicaid", "medicare", "insurance", "prescription", "hospital", "drug pric"],
    "Energy & Utilities": ["energy", "utility", "electric", "natural gas", "gasoline", "fuel", "ratepayer", "power"],
    "Education": ["education", "school", "tuition", "student", "university", "college", "scholarship"],
    "Consumer & Credit": ["consumer", "credit", "loan", "lending", "debt", "fee", "interest rate", "payday"],
    "Benefits": ["unemployment", "snap", "benefit", "pension", "retirement", "welfare", "assistance", "social"],
    "Business": ["business", "small business", "commerce", "license", "regulation", "economic development", "tariff"],
}


def get(**params):
    params["key"] = KEY
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "ThinkFree/1.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        d = json.load(r)
    if d.get("status") != "OK":
        raise RuntimeError(d.get("alert", {}).get("message", "LegiScan error"))
    return d


def topics_for(text):
    t = (text or "").lower()
    hits = []
    for topic, kws in TOPICS.items():
        if any(kw in t for kw in kws):
            hits.append(topic)
    return hits


def pick_session(sessions):
    """Most recent regular (non-special) session; fall back to most recent overall."""
    regular = [s for s in sessions if not s.get("special")]
    pool = regular or sessions
    return sorted(pool, key=lambda s: (s.get("year_start", 0), s.get("session_id", 0)), reverse=True)[0]


def clean_people(raw):
    """Drop committee 'sponsors'; keep real legislators with a trimmed record."""
    out = []
    for p in raw:
        if p.get("committee_sponsor") == 1:
            continue
        role = p.get("role", "")
        if role not in ("Sen", "Rep"):
            continue
        out.append({
            "people_id": p.get("people_id"),
            "name": p.get("name"),
            "party": p.get("party") or "?",
            "chamber": "Senate" if role == "Sen" else "House",
            "district": p.get("district", ""),
            "ballotpedia": p.get("ballotpedia", ""),
            "votesmart_id": p.get("votesmart_id") or None,
        })
    return out


def composition(legislators):
    comp = {"Senate": {"D": 0, "R": 0, "I": 0, "Other": 0},
            "House": {"D": 0, "R": 0, "I": 0, "Other": 0}}
    for p in legislators:
        ch = p["chamber"]
        party = p["party"]
        bucket = party if party in ("D", "R", "I") else "Other"
        comp[ch][bucket] += 1
    return comp


def deep_dive(bill_id):
    """Sponsors + recent roll-call vote summaries for one bill."""
    try:
        b = get(op="getBill", id=bill_id)["bill"]
    except Exception:
        return None
    sponsors = []
    for s in b.get("sponsors", []):
        if s.get("committee_sponsor") == 1:
            sponsors.append({"name": s.get("name"), "party": "", "role": "Committee", "district": ""})
        else:
            sponsors.append({
                "name": s.get("name"), "party": s.get("party") or "?",
                "role": s.get("role", ""), "district": s.get("district", ""),
            })
    votes = []
    for v in sorted(b.get("votes", []), key=lambda x: x.get("date", ""), reverse=True)[:5]:
        votes.append({
            "date": v.get("date"), "desc": v.get("desc"),
            "yea": v.get("yea"), "nay": v.get("nay"),
            "passed": v.get("passed"), "chamber": v.get("chamber"),
            "url": v.get("url"),
        })
    return {"sponsors": sponsors[:8], "votes": votes}


def build_state(abbr):
    name = STATE_NAMES[abbr]
    sessions = get(op="getSessionList", state=abbr).get("sessions", [])
    if not sessions:
        return None
    sess = pick_session(sessions)
    sid = sess["session_id"]
    time.sleep(SLEEP)

    ml = get(op="getMasterList", id=sid)["masterlist"]
    bills_raw = [v for k, v in ml.items() if k != "session"]
    time.sleep(SLEEP)

    # session-wide status breakdown across ALL bills
    status_breakdown = {}
    for b in bills_raw:
        lbl = STATUS.get(b.get("status", 0), "Other")
        status_breakdown[lbl] = status_breakdown.get(lbl, 0) + 1

    # economically-relevant bills, most-recently-acted first.
    # Tag on the TITLE only: bill descriptions carry boilerplate fiscal/health
    # language ("no appropriation is made", etc.) that produces false matches.
    relevant = []
    for b in bills_raw:
        topics = topics_for(b.get("title", ""))
        if not topics:
            continue
        relevant.append({
            "bill_id": b.get("bill_id"),
            "number": b.get("number"),
            "url": b.get("url"),
            "title": b.get("title"),
            "status": STATUS.get(b.get("status", 0), "Other"),
            "status_code": b.get("status"),
            "last_action_date": b.get("last_action_date"),
            "last_action": b.get("last_action"),
            "topics": topics,
        })
    relevant.sort(key=lambda x: x.get("last_action_date") or "", reverse=True)
    relevant = relevant[:RELEVANT_CAP]

    # deep dive: sponsors + votes for the top-N most recent relevant bills
    for b in relevant[:DEEP_DIVE]:
        dd = deep_dive(b["bill_id"])
        if dd:
            b["sponsors"] = dd["sponsors"]
            b["votes"] = dd["votes"]
        time.sleep(SLEEP)

    people = clean_people(get(op="getSessionPeople", id=sid).get("sessionpeople", {}).get("people", []))
    time.sleep(SLEEP)

    return {
        "state": abbr,
        "name": name,
        "session": {
            "id": sid,
            "name": sess.get("session_name"),
            "year_start": sess.get("year_start"),
            "year_end": sess.get("year_end"),
            "special": bool(sess.get("special")),
        },
        "bill_total": len(bills_raw),
        "status_breakdown": status_breakdown,
        "relevant_count": len(relevant),
        "bills": relevant,
        "legislator_total": len(people),
        "composition": composition(people),
        "legislators": people,
    }


def main():
    if not KEY:
        print("ERROR: LEGISCAN_API_KEY missing from .env")
        return
    print(f"Fetching LegiScan legislative data for {len(STATES)} jurisdictions...")
    out = {}
    for abbr in STATES:
        try:
            rec = build_state(abbr)
            if not rec:
                print(f"  x {abbr}: no sessions")
                continue
            out[abbr] = rec
            c = rec["composition"]
            print(f"  + {abbr} {rec['name'][:16]:18} {rec['session']['year_start']} | "
                  f"{rec['bill_total']:>5} bills ({rec['relevant_count']} econ) | "
                  f"{rec['legislator_total']:>3} legislators "
                  f"[Sen D{c['Senate']['D']}/R{c['Senate']['R']}  House D{c['House']['D']}/R{c['House']['R']}]")
        except Exception as e:  # noqa: BLE001
            print(f"  x {abbr}: {e}")
        time.sleep(SLEEP)

    data = {
        "source": "LegiScan (legiscan.com) Public API",
        "disclaimer": ("This data describes publicly available state-legislative activity. "
                       "It does not imply or allege wrongdoing of any kind."),
        "byState": out,
        "count": len(out),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// AUTO-GENERATED by webapp/build_legiscan.py (LegiScan API). No API key stored here.\n")
        f.write("window.LEGISCAN_DATA = ")
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write(";\n")
    print(f"\nwrote {OUT} ({OUT.stat().st_size//1024} KB) - {len(out)} jurisdictions")


if __name__ == "__main__":
    main()
