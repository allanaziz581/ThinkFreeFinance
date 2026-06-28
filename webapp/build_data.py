"""ThinkFree Web Front-End — Data Compiler.

Reads the real ThinkFree project JSON outputs and emits webapp/js/data.js as
`window.TF_DATA = {...}`. This lets the static front-end render real content
without a server (works by opening index.html directly).

Run:  python webapp/build_data.py
"""
from __future__ import annotations

import json
import re
import urllib.parse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "js" / "data.js"


def load(name: str, default=None):
    p = ROOT / name
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001
        print(f"  [skip] {name}: {e}")
        return default if default is not None else {}


def money(n: float) -> str:
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "$0"
    a = abs(n)
    sign = "-" if n < 0 else ""
    if a >= 1e9:
        return f"{sign}${a/1e9:.2f}B"
    if a >= 1e6:
        return f"{sign}${a/1e6:.2f}M"
    if a >= 1e3:
        return f"{sign}${a/1e3:.1f}K"
    return f"{sign}${a:,.0f}"


# ---------------------------------------------------------------------------
# Source credibility: rate and rank news outlets so unreliable / PR-only
# sources are flagged or filtered out. Score 0-1.
# ---------------------------------------------------------------------------
CREDIBILITY = {
    # Trusted wire services & papers of record
    "reuters": 0.97, "associated press": 0.97, "ap news": 0.97, "bloomberg": 0.96,
    "wall street journal": 0.94, "wsj": 0.94, "dowjones": 0.93, "dow jones": 0.93,
    "financial times": 0.93, "ft": 0.93, "the economist": 0.92,
    # Reliable mainstream financial press
    "cnbc": 0.88, "barron": 0.87, "barrons": 0.87, "forbes": 0.80,
    "marketwatch": 0.82, "finnhub": 0.80, "morningstar": 0.85, "investopedia": 0.80,
    "associated": 0.95,
    # Mixed: large aggregators / mainstream but lighter editing
    "yahoo": 0.72, "business insider": 0.66, "businessinsider": 0.66, "cnn": 0.72,
    # Low: crowd-sourced opinion / commentary (legitimate but not vetted reporting)
    "seekingalpha": 0.55, "seeking alpha": 0.55, "motley fool": 0.52, "fool": 0.52,
    "zacks": 0.55, "thestreet": 0.58, "benzinga": 0.50, "investorplace": 0.50,
    # Filtered: PR wires / press releases (company-controlled, not reporting)
    "globenewswire": 0.40, "pr newswire": 0.40, "prnewswire": 0.40,
    "business wire": 0.42, "businesswire": 0.42, "accesswire": 0.38,
    "default": 0.50,
}
# below this, a source is treated as unreliable and dropped from the feed
MIN_CREDIBILITY = 0.45


def source_credibility(source: str):
    src = str(source or "").lower()
    for key, val in CREDIBILITY.items():
        if key != "default" and key in src:
            return val
    return CREDIBILITY["default"]


def credibility_tier(score: float) -> str:
    if score >= 0.9:
        return "Trusted"
    if score >= 0.75:
        return "Reliable"
    if score >= 0.6:
        return "Mixed"
    if score >= MIN_CREDIBILITY:
        return "Low / Opinion"
    return "Unreliable"


def _clean_str(s: str) -> str:
    """Remove em/en dashes from displayed text. Never use '—'."""
    s = s.replace(" — ", ", ").replace("— ", ", ").replace(" —", ",").replace("—", ", ")
    s = s.replace(" – ", " to ").replace("–", "-")
    # tidy artifacts
    while "  " in s:
        s = s.replace("  ", " ")
    s = s.replace(" ,", ",").replace(",,", ",").replace(", .", ".").strip()
    return s


def strip_dashes(obj):
    """Recursively clean all strings in the data structure."""
    if isinstance(obj, str):
        return _clean_str(obj)
    if isinstance(obj, list):
        return [strip_dashes(x) for x in obj]
    if isinstance(obj, dict):
        return {k: strip_dashes(v) for k, v in obj.items()}
    return obj


def ordinal(n) -> str:
    n = int(n)
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def bill_url(bill_id: str) -> str:
    """Turn 'S2393-119' / 'HR1234-119' into a congress.gov URL."""
    m = re.match(r"([A-Za-z]+)(\d+)-(\d+)", bill_id or "")
    if not m:
        return ""
    typ, num, cong = m.group(1).upper(), m.group(2), m.group(3)
    slug = {
        "HR": "house-bill", "S": "senate-bill",
        "HRES": "house-resolution", "SRES": "senate-resolution",
        "HJRES": "house-joint-resolution", "SJRES": "senate-joint-resolution",
        "HCONRES": "house-concurrent-resolution", "SCONRES": "senate-concurrent-resolution",
    }.get(typ, "house-bill")
    return f"https://www.congress.gov/bill/{ordinal(cong)}-congress/{slug}/{num}"


def quiver_url(name: str, bg: str) -> str:
    return f"https://www.quiverquant.com/congresstrading/politician/{urllib.parse.quote(name)}-{bg}"


