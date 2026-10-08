"""ThinkFree - News Intelligence pipeline (local analysis -> minimal Chef GPT).

Design (cost-conscious, per the architecture):
  1. LOCAL (no API): gather the news already pulled, attach each ticker's
     Module-2 technical signal (signal_output_phase3.json) + QuantLib metrics
     (quant_data.js) + the sector's economic-reasoning summary
     (news_output/sector_summaries.json + economic_reasoning_summary.json).
  2. THIN: keep only the most important stories per sector, condensed into a
     compact brief that preserves the numbers + signals + context.
  3. API ONLY AT THE END: ONE batched Chef GPT call PER SECTOR (~8 calls total)
     translates the condensed brief into a simple, friendly, jargon-free summary
     plus a per-ticker "what it means for you" line.

Writes webapp/js/news_intel.js (window.NEWS_INTEL) for in-app display.

Run:  ./tf_env/bin/python webapp/build_news_intel.py [--limit-sectors N]
Model: THINKFREE_NEWS_MODEL env (default gpt-4o-mini, cheap; the heavy lifting
is local so a small model translates accurately).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from numeral_validation import collect_numbers, validate_numerals
JS = Path(__file__).resolve().parent / "js"
OUT = JS / "news_intel.js"
MODEL = os.getenv("THINKFREE_NEWS_MODEL", "gpt-4o-mini")
MAX_NEWS_PER_SECTOR = 8   # thinning: only the most important stories per sector

# read OPENAI_API_KEY straight from .env (the openai SDK hangs on import in this env;
# urllib to the REST endpoint is what the other build scripts use)
load_dotenv(ROOT / ".env")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")


def checked_summary(summary, why, sources, missing_sources=()):
    """Fail closed for unsupported numeric values; expose limits to the reader.

    Callers must scope sources to the ticker/sector being summarized. This is
    not an entailment or truth detector. Raw rejected prose is not published.
    """
    summary = summary if isinstance(summary, str) else ""
    why = why if isinstance(why, str) else ""
    result = validate_numerals(collect_numbers(sources), summary + " " + why, strict=True)
    result["status"] = "checked" if result["ok"] and sources and summary else "withheld"
    result["missing_sources"] = list(missing_sources)
    if result["status"] == "withheld":
        summary, why = "Summary unavailable: source checks need review.", ""
    return {"summary": summary, "what_it_means": why, "source_check": result}


def chat_json(system, user, model, timeout=60):
    body = json.dumps({
        "model": model, "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions", data=body, method="POST",
        headers={"Authorization": "Bearer " + OPENAI_KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    return json.loads(d["choices"][0]["message"]["content"] or "{}")


def load_window(fname, marker):
    t = (JS / fname).read_text(encoding="utf-8")
    return json.loads(t.split(marker, 1)[1].rstrip().rstrip(";").strip())


def load_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


# GICS-ish sector name normalization so news sectors line up with summaries/quant
SECTOR_ALIASES = {
    "Technology": "Information Technology", "Tech": "Information Technology",
    "Healthcare": "Health Care", "Financial Services": "Financials",
    "Telecommunications": "Communication Services", "Telecom": "Communication Services",
}


def norm_sector(s):
    s = (s or "Markets").strip()
    return SECTOR_ALIASES.get(s, s)


COMMON_TK = {"ON", "IT", "ALL", "NOW", "HAS", "A", "ARE", "SO", "D", "T", "K", "DD", "BY", "OR", "AN", "GO", "ONE", "KEY", "CAR"}
GENERIC_CO = {"inc", "corp", "corporation", "company", "co", "ltd", "plc", "group", "holdings", "the", "technologies", "international", "systems", "industries", "financial"}


def news_relevant(item, tk, names):
    """True if the article actually names the company (filters common-word ticker mismatches)."""
    import re as _re
    blob = (item.get("headline", "") or "") + " " + (item.get("summary", "") or "")
    low = blob.lower()
    toks = [t for t in (names.get(tk, "") or tk).lower().replace(".", "").replace(",", "").split() if len(t) >= 4 and t not in GENERIC_CO]
    if any(t in low for t in toks):
        return True
    if _re.search(r"\$" + tk + r"\b|\(" + tk + r"\)", blob):
        return True
    if tk not in COMMON_TK and len(tk) >= 3 and _re.search(r"\b" + tk + r"\b", blob):
        return True
    return False


def main():
    d = load_window("data.js", "window.TF_DATA =")
    quant = load_window("quant_data.js", "window.QUANT_DATA =").get("byTicker", {}) if (JS / "quant_data.js").exists() else {}
    names = {tk: v.get("name", "") for tk, v in (load_window("prices_data.js", "window.PRICES_DATA =").get("byTicker", {}) if (JS / "prices_data.js").exists() else {}).items()}
    ta_list = load_json(ROOT / "Module_2_Technical_Analysis" / "signal_output_phase3.json", [])
    ta = {x.get("ticker"): x for x in ta_list if x.get("ticker")}
    sector_sum = load_json(ROOT / "news_output" / "sector_summaries.json", {})
    econ = load_json(ROOT / "news_output" / "economic_reasoning_summary.json", {})

    news = d.get("news", [])
    # ---- LOCAL: group news by sector, rank by importance, attach signals ----
    by_sector = defaultdict(list)
    for n in news:
        by_sector[norm_sector(n.get("sector"))].append(n)

    def importance(n):
        cred = n.get("credibility") or 0
        imp = abs(n.get("impact") or 0)
        return imp * 2 + cred

    if not OPENAI_KEY:
        raise SystemExit("OPENAI_API_KEY is required to regenerate summaries; existing output was not changed.")

    limit = None
    if "--limit-sectors" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit-sectors") + 1])

    SYSTEM = (
        "You are ThinkFree's Chef GPT: you translate financial news, economics, and market signals "
        "into plain, friendly English for everyday people with no finance background. Be clear and "
        "warm, never use corporate jargon, never intimidate, and explain any term you must use. "
        "Be objective and honest about uncertainty. Never give buy/sell advice or guarantees."
    )

    out_sectors, out_tickers = {}, {}
    sectors = sorted(by_sector, key=lambda s: -len(by_sector[s]))
    if limit:
        sectors = sectors[:limit]

    calls = 0
    for sec in sectors:
        items = sorted(by_sector[sec], key=importance, reverse=True)[:MAX_NEWS_PER_SECTOR]
        if not items:
            continue
        # build the condensed, signal-enriched brief (LOCAL)
        brief = []
        for n in items:
            tk = n.get("symbol", "")
            if tk and not news_relevant(n, tk, names):
                tk = ""   # generic article mis-tagged to a common-word ticker: don't attribute
            t = ta.get(tk, {})
            q = quant.get(tk, {})
            sig = t.get("final_signal") or q.get("ta_signal")
            reason = t.get("reasoning", "")
            vol = q.get("volatility")
            brief.append({
                "ticker": tk,
                "headline": n.get("headline", "")[:160],
                "snippet": (n.get("summary", "") or "")[:320],
                "sentiment": n.get("sentiment"),
                "tech_signal": sig,
                "tech_reason": reason[:160] if reason else "",
                "volatility_pct": vol,
            })
        sec_context = ""
        if isinstance(sector_sum.get(sec), dict):
            sec_context = sector_sum[sec].get("sector_summary", "")[:700]
        elif isinstance(sector_sum.get(sec), str):
            sec_context = sector_sum[sec][:700]

        user = (
            f"SECTOR: {sec}\n"
            f"ECONOMIC CONTEXT (from our economic model): {sec_context or 'n/a'}\n"
            f"OVERALL ECONOMY: {(econ.get('summary','') or '')[:400]}\n\n"
            f"NEWS + SIGNALS (already analyzed locally):\n{json.dumps(brief, ensure_ascii=False)}\n\n"
            "Write JSON exactly as: {\"sector_summary\": <3-4 friendly sentences on what is happening "
            "in this sector and what it means for an everyday person's money/jobs/costs>, "
            "\"tickers\": {<TICKER>: {\"summary\": <2 plain sentences on this company's news>, "
            "\"what_it_means\": <1 sentence on why a regular person might care>}}}. "
            "Blend the news with the technical signal and economic context. Keep it simple and non-intimidating."
        )
        try:
            data = chat_json(SYSTEM, user, MODEL)
            calls += 1
            if data.get("sector_summary"):
                source_context = {"news": brief, "sector": sec_context, "economy": (econ.get("summary", "") or "")[:400]}
                missing = [name for name, value in (("sector context", sec_context),
                           ("economic context", source_context["economy"])) if not value]
                out_sectors[sec] = {**checked_summary(data["sector_summary"], "", source_context, missing),
                                    "stories": len(by_sector[sec])}
            for tk, v in (data.get("tickers") or {}).items():
                if isinstance(v, dict) and v.get("summary"):
                    ticker_sources = [item for item in brief if item["ticker"] == tk]
                    out_tickers[tk] = {**checked_summary(v.get("summary"), v.get("what_it_means", ""),
                                           ticker_sources, [] if ticker_sources else ["ticker-specific news"]), "sector": sec}
            print(f"  + {sec:24} {len(items)} stories -> summary + {len(data.get('tickers') or {})} tickers")
        except Exception as e:  # noqa: BLE001
            print(f"  x {sec}: {e}")

    if not out_sectors and not out_tickers:
        raise SystemExit("No summaries were generated; existing output was not changed.")
    data_out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "ThinkFree pipeline: local TA/QuantLib/economic analysis -> Chef GPT translation",
        "model": MODEL, "api_calls": calls,
        "bySector": out_sectors, "byTicker": out_tickers,
        "disclaimer": "Plain-English summary generated from public data and our models. Not financial advice.",
    }
    OUT.write_text("// AUTO-GENERATED by webapp/build_news_intel.py. No API keys stored here.\nwindow.NEWS_INTEL = " + json.dumps(data_out, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"\nwrote {OUT} ({OUT.stat().st_size // 1024} KB) | {calls} API calls | {len(out_sectors)} sectors, {len(out_tickers)} tickers")


if __name__ == "__main__":
    main()
