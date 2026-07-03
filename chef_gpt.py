#!/usr/bin/env python3
"""
ThinkFree Finance, Chef GPT Intelligence Synthesis (Phase 11)

Reads all available pipeline outputs and generates a plain-English intelligence
briefing tailored to the user's risk profile.

The report answers 8 questions for every major event:
  1. What happened?
  2. Why did it happen?
  3. Who benefits?
  4. Who is negatively affected?
  5. How could this affect consumers (rent, groceries, bills, jobs)?
  6. How could this affect businesses?
  7. How could this affect financial markets?
  8. What happened historically in similar situations?

Output: intelligence_report.json
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_DIR = Path(__file__).parent
OUTPUT_PATH = BASE_DIR / "intelligence_report.json"

OPENAI_MODEL = os.getenv("THINKFREE_MODEL", "gpt-4o")


# ------------------------------------------------------------------
# Safe file loader
# ------------------------------------------------------------------

def load_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


# ------------------------------------------------------------------
# Input assembler, collects all phase outputs
# ------------------------------------------------------------------

def assemble_inputs() -> dict:
    user_profile = load_json(BASE_DIR / "user_profile.json", {})

    economic_reasoning = load_json(
        BASE_DIR / "news_output" / "economic_reasoning_summary.json", {}
    )

    sector_summaries = load_json(
        BASE_DIR / "news_output" / "sector_summaries.json", {}
    )

    technical_signals = load_json(
        BASE_DIR / "Module_2_Technical_Analysis" / "signal_output_phase3.json", []
    )

    # Backtest metrics are SUPPRESSED. The existing results_run/summary_metrics.json came
    # from a look-ahead-contaminated run (the universe was drawn from TODAY's sector
    # membership and backtested over the past year, which leaks survivorship and
    # composition the strategy could not have known at the time). It is archived, not
    # loaded. A clean point-in-time re-run is a documented follow-up (see
    # Module_2_Technical_Analysis/BACKTEST_STATUS.md); until then the briefing cites no
    # backtest CAGR/Sharpe.

    recession_data = load_json(BASE_DIR / "recession_signals_output.json", {})

    political_trades = load_json(
        BASE_DIR / "GPT_Economy" / "Intelligence_layer (IN PROGRESS)" / "intelligence_output.json",
        {}
    )

    historical_parallels = load_json(BASE_DIR / "historical_parallels.json", {})

    opportunity_scores = load_json(BASE_DIR / "opportunity_scores.json", {})

    quantlib_metrics = load_json(BASE_DIR / "quantlib_metrics.json", {})

    return {
        "user_profile": user_profile,
        "economic_reasoning": economic_reasoning,
        "sector_summaries": sector_summaries,
        "technical_signals": technical_signals,
        "recession_data": recession_data,
        "political_trades": political_trades,
        "historical_parallels": historical_parallels,
        "opportunity_scores": opportunity_scores,
        "quantlib_metrics": quantlib_metrics,
    }


# ------------------------------------------------------------------
# Prompt builder
# ------------------------------------------------------------------

def build_prompt(inputs: dict) -> str:
    profile = inputs["user_profile"]
    econ = inputs["economic_reasoning"]
    sectors = inputs["sector_summaries"]
    signals = inputs["technical_signals"]
    recession = inputs["recession_data"]
    political = inputs["political_trades"]
    historical = inputs["historical_parallels"]
    opportunity = inputs["opportunity_scores"]

    # Profile summary
    age = profile.get("age", "unknown")
    risk = profile.get("risk_tolerance", "moderate")
    goal = profile.get("investment_goal", "growth")
    timeline = profile.get("timeline", "mid-term")
    emotional = profile.get("emotional_response", "hold")

    profile_text = (
        f"The reader is {age} years old with a {risk} risk tolerance. "
        f"Their investment goal is {goal} over a {timeline} horizon. "
        f"When markets drop, they tend to {emotional}."
    )

    # Economic summary
    econ_summary = econ.get("summary", "No economic summary available.")
    bullish_sectors = econ.get("bullish_sectors", [])
    bearish_sectors = econ.get("bearish_sectors", [])

    econ_text = f"{econ_summary}\n\nBullish sectors: {', '.join(bullish_sectors) or 'None identified'}"
    econ_text += f"\nBearish sectors: {', '.join(bearish_sectors) or 'None identified'}"

    # Sector details (top 5)
    sector_text = ""
    for i, (sector, data) in enumerate(sectors.items()):
        if i >= 5:
            break
        if isinstance(data, dict):
            summary = data.get("sector_summary", "")[:400]
            sector_text += f"\n{sector}: {summary}\n"

    # Technical signals (top 5 BUY or SELL)
    signal_text = ""
    buy_signals = [s for s in signals if isinstance(s, dict) and s.get("final_signal") == "BUY"][:3]
    sell_signals = [s for s in signals if isinstance(s, dict) and s.get("final_signal") == "SELL"][:3]
    for s in buy_signals:
        signal_text += f"\n{s.get('ticker', '?')}: BUY signal (confidence: {s.get('confidence_score', 0)})"
    for s in sell_signals:
        signal_text += f"\n{s.get('ticker', '?')}: SELL signal (confidence: {s.get('confidence_score', 0)})"
    if not signal_text:
        signal_text = "No strong buy or sell signals detected today."

    # Recession
    recession_risk = recession.get("recession_risk", {})
    recession_score = recession_risk.get("score", "N/A")
    recession_label = recession_risk.get("label", "Unknown")
    recession_plain = recession_risk.get("plain_english_summary", "")
    real_world = recession.get("real_world_impact", {})

    recession_text = (
        f"Recession Risk Score: {recession_score}/10 ({recession_label}). {recession_plain}\n"
        f"Real-world impact on consumers:\n"
        f"- Mortgages: {real_world.get('mortgages', 'N/A')}\n"
        f"- Credit cards: {real_world.get('credit_cards', 'N/A')}\n"
        f"- Jobs: {real_world.get('jobs', 'N/A')}\n"
        f"- Savings: {real_world.get('savings', 'N/A')}"
    )

    # Political intelligence (from intelligence_output.json)
    political_text = ""
    if political and isinstance(political, dict):
        trade_links = political.get("congressional_trade_links", [])
        housing_trades = political.get("housing_trades", [])
        if trade_links or housing_trades:
            political_text = "Recent congressional trade disclosures (public STOCK Act filings):\n"
            for item in trade_links[:5]:
                ticker = item.get("ticker", "")
                events = item.get("political_events", [])
                if ticker and events:
                    political_text += f"- {ticker}: {events[0][:200]}\n"
            for trade in housing_trades[:3]:
                ticker = trade.get("Ticker", trade.get("ticker", ""))
                rep = trade.get("Representative", "")
                tx = trade.get("Transaction", "")
                if ticker:
                    political_text += f"- {rep}, {tx} {ticker}\n"
        political_text += (
            "\nIMPORTANT: All political intelligence is based entirely on publicly available "
            "financial disclosures. This identifies timing relationships only and does not "
            "imply or allege any wrongdoing."
        )
    else:
        political_text = "No congressional trade data available."

    # Historical parallels
    historical_text = ""
    if historical and historical.get("historical_parallels"):
        events_detected = historical.get("events_detected", [])
        parallels = historical.get("historical_parallels", [])
        if events_detected:
            historical_text = f"Current events matching historical patterns: {', '.join(e.replace('_', ' ').title() for e in events_detected)}\n\n"
        for parallel in parallels[:3]:
            if not isinstance(parallel, dict):
                continue
            event_type = parallel.get("event_type", "").replace("_", " ").title()
            period_name = parallel.get("period_name", "")
            period_dates = parallel.get("period_dates", "")
            narrative = parallel.get("narrative", "")[:400]
            winners = parallel.get("winners", [])[:3]
            losers = parallel.get("losers", [])[:3]
            winner_str = ", ".join(
                f"{w.get('ticker', w)} (+{w.get('total_return_pct', 0):.0f}%)" if isinstance(w, dict) else str(w)
                for w in winners
            )
            loser_str = ", ".join(
                f"{l.get('ticker', l)} ({l.get('total_return_pct', 0):.0f}%)" if isinstance(l, dict) else str(l)
                for l in losers
            )
            historical_text += (
                f"Event: {event_type}, Analogue: {period_name} ({period_dates})\n"
                f"What happened: {narrative}\n"
            )
            if winner_str:
                historical_text += f"Winners: {winner_str}\n"
            if loser_str:
                historical_text += f"Losers: {loser_str}\n"
            historical_text += "\n"
    else:
        historical_text = "Historical correlation data not yet available."

    # Opportunity scores summary
    opportunity_text = ""
    if opportunity:
        rec_used = opportunity.get("recession_risk_used", "N/A")
        sector_opps = opportunity.get("sector_opportunities", [])
        ticker_opps = opportunity.get("ticker_opportunities", [])
        # Outlook and suitability are separate: show the outlook label/conviction, and the
        # suitability separately, never a single blended 0-10 score.
        top_sectors = [
            f"{s.get('sector')} (outlook {(s.get('outlook') or {}).get('label', 'Neutral')}, "
            f"conviction {(s.get('outlook') or {}).get('conviction', 0)}; "
            f"{(s.get('suitability') or {}).get('label', 'Neutral fit')})"
            for s in sector_opps[:5]
        ]
        top_tickers_buy = [
            f"{t.get('ticker')} (signal {t.get('signal')}, conviction {t.get('signal_conviction', 0)})"
            for t in ticker_opps if t.get("signal") == "BUY"
        ][:3]
        opportunity_text = (
            f"Top sectors by outlook: {', '.join(top_sectors) or 'None'}\n"
            f"Top buy-signal tickers: {', '.join(top_tickers_buy) or 'None'}\n"
            f"Recession discount applied: {rec_used}/10"
        )
    else:
        opportunity_text = "Opportunity scores not yet available."

    # Output schema
    schema = json.dumps({
        "generated_at": "<ISO timestamp>",
        "profile_match": "<one sentence about how today's market aligns with user profile>",
        "headline": "<one compelling sentence summarizing today's most important market development>",
        "market_overview": {
            "what_happened": "<2-3 sentences, plain English, no jargon>",
            "why_it_happened": "<2-3 sentences explaining the economic cause>",
            "who_benefits": "<list of who stands to gain, with brief explanation>",
            "who_is_hurt": "<list of who may be negatively impacted>",
        },
        "consumer_impact": {
            "summary": "<2-3 sentences on how this affects everyday people's finances>",
            "rent_and_housing": "<one sentence>",
            "groceries_and_gas": "<one sentence>",
            "credit_cards_and_loans": "<one sentence>",
            "jobs_and_income": "<one sentence>",
        },
        "sector_outlook": {
            "bullish": ["<sector>"],
            "bearish": ["<sector>"],
            "why": "<one paragraph explaining the sector dynamics in plain English>",
        },
        "political_intelligence": {
            "summary": "<2-3 sentences about relevant government disclosures>",
            "notable_events": ["<event 1>", "<event 2>"],
            "disclaimer": "This analysis identifies timing relationships between publicly available government disclosures and market events. It does not imply or allege wrongdoing of any kind.",
        },
        "market_signals": {
            "summary": "<plain English explanation of what the technical indicators say>",
            "top_opportunities": ["<ticker: what the signal says in plain English>"],
            "caution_flags": ["<ticker: what the signal says in plain English>"],
        },
        "historical_context": "<2-3 sentences: what happened last time the market faced similar conditions>",
        "recession_risk": {
            "score": "<number 0-10>",
            "label": "<Low/Moderate/Elevated/High/Very High>",
            "plain_english": "<one paragraph>",
            "what_to_watch": "<one sentence on the most important indicator to monitor>",
        },
        "what_it_means_for_you": "<2-3 sentences tailored specifically to the user's age, risk tolerance, and goals>",
        "bottom_line": "<one sentence, the single most important takeaway from today's intelligence>",
        "disclaimer": "ThinkFree provides financial intelligence and economic education for informational purposes only. This is not investment advice. All investment decisions are yours to make.",
    }, indent=2)

    # QuantLib text
    quantlib = inputs.get("quantlib_metrics", {})
    quantlib_text = ""
    if quantlib and quantlib.get("ticker_metrics"):
        top_ql = quantlib["ticker_metrics"][:5]
        quantlib_text = "QuantLib risk metrics (top signals):\n"
        for t in top_ql:
            ticker = t.get("ticker", "?")
            signal = t.get("technical_signal", "")
            freq   = t.get("hist_freq_up_5pct_1mo")
            years  = t.get("hist_lookback_years", 0)
            vol    = t.get("annualized_volatility", 0)
            var95  = t.get("var_95_daily", 0)
            freq_txt = (
                f"over the past {years:.0f}yr {freq:.0f}% of 1-month periods gained 5%+"
                if freq is not None else "insufficient history for a 5% frequency"
            )
            quantlib_text += (
                f"- {ticker} ({signal}): {freq_txt}. Vol={vol:.0f}%/yr  "
                f"Daily VaR(95%)={var95:.2f}%\n"
            )
    else:
        quantlib_text = "QuantLib risk metrics not yet available."

    prompt = f"""You are ThinkFree's AI financial analyst. Your job is to translate complex financial and economic events into plain English that any person can understand, including someone who has never studied finance, economics, or investing.