# Representative campaign-finance data (clearly labeled as sample in the UI;
# swap for QuiverQuant/FEC API output when a key is available).
_INDUSTRIES = [
    "Securities & Investment", "Real Estate", "Health Professionals", "Pharmaceuticals",
    "Oil & Gas", "Commercial Banks", "Insurance", "Defense/Electronics",
    "Lawyers/Law Firms", "Tech / Internet", "Telecom", "Agribusiness",
]
_DONOR_PACS = [
    "Honeywell Intl PAC", "Lockheed Martin Employees PAC", "Comcast Corp PAC",
    "AT&T Inc PAC", "Northrop Grumman PAC", "Boeing Co PAC", "Microsoft Corp PAC",
    "Amazon.com PAC", "NextEra Energy PAC", "American Bankers Assn", "Natl Assn of Realtors",
    "Blue Cross / Blue Shield", "Pfizer Inc PAC", "Raytheon Co PAC",
]
_OUTSIDE_GROUPS = [
    "Senate Majority PAC", "Congressional Leadership Fund", "House Majority PAC",
    "Club for Growth Action", "End Citizens United", "League of Conservation Voters",
    "National Assn of Realtors PAC", "Americans for Prosperity",
]


def _seed(name: str) -> int:
    return sum(ord(c) for c in name) or 7


def make_donors(name: str):
    s = _seed(name)
    out = []
    for i in range(6):
        out.append({
            "org": _DONOR_PACS[(s + i * 3) % len(_DONOR_PACS)],
            "industry": _INDUSTRIES[(s + i * 5) % len(_INDUSTRIES)],
            "amount_fmt": money(2500 + ((s + i * 137) % 18) * 2500),
            "cycle": "2024",
        })
    return out


def make_supporters(name: str):
    s = _seed(name)
    out = []
    for i in range(4):
        out.append({
            "org": _OUTSIDE_GROUPS[(s + i * 2) % len(_OUTSIDE_GROUPS)],
            "stance": "Support" if (s + i) % 4 else "Oppose",
            "amount_fmt": money(15000 + ((s + i * 91) % 40) * 5000),
        })
    return out


# Sector -> representative industry groups / PACs that lobby on that area.
# (Labeled as sample in the UI; swap for OpenSecrets/Senate LDA data with a key.)
_SECTOR_LOBBY = {
    "Technology": ["Information Technology Industry Council", "Microsoft Corp PAC", "Alphabet Inc PAC", "Semiconductor Industry Assn"],
    "Communication Services": ["Comcast Corp PAC", "AT&T Inc PAC", "Internet & Television Assn"],
    "Health Care": ["PhRMA", "American Hospital Assn", "Blue Cross / Blue Shield", "Pfizer Inc PAC"],
    "Financials": ["American Bankers Assn", "Securities Industry & Fin. Markets Assn", "JPMorgan Chase PAC"],
    "Energy": ["American Petroleum Institute", "ExxonMobil PAC", "Chevron Corp PAC"],
    "Utilities": ["Edison Electric Institute", "NextEra Energy PAC", "Duke Energy PAC"],
    "Industrials": ["Boeing Co PAC", "Lockheed Martin PAC", "Natl Assn of Manufacturers"],
    "Defense": ["Lockheed Martin PAC", "Northrop Grumman PAC", "Raytheon Co PAC"],
    "Real Estate": ["Natl Assn of Realtors", "Real Estate Roundtable"],
    "Consumer Discretionary": ["Amazon.com PAC", "Natl Retail Federation"],
    "Consumer Staples": ["Grocery Manufacturers Assn", "Walmart Inc PAC"],
    "Materials": ["American Chemistry Council", "Natl Mining Assn"],
}


def lobby_for(sectors):
    out, seen = [], set()
    for sec in (sectors or []):
        for g in _SECTOR_LOBBY.get(sec, []):
            if g not in seen:
                seen.add(g)
                out.append({"org": g, "sector": sec})
    if not out:
        out = [{"org": "Multi-industry coalition", "sector": "General"}]
    return out[:6]


def plain_bill(title: str, sectors, tickers) -> str:
    """Best-effort plain-English explanation of what a bill does."""
    t = (title or "").lower()
    secs = ", ".join(sectors) if sectors else "several industries"
    themes = [
        ("chips", "boosts U.S. semiconductor manufacturing and funding"),
        ("semiconductor", "supports domestic chip production"),
        ("veterans affairs", "funds veterans' medical facilities and care"),
        ("energy", "changes federal energy rules, costs, or incentives"),
        ("federal energy regulatory", "directs how energy markets and utilities are regulated"),
        ("defense", "sets military spending and defense priorities"),
        ("appropriation", "decides how federal money gets spent"),
        ("tax", "changes who pays taxes and how much"),
        ("health", "affects healthcare costs, coverage, or drug rules"),
        ("artificial intelligence", "sets rules or funding for AI development"),
        ("medicare", "changes Medicare benefits or payments"),
        ("disapproval", "overturns a federal agency rule using Congress's review power"),
        ("infrastructure", "funds roads, grid, or construction projects"),
        ("trade", "changes tariffs or international trade terms"),
    ]
    hit = next((desc for key, desc in themes if key in t), None)
    if hit:
        return (f"In plain terms: this bill {hit}. It touches {secs}, which is why "
                f"trades in {', '.join((tickers or [])[:3]) or 'related stocks'} are connected to it.")
    return (f"In plain terms: this measure affects federal policy around {secs}. Companies in "
            f"that space ({', '.join((tickers or [])[:3]) or 'related stocks'}) could see their costs, "
            f"contracts, or regulation change if it advances.")


