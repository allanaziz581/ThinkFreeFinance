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
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = Path(__file__).resolve().parent / "js"
OUT = JS / "news_intel.js"
MODEL = os.getenv("THINKFREE_NEWS_MODEL", "gpt-4o-mini")
MAX_NEWS_PER_SECTOR = 8   # thinning: only the most important stories per sector

# read OPENAI_API_KEY straight from .env (the openai SDK hangs on import in this env;
# urllib to the REST endpoint is what the other build scripts use)
OPENAI_KEY = None
for _l in open(ROOT / ".env", encoding="utf-8"):
    if _l.startswith("OPENAI_API_KEY="):
        OPENAI_KEY = _l.strip().split("=", 1)[1]


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


def main():
    d = load_window("data.js", "window.TF_DATA =")
    quant = load_window("quant_data.js", "window.QUANT_DATA =").get("byTicker", {}) if (JS / "quant_data.js").exists() else {}
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
        print("ERROR: OPENAI_API_KEY missing"); return

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
                out_sectors[sec] = {"summary": data["sector_summary"], "stories": len(by_sector[sec])}
            for tk, v in (data.get("tickers") or {}).items():
                if isinstance(v, dict) and v.get("summary"):
                    out_tickers[tk] = {"summary": v.get("summary"), "what_it_means": v.get("what_it_means", ""), "sector": sec}
            print(f"  + {sec:24} {len(items)} stories -> summary + {len(data.get('tickers') or {})} tickers")
        except Exception as e:  # noqa: BLE001
            print(f"  x {sec}: {e}")

    data_out = {
        "source": "ThinkFree pipeline: local TA/QuantLib/economic analysis -> Chef GPT translation",
        "model": MODEL, "api_calls": calls,
        "bySector": out_sectors, "byTicker": out_tickers,
        "disclaimer": "Plain-English summary generated from public data and our models. Not financial advice.",
    }
    OUT.write_text("// AUTO-GENERATED by webapp/build_news_intel.py. No API keys stored here.\nwindow.NEWS_INTEL = " + json.dumps(data_out, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"\nwrote {OUT} ({OUT.stat().st_size // 1024} KB) | {calls} API calls | {len(out_sectors)} sectors, {len(out_tickers)} tickers")


if __name__ == "__main__":
    main()
