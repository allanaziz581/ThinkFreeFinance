#!/usr/bin/env python3
"""
ThinkFree Finance, Phase 7: Historical Correlation Engine

Answers "What happened last time?" for current market events.

For each major market event detected in today's analysis:
  1. Identifies the event type (rate hike, recession, tariff, earnings shock, etc.)
  2. Finds historical periods with similar characteristics using yfinance
  3. Measures what happened to sectors and key ETFs in those periods
  4. Produces plain-English explanations of historical outcomes

Input:  news_output/economic_reasoning_summary.json
        news_output/enriched_news_sentiment.json (optional, for event detection)
Output: historical_parallels.json
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
OUTPUT_PATH = BASE_DIR / "historical_parallels.json"

# ---------------------------------------------------------------------------
# Historical event definitions
# Each event has: trigger keywords, historical date ranges, and context
# ---------------------------------------------------------------------------

HISTORICAL_EVENTS: list[dict] = [
    {
        "event_type": "fed_rate_hike",
        "label": "Federal Reserve Rate Hike Cycle",
        "trigger_keywords": ["rate hike", "interest rate increase", "tightening", "hawkish", "federal reserve raised"],
        "historical_periods": [
            {"label": "2022 Rate Hike Cycle", "start": "2022-03-01", "end": "2023-07-01",
             "context": "The Fed raised rates from near 0% to 5.25%, the fastest tightening in 40 years."},
            {"label": "2018 Rate Hike Cycle", "start": "2018-01-01", "end": "2018-12-31",
             "context": "The Fed raised rates 4 times in 2018, contributing to a Q4 market selloff of ~20%."},
            {"label": "2004-2006 Rate Hike Cycle", "start": "2004-06-01", "end": "2006-07-01",
             "context": "The Fed raised rates 17 consecutive times from 1% to 5.25%. Markets remained relatively resilient."},
        ],
        "plain_english": "When the Federal Reserve raises interest rates, borrowing costs rise for everyone. Mortgages get more expensive, businesses pay more to borrow, and consumers carry higher credit card bills. Stocks, especially growth stocks and real estate, typically come under pressure.",
    },
    {
        "event_type": "fed_rate_cut",
        "label": "Federal Reserve Rate Cut",
        "trigger_keywords": ["rate cut", "interest rate decrease", "easing", "dovish", "federal reserve cut"],
        "historical_periods": [
            {"label": "2020 Emergency Cuts (COVID)", "start": "2020-03-01", "end": "2020-12-31",
             "context": "The Fed cut rates to near zero in March 2020. Markets crashed then rallied strongly."},
            {"label": "2008 Rate Cuts (Financial Crisis)", "start": "2008-09-01", "end": "2009-06-01",
             "context": "The Fed slashed rates from 2% to 0% during the financial crisis. Markets fell 50% before recovering."},
            {"label": "2019 Preventive Cuts", "start": "2019-07-01", "end": "2020-02-01",
             "context": "The Fed cut rates three times in 2019 as a 'mid-cycle adjustment.' Markets rose ~25%."},
        ],
        "plain_english": "Rate cuts make borrowing cheaper for everyone. Mortgages become more affordable, businesses can expand more cheaply, and consumers have lower monthly payments. Stocks, especially real estate, utilities, and growth companies, tend to benefit.",
    },
    {
        "event_type": "inflation_spike",
        "label": "Inflation Surge",
        "trigger_keywords": ["inflation", "cpi", "price surge", "cost of living", "price level"],
        "historical_periods": [
            {"label": "2021-2022 Post-COVID Inflation", "start": "2021-04-01", "end": "2023-01-01",
             "context": "CPI peaked at 9.1% in June 2022, the highest since 1981. Energy and commodity stocks outperformed."},
            {"label": "1979-1982 Great Inflation", "start": "1979-01-01", "end": "1982-12-31",
             "context": "Inflation reached 14.8% in 1980. The Fed raised rates to 20%, causing a severe recession but breaking inflation."},
        ],
        "plain_english": "Inflation means prices rise faster than wages, reducing purchasing power. Groceries, rent, and gas become more expensive. Savings accounts lose real value. Companies that sell physical goods or energy often do well. Growth stocks and bonds typically underperform.",
    },
    {
        "event_type": "tariff_announcement",
        "label": "Tariff / Trade War",
        "trigger_keywords": ["tariff", "trade war", "import duty", "trade barrier", "protectionist"],
        "historical_periods": [
            {"label": "2018-2019 US-China Trade War", "start": "2018-03-01", "end": "2020-01-15",
             "context": "The US imposed tariffs on $360B of Chinese goods. Markets were volatile; supply chains shifted. A Phase 1 deal was signed Jan 2020."},
            {"label": "2002 Steel Tariffs", "start": "2002-03-01", "end": "2003-12-01",
             "context": "The US imposed 8-30% tariffs on imported steel. Steel producers benefited; manufacturers faced higher costs. WTO ruled against the US."},
        ],
        "plain_english": "Tariffs are taxes on imported goods. They raise prices for American businesses and consumers who buy those goods. Some domestic industries are protected; others that rely on imported parts face higher costs. Trade partners often retaliate.",
    },
    {
        "event_type": "recession",
        "label": "Economic Recession",
        "trigger_keywords": ["recession", "economic contraction", "gdp decline", "downturn"],
        "historical_periods": [
            {"label": "2020 COVID Recession", "start": "2020-02-01", "end": "2020-09-01",
             "context": "The sharpest recession in modern history, GDP fell 31.4% annualized in Q2 2020. Recovery was rapid due to massive stimulus."},
            {"label": "2008-2009 Great Recession", "start": "2007-12-01", "end": "2009-06-01",
             "context": "Triggered by the housing collapse. GDP fell for 6 consecutive quarters. Unemployment peaked at 10%. S&P 500 fell 57%."},
            {"label": "2001 Dot-Com Recession", "start": "2001-03-01", "end": "2001-11-01",
             "context": "Mild recession triggered by the tech bubble burst and 9/11. GDP fell 1.1%. Nasdaq fell 78% peak to trough."},
        ],
        "plain_english": "A recession is when the economy shrinks, businesses cut back, unemployment rises, and people spend less. Some sectors like healthcare, utilities, and consumer staples tend to hold up better. Banks and discretionary spending typically suffer most.",
    },
    {
        "event_type": "ai_boom",
        "label": "AI / Technology Boom",
        "trigger_keywords": ["artificial intelligence", "ai infrastructure", "generative ai", "llm", "chip demand"],
        "historical_periods": [
            {"label": "2023-2024 Generative AI Surge", "start": "2023-01-01", "end": "2024-12-31",
             "context": "ChatGPT's launch triggered massive AI infrastructure investment. Nvidia rose 800%+. Cloud providers surged."},
            {"label": "1995-2000 Internet Boom", "start": "1995-01-01", "end": "2000-03-31",
             "context": "The internet boom drove Nasdaq up 400%. Ultimately a bubble burst, but the underlying technology transformed the economy."},
        ],
        "plain_english": "Technology booms create wealth rapidly for those invested in the sector, but also risk overvaluation. The companies building the infrastructure (chips, data centers, energy) often outperform the end-application companies.",
    },
    {
        "event_type": "energy_shock",
        "label": "Energy / Oil Price Shock",
        "trigger_keywords": ["oil price", "energy crisis", "opec", "crude oil", "oil shock", "natural gas"],
        "historical_periods": [
            {"label": "2022 Russia-Ukraine Energy Crisis", "start": "2022-02-01", "end": "2022-12-31",
             "context": "Russia's invasion of Ukraine triggered a European energy crisis. Oil hit $130/barrel. Energy stocks surged 60%."},
            {"label": "2014 Oil Price Collapse", "start": "2014-06-01", "end": "2016-02-01",
             "context": "Oil fell from $107 to $26/barrel due to US shale supply glut. Energy sector lost 50%. Consumer goods benefited from cheaper fuel."},
            {"label": "1973 OPEC Oil Embargo", "start": "1973-10-01", "end": "1974-12-31",
             "context": "OPEC quadrupled oil prices. Stagflation followed. Long gas lines became a symbol of the era."},
        ],
        "plain_english": "Energy shocks ripple through the entire economy. High oil prices raise costs for transportation, manufacturing, and heating. Consumers pay more at the gas pump and for groceries. Energy companies profit while most others face margin pressure.",
    },
    {
        "event_type": "defense_spending",
        "label": "Defense / Military Spending Increase",
        "trigger_keywords": ["defense spending", "military budget", "pentagon", "defense contract", "military appropriation"],
        "historical_periods": [
            {"label": "Post-9/11 Defense Buildup", "start": "2001-09-01", "end": "2005-12-31",
             "context": "Defense spending rose from $300B to $500B. Lockheed, Raytheon, Boeing surged 50-100% over 4 years."},
            {"label": "Ukraine War Defense Surge", "start": "2022-02-01", "end": "2024-12-31",
             "context": "NATO countries increased defense budgets to 2%+ of GDP. US defense stocks gained 30-60%."},
        ],
        "plain_english": "Increased defense spending directly benefits defense contractors, aerospace companies, and their supply chains. Government contracts provide predictable, long-term revenue. NATO allies tend to buy American equipment.",
    },
]

# ---------------------------------------------------------------------------
# Sector ETF proxies for historical performance measurement
# ---------------------------------------------------------------------------

SECTOR_ETFS = {
    "Information Technology": "XLK",
    "Health Care": "XLV",
    "Financials": "XLF",
    "Energy": "XLE",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Communication Services": "XLC",
    "Broad Market": "SPY",
    "Bonds": "TLT",
    "Gold": "GLD",
}

# The SPDR sector ETFs (XLK, XLE, ...) launched 1998-12-22; SPY launched 1993-01-29.
# Periods that predate these cannot be measured with the ETFs, so for older periods we
# fall back to the S&P 500 index (^GSPC, price return, available from the 1950s) and say
# so, rather than silently showing an empty or ETF-only picture.
SPY_INCEPTION = "1993-02-01"
ETF_INCEPTION = "1998-12-22"


def broad_market_proxy(start: str) -> str:
    """SPY once it exists, otherwise the ^GSPC index (price return) for older periods."""
    return "SPY" if start >= SPY_INCEPTION else "^GSPC"


def sector_data_available(start: str) -> bool:
    """Sector ETFs only exist for periods starting on/after their 1998 inception."""
    return start >= ETF_INCEPTION

# ---------------------------------------------------------------------------
# Event detection
# ---------------------------------------------------------------------------

import re

# Words that flip the meaning of the sentence they appear in. If the only sentence
# mentioning an event keyword is negated ("the Fed did NOT raise rates"), that keyword
# is not real evidence the event is happening.
NEGATION_WORDS = {
    "no", "not", "never", "without", "avoided", "avoid", "avoids", "denied", "deny",
    "denies", "unlikely", "against", "ruled out", "rules out", "rule out", "isn't",
    "aren't", "wasn't", "weren't", "won't", "wouldn't", "doesn't", "didn't", "don't",
    "hasn't", "haven't", "cannot", "can't", "declined", "reject", "rejected", "n't",
}


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[.!?\n]+", text) if s.strip()]


def _sentence_is_negated(sentence: str) -> bool:
    low = sentence.lower()
    tokens = set(re.findall(r"[a-z']+", low))
    if tokens & NEGATION_WORDS:
        return True
    # multi-word negations ("ruled out") won't survive tokenisation, check the raw string
    return any(neg in low for neg in NEGATION_WORDS if " " in neg)


def event_matches(text: str, keywords: list[str]) -> bool:
    """An event is only 'detected' when at least TWO distinct trigger keywords appear AND
    at least one of them sits in a sentence that is not negated.

    The old code fired on a single substring match anywhere in the blob, so one incidental
    phrase (or a sentence saying the event did NOT happen) was enough to attach a whole
    historical event. Requiring two distinct keywords plus a non-negated sentence makes a
    'no historical parallel today' result the normal, expected outcome.
    """
    low = text.lower()
    hits = {kw for kw in keywords if kw in low}
    if len(hits) < 2:
        return False
    sentences = _split_sentences(text)
    for kw in hits:
        for sent in sentences:
            if kw in sent.lower() and not _sentence_is_negated(sent):
                return True
    return False


def detect_current_events(economic_summary: str, enriched_articles: list[dict]) -> list[dict]:
    """Find which historical event types are relevant to today's news."""
    combined_text = economic_summary
    for art in enriched_articles[:50]:
        combined_text += " " + art.get("title", "")
        combined_text += " " + art.get("summary", "")

    detected = []
    for event in HISTORICAL_EVENTS:
        if event_matches(combined_text, event["trigger_keywords"]):
            detected.append(event)

    return detected