Write for a blue-collar worker, a small business owner, a renter, a recent college graduate, or anyone trying to understand how the news might affect their wallet. Use simple words. When you must use a financial term, define it immediately in plain language.

THE USER YOU ARE WRITING FOR:
{profile_text}

TODAY'S MARKET INTELLIGENCE:
===== ECONOMIC OVERVIEW =====
{econ_text}

===== SECTOR ANALYSIS =====
{sector_text}

===== POLITICAL INTELLIGENCE (PUBLIC DISCLOSURES ONLY) =====
{political_text}

===== MARKET SIGNALS =====
{signal_text}

===== QUANTLIB RISK METRICS (volatility, VaR, historical 5% frequency) =====
{quantlib_text}

===== OPPORTUNITY SCORES (Combined Signal Ranking) =====
{opportunity_text}

===== RECESSION INDICATORS =====
{recession_text}

===== HISTORICAL PARALLELS, WHAT HAPPENED LAST TIME? =====
{historical_text}

YOUR TASK:
Write a complete intelligence briefing in the JSON format below. Every section must answer the question in plain English that anyone can understand. Use a friendly, informative tone, like a knowledgeable friend explaining the news over coffee, not a Wall Street analyst writing a report.

For every major event, apply the 8-question framework:
1. What happened? (plain facts)
2. Why did it happen? (economic cause, explained simply)
3. Who benefits? (specific groups, companies, sectors)
4. Who is negatively affected? (specific groups who may be hurt)
5. How does this affect consumers? (rent, groceries, gas, credit cards, loans, jobs)
6. How does this affect businesses? (which types win or lose)
7. How does this affect markets? (sectors, stocks, bonds, plain English)
8. What happened historically? (use the historical parallels data above, cite actual periods and measured returns)

