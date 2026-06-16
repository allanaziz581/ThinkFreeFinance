"""ThinkFree - SEC EDGAR bulk extractor (companyfacts.zip + submissions.zip).

The official SEC bulk datasets are keyed by CIK. LittleSis gave us a sec_cik
for most companies. This reads ONLY the per-company JSON for our tickers out of
the (multi-GB) zips, extracting real XBRL financials + filing activity, and
writes webapp/js/secbulk_data.js (window.SECBULK_DATA).

No network, no rate limits. Reads the two zips from ~/Downloads.

Run:  ./tf_env/bin/python webapp/build_secbulk.py
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DL = Path.home() / "Downloads"
FACTS_ZIP = DL / "companyfacts.zip"
SUBS_ZIP = DL / "submissions.zip"
OUT = Path(__file__).resolve().parent / "js" / "secbulk_data.js"


def load_ciks():
    """ticker -> zero-padded CIK, from LittleSis influence_data (has sec_cik) and any extras."""
    out = {}
    # influence_data.js doesn't carry cik; pull from the raw LittleSis entities slice we already matched.
    # We saved entity_id but not cik there, so fall back to a ticker->cik map built from submissions.
    return out


def fmt(n):
    if n is None:
        return None
    a = abs(n)
    if a >= 1e12:
        return f"${a/1e12:.2f}T"
    if a >= 1e9:
        return f"${a/1e9:.1f}B"
    if a >= 1e6:
        return f"${a/1e6:.1f}M"
    if a >= 1e3:
        return f"${a/1e3:.0f}K"
    return f"${a:,.0f}"


def latest_fact(us, concepts):
    """Return latest annual value among the given XBRL concepts."""
    for c in concepts:
        if c not in us:
            continue
        units = us[c].get("units", {})
        key = "USD" if "USD" in units else (list(units)[0] if units else None)
        if not key:
            continue
        vals = [v for v in units[key] if v.get("form") in ("10-K", "20-F")]
        if not vals:
            vals = units[key]
        if vals:
            vals.sort(key=lambda v: (v.get("fy") or 0, v.get("end") or ""))
            v = vals[-1]
            return v.get("val"), v.get("fy"), key
    return None, None, None


def our_tickers():
    s = open(ROOT / "webapp" / "js" / "influence_data.js", encoding="utf-8").read()
    d = json.loads(s[s.index("{"): s.rindex("}") + 1])
    return set((d.get("companies") or {}).keys())


def main():
    if not FACTS_ZIP.exists() or not SUBS_ZIP.exists():
        print(f"ERROR: need {FACTS_ZIP} and {SUBS_ZIP}")
        return
    want = our_tickers()
    print(f"Scanning submissions.zip to map {len(want)} tickers -> CIK...")

    # Pass 1: walk submissions.zip, find which CIK files belong to our tickers.
    tk_to_cik, cik_meta = {}, {}
    with zipfile.ZipFile(SUBS_ZIP) as z:
        names = [n for n in z.namelist() if n.startswith("CIK") and n.endswith(".json") and "-submissions-" not in n]
        for i, name in enumerate(names):
            if i % 2000 == 0:
                print(f"  submissions scanned: {i}/{len(names)}  matched: {len(tk_to_cik)}")
            try:
                d = json.loads(z.read(name))
            except Exception:
                continue
            tks = d.get("tickers") or []
            hit = [t for t in tks if t in want]
            if not hit:
                continue
            cik = str(d.get("cik") or name[3:].split(".")[0].lstrip("0"))
            recent = d.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            from collections import Counter
            fc = Counter(forms)
            cik_meta[cik] = {
                "name": d.get("name"),
                "sic": d.get("sicDescription"),
                "exchange": (d.get("exchanges") or [None])[0],
                "ein": d.get("ein"),
                "filings_total": len(forms),
                "last_filing": dates[0] if dates else None,
                "form_counts": dict(fc.most_common(8)),
                "tickers": tks,
            }
            for t in hit:
                tk_to_cik[t] = cik
            if len(tk_to_cik) >= len(want):
                break
    print(f"  matched {len(tk_to_cik)}/{len(want)} tickers to CIK")

    # Pass 2: pull financials from companyfacts.zip for matched CIKs.
    print("Reading companyfacts.zip for financials...")
    out = {}
    with zipfile.ZipFile(FACTS_ZIP) as z:
        have = set(z.namelist())
        for tk, cik in tk_to_cik.items():
            fname = f"CIK{int(cik):010d}.json"
            meta = cik_meta.get(cik, {})
            rec = {
                "cik": cik, "name": meta.get("name"), "sic": meta.get("sic"),
                "exchange": meta.get("exchange"), "ein": meta.get("ein"),
                "filings_total": meta.get("filings_total"), "last_filing": meta.get("last_filing"),
                "form_counts": meta.get("form_counts"),
            }
            if fname in have:
                try:
                    d = json.loads(z.read(fname))
                    us = d.get("facts", {}).get("us-gaap", {})
                    rev, rfy, _ = latest_fact(us, ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"])
                    ast, _, _ = latest_fact(us, ["Assets"])
                    ni, _, _ = latest_fact(us, ["NetIncomeLoss", "ProfitLoss"])
                    lia, _, _ = latest_fact(us, ["Liabilities"])
                    emp, _, _ = latest_fact(us, ["dei:EntityCommonStockSharesOutstanding"])
                    rec.update({
                        "revenue": rev, "revenue_fmt": fmt(rev), "fy": rfy,
                        "assets": ast, "assets_fmt": fmt(ast),
                        "net_income": ni, "net_income_fmt": fmt(ni),
                        "liabilities": lia, "liabilities_fmt": fmt(lia),
                        "xbrl_concepts": len(us),
                    })
                except Exception as e:  # noqa: BLE001
                    rec["error"] = str(e)[:60]
            rec["url"] = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K"
            out[tk] = rec
            print(f"  + {tk}: {rec.get('name','?')[:26]:28} rev {rec.get('revenue_fmt')} | assets {rec.get('assets_fmt')} | filings {rec.get('filings_total')}")

    data = {"source": "SEC EDGAR bulk (companyfacts + submissions)", "byTicker": out, "count": len(out)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// AUTO-GENERATED by webapp/build_secbulk.py from SEC EDGAR bulk data.\n")
        f.write("window.SECBULK_DATA = ")
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write(";\n")
    print(f"\nwrote {OUT} ({OUT.stat().st_size//1024} KB) - {len(out)} companies")


if __name__ == "__main__":
    main()