# ---------------------------------------------------------------------------
# Historical performance measurement
# ---------------------------------------------------------------------------

def max_drawdown_pct(prices) -> float:
    """Largest peak-to-subsequent-trough decline, in percent (a non-positive number).

    Time order matters: max drawdown is min over time of (price / running_peak - 1).
    The old code used (global_min - global_max) / global_max, which ignores order, so a
    series that dipped BEFORE it peaked reported a drawdown that never happened (e.g.
    [100, 80, 120] gave -33% when the real peak-to-trough drop was only -20%, and a
    monotonically rising series gave a spurious loss instead of 0).
    """
    s = pd.Series(list(prices), dtype="float64")
    if len(s) < 2:
        return 0.0
    running_peak = s.cummax()
    dd = s / running_peak - 1.0
    return float(round(dd.min() * 100, 1))


def measure_period_performance(ticker: str, start: str, end: str) -> dict | None:
    """Download price data and compute performance metrics for a period."""
    try:
        data = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        if data.empty or len(data) < 5:
            return None

        close = data["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        start_price = float(close.iloc[0])
        end_price   = float(close.iloc[-1])

        total_return = (end_price - start_price) / start_price * 100
        max_drawdown = max_drawdown_pct(close.tolist())   # time-ordered peak-to-trough

        return {
            "ticker": ticker,
            "start_price": round(start_price, 2),
            "end_price":   round(end_price, 2),
            "total_return_pct": round(total_return, 1),
            "max_drawdown_pct": max_drawdown,
            "trading_days": len(data),
        }
    except Exception:
        return None


def analyze_historical_period(period: dict) -> dict:
    """Measure sector ETF performance during a historical period."""
    start = period["start"]
    end   = period["end"]

    performances = {}
    print(f"    Fetching data for {period['label']} ({start} to {end})...")

    # Broad market always uses the best available proxy for the era. Sector granularity
    # only exists once the sector ETFs launched (Dec 1998); for older periods we show the
    # index alone and flag the limitation instead of pretending sector data existed.
    sample_etfs = {"Broad Market": broad_market_proxy(start)}
    data_note = ""
    if sector_data_available(start):
        sample_etfs.update({
            "Technology": "XLK",
            "Energy": "XLE",
            "Financials": "XLF",
            "Health Care": "XLV",
            "Consumer Staples": "XLP",
            "Bonds": "TLT",
            "Gold": "GLD",
        })
    else:
        data_note = (
            f"Sector ETFs did not exist before {ETF_INCEPTION[:4]}; only the broad market "
            f"index ({sample_etfs['Broad Market']}, price return) is shown for this period."
        )

    for label, ticker in sample_etfs.items():
        perf = measure_period_performance(ticker, start, end)
        if perf:
            performances[label] = perf

    # Rank sectors by return
    ranked = sorted(
        [(label, p["total_return_pct"]) for label, p in performances.items()],
        key=lambda x: x[1],
        reverse=True,
    )

    winners = [f"{label} ({ret:+.1f}%)" for label, ret in ranked[:3]]
    losers  = [f"{label} ({ret:+.1f}%)" for label, ret in ranked[-3:]]

    return {
        **period,
        "sector_performance": performances,
        "winners": winners,
        "losers":  losers,
        "data_note": data_note,
    }


# ---------------------------------------------------------------------------
# Plain-English narrative generator
# ---------------------------------------------------------------------------

def generate_historical_narrative(event: dict, analyzed_periods: list[dict]) -> str:
    """Build a plain-English explanation of what historically happened."""
    lines = [f"**Historical context: {event['label']}**\n"]
    lines.append(event["plain_english"])
    lines.append("\n**What happened in similar past situations:**\n")

    for period in analyzed_periods:
        label = period["label"]
        context = period["context"]
        winners = ", ".join(period.get("winners", []))
        losers  = ", ".join(period.get("losers", []))

        spy_ret = period.get("sector_performance", {}).get("Broad Market", {}).get("total_return_pct", "N/A")

        lines.append(f"- **{label}**: {context}")
        if period.get("data_note"):
            lines.append(f"  Note: {period['data_note']}")
        if spy_ret != "N/A":
            direction = "rose" if spy_ret > 0 else "fell"
            lines.append(f"  Overall market {direction} {abs(spy_ret):.1f}%.")
        if winners:
            lines.append(f"  Best performers: {winners}")
        if losers:
            lines.append(f"  Worst performers: {losers}")
        lines.append("")

    lines.append("*Historical patterns are informative but do not guarantee future outcomes.*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_historical_correlation() -> dict:
    print("=== ThinkFree, Phase 7: Historical Correlation Engine ===")

    # Load current market context
    econ_path = BASE_DIR / "news_output" / "economic_reasoning_summary.json"
    enriched_path = BASE_DIR / "news_output" / "enriched_news_sentiment.json"

    economic_summary = ""
    enriched_articles: list[dict] = []

    if econ_path.exists():
        with open(econ_path, "r", encoding="utf-8") as f:
            econ_data = json.load(f)
        economic_summary = econ_data.get("summary", "")
        print("Loaded economic reasoning summary.")
    else:
        print("[WARN] No economic_reasoning_summary.json found. Using keyword detection only.")

    if enriched_path.exists():
        with open(enriched_path, "r", encoding="utf-8") as f:
            enriched_articles = json.load(f)
        print(f"Loaded {len(enriched_articles)} enriched articles.")

    # Detect relevant event types
    print("\nDetecting current market events...")
    detected_events = detect_current_events(economic_summary, enriched_articles)
    print(f"Detected {len(detected_events)} relevant event type(s): {[e['event_type'] for e in detected_events]}")

    if not detected_events:
        # No strong parallel is a normal, honest outcome, do NOT force a default event.
        print("[INFO] No strong historical parallel to today's news.")
        output = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "events_analyzed": 0,
            "message": "No strong historical parallel to today's news.",
            "historical_parallels": [],
        }
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"Saved to: {OUTPUT_PATH}")
        return output

    # Analyze historical periods for each detected event
    results = []
    for event in detected_events[:3]:  # Limit to top 3 event types
        print(f"\nAnalyzing historical parallels for: {event['label']}")

        analyzed_periods = []
        for period in event["historical_periods"][:2]:  # Top 2 historical periods per event
            analysis = analyze_historical_period(period)
            analyzed_periods.append(analysis)

        narrative = generate_historical_narrative(event, analyzed_periods)

        results.append({
            "event_type": event["event_type"],
            "label": event["label"],
            "trigger_keywords_matched": [
                kw for kw in event["trigger_keywords"]
                if kw in economic_summary.lower()
            ],
            "plain_english_context": event["plain_english"],
            "historical_periods": analyzed_periods,
            "narrative": narrative,
            "key_takeaway": _extract_key_takeaway(event["event_type"], analyzed_periods),
        })

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "events_analyzed": len(results),
        "historical_parallels": results,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nHistorical correlation complete. {len(results)} event type(s) analyzed.")
    print(f"Saved to: {OUTPUT_PATH}")

    return output


