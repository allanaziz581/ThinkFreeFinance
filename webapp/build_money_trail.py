"""The Money Trail Detective Engine.

Upgrades the loose "suspicion correlation" score into a chain-of-evidence CASE
FILE. Each law is scored as CASE STRENGTH built from a 6-link chain; the
composite leans MULTIPLICATIVE on the two critical links (a real beneficiary and
real access), so a case cannot score high on trade volume alone.

The six links (each returns a 0..1 strength):
  1. The Law         what economic action the bill takes (funds / awards / rule).
  2. The Beneficiary  the specific companies whose revenue depends on it (materiality).
  3. The Access       did a trader sponsor/cosponsor the bill (Congress.gov).
  4. The Trade        did access-holders trade the beneficiary BEFORE the
                      committee/markup milestone (re-anchored timing, not final passage).
  5. The Payoff       abnormal (market-adjusted, baseline-relative) return, from
                      QuiverQuant excess_return vs the member's own baseline.
  6. The Pattern      cross-law repetition per member + multi-member clustering.

CASE STRENGTH = 100 * gate(L2, L3) * evidence(L1, L4, L5, L6)
  gate     = (0.15 + 0.85*L2) * (0.15 + 0.85*L3)        # critical, multiplicative
  evidence = 0.20*L1 + 0.35*L4 + 0.25*L5 + 0.20*L6        # supporting, additive (sums to 1)
With no beneficiary OR no access the gate collapses toward ~0.02, capping the
score in the single digits no matter how many trades exist.

Data sources per link:
  Congress.gov  /bill/{c}/{type}/{num}/actions      -> milestones (Phase 1)
  Congress.gov  /bill/.../committees, .../cosponsors -> access     (Phase 2)
  QuiverQuant   /bulk/congresstrading excess_return  -> payoff     (Phase 3)
  curated map (defense/energy/health/tech)           -> materiality (Phase 4 now)
  derived from the case set                          -> pattern    (Phase 5)

Phase 4 note: a gpt-4o-grounded materiality path is SCAFFOLDED below
(infer_beneficiaries_via_gpt) but NOT run at scale. It is clearly labeled
model-inferred when used. See README / docs for the cost estimate.

Writes webapp/js/money_trail_data.js (window.MONEY_TRAIL). Keys read from .env,
never logged or written to output.
Run: ./tf_env/bin/python webapp/build_money_trail.py [--limit N]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "js" / "money_trail_data.js"
CONGRESS_BASE = "https://api.congress.gov/v3"
QUIVER_BULK = "https://api.quiverquant.com/beta/bulk/congresstrading"
MAX_BYTES = 96 * 1024 * 1024
UA = {"User-Agent": "ThinkFree/1.0", "Accept": "application/json"}


def _key(name: str) -> str:
    env = ROOT / ".env"
    if env.exists():
        for line in open(env, encoding="utf-8"):
            if line.startswith(name + "="):
                return line.strip().split("=", 1)[1]
    return os.environ.get(name, "")


CONGRESS_KEY = _key("CONGRESS_API_KEY")
QUIVER_KEY = _key("QUIVERQUANT_API_KEY")


# ---- Phase 4 (materiality): curated beneficiary map for high-impact sectors ----
# Maps a law's economic area to the SPECIFIC companies whose revenue depends on
# it. This is a hand-curated map (accurate, evidenced). The gpt-4o path below is
# a scaffold for extending coverage to every law, labeled model-inferred.
MATERIALITY = {
    "defense":  {"kw": ["defense", "armed forces", "military", "navy", "army", "air force", "missile", "shipbuild", "munition", "national security"],
                 "tickers": ["LMT", "RTX", "NOC", "GD", "BA", "HII", "LHX", "LDOS"]},
    "energy":   {"kw": ["energy", "oil", "natural gas", "pipeline", "nuclear", "drilling", "ferc", "solar", "offshore", "petroleum", "lng"],
                 "tickers": ["XOM", "CVX", "COP", "NEE", "SLB", "OXY", "FSLR", "ENPH", "KMI", "WMB"]},
    "health":   {"kw": ["medical", "drug", "medicare", "medicaid", "health", "veterans health", "pharmaceutical", "hospital", "fda", "vaccine"],
                 "tickers": ["UNH", "JNJ", "PFE", "LLY", "MRK", "CVS", "HCA", "ABBV", "AMGN", "BMY"]},
    "tech":     {"kw": ["semiconductor", "chip", "broadband", "quantum", "artificial intelligence", "cyber", "spectrum", "data center", "cloud"],
                 "tickers": ["NVDA", "AMD", "INTC", "MSFT", "GOOGL", "AVGO", "QCOM", "PLTR", "MU", "ORCL"]},
}


def http_json(url: str, headers: dict | None = None, timeout: int = 30):
    req = urllib.request.Request(url, headers=headers or UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("response too large")
        return json.loads(body.decode())


def norm_name(s: str) -> str:
    s = re.sub(r"^(mr|mrs|ms|dr|rep|sen|senator|representative)\.?\s+", "", str(s or "").strip(), flags=re.I)
    s = re.sub(r"\b(jr|sr|ii|iii|iv|dr)\b\.?", "", s, flags=re.I)
    return re.sub(r"[^a-z ]", "", s.lower()).strip()


def name_tokens(s: str) -> set:
    return set(t for t in norm_name(s).split() if len(t) > 1)


def names_match(a: str, b: str) -> bool:
    """Loose match: same last name + first-initial/first-name overlap."""
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return False
    # last token (surname) must match, plus one more shared token
    return list(ta)[-1] == list(tb)[-1] and len(ta & tb) >= 2 or (ta <= tb or tb <= ta)


# ---- Congress.gov bill enrichment (Phase 1 + 2) ----------------------------
_MILESTONE_RULES = [
    ("introduced", re.compile(r"introduced", re.I)),
    ("to_committee", re.compile(r"referred to (the )?committee|committee on", re.I)),
    ("markup", re.compile(r"markup|ordered to be reported|reported by|committee.*reported", re.I)),
    ("passed_house", re.compile(r"passed.*house|on passage.*passed.*house|house agreed", re.I)),
    ("passed_senate", re.compile(r"passed.*senate|senate agreed|cloture", re.I)),
    ("enacted", re.compile(r"became public law|signed by president|presented to president", re.I)),
]


def bill_path(bill_id: str) -> tuple[str, str, str] | None:
    m = re.match(r"^([A-Za-z]+)(\d+)-(\d+)$", bill_id)
    if not m:
        return None
    t = m.group(1).lower()
    typ = {"hr": "hr", "s": "s", "hres": "hres", "sres": "sres", "hjres": "hjres", "sjres": "sjres",
           "hconres": "hconres", "sconres": "sconres"}.get(t, t)
    return (m.group(3), typ, m.group(2))   # congress, type, number


def fetch_bill_evidence(bill_id: str) -> dict:
    """Pull the action timeline, committee, sponsor and cosponsors for one bill."""
    p = bill_path(bill_id)
    if not p or not CONGRESS_KEY:
        return {}
    congress, typ, num = p
    base = f"{CONGRESS_BASE}/bill/{congress}/{typ}/{num}"
    out = {"milestones": {}, "committees": [], "committee_codes": [], "sponsors": [], "access_names": []}
    # actions -> milestones (earliest date per milestone type)
    try:
        d = http_json(f"{base}/actions?format=json&limit=250&api_key={CONGRESS_KEY}")
        for a in d.get("actions", []):
            txt, date = a.get("text", "") or "", a.get("actionDate", "") or ""
            for name, rx in _MILESTONE_RULES:
                if rx.search(txt):
                    cur = out["milestones"].get(name)
                    if not cur or date < cur:
                        out["milestones"][name] = date
    except Exception as e:
        print(f"   [actions] {bill_id}: {type(e).__name__}")
    # committees of jurisdiction
    try:
        d = http_json(f"{base}/committees?format=json&limit=20&api_key={CONGRESS_KEY}")
        for c in d.get("committees", []):
            if c.get("name"):
                out["committees"].append(c["name"])
            if c.get("systemCode"):
                out["committee_codes"].append(c["systemCode"])
    except Exception:
        pass
    # sponsor (from bill detail) + cosponsors -> the access roster (names)
    try:
        d = http_json(f"{base}?format=json&api_key={CONGRESS_KEY}")
        for sp in (d.get("bill", {}) or {}).get("sponsors", []) or []:
            if sp.get("fullName"):
                out["sponsors"].append(sp["fullName"])
                out["access_names"].append((sp["fullName"], "sponsor"))
    except Exception:
        pass
    try:
        d = http_json(f"{base}/cosponsors?format=json&limit=250&api_key={CONGRESS_KEY}")
        for cs in d.get("cosponsors", []):
            if cs.get("fullName"):
                out["access_names"].append((cs["fullName"], "cosponsor"))
    except Exception:
        pass
    return out


# ---- Phase 2 data: committee rosters (who sits where) ----------------------
COMMITTEE_MEMBERSHIP_URL = "https://unitedstates.github.io/congress-legislators/committee-membership-current.json"


def load_committee_rosters() -> dict:
    """thomas_id (e.g. 'SSAS') -> set of normalized member names. Free, public,
    from the unitedstates/congress-legislators project. This is what gives the
    Access link its main channel: sitting on the committee of jurisdiction."""
    try:
        d = http_json(COMMITTEE_MEMBERSHIP_URL, timeout=40)
    except Exception as e:
        print(f"   [committee rosters] {type(e).__name__}: committee access disabled")
        return {}
    out = {}
    for thomas_id, members in d.items():
        out[thomas_id.upper()] = set(norm_name(m.get("name", "")) for m in members if m.get("name"))
    return out


def committee_member_names(committee_codes: list, rosters: dict) -> set:
    """Resolve a bill's committee systemCodes (e.g. 'ssas00') to the set of
    normalized member names, including the parent committee roster."""
    names = set()
    for code in committee_codes or []:
        parent = re.sub(r"\d+$", "", str(code)).upper()   # 'ssas00' -> 'SSAS'
        for key in (parent, str(code).upper()):
            if key in rosters:
                names |= rosters[key]
    return names


# ---- Phase 3 data: QuiverQuant bulk for excess_return + member baselines -----
def load_excess_index() -> tuple[dict, dict]:
    """Return (by_key, baseline) where by_key[(name,ticker)] -> list of
    {date, excess} and baseline[name] -> mean excess across all the member's
    trades. excess_return is QuiverQuant's market-adjusted return (event-study
    style: trade return minus the market over the holding period)."""
    if not QUIVER_KEY:
        return {}, {}
    try:
        req = urllib.request.Request(QUIVER_BULK, headers={"Authorization": f"Bearer {QUIVER_KEY}", **UA})
        with urllib.request.urlopen(req, timeout=90) as r:
            body = r.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError("bulk response too large")
            rows = json.loads(body.decode())
    except Exception as e:
        print(f"   [quiver bulk] {type(e).__name__}: skipping payoff baselines")
        return {}, {}
    import statistics
    # excess_return is a PERCENT (market-adjusted) with heavy outliers (penny
    # stocks etc.). Winsorize to +/-100 points and use the MEDIAN baseline so a
    # few extreme trades cannot dominate.
    def clip(x):
        return max(-100.0, min(100.0, x))
    by_key: dict = {}
    per_member: dict = {}
    for row in rows:
        nm = norm_name(row.get("Name", ""))
        tk = str(row.get("Ticker", "") or "").upper()
        if not nm or not tk:
            continue
        try:
            ex = float(row.get("excess_return")) if row.get("excess_return") not in (None, "") else None
        except Exception:
            ex = None
        if ex is None:
            continue
        ex = clip(ex)
        by_key.setdefault((nm, tk), []).append({"date": str(row.get("Traded", ""))[:10], "excess": ex})
        per_member.setdefault(nm, []).append(ex)
    baseline = {nm: statistics.median(v) for nm, v in per_member.items() if v}
    return by_key, baseline


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def days_between(later: str, earlier: str):
    try:
        return (datetime.strptime(later[:10], "%Y-%m-%d") - datetime.strptime(earlier[:10], "%Y-%m-%d")).days
    except Exception:
        return None


class MoneyTrailDetectiveEngine:
    """Builds a chain-of-evidence Case File and CASE STRENGTH per law."""

    EVIDENCE_WEIGHTS = {"law": 0.20, "trade": 0.35, "payoff": 0.25, "pattern": 0.20}

    def __init__(self, excess_index: dict, baselines: dict, committee_rosters: dict | None = None):
        self.excess = excess_index
        self.baselines = baselines
        self.committee_rosters = committee_rosters or {}
        self.member_case_count: dict = {}   # filled during a two-pass pattern step

    # ---- Link 1: The Law (economic action) ----
    def link_law(self, corr: dict) -> tuple[float, str]:
        text = f"{corr.get('title','')} {corr.get('action_text','')}".lower()
        if any(k in text for k in ("appropriat", "fund", "authoriz", "billion", "million")):
            return 0.9, "The bill directs federal money (appropriations or authorization), a concrete economic action."
        if any(k in text for k in ("award", "contract", "procure")):
            return 0.85, "The bill steers federal contracts or procurement to specific industries."
        if any(k in text for k in ("rule", "regulat", "tariff", "waiv", "require")):
            return 0.7, "The bill changes a rule, requirement, or tariff that moves company economics."
        return 0.45, "The bill's economic action is indirect; money flow is not explicit in the text available."

    # ---- Link 2: The Beneficiary (materiality) ----
    def link_beneficiary(self, corr: dict) -> tuple[float, str, list, str]:
        text = f"{corr.get('title','')} {corr.get('action_text','')}".lower()
        matched_tickers = set(corr.get("matched_tickers", []) or [])
        for cat, spec in MATERIALITY.items():
            if any(k in text for k in spec["kw"]):
                beneficiaries = [t for t in spec["tickers"]]
                traded_benef = [t for t in beneficiaries if t in matched_tickers]
                if traded_benef:
                    return 0.92, f"The law materially affects {cat} companies; traded names {', '.join(traded_benef)} sit in that group.", beneficiaries, "curated"
                return 0.55, f"The law materially affects {cat} companies, though the traded names are not core {cat} beneficiaries.", beneficiaries, "curated"
        if matched_tickers:
            return 0.3, "Beneficiaries are inferred from keyword sector tags, not a verified revenue dependency.", sorted(matched_tickers)[:8], "keyword"
        return 0.05, "No specific corporate beneficiary could be identified for this law.", [], "none"

    # ---- Link 3: The Access ----
    def link_access(self, corr: dict, evidence: dict) -> tuple[float, str, dict]:
        access_roster = (evidence or {}).get("access_names", [])
        committee_names = committee_member_names((evidence or {}).get("committee_codes", []), self.committee_rosters)
        per_trader: dict = {}
        best = 0.1
        ACCESS_W = {"sponsor": 1.0, "cosponsor": 0.8, "committee": 0.7}
        for ct in corr.get("correlated_trades", []):
            pol = ct.get("politician", "")
            level = "none"
            # sponsor/cosponsor of record (strongest)
            for full, role in access_roster:
                if names_match(pol, full):
                    level = role
                    break
            # else: sits on the committee of jurisdiction
            if level == "none" and norm_name(pol) in committee_names:
                level = "committee"
            per_trader[pol] = level
            if level in ACCESS_W:
                best = max(best, ACCESS_W[level])
        counts = {k: sum(1 for v in per_trader.values() if v == k) for k in ACCESS_W}
        n_access = sum(counts.values())
        if n_access:
            bits = []
            if counts["sponsor"]: bits.append(f"{counts['sponsor']} sponsored it")
            if counts["cosponsor"]: bits.append(f"{counts['cosponsor']} cosponsored it")
            if counts["committee"]: bits.append(f"{counts['committee']} sit on the committee of jurisdiction")
            why = "Traders with real access: " + ", ".join(bits) + "."
        else:
            why = "No trader sponsored, cosponsored, or sits on the committee of jurisdiction. Access is low, which caps the case."
        return best, why, per_trader

    # ---- Link 4: The Trade (re-anchored timing) ----
    def link_trade(self, corr: dict, evidence: dict, access: dict, beneficiaries: list) -> tuple[float, str, list, str]:
        ms = (evidence or {}).get("milestones", {})
        # earliest NON-PUBLIC-ish milestone we can see: committee/markup, else introduced
        anchor = ms.get("markup") or ms.get("to_committee") or ms.get("introduced") or corr.get("action_date", "")
        anchor_label = ("markup" if ms.get("markup") else "committee referral" if ms.get("to_committee")
                        else "introduction" if ms.get("introduced") else "final action")
        benef = set(beneficiaries or [])
        plotted = []
        before_access = 0
        access_trades = 0
        for ct in corr.get("correlated_trades", []):
            pol = ct.get("politician", "")
            tk = (ct.get("ticker", "") or "").upper()
            tdate = ct.get("trade_date", "")
            d = days_between(anchor, tdate)   # >0 => trade before the anchor
            is_benef = (not benef) or (tk in benef)
            has_access = access.get(pol) in ("sponsor", "cosponsor")
            plotted.append({
                "politician": pol, "ticker": tk, "date": tdate,
                "action": "BUY" if "purchase" in str(ct.get("transaction", "")).lower() else "SELL",
                "amount": ct.get("amount", ""), "lead_days": d if d is not None else 0,
                "before_anchor": bool(d is not None and d > 0),
                "beneficiary": is_benef, "access": has_access,
            })
            if has_access and is_benef:
                access_trades += 1
                if d is not None and d > 0:
                    before_access += 1
        if access_trades:
            strength = clamp01(0.3 + 0.7 * (before_access / access_trades))
            why = f"{before_access} of {access_trades} access-holder trades in beneficiary names were placed before the {anchor_label}."
        else:
            # fall back to any pre-anchor trading in beneficiaries (weaker)
            pre = sum(1 for p in plotted if p["before_anchor"] and p["beneficiary"])
            tot = sum(1 for p in plotted if p["beneficiary"]) or 1
            strength = clamp01(0.4 * (pre / tot))
            why = f"No access-holder trades to anchor; {pre} of {tot} beneficiary trades preceded the {anchor_label} (no confirmed access)."
        return strength, why, plotted, anchor_label

    # ---- Link 5: The Payoff (abnormal return) ----
    def link_payoff(self, corr: dict, plotted: list) -> tuple[float, str, float]:
        import statistics
        abn = []
        for p in plotted:
            if not p.get("before_anchor"):
                continue
            nm = norm_name(p["politician"])
            recs = self.excess.get((nm, p["ticker"]), [])
            if not recs:
                continue
            # market-adjusted (excess) return nearest this trade date, in PERCENT
            ex = min(recs, key=lambda r: abs((days_between(p["date"], r["date"]) or 999)))["excess"]
            base = self.baselines.get(nm, 0.0)
            abn.append(ex - base)   # abnormal portion = excess over the member's own baseline
        if not abn:
            return 0.2, "No market-adjusted return data was available to test the payoff against a baseline.", 0.0
        med = statistics.median(abn)   # robust to outliers
        # 25 points of market-adjusted return above the member's baseline ~ very strong
        strength = clamp01(med / 25.0)
        med_pct = round(med, 1)
        why = (f"Pre-milestone trades beat the member's own baseline by a median {med_pct} points of market-adjusted (excess) return."
               if med > 0 else "Pre-milestone trades did not beat the member's baseline; the payoff link is weak.")
        return strength, why, med_pct

    # ---- Link 6: The Pattern ----
    def link_pattern(self, corr: dict, plotted: list) -> tuple[float, str]:
        # clustering: multiple distinct members trading the same beneficiary pre-anchor
        from collections import Counter
        pre = [p for p in plotted if p["before_anchor"] and p["beneficiary"]]
        by_ticker = Counter(p["ticker"] for p in pre)
        members_pre = set(p["politician"] for p in pre)
        cluster = max(by_ticker.values()) if by_ticker else 0
        # repetition: how many other cases the busiest pre-trader appears in
        rep = max((self.member_case_count.get(norm_name(m), 0) for m in members_pre), default=0)
        strength = clamp01(0.25 * min(cluster, 4) + 0.12 * min(rep, 5))
        bits = []
        if cluster >= 2:
            bits.append(f"{cluster} members traded the same beneficiary before the milestone (clustering)")
        if rep >= 2:
            bits.append(f"a trader here repeats across {rep} other cases")
        why = ("Pattern signal: " + "; ".join(bits) + ".") if bits else "No repeat or clustering pattern stands out."
        return strength, why

    def score_case(self, corr: dict, evidence: dict) -> dict:
        l1, why1 = self.link_law(corr)
        l2, why2, beneficiaries, mat_basis = self.link_beneficiary(corr)
        l3, why3, access = self.link_access(corr, evidence)
        l4, why4, plotted, anchor_label = self.link_trade(corr, evidence, access, beneficiaries)
        l5, why5, abn_pct = self.link_payoff(corr, plotted)
        l6, why6 = self.link_pattern(corr, plotted)

        gate = (0.15 + 0.85 * l2) * (0.15 + 0.85 * l3)
        w = self.EVIDENCE_WEIGHTS
        evidence_score = w["law"] * l1 + w["trade"] * l4 + w["payoff"] * l5 + w["pattern"] * l6
        case_strength = round(100 * gate * evidence_score)

        # weakest link, for the honest note
        links = [("The Law", l1), ("The Beneficiary", l2), ("The Access", l3),
                 ("The Trade", l4), ("The Payoff", l5), ("The Pattern", l6)]
        weakest = min(links, key=lambda x: x[1])

        return {
            "bill_id": corr.get("bill_id", ""),
            "title": corr.get("title", ""),
            "action_date": corr.get("action_date", ""),
            "is_enacted": corr.get("is_enacted", False),
            "sectors": corr.get("matched_sectors", []),
            "case_strength": case_strength,
            "anchor_milestone": anchor_label,
            "milestones": (evidence or {}).get("milestones", {}),
            "committees": (evidence or {}).get("committees", []),
            "beneficiaries": beneficiaries,
            "materiality_basis": mat_basis,
            "abnormal_return_pct": abn_pct,
            "links": [
                {"key": "law", "name": "The Law", "label": "What it does", "strength": round(l1, 2), "why": why1},
                {"key": "beneficiary", "name": "Who It Pays", "label": "Beneficiary", "strength": round(l2, 2), "why": why2, "critical": True},
                {"key": "access", "name": "Who Knew", "label": "Access", "strength": round(l3, 2), "why": why3, "critical": True},
                {"key": "trade", "name": "Who Traded", "label": "Timing", "strength": round(l4, 2), "why": why4},
                {"key": "payoff", "name": "The Payoff", "label": "Abnormal return", "strength": round(l5, 2), "why": why5},
                {"key": "pattern", "name": "The Pattern", "label": "Repetition", "strength": round(l6, 2), "why": why6},
            ],
            "trades": sorted(plotted, key=lambda p: p.get("date", "")),
            "weak_link": {"name": weakest[0], "strength": round(weakest[1], 2)},
        }


def verdict_sentence(case: dict) -> str:
    s = case["case_strength"]
    benef = case["beneficiaries"][:3]
    tag = "a strong" if s >= 70 else "a notable" if s >= 45 else "an emerging" if s >= 25 else "a thin"
    body = (f"This is {tag} money-trail case: {case['title'][:80]}. "
            f"The law affects {', '.join(benef) if benef else 'no clearly identified companies'}, "
            f"and trades were measured against the {case['anchor_milestone']} milestone rather than final passage.")
    wl = case["weak_link"]
    if wl["strength"] < 0.3:
        body += f" The chain is weakest at {wl['name']}, so read this as evidence, not a conclusion."
    return body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=80, help="max bills to analyze")
    args = ap.parse_args()

    cb = json.loads((ROOT / "congress_bills.json").read_text(encoding="utf-8"))
    correlations = [c for c in cb.get("correlations", []) if c.get("correlated_trades")]
    correlations = correlations[: args.limit]
    print(f"[money_trail] analyzing {len(correlations)} laws with correlated trades")

    print("[money_trail] loading committee rosters (Phase 2)...")
    rosters = load_committee_rosters()
    print(f"   {len(rosters)} committee rosters")

    print("[money_trail] loading QuiverQuant excess-return baselines (Phase 3)...")
    excess_index, baselines = load_excess_index()
    print(f"   baselines for {len(baselines)} members")

    engine = MoneyTrailDetectiveEngine(excess_index, baselines, rosters)

    # First pass: fetch evidence + provisional cases (also count member repetition).
    raw = []
    for i, corr in enumerate(correlations):
        bid = corr.get("bill_id", "")
        ev = fetch_bill_evidence(bid)
        raw.append((corr, ev))
        for ct in corr.get("correlated_trades", []):
            nm = norm_name(ct.get("politician", ""))
            engine.member_case_count[nm] = engine.member_case_count.get(nm, 0) + 0  # init
        time.sleep(0.05)
        if (i + 1) % 20 == 0:
            print(f"   fetched evidence for {i + 1}/{len(correlations)} bills")

    # member repetition: count distinct cases each member trades in
    seen_member_case = {}
    for corr, _ in raw:
        for ct in corr.get("correlated_trades", []):
            nm = norm_name(ct.get("politician", ""))
            seen_member_case.setdefault(nm, set()).add(corr.get("bill_id"))
    engine.member_case_count = {nm: len(s) for nm, s in seen_member_case.items()}

    # Second pass: score.
    cases = []
    for corr, ev in raw:
        case = engine.score_case(corr, ev)
        case["verdict"] = verdict_sentence(case)
        cases.append(case)
    cases.sort(key=lambda c: c["case_strength"], reverse=True)

    doc = {
        "engine": "The Money Trail Detective Engine",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "model": "chain-of-evidence, 6-link, multiplicative gate on beneficiary x access",
        "weights": {"gate": "(0.15+0.85*beneficiary)*(0.15+0.85*access)",
                    "evidence": MoneyTrailDetectiveEngine.EVIDENCE_WEIGHTS},
        "disclaimer": ("This engine measures timing relationships between public disclosures, "
                       "legislative milestones, and market-adjusted returns. It does not imply or "
                       "allege wrongdoing of any kind. Links marked model-inferred are not verified."),
        "cases": cases,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".js.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("// AUTO-GENERATED by webapp/build_money_trail.py - The Money Trail Detective Engine.\n")
        f.write("window.MONEY_TRAIL = ")
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";")
    tmp.replace(OUT)
    top = cases[:5]
    print(f"[money_trail] wrote {len(cases)} cases. Top 5:")
    for c in top:
        print(f"   {c['case_strength']:3d}  {c['bill_id']:12} {c['title'][:54]}")
    return 0


# ---- Phase 4 scaffold: gpt-4o-grounded beneficiary inference (NOT run at scale) ----
def infer_beneficiaries_via_gpt(bill_title: str, bill_text: str) -> dict:
    """SCAFFOLD ONLY. Reads bill text and proposes the specific companies whose
    revenue depends on it, labeled model-inferred. Disabled by default to avoid
    OpenAI spend; enable per the cost estimate in the docs. Returns
    {"beneficiaries": [...], "basis": "model-inferred", "rationale": "..."}.
    """
    raise NotImplementedError(
        "gpt-4o materiality path is scaffolded but not enabled. See docs for the "
        "cost estimate before running it across all laws."
    )


if __name__ == "__main__":
    raise SystemExit(main())
