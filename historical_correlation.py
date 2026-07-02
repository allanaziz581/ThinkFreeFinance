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

# ---------------------------------------------------------------------------
# Event detection
# ---------------------------------------------------------------------------

def detect_current_events(economic_summary: str, enriched_articles: list[dict]) -> list[dict]:
    """Find which historical event types are relevant to today's news."""
    combined_text = economic_summary.lower()
    for art in enriched_articles[:50]:
        combined_text += " " + art.get("title", "").lower()
        combined_text += " " + art.get("summary", "").lower()

    detected = []
    for event in HISTORICAL_EVENTS:
        if any(kw in combined_text for kw in event["trigger_keywords"]):
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
    print(f"    Fetching data for {period['label']} ({start} → {end})...")

    # Sample key sectors (limit API calls)
    sample_etfs = {
        "Broad Market": "SPY",
        "Technology": "XLK",
        "Energy": "XLE",
        "Financials": "XLF",
        "Health Care": "XLV",
        "Consumer Staples": "XLP",
        "Bonds": "TLT",
        "Gold": "GLD",
    }

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

        lines.append(f"• **{label}**: {context}")
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
        detected_events = [HISTORICAL_EVENTS[0]]  # Default: always show at least one
        print("[INFO] No specific events detected. Using default: Fed Rate context.")

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

    print(f"\n✅ Historical correlation complete. {len(results)} event type(s) analyzed.")
    print(f"Saved to: {OUTPUT_PATH}")

    return output


def _extract_key_takeaway(event_type: str, periods: list[dict]) -> str:
    """Extract the single most useful insight from analyzed historical periods."""
    if not periods:
        return "Insufficient historical data for this event type."

    all_returns = []
    for p in periods:
        spy = p.get("sector_performance", {}).get("Broad Market", {})
        ret = spy.get("total_return_pct")
        if ret is not None:
            all_returns.append(ret)

    if not all_returns:
        return "Historical market data was not available for this period."

    avg = sum(all_returns) / len(all_returns)
    if avg > 10:
        direction = f"markets generally rose an average of {avg:.1f}%"
    elif avg < -10:
        direction = f"markets generally fell an average of {abs(avg):.1f}%"
    else:
        direction = f"markets were mixed, averaging {avg:+.1f}%"

    return f"In similar historical periods, {direction}. Past outcomes do not guarantee future results."


if __name__ == "__main__":
    run_historical_correlation()