def _extract_key_takeaway(event_type: str, periods: list[dict]) -> str:
    """Summarise each comparable period on its own terms, never as a single average.

    Averaging across historical episodes (as the old code did) invents a number that
    happened in none of them, and lets one outlier dominate. Instead we report each
    period's outcome and the overall range, so the reader sees the dispersion.
    """
    if not periods:
        return "Insufficient historical data for this event type."

    per_period = []
    for p in periods:
        spy = p.get("sector_performance", {}).get("Broad Market", {})
        ret = spy.get("total_return_pct")
        if ret is not None:
            per_period.append((p.get("label", "period"), ret))

    if not per_period:
        return "Historical market data was not available for these periods."

    parts = [
        f"{label}: the market {'rose' if r > 0 else 'fell'} {abs(r):.1f}%"
        for label, r in per_period
    ]
    if len(per_period) == 1:
        return (
            f"In the one comparable period, {parts[0]}. "
            "Past outcomes do not guarantee future results."
        )

    lo = min(r for _, r in per_period)
    hi = max(r for _, r in per_period)
    return (
        "Each comparable period differed. "
        + "; ".join(parts)
        + f". Across these separate episodes the market ranged from {lo:+.1f}% to "
        f"{hi:+.1f}% (each period reported on its own, not blended into one figure). "
        "Past outcomes do not guarantee future results."
    )


if __name__ == "__main__":
    run_historical_correlation()