def build_everyday(raw: dict, oil_price: float, rec: dict) -> list:
    """Translate market/economic indicators into plain-English everyday impact —
    the core ThinkFree mission. Grounded in real indicators where available."""
    yc = raw.get("yield_curve", {}) or {}
    fred = raw.get("fred", {}) or {}
    ten_year = yc.get("ten_year")
    gdp = fred.get("gdp_growth")
    unemp = fred.get("unemployment_rate")
    rec_label = (rec.get("recession_risk", {}) or {}).get("label", "Low")

    # Approx 30yr mortgage ~ 10yr + ~2.7 spread
    mortgage = round(ten_year + 2.7, 2) if ten_year else None

    items = []

    # Rent & mortgages
    if mortgage:
        items.append({
            "category": "Rent & Mortgages",
            "dir": "up" if mortgage >= 6.5 else "neutral",
            "impact": f"30-year mortgage rates are around {mortgage}%",
            "detail": (f"With the 10-year Treasury at {ten_year}%, home loans stay expensive — "
                       "a higher monthly payment on any new mortgage, and landlords often pass "
                       "elevated financing costs through to rent."),
        })

    # Credit cards & auto loans
    items.append({
        "category": "Credit Cards & Auto Loans",
        "dir": "up" if (ten_year or 0) >= 4 else "neutral",
        "impact": "Borrowing stays pricey — APRs remain high",
        "detail": ("Credit-card and car-loan rates track the Fed's benchmark, which is still "
                   "elevated. Carrying a balance or financing a vehicle costs more than it did "
                   "a few years ago; paying down high-interest debt is the best 'return' available."),
    })

    # Gas prices (oil-driven)
    items.append({
        "category": "Gas Prices",
        "dir": "down" if oil_price < 80 else "up",
        "impact": f"Crude oil near ${oil_price:.0f}/barrel — pump prices {'easing' if oil_price < 80 else 'climbing'}",
        "detail": ("Gas at the pump follows crude oil with a 1–2 week lag. "
                   f"At ${oil_price:.0f}, fill-ups are {'a bit cheaper' if oil_price < 80 else 'getting more expensive'} — "
                   "which also feeds into the cost of anything shipped by truck."),
    })

    # Groceries
    items.append({
        "category": "Groceries",
        "dir": "neutral",
        "impact": "Food inflation is cooling, but prices remain elevated",
        "detail": ("Grocery price growth has slowed from its peak, yet the cost of a typical cart "
                   "is still well above pre-2021 levels. Fuel and labor costs keep a floor under "
                   "what you pay at checkout."),
    })

    # Utilities & electricity grid
    items.append({
        "category": "Utilities & Electricity",
        "dir": "up",
        "impact": "Electric bills are rising as grid demand surges",
        "detail": ("Power demand from AI data centers, electrification, and summer cooling is "
                   "straining the grid, and utilities are raising rates to fund upgrades. Expect "
                   "higher monthly electricity bills in many regions."),
    })

    # Jobs & hiring
    job_dir = "neutral"
    if unemp is not None:
        job_dir = "down" if unemp >= 5 else "neutral"
    items.append({
        "category": "Jobs & Hiring",
        "dir": job_dir,
        "impact": (f"Unemployment {unemp}% — job market is steady but cooling"
                   if unemp is not None else "Job market is steady but cooling"),
        "detail": (f"GDP growth at {gdp}% is below trend, so hiring is slowing without big layoffs. "
                   "It's a tougher market to switch jobs into than a year ago, but widespread job "
                   "losses aren't showing up yet." if gdp is not None else
                   "Hiring is slowing without major layoffs — a more cautious market than a year ago."),
    })

    # Consumer goods & tariffs
    items.append({
        "category": "Consumer Goods & Tariffs",
        "dir": "up",
        "impact": "New tariffs could push up prices on imported goods",
        "detail": ("Tariffs on imported electronics, appliances, cars, and household goods get "
                   "passed to shoppers as higher shelf prices. Big-ticket and imported items are "
                   "the most exposed if trade barriers rise."),
    })

    # Savings
    items.append({
        "category": "Savings & CDs",
        "dir": "up",
        "impact": "High-yield savings still pay well — for now",
        "detail": ("Because rates are elevated, savings accounts, CDs, and money-market funds are "
                   "still paying some of the best yields in years. A good moment to build an "
                   "emergency fund before rates eventually come down."),
    })

    return items


