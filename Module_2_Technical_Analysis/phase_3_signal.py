#!/usr/bin/env python3
"""
ThinkFree Finance — Phase 3b: Signal Generation
Reads ta_analysis_detailed.csv, applies multi-indicator signal rules,
and outputs signal_output_phase3.json.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

BASE_DIR    = Path(__file__).parent.parent
TA_CSV_PATH = Path(__file__).parent / "ta_analysis_detailed.csv"
OUTPUT_PATH = Path(__file__).parent / "signal_output_phase3.json"

LOOKBACK_DAYS = 5


def analyze_row(row: pd.Series) -> dict:
    signal     = "HOLD"
    confidence = 0
    support: list[str]       = []
    contradiction: list[str] = []

    rsi = row.get("rsi")
    if rsi is not None and not pd.isna(rsi):
        if rsi < 30:
            confidence += 1
            support.append(f"RSI (oversold at {rsi:.2f})")
        elif rsi > 70:
            confidence -= 1
            support.append(f"RSI (overbought at {rsi:.2f})")
        else:
            contradiction.append("RSI in neutral zone")

    macd      = row.get("macd")
    # Accept either 'macd_signal_line' (raw) or 'macd_signal' (binary flag)
    macd_sig  = row.get("macd_signal_line")
    if macd is not None and macd_sig is not None and not pd.isna(macd) and not pd.isna(macd_sig):
        if macd > macd_sig:
            confidence += 1
            support.append("MACD bullish crossover")
        elif macd < macd_sig:
            confidence -= 1
            support.append("MACD bearish crossover")
        else:
            contradiction.append("MACD flat")

    sma50  = row.get("sma_50")
    sma200 = row.get("sma_200")
    if sma50 is not None and sma200 is not None and not pd.isna(sma50) and not pd.isna(sma200):
        if sma50 > sma200:
            confidence += 1
            support.append("SMA 50 > SMA 200 (golden cross)")
        elif sma50 < sma200:
            confidence -= 1
            support.append("SMA 50 < SMA 200 (death cross)")

    obv = row.get("obv")
    if obv is not None and not pd.isna(obv):
        if obv > 0:
            confidence += 1
            support.append("OBV increasing")
        else:
            contradiction.append("OBV flat or decreasing")

    adx = row.get("adx")
    if adx is not None and not pd.isna(adx):
        if adx < 20:
            contradiction.append("ADX below 20 (weak trend)")
        else:
            support.append("ADX shows trend strength")

    cci = row.get("cci")
    if cci is not None and not pd.isna(cci):
        if abs(cci) < 100:
            contradiction.append("CCI in neutral zone")
        else:
            support.append("CCI showing trend")

    if confidence >= 2:
        signal = "BUY"
    elif confidence <= -2:
        signal = "SELL"

    reason_parts: list[str] = []
    if signal == "BUY":
        reason_parts.append("Indicators suggest a bullish setup")
    elif signal == "SELL":
        reason_parts.append("Bearish signals dominate across indicators")
    else:
        reason_parts.append("Indicators are mixed or weak")

    if support:
        reason_parts.append("Supporting: " + ", ".join(support))
    if contradiction:
        reason_parts.append("Conflicting: " + ", ".join(contradiction))

    return {
        "date":                   str(row.get("date", "")),
        "ticker":                 str(row.get("ticker", "")),
        "final_signal":           signal,
        "confidence_score":       confidence,
        "supporting_indicators":  support,
        "contradicting_indicators": contradiction,
        "reasoning":              ". ".join(reason_parts),
    }


def main():
    if not TA_CSV_PATH.exists():
        print(f"TA analysis file not found at {TA_CSV_PATH}. Run ta_analysis.py first.")
        return

    df = pd.read_csv(TA_CSV_PATH)

    # Normalize date column
    if "date" not in df.columns and len(df.columns) > 0:
        df = df.rename(columns={df.columns[0]: "date"})

    df = df.sort_values(by=["ticker", "date"])
    latest_df = df.groupby("ticker").tail(1)

    signal_data = [analyze_row(row) for _, row in latest_df.iterrows()]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(signal_data, f, indent=2)

    buys  = sum(1 for s in signal_data if s["final_signal"] == "BUY")
    sells = sum(1 for s in signal_data if s["final_signal"] == "SELL")
    holds = sum(1 for s in signal_data if s["final_signal"] == "HOLD")
    print(f"Signal output written to {OUTPUT_PATH}")
    print(f"  BUY: {buys}  SELL: {sells}  HOLD: {holds}  Total: {len(signal_data)}")


if __name__ == "__main__":
    main()
