#!/usr/bin/env python3
"""
ThinkFree Finance — Phase 8: Opportunity Scoring Engine

Combines signals from all prior phases into a single ranked list of
sector and ticker opportunities, scored 0–10.

Scoring components:
  - Sector economic outlook (from Phase 6 economic reasoning)
  - Technical signal alignment (from Phase 8.5 signals)
  - Historical correlation outcome (from Phase 7)
  - Recession risk discount (from Phase 13)
  - User profile match (from Phase 1)

Output: opportunity_scores.json
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
OUTPUT_PATH = BASE_DIR / "opportunity_scores.json"


def load_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def score_sector_outlook(sector: str, bullish_sectors: list, bearish_sectors: list) -> float:
    """0.0 – 1.0 based on economic reasoning output."""
    if sector in bullish_sectors:
        return 1.0
    if sector in bearish_sectors:
        return 0.0
    return 0.5


def score_technical_signal(ticker: str, signals: list[dict]) -> float:
    """0.0 – 1.0 based on BUY/SELL/HOLD signal and confidence."""
    for sig in signals:
        if sig.get("ticker", "").upper() == ticker.upper():
            final = sig.get("final_signal", "HOLD")
            confidence = abs(sig.get("confidence_score", 0))
            if final == "BUY":
                return min(1.0, 0.5 + confidence * 0.1)
            if final == "SELL":
                return max(0.0, 0.5 - confidence * 0.1)
            return 0.5
    return 0.5  # No signal = neutral


def recession_discount(recession_score: float) -> float:
    """Discount opportunity score based on recession risk. Higher risk = lower multiplier."""
    if recession_score <= 2:
        return 1.0
    if recession_score <= 4:
        return 0.9
    if recession_score <= 6:
        return 0.75
    if recession_score <= 8:
        return 0.60
    return 0.45


def profile_multiplier(sector: str, profile: dict) -> float:
    """Adjust score based on user's risk profile and investment goal."""
    risk = profile.get("risk_tolerance", "moderate")
    goal = profile.get("investment_goal", "growth")

    HIGH_GROWTH_SECTORS = {"Information Technology", "Consumer Discretionary", "Communication Services"}
    DEFENSIVE_SECTORS   = {"Health Care", "Utilities", "Consumer Staples"}
    INCOME_SECTORS      = {"Real Estate", "Utilities", "Financials"}

    multiplier = 1.0

    if risk == "high" and sector in HIGH_GROWTH_SECTORS:
        multiplier = 1.2
    elif risk == "low" and sector in DEFENSIVE_SECTORS:
        multiplier = 1.2
    elif risk == "moderate":
        multiplier = 1.0

    if goal == "income" and sector in INCOME_SECTORS:
        multiplier *= 1.15

    return min(1.5, multiplier)


def build_sector_scores(
    bullish_sectors: list,
    bearish_sectors: list,
    signals: list[dict],
    recession_risk_score: float,
    profile: dict,
    sector_summaries: dict,
) -> list[dict]:
    """Build opportunity scores for each sector."""
    all_sectors = set(bullish_sectors + bearish_sectors + list(sector_summaries.keys()))
    if not all_sectors:
        all_sectors = {
            "Information Technology", "Health Care", "Financials", "Energy",
            "Consumer Discretionary", "Consumer Staples", "Industrials",
            "Materials", "Real Estate", "Utilities", "Communication Services",
        }

    sector_scores = []
    rec_discount = recession_discount(recession_risk_score)

    for sector in all_sectors:
        # Component scores
        outlook  = score_sector_outlook(sector, bullish_sectors, bearish_sectors)
        rec_adj  = outlook * rec_discount
        pm       = profile_multiplier(sector, profile)
        raw_score = rec_adj * pm

        # Final 0–10 score
        final = min(10.0, raw_score * 10)

        # Direction label
        if final >= 7.0:
            direction = "Bullish"
            direction_emoji = "📈"
        elif final >= 5.0:
            direction = "Neutral"
            direction_emoji = "➡️"
        else:
            direction = "Bearish"
            direction_emoji = "📉"

        # Plain-English rationale
        rationale_parts = []
        if sector in bullish_sectors:
            rationale_parts.append("Economic analysis shows positive momentum in this sector.")
        elif sector in bearish_sectors:
            rationale_parts.append("Economic analysis indicates headwinds for this sector.")
        else:
            rationale_parts.append("This sector shows neutral economic signals.")

        if recession_risk_score > 5:
            rationale_parts.append(
                f"Elevated recession risk ({recession_risk_score:.1f}/10) reduces conviction across all sectors."
            )

        if pm > 1.1:
            rationale_parts.append("This sector aligns well with your investment profile.")

        sector_scores.append({
            "sector": sector,
            "opportunity_score": round(final, 1),
            "direction": direction,
            "direction_emoji": direction_emoji,
            "components": {
                "economic_outlook": round(outlook * 10, 1),
                "recession_discount": round(rec_discount, 2),
                "profile_match": round(pm, 2),
            },
            "rationale": " ".join(rationale_parts),
        })

    # Sort by score descending
    sector_scores.sort(key=lambda x: x["opportunity_score"], reverse=True)
    return sector_scores


