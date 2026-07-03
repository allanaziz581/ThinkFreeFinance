#!/usr/bin/env python3
"""
ThinkFree Finance, Phase 8: Opportunity Scoring Engine

Combines signals from all prior phases into ranked sector and ticker opportunities.
OUTLOOK (market view) and SUITABILITY (fit to the user) are reported separately.

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


# Canonical GICS sectors and common aliases. Economic-reasoning output and sector
# summaries use inconsistent names ("Tech", "Infotech", "Telecom"); exact string matching
# silently missed them, so a bullish "Tech" call never lifted "Information Technology".
GICS_ALIASES = {
    "information technology": "Information Technology",
    "tech": "Information Technology",
    "technology": "Information Technology",
    "infotech": "Information Technology",
    "it": "Information Technology",
    "health care": "Health Care",
    "healthcare": "Health Care",
    "health": "Health Care",
    "financials": "Financials",
    "financial": "Financials",
    "finance": "Financials",
    "banks": "Financials",
    "energy": "Energy",
    "consumer discretionary": "Consumer Discretionary",
    "discretionary": "Consumer Discretionary",
    "consumer staples": "Consumer Staples",
    "staples": "Consumer Staples",
    "industrials": "Industrials",
    "industrial": "Industrials",
    "materials": "Materials",
    "real estate": "Real Estate",
    "reit": "Real Estate",
    "reits": "Real Estate",
    "utilities": "Utilities",
    "communication services": "Communication Services",
    "communications": "Communication Services",
    "communication": "Communication Services",
    "telecom": "Communication Services",
    "telecommunications": "Communication Services",
}


def canonical_sector(name: str) -> str:
    """Map a free-form sector name to its canonical GICS label. Unknown names are returned
    title-cased so matching is at least case- and whitespace-insensitive."""
    if not name:
        return ""
    key = " ".join(str(name).strip().lower().split())
    return GICS_ALIASES.get(key, str(name).strip().title())


def score_sector_outlook(sector: str, bullish_sectors: list, bearish_sectors: list) -> float:
    """0.0 - 1.0 market outlook from economic reasoning, matched on canonical GICS names."""
    csector = canonical_sector(sector)
    bulls = {canonical_sector(s) for s in bullish_sectors}
    bears = {canonical_sector(s) for s in bearish_sectors}
    if csector in bulls:
        return 1.0
    if csector in bears:
        return 0.0
    return 0.5


def score_technical_signal(ticker: str, signals: list[dict]) -> float:
    """0.0 to 1.0 based on BUY/SELL/HOLD signal and confidence."""
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

    csector = canonical_sector(sector)
    multiplier = 1.0

    if risk == "high" and csector in HIGH_GROWTH_SECTORS:
        multiplier = 1.2
    elif risk == "low" and csector in DEFENSIVE_SECTORS:
        multiplier = 1.2
    elif risk == "moderate":
        multiplier = 1.0

    if goal == "income" and csector in INCOME_SECTORS:
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
        # OUTLOOK: the market view, economic outlook tempered by recession risk. This is a
        # 0-1 conviction, kept as-is (no x10 costume that dressed a coarse heuristic up as a
        # precise "7.3/10").
        outlook_conviction = score_sector_outlook(sector, bullish_sectors, bearish_sectors) * rec_discount
        csector = canonical_sector(sector)
        bulls = {canonical_sector(s) for s in bullish_sectors}
        bears = {canonical_sector(s) for s in bearish_sectors}
        if csector in bulls:
            outlook_label = "Bullish"
        elif csector in bears:
            outlook_label = "Bearish"
        else:
            outlook_label = "Neutral"

        # SUITABILITY: how well the sector fits THIS user. Reported SEPARATELY, never
        # multiplied into the outlook, so a great-outlook sector that does not fit the user
        # still shows a strong outlook (and vice versa).
        pm = profile_multiplier(sector, profile)
        if pm > 1.1:
            suitability_label = "Good fit for your profile"
        elif pm < 1.0:
            suitability_label = "Less suitable for your profile"
        else:
            suitability_label = "Neutral fit"

        rationale_parts = []
        if outlook_label == "Bullish":
            rationale_parts.append("Economic analysis shows positive momentum in this sector.")
        elif outlook_label == "Bearish":
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
            "sector": canonical_sector(sector),
            "outlook": {"label": outlook_label, "conviction": round(outlook_conviction, 2)},
            "suitability": {"label": suitability_label, "factor": round(pm, 2)},
            "components": {
                "economic_outlook_0_1": round(score_sector_outlook(sector, bullish_sectors, bearish_sectors), 2),
                "recession_discount": round(rec_discount, 2),
                "profile_factor": round(pm, 2),
            },
            "rationale": " ".join(rationale_parts),
        })

    # Rank on market OUTLOOK conviction (not a blend with personal suitability).
    sector_scores.sort(key=lambda x: x["outlook"]["conviction"], reverse=True)
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

        # Signal conviction: the technical strength tempered by recession risk, 0-1.
        # No x10 costume, and the DIRECTION is the actual technical signal, not a label
        # re-derived from the score (which used to flip a real BUY to "Sell Signal"
        # whenever the discounted score fell below a threshold).
        signal_conviction = score_technical_signal(ticker, signals) * rec_discount_val

        # Suitability adjustment is reported separately, not folded into the signal.
        if profile.get("risk_tolerance") == "low" and final_sig == "BUY":
            suitability_note = "Aggressive buy: weigh against your lower risk tolerance."
        elif profile.get("risk_tolerance") == "high" and final_sig == "SELL":
            suitability_note = "Exit signal: may be conservative for your higher risk tolerance."
        else:
            suitability_note = "No profile-specific caveat."

        ticker_scores.append({
            "ticker": ticker,
            "signal": final_sig,                 # the actual signal, never relabelled
            "signal_conviction": round(signal_conviction, 2),
            "confidence": confidence,
            "suitability_note": suitability_note,
            "plain_english_signal": _signal_to_plain_english(ticker, final_sig, confidence, reasoning),
        })

    # Rank by how decisive the signal is (conviction), keeping the actual BUY/SELL/HOLD.
    ticker_scores.sort(key=lambda x: x["signal_conviction"], reverse=True)
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
    print("=== ThinkFree, Phase 8: Opportunity Scoring ===")

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
            "OUTLOOK and SUITABILITY are reported separately, never multiplied into one "
            "number. Outlook is the economic sector view tempered by recession risk (a 0-1 "
            "conviction). Suitability is how well the sector or signal fits your profile. "
            "Ticker direction is the actual technical signal, not a label derived from a "
            "score. This is not investment advice."
        ),
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    top_sector = sector_scores[0]["sector"] if sector_scores else "N/A"
    top_conv   = sector_scores[0]["outlook"]["conviction"] if sector_scores else 0

    print(f"\nOpportunity scoring complete:")
    print(f"  Top sector by outlook: {top_sector} (conviction {top_conv})")
    print(f"  Sectors scored: {len(sector_scores)}")
    print(f"  Tickers scored: {len(ticker_scores)}")
    print(f"\nSaved to: {OUTPUT_PATH}")

    return output


if __name__ == "__main__":
    run_opportunity_scoring()