def build():
    print("Compiling ThinkFree data -> data.js")

    pol = load("politician_performance.json")
    parties = load("politician_parties.json")
    port = load("portfolio_snapshot.json")
    rec = load("recession_signals_output.json")
    opp = load("opportunity_scores.json")
    hist = load("historical_parallels.json")
    summaries = load("news_output/summaries.json", default=[])
    clustered = load("news_output/clustered_summaries.json", default={})
    enriched = load("news_output/enriched_news_sentiment.json", default=[])
    bills_raw = load("congress_bills.json")
    hist_events = load("historical_events_db.json")

    # Full-history congressional trade counts (from QuiverQuant /bulk via
    # build_trades.py). Keyed by a normalized politician name so the displayed
    # trade count + transparency/integrity scores reflect REAL volume, not the
    # ~1000-row recent slice that undercounted frequent traders.
    _tc = load("congress_trade_counts.json", default={})
    _tc_pols = (_tc.get("politicians", {}) if isinstance(_tc, dict) else {})

    def _norm_name(s: str) -> str:
        s = re.sub(r"^(mr|mrs|ms|dr|rep|sen|senator|representative)\.?\s+", "", str(s or "").strip(), flags=re.I)
        return re.sub(r"\s+", " ", s).lower()

    _counts_by_name = {}
    for _nm, _c in _tc_pols.items():
        k = _norm_name(_nm)
        # keep the record with the most trades when name variants collide
        if k not in _counts_by_name or _c.get("all_time", 0) > _counts_by_name[k].get("all_time", 0):
            _counts_by_name[k] = _c

    def trade_counts_for(name: str) -> dict:
        return _counts_by_name.get(_norm_name(name), {})

    def transparency_integrity(all_time: int, avg_lag):
        """Real scores: prompt disclosure raises transparency; very high trade
        volume lowers both (more activity to scrutinize). avg_lag in days."""
        lag = avg_lag if isinstance(avg_lag, (int, float)) else 30
        vol = all_time or 0
        transparency = 100 - lag * 1.0 - min(35, vol * 0.08)
        integrity = 100 - lag * 0.9 - min(45, vol * 0.10)
        clamp = lambda x: max(5, min(99, round(x)))
        return clamp(transparency), clamp(integrity)

    # ---- bioguide map (name -> bioguide id for photo lookup) ----
    bioguide = {}
    for name, meta in (parties or {}).items():
        if isinstance(meta, dict) and meta.get("bioguide"):
            bioguide[name] = meta["bioguide"]

    # ---- per-politician trade aggregation (real, from trade_detail) ----
    detail = pol.get("trade_detail", []) if isinstance(pol, dict) else []
    by_pol = defaultdict(list)
    pt_profit = {}  # (politician, ticker) -> {pct_return, est_pnl} (best/representative)
    for t in detail:
        nm_t, tk_t = t.get("politician", ""), t.get("ticker", "")
        by_pol[nm_t].append(t)
        key = (nm_t, tk_t)
        prev = pt_profit.get(key)
        pnl_t = t.get("est_pnl") or 0
        # keep the most profitable disclosed trade for that name+ticker
        if prev is None or pnl_t > prev["est_pnl"]:
            pt_profit[key] = {"pct_return": t.get("pct_return") or 0, "est_pnl": pnl_t}

    # ---- bills (congress.gov links + correlated politicians) ----
    all_corr = bills_raw.get("correlations", []) if isinstance(bills_raw, dict) else []
    bills = []
    pol_bills = defaultdict(list)  # politician name -> [bill dicts]
    # (politician, ticker) -> best correlated bill (the one a trade most precedes)
    corr_by_pt = {}
    for ci, corr in enumerate(all_corr):
        bid = corr.get("bill_id", "")
        url = bill_url(bid)
        cts = corr.get("correlated_trades", [])
        names = sorted({ct.get("politician", "") for ct in cts if ct.get("politician")})
        b = {
            "bill_id": bid,
            "title": corr.get("title", ""),
            "url": url,
            "action_date": corr.get("action_date", ""),
            "action_text": corr.get("action_text", ""),
            "tickers": corr.get("matched_tickers", [])[:8],
            "sectors": corr.get("matched_sectors", []),
            "plain_summary": plain_bill(corr.get("title", ""), corr.get("matched_sectors", []), corr.get("matched_tickers", [])),
            "lobbying": lobby_for(corr.get("matched_sectors", [])),
            "politicians": names[:8],
        }
        if ci < 80:
            bills.append(b)
        for nm in names:
            if len(pol_bills[nm]) < 4 and not any(x["bill_id"] == bid for x in pol_bills[nm]):
                pol_bills[nm].append(b)
        # trade-level: link each (politician, ticker) to a bill, keeping the
        # one the trade most precedes (most-negative days_delta = strongest signal)
        for ct in cts:
            key = (ct.get("politician", ""), ct.get("ticker", ""))
            dd = ct.get("days_delta") or 0
            entry = {
                "bill_id": bid, "title": corr.get("title", ""), "url": url,
                "sectors": corr.get("matched_sectors", []), "days_delta": dd,
                "action_date": corr.get("action_date", ""),
            }
            prev = corr_by_pt.get(key)
            if prev is None or dd < prev["days_delta"]:
                corr_by_pt[key] = entry

    def enrich(nm: str, p_meta: dict):
        trades = by_pol.get(nm, [])
        cnt = Counter(t.get("ticker", "") for t in trades if t.get("ticker"))
        top = [{"ticker": tk, "trades": n} for tk, n in cnt.most_common(8)]
        est_value = sum((t.get("midpoint_est") or 0) for t in trades if "urchase" in str(t.get("transaction", "")))
        buys, sells = p_meta.get("Buys", 0), p_meta.get("Sells", 0)
        direction = "net buyer" if buys >= sells else "net seller"
        tickers_str = ", ".join(t["ticker"] for t in top[:4]) or "various names"
        ret = p_meta.get("Est. Return (%)", 0)
        summary_txt = (
            f"{nm} ({p_meta.get('Party','')}, {p_meta.get('State','')}) disclosed "
            f"{p_meta.get('Trades (6mo)',0)} trades over the past 6 months "
            f"({buys} buys, {sells} sells) — a {direction}. Estimated activity totals "
            f"{money(p_meta.get('Est. Total Traded',0))} with an estimated P&L of "
            f"{money(p_meta.get('Est. P&L ($)',0))} ({ret}% return). Most-traded names: {tickers_str}. "
            f"All figures are estimates from public disclosure ranges and reflect timing relationships only."
        )
        # est net worth: not provided by public APIs — show a labeled estimate range
        nw_low = est_value * 2.5
        nw_high = est_value * 6.0

        # ---- trade timeline: every trade, its bill link, and the profit ----
        timeline = []
        for t in trades:
            tk = t.get("ticker", "")
            is_buy = "urchase" in str(t.get("transaction", ""))
            bill = corr_by_pt.get((nm, tk))
            ev = {
                "date": t.get("date", ""),
                "ticker": tk,
                "action": "BUY" if is_buy else "SELL",
                "range": t.get("range_disclosed", ""),
                "pct_return": t.get("pct_return", 0),
                "pnl_fmt": money(t.get("est_pnl", 0)),
                "pnl": t.get("est_pnl", 0),
            }
            if bill:
                dd = bill["days_delta"]
                ev["bill"] = {
                    "bill_id": bill["bill_id"],
                    "title": bill["title"],
                    "url": bill["url"],
                    "sectors": bill["sectors"],
                    "days_delta": dd,
                    "before": dd < 0,
                    "lead_days": abs(dd),
                }
            timeline.append(ev)
        timeline.sort(key=lambda e: e["date"], reverse=True)
        influenced = sum(1 for e in timeline if e.get("bill", {}).get("before"))

        return {
            "summary": summary_txt,
            "top_tickers": top,
            "est_portfolio_value_fmt": money(est_value),
            "networth_range_fmt": f"{money(nw_low)} – {money(nw_high)}",
            "donors": make_donors(nm),
            "supporters": make_supporters(nm),
            "related_bills": pol_bills.get(nm, []),
            "trade_timeline": timeline,
            "influenced_count": influenced,
        }

    # ---- politicians (top performers) ----
    summary = pol.get("politician_summary", []) if isinstance(pol, dict) else []
    politicians = []
    for p in summary:
        nm = p.get("Politician", "")
        rec_p = {
            "name": nm,
            "party": p.get("Party", ""),
            "party_abbr": "D" if str(p.get("Party", "")).startswith("Democr") else ("R" if str(p.get("Party", "")).startswith("Rep") else "I"),
            "state": p.get("State", ""),
            "chamber": p.get("Chamber", ""),
            "trades": p.get("Trades (6mo)", 0),
            "buys": p.get("Buys", 0),
            "sells": p.get("Sells", 0),
            "total_traded": p.get("Est. Total Traded", 0),
            "total_traded_fmt": money(p.get("Est. Total Traded", 0)),
            "pnl": p.get("Est. P&L ($)", 0),
            "pnl_fmt": money(p.get("Est. P&L ($)", 0)),
            "ret": p.get("Est. Return (%)", 0),
            "bioguide": bioguide.get(nm, ""),
        }
        # Real full-history counts + recomputed transparency/integrity scores.
        _c = trade_counts_for(nm)
        _all = _c.get("all_time", 0)
        _month = _c.get("past_month", 0)
        _lag = _c.get("avg_disclosure_lag_days")
        _transp, _integ = transparency_integrity(_all, _lag)
        rec_p["trades_all_time"] = _all
        rec_p["trades_past_month"] = _month
        rec_p["avg_disclosure_lag_days"] = _lag
        rec_p["transparency_score"] = _transp
        rec_p["integrity_score"] = _integ
        # Use the real all-time count as the headline "trades" when available
        # (fixes the undercount); fall back to the 6-month figure otherwise.
        if _all:
            rec_p["trades"] = _all
        rec_p.update(enrich(nm, p))
        politicians.append(rec_p)

    # ---- recent congressional trades ----
    recent_trades = []
    for t in detail[:250]:
        recent_trades.append({
            "politician": t.get("politician", ""),
            "party_abbr": t.get("party_abbr", ""),
            "ticker": t.get("ticker", ""),
            "transaction": t.get("transaction", ""),
            "date": t.get("date", ""),
            "range": t.get("range_disclosed", ""),
            "pct_return": t.get("pct_return", 0),
            "pnl_fmt": money(t.get("est_pnl", 0)),
            "pnl": t.get("est_pnl", 0),
            "bioguide": bioguide.get(t.get("politician", ""), ""),
        })

    # ---- portfolio ----
    metrics = port.get("metrics", {}) if isinstance(port, dict) else {}
    positions = []
    for tk, pos in (port.get("positions", {}) if isinstance(port, dict) else {}).items():
        positions.append({
            "ticker": pos.get("ticker", tk),
            "shares": pos.get("shares", 0),
            "entry": pos.get("entry_price", 0),
            "last": pos.get("last_price", 0),
            "cost_basis": pos.get("cost_basis", 0),
            "cost_basis_fmt": money(pos.get("cost_basis", 0)),
            "pnl": pos.get("unrealized_pnl", 0),
            "pnl_pct": pos.get("unrealized_pnl_pct", 0),
            "score": pos.get("opportunity_score", 0),
            "reasoning": pos.get("signal_reasoning", ""),
        })

    # ---- recession ----
    rr = rec.get("recession_risk", {}) if isinstance(rec, dict) else {}
    raw = rec.get("raw_indicators", {}) if isinstance(rec, dict) else {}

    # ---- opportunities ----
    sectors = []
    for s in (opp.get("sector_opportunities", []) if isinstance(opp, dict) else [])[:8]:
        sectors.append({
            "sector": s.get("sector", ""),
            "score": s.get("opportunity_score", 0),
            "direction": s.get("direction", ""),
            "rationale": s.get("rationale", ""),
        })
    # Ticker signals derived from REAL per-ticker quant signals (RSI/MACD/trend/
    # probabilities/Sharpe) so scores actually vary and we surface both bullish
    # AND bearish names. The old path read a uniform opportunity_score (all 7.0).
    def _load_window_js(fname: str) -> dict:
        p = ROOT / "webapp" / "js" / fname
        if not p.exists():
            return {}
        try:
            txt = p.read_text(encoding="utf-8")
            m = re.search(r"window\.\w+\s*=\s*", txt)
            body = txt[m.end():].rsplit(";", 1)[0]
            d = json.loads(body)
            return d.get("byTicker", d) if isinstance(d, dict) else {}
        except Exception:
            return {}

    def ticker_signal(q: dict):
        score = 5.0
        cross = q.get("macd_cross", "")
        if cross == "bullish": score += 1.2
        elif cross == "bearish": score -= 1.2
        trend = q.get("trend", "")
        if trend == "golden": score += 1.0
        elif trend == "death": score -= 1.0
        rsi = q.get("rsi", 50) or 50
        if rsi < 30: score += 1.0
        elif rsi > 70: score -= 1.0
        score += (float(q.get("prob_up", 0) or 0) - float(q.get("prob_down", 0) or 0)) * 0.04
        er = float(q.get("exp_return_1mo", 0) or 0)
        score += max(-1.5, min(1.5, er * 0.3))
        score += max(-1.0, min(1.0, float(q.get("sharpe", 0) or 0) * 0.5))
        score = round(max(0.5, min(9.9, score)), 1)
        direction = "Bullish" if score >= 6 else ("Bearish" if score <= 4.3 else "Neutral")
        bits = []
        if cross: bits.append(f"MACD {cross} cross")
        if trend in ("golden", "death"): bits.append(f"{trend} cross (50/200d)")
        bits.append(f"RSI {rsi:.0f} ({'oversold' if rsi < 30 else 'overbought' if rsi > 70 else 'neutral'})")
        if er: bits.append(f"model expects {er:+.1f}% over 1mo")
        sh = float(q.get("sharpe", 0) or 0)
        if sh: bits.append(f"Sharpe {sh:.2f}")
        why = "; ".join(bits) + "."
        return score, direction, why

    quant = _load_window_js("quant_data.js")
    sig_rows = []
    for tk, q in (quant.items() if isinstance(quant, dict) else []):
        if not isinstance(q, dict):
            continue
        sc, direction, why = ticker_signal(q)
        sig_rows.append({"ticker": tk, "score": sc, "direction": direction, "why": why,
                         "price": q.get("price"), "rsi": q.get("rsi")})
    # Most decisive signals first (furthest from neutral), keeping both extremes.
    sig_rows.sort(key=lambda r: abs(r["score"] - 5), reverse=True)
    tickers_opp = sig_rows[:28]
    # Fallback to the legacy source if quant_data wasn't available.
    if not tickers_opp:
        for s in (opp.get("ticker_opportunities", []) if isinstance(opp, dict) else [])[:8]:
            tickers_opp.append({"ticker": s.get("ticker", s.get("symbol", "")),
                                "score": s.get("opportunity_score", 0),
                                "direction": s.get("direction", ""), "why": ""})

    # ---- historical parallels ----
    parallels = []
    for hp in (hist.get("historical_parallels", []) if isinstance(hist, dict) else []):
        periods = []
        for per in hp.get("historical_periods", [])[:3]:
            periods.append({
                "label": per.get("label", ""),
                "context": per.get("context", ""),
            })
        parallels.append({
            "label": hp.get("label", ""),
            "context": hp.get("plain_english_context", ""),
            "periods": periods,
        })

    # ---- bill-trade correlation index (real, from days_delta timing) ----
    correlations = bills_raw.get("correlations", []) if isinstance(bills_raw, dict) else []
    all_ct = []
    bills_with_trades = 0
    bill_stats = []
    for corr in correlations:
        cts = corr.get("correlated_trades", [])
        if not cts:
            continue
        bills_with_trades += 1
        deltas = [(ct.get("days_delta") or 0) for ct in cts]
        before = [d for d in deltas if d < 0]  # trade BEFORE the bill action
        all_ct.extend(cts)
        bid = corr.get("bill_id", "")
        secs = corr.get("matched_sectors", [])
        tks = corr.get("matched_tickers", [])
        # who traded it + how they benefited (profit cross-referenced from trade detail)
        traders = []
        for ct in cts:
            nm_c, tk_c = ct.get("politician", ""), ct.get("ticker", "")
            dd = ct.get("days_delta") or 0
            prof = pt_profit.get((nm_c, tk_c), {})
            traders.append({
                "politician": nm_c,
                "party_abbr": ct.get("party_abbr", ""),
                "ticker": tk_c,
                "action": "BUY" if "urchase" in str(ct.get("transaction", "")) else "SELL",
                "amount": ct.get("amount", ""),
                "trade_date": ct.get("trade_date", ""),
                "days_delta": dd,
                "before": dd < 0,
                "lead_days": abs(dd),
                "pct_return": prof.get("pct_return", 0),
                "pnl_fmt": money(prof.get("est_pnl", 0)),
            })
        # surface the ones who positioned earliest (strongest signal) first
        traders.sort(key=lambda x: x["days_delta"])
        bill_stats.append({
            "bill_id": bid,
            "title": corr.get("title", ""),
            "url": bill_url(bid),
            "sectors": secs,
            "tickers": tks[:8],
            "plain_summary": plain_bill(corr.get("title", ""), secs, tks),
            "action_text": corr.get("action_text", ""),
            "action_date": corr.get("action_date", ""),
            "trade_count": len(cts),
            "before_count": len(before),
            "max_lead": int(abs(min(deltas))) if deltas else 0,
            "avg_delta": round(sum(deltas) / len(deltas), 1) if deltas else 0,
            "traders": traders[:12],
            "lobbying": lobby_for(secs),
        })

    total_ct = len(all_ct)
    deltas_all = [ct.get("days_delta", 0) for ct in all_ct]
    before_all = [d for d in deltas_all if d < 0]
    pct_before = round(100 * len(before_all) / total_ct) if total_ct else 0
    avg_lead = round(sum(abs(d) for d in before_all) / len(before_all)) if before_all else 0

    # How widespread is the "traded before the bill" pattern across bills?
    bills_with_before = sum(1 for b in bill_stats if b["before_count"] > 0)
    breadth_pct = round(100 * bills_with_before / bills_with_trades) if bills_with_trades else 0

    # Conflict index 0-100. Buying ahead of legislation that benefits the holding
    # is the core conflict signal, so it drives the score. A meaningful lead time
    # REWARDS the score (more advance positioning), it does not penalize it.
    #   - breadth   (45%): share of related bills that had trades opened beforehand
    #   - intensity (35%): share of correlated trades placed before the action
    #   - lead      (20%): advance positioning, rewarded up to ~90 days
    lead_factor = max(0.0, min(1.0, avg_lead / 90.0))
    index = round(min(100, 0.45 * breadth_pct + 0.35 * pct_before + 0.20 * lead_factor * 100))
    # rank bills by how many trades preceded the action
    bill_stats.sort(key=lambda b: (b["before_count"], b["trade_count"]), reverse=True)

    correlation = {
        "index": index,
        "headline": (
            f"{breadth_pct}% of {bills_with_trades} related bills had trades opened "
            f"beforehand — {len(before_all):,} trades positioned an avg {avg_lead} days "
            f"ahead of the bill's action."
        ),
        "correlated_trades": total_ct,
        "bills_with_trades": bills_with_trades,
        "bills_with_before": bills_with_before,
        "breadth_pct": breadth_pct,
        "pct_before": pct_before,
        "avg_lead_days": avg_lead,
        "top_bills": bill_stats,   # all trade-correlated bills (was capped at 8)
    }

    # ---- historical events library (20 events: tulip mania -> AI boom) ----
    events = []
    for e in (hist_events.get("events", []) if isinstance(hist_events, dict) else []):
        events.append({
            "id": e.get("id", ""),
            "name": e.get("name", ""),
            "date_range": e.get("date_range", ""),
            "category": str(e.get("category", "")).replace("_", " ").title(),
            "summary": e.get("summary", ""),
            "why_similar": e.get("why_similar", ""),
            "what_happened_after": e.get("what_happened_after", ""),
            "history_warning": e.get("history_warning", ""),
            "personal_impact": e.get("personal_impact", ""),
            "modern_parallel_themes": e.get("modern_parallel_themes", []),
        })

    # ---- news (with source credibility) ----
    # Join the real publisher + sentiment from enriched_news_sentiment.json by URL,
    # rate each source's credibility, DROP unreliable sources, and rank by a
    # credibility-weighted impact score.
    enr_by_link = {}
    for e in (enriched if isinstance(enriched, list) else []):
        link = e.get("link") or e.get("url")
        if link:
            enr_by_link[link] = e

    src = summaries if isinstance(summaries, list) else []
    by_symbol = defaultdict(list)
    dropped = 0
    for a in src:
        summ = a.get("summary", "")
        if not summ or len(summ) < 30:
            continue
        url = a.get("url", "")
        e = enr_by_link.get(url, {})
        source = e.get("source", "") or "Unknown"
        cred = source_credibility(source)
        if cred < MIN_CREDIBILITY:        # filter out unreliable / PR-only sources
            dropped += 1
            continue
        sent = e.get("sentiment", {}) or {}
        compound = abs(sent.get("compound", 0) or 0)
        richness = e.get("data_richness_score", 0) or 0
        impact = round(cred * (0.5 + compound) * (1 + min(richness, 1)), 3)
        by_symbol[a.get("symbol", "")].append({
            "symbol": a.get("symbol", ""),
            "headline": a.get("headline", "") or summ[:90],
            "summary": summ[:320],
            "sector": a.get("gics_sector", ""),
            "url": url,
            "source": source,
            "credibility": round(cred, 2),
            "credibility_tier": credibility_tier(cred),
            "sentiment": sent.get("label", "neutral"),
            "impact": impact,
        })
    # round-robin across companies for diversity, then rank by credibility-weighted impact
    news = []
    for rnd in range(8):
        for sym in sorted(by_symbol):
            if len(by_symbol[sym]) > rnd:
                news.append(by_symbol[sym][rnd])
    news.sort(key=lambda n: (n["credibility"], n["impact"]), reverse=True)
    news = news[:160]
    print(f"  news: kept {len(news)}, dropped {dropped} from unreliable sources")

    # ---- "what this means for you" from clustered summaries ----
    means = []
    if isinstance(clustered, dict):
        for cid, items in clustered.items():
            if not isinstance(items, list) or not items:
                continue
            it = items[0]
            means.append({
                "title": it.get("title", "")[:90],
                "summary": it.get("summary", "")[:260],
            })
            if len(means) >= 8:
                break

    # ---- market summary categories (derived/representative) ----
    market = [
        {"label": "S&P 500", "value": "5,431.60", "change": "+0.41%", "dir": "up"},
        {"label": "NASDAQ", "value": "17,688.88", "change": "+0.79%", "dir": "up"},
        {"label": "DOW", "value": "38,589.16", "change": "-0.15%", "dir": "down"},
        {"label": "10Y Yield", "value": f"{raw.get('yield_curve', {}).get('ten_year', 4.49)}%", "change": "+0.02", "dir": "up"},
        {"label": "VIX", "value": f"{raw.get('vix', {}).get('vix', 17.68)}", "change": "-0.30", "dir": "down"},
        {"label": "Crude Oil", "value": "$78.45", "change": "-0.62%", "dir": "down"},
    ]

    # ---- everyday impact ("What This Means For You") ----
    everyday = build_everyday(raw, 78.45, rec if isinstance(rec, dict) else {})

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "user": {"name": "Allan", "plan": "Free Plan"},
        "disclaimer": pol.get("disclaimer", "This analysis identifies timing relationships between publicly available government disclosures and market events. It does not imply or allege wrongdoing of any kind."),
        "market_ticker": market,
        "recession": {
            "score": rr.get("score", 0),
            "max": rr.get("max_score", 10),
            "label": rr.get("label", ""),
            "summary": rr.get("plain_english_summary", ""),
            "factors": rr.get("factors", []),
            "indicators": raw,
        },
        "portfolio": {
            "value": metrics.get("total_portfolio_value", 0),
            "value_fmt": money(metrics.get("total_portfolio_value", 0)),
            "cash": metrics.get("cash", 0),
            "exposure": metrics.get("exposure_pct", 0),
            "return_pct": metrics.get("total_return_pct", 0),
            "open_count": metrics.get("open_positions_count", 0),
            "win_rate": metrics.get("win_rate_pct", 0),
            "positions": positions,
        },
        "politicians": politicians,
        "recent_trades": recent_trades,
        "sectors": sectors,
        "tickers_opp": tickers_opp,
        "parallels": parallels,
        "events": events,
        "bills": bills,
        "correlation": correlation,
        "news": news,
        "means": means,
        "everyday": everyday,
    }

    data = strip_dashes(data)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// AUTO-GENERATED by webapp/build_data.py - do not edit by hand.\n")
        f.write("window.TF_DATA = ")
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write(";\n")

    print(f"  wrote {OUT}  ({OUT.stat().st_size//1024} KB)")
    print(f"  politicians={len(politicians)} trades={len(recent_trades)} bills={len(bills)} events={len(events)} news={len(news)}")


if __name__ == "__main__":
    build()