def build_ticker_scores(
    signals: list[dict],
    bullish_sectors: list,
    bearish_sectors: list,
    recession_risk_score: float,
    profile: dict,
    sector_summaries: dict,
) -> list[dict]:
    """Build opportunity scores for individual tickers with signals."""
    ticker_scores = []
    rec_discount_val = recession_discount(recession_risk_score)

    for sig in signals:
        if not isinstance(sig, dict):
            continue

        ticker   = sig.get("ticker", "")
        final_sig = sig.get("final_signal", "HOLD")
        confidence = sig.get("confidence_score", 0)
        reasoning  = sig.get("reasoning", "")

        tech_score = score_technical_signal(ticker, signals)

        # Combine with recession discount
        base = tech_score * rec_discount_val

        # Risk profile adjustment
        if profile.get("risk_tolerance") == "low" and final_sig == "BUY":
            base *= 0.85  # conservative investors get lower scores for aggressive buys
        elif profile.get("risk_tolerance") == "high" and final_sig == "SELL":
            base *= 0.85

        final = min(10.0, base * 10)

        if final >= 7.0:
            direction = "Buy Signal"
            emoji = "🟢"
        elif final >= 5.0:
            direction = "Neutral / Hold"
            emoji = "🟡"
        else:
            direction = "Sell Signal"
            emoji = "🔴"

        ticker_scores.append({
            "ticker": ticker,
            "opportunity_score": round(final, 1),
            "signal": final_sig,
            "direction": direction,
            "direction_emoji": emoji,
            "confidence": confidence,
            "plain_english_signal": _signal_to_plain_english(ticker, final_sig, confidence, reasoning),
        })

    ticker_scores.sort(key=lambda x: x["opportunity_score"], reverse=True)
    return ticker_scores[:25]  # Top 25


def _signal_to_plain_english(ticker: str, signal: str, confidence: int, reasoning: str) -> str:
    if signal == "BUY":
        return (
            f"{ticker} is showing momentum signals that suggest it may be gaining strength. "
            f"Multiple technical indicators are aligned in a positive direction (confidence: {confidence}/5). "
            "This is a signal to watch, not a guarantee."
        )
    elif signal == "SELL":
        return (
            f"{ticker} is showing warning signs that its momentum may be fading. "
            f"Technical indicators suggest caution (confidence: {confidence}/5). "
            "Consider reviewing this position if you own it."
        )
    else:
        return (
            f"{ticker} signals are mixed or inconclusive. No strong directional bet is indicated. "
            "Holding existing positions while monitoring for clearer signals is reasonable."
        )


def run_opportunity_scoring() -> dict:
    print("=== ThinkFree — Phase 8: Opportunity Scoring ===")

    # Load all inputs
    econ       = load_json(BASE_DIR / "news_output" / "economic_reasoning_summary.json", {})
    signals    = load_json(BASE_DIR / "Module_2_Technical_Analysis" / "signal_output_phase3.json", [])
    recession  = load_json(BASE_DIR / "recession_signals_output.json", {})
    profile    = load_json(BASE_DIR / "user_profile.json", {})
    sector_sum = load_json(BASE_DIR / "news_output" / "sector_summaries.json", {})

    bullish_sectors = econ.get("bullish_sectors", [])
    bearish_sectors = econ.get("bearish_sectors", [])
    recession_score = recession.get("recession_risk", {}).get("score", 3.0)

    print(f"Bullish sectors: {bullish_sectors}")
    print(f"Bearish sectors: {bearish_sectors}")
    print(f"Recession risk:  {recession_score}/10")
    print(f"Technical signals available: {len(signals)}")

    sector_scores = build_sector_scores(
        bullish_sectors, bearish_sectors, signals,
        recession_score, profile, sector_sum
    )

    ticker_scores = build_ticker_scores(
        signals, bullish_sectors, bearish_sectors,
        recession_score, profile, sector_sum
    )

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "recession_risk_used": recession_score,
        "user_profile_id": profile.get("profile_id", "unknown"),
        "sector_opportunities": sector_scores,
        "ticker_opportunities": ticker_scores,
        "methodology": (
            "Opportunity scores combine economic sector outlook, recession risk discount, "
            "technical signal alignment, and user profile compatibility. "
            "Scores are 0–10 where 10 = strongest opportunity alignment. "
            "This is not investment advice."
        ),
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    top_sector = sector_scores[0]["sector"] if sector_scores else "N/A"
    top_score  = sector_scores[0]["opportunity_score"] if sector_scores else 0

    print(f"\nOpportunity scoring complete:")
    print(f"  Top sector: {top_sector} ({top_score}/10)")
    print(f"  Sectors scored: {len(sector_scores)}")
    print(f"  Tickers scored: {len(ticker_scores)}")
    print(f"\nSaved to: {OUTPUT_PATH}")

    return output


if __name__ == "__main__":
    run_opportunity_scoring()