In the historical_context field: be specific. Name the actual historical period (e.g., "During the 2022 rate hike cycle..."), describe what happened, and mention measured sector performance if available.

Return ONLY valid JSON in exactly this structure (no markdown, no explanation outside the JSON):
{schema}"""

    return prompt


# ------------------------------------------------------------------
# Chef GPT runner
# ------------------------------------------------------------------

def run_chef_gpt() -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Add your API key to .env and try again."
        )

    print("=== ThinkFree, Chef GPT Intelligence Synthesis ===")
    print("Loading pipeline outputs...")
    inputs = assemble_inputs()

    available = []
    if inputs["economic_reasoning"]:
        available.append("Economic Reasoning")
    if inputs["sector_summaries"]:
        available.append("Sector Summaries")
    if inputs["technical_signals"]:
        available.append("Technical Signals")
    if inputs["recession_data"]:
        available.append("Recession Indicators")
    if inputs["political_trades"]:
        available.append("Political Intelligence")
    if inputs["historical_parallels"]:
        available.append("Historical Parallels")
    if inputs["opportunity_scores"]:
        available.append("Opportunity Scores")
    if inputs.get("quantlib_metrics"):
        available.append("QuantLib Risk Metrics")

    print(f"Available data sources: {', '.join(available) if available else 'Minimal, run more pipeline phases first'}")

    print("Building intelligence prompt...")
    prompt = build_prompt(inputs)

    print(f"Sending to {OPENAI_MODEL}...")
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are ThinkFree's AI financial analyst. You translate complex financial events "
                    "into plain English for everyday people. You always write at a level that someone "
                    "with no financial background can understand. You never use jargon without immediately "
                    "explaining it. You are informative, objective, and always honest about uncertainty."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"

    try:
        report = json.loads(raw)
    except json.JSONDecodeError:
        report = {"raw_response": raw, "parse_error": "Could not parse JSON response"}

    # Stamp metadata
    report["generated_at"] = datetime.utcnow().isoformat() + "Z"
    report["data_sources_used"] = available
    report["user_profile"] = inputs["user_profile"]

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nIntelligence report generated: {OUTPUT_PATH}")
    if "headline" in report:
        print(f"\nHeadline: {report['headline']}")
    if "bottom_line" in report:
        print(f"Bottom line: {report['bottom_line']}")

    return report


if __name__ == "__main__":
    run_chef_gpt()
