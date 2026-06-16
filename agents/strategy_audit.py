#!/usr/bin/env python3
"""
ThinkFree Finance — StrategyAuditAgent

Adversarially reviews Phase 9 (backtesting) output for:
  1. Negative Sharpe ratio (strategy is destroying value)
  2. Excessive drawdown (> 20%)
  3. Insufficient trade count (possible lookahead bias or bad signals)
  4. Unrealistic CAGR (> 100%/yr is suspicious)
  5. Near-zero time in market (signals not firing)
  6. Missing backtest output (pipeline hasn't run)

Inspired by PentestGPT's adversarial reasoning approach:
separate "reasoning" pass to identify issues + "generation" pass to explain them plainly.

Returns: pass/fail verdict with findings and plain-English explanation.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.parent

BACKTEST_METRICS_PATH = BASE_DIR / "Module_2_Technical_Analysis" / "results_run" / "summary_metrics.json"
TRADE_LOG_PATH        = BASE_DIR / "Module_2_Technical_Analysis" / "results_run" / "trade_log.csv"


class StrategyFinding:
    def __init__(self, severity: str, check: str, message: str, value: Any = None, plain_english: str = ""):
        self.severity = severity      # BLOCKER, WARN, INFO
        self.check = check
        self.message = message
        self.value = value
        self.plain_english = plain_english

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "check": self.check,
            "message": self.message,
            "value": self.value,
            "plain_english": self.plain_english,
        }


def load_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def count_trades(trade_log_path: Path) -> int:
    try:
        with open(trade_log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return max(0, len(lines) - 1)  # subtract header
    except FileNotFoundError:
        return -1  # not generated


def run_strategy_audit(verbose: bool = True) -> dict:
    if verbose:
        print("=== ThinkFree — StrategyAuditAgent ===")

    findings: list[StrategyFinding] = []

    # Load backtest metrics
    metrics = load_json(BACKTEST_METRICS_PATH)
    if not metrics:
        findings.append(StrategyFinding(
            "INFO", "missing_backtest",
            "Backtest output not found. Phase 9 has not been run yet.",
            None,
            "The strategy hasn't been tested yet. Run python Module_2_Technical_Analysis/phase_4_backtrader.py first."
        ))
        return _build_result(findings, verbose)

    sharpe         = float(metrics.get("Sharpe", 0) or 0)
    sortino        = float(metrics.get("Sortino", 0) or 0) if metrics.get("Sortino") not in (None, float("inf")) else None
    max_drawdown   = float(metrics.get("Max Drawdown %", 0) or 0)
    cagr           = float(metrics.get("CAGR %", 0) or 0)
    time_in_market = float(metrics.get("Time in Market %", 0) or 0)
    trade_count    = count_trades(TRADE_LOG_PATH)

    if verbose:
        print(f"  Sharpe: {sharpe}  Drawdown: {max_drawdown}%  CAGR: {cagr}%  Trades: {trade_count}  Time in Market: {time_in_market}%")

    # ── Check 1: Sharpe ratio ───────────────────────────────────────────
    if sharpe < 0:
        findings.append(StrategyFinding(
            "BLOCKER", "negative_sharpe",
            f"Sharpe ratio is {sharpe:.2f} — strategy is destroying value relative to risk.",
            sharpe,
            "A negative Sharpe means the strategy is losing more money than it would if you just held cash. "
            "The signal logic needs to be fixed before this can be trusted."
        ))
    elif sharpe < 0.5:
        findings.append(StrategyFinding(
            "WARN", "low_sharpe",
            f"Sharpe ratio is {sharpe:.2f} — below the 0.5 minimum threshold for a viable strategy.",
            sharpe,
            "The strategy is barely generating returns for the risk taken. Aim for Sharpe > 1.0."
        ))
    else:
        findings.append(StrategyFinding(
            "INFO", "sharpe_ok",
            f"Sharpe ratio is acceptable: {sharpe:.2f}",
            sharpe, ""
        ))

    # ── Check 2: Max drawdown ───────────────────────────────────────────
    if max_drawdown > 35:
        findings.append(StrategyFinding(
            "BLOCKER", "excessive_drawdown",
            f"Max drawdown is {max_drawdown:.1f}% — exceeds 35% hard limit.",
            max_drawdown,
            "The strategy lost more than a third of its value at its worst point. "
            "Most retail investors would panic-sell at this level. ATR-based stops must be added."
        ))
    elif max_drawdown > 20:
        findings.append(StrategyFinding(
            "WARN", "high_drawdown",
            f"Max drawdown is {max_drawdown:.1f}% — exceeds 20% recommended limit.",
            max_drawdown,
            "Drawdown above 20% is uncomfortable for most investors and indicates the strategy "
            "holds through large losses. Consider tighter trailing stops."
        ))

    # ── Check 3: CAGR ──────────────────────────────────────────────────
    if cagr < 0:
        findings.append(StrategyFinding(
            "BLOCKER", "negative_cagr",
            f"CAGR is {cagr:.1f}% — the strategy is losing money year over year.",
            cagr,
            "The backtest is generating negative annual returns. This means the signals, "
            "as currently configured, are predicting price movements in the wrong direction "
            "or the costs are eating all profits."
        ))
    elif cagr > 100:
        findings.append(StrategyFinding(
            "WARN", "suspicious_cagr",
            f"CAGR is {cagr:.1f}% — suspiciously high. Check for lookahead bias.",
            cagr,
            "A CAGR above 100% per year almost never reflects real-world results. "
            "This may indicate the strategy is using future price data it shouldn't have access to."
        ))

    # ── Check 4: Trade count ────────────────────────────────────────────
    if trade_count == 0:
        findings.append(StrategyFinding(
            "BLOCKER", "no_trades",
            "Zero trades were executed. Signals are not firing.",
            trade_count,
            "The strategy never entered a position. This usually means the signal requirements "
            "are too strict — all three indicators (RSI, MACD, SMA trend) never agreed at the same time. "
            "Lower min_align from 3 to 2, or check that signal columns are mapped correctly."
        ))
    elif trade_count < 5:
        findings.append(StrategyFinding(
            "WARN", "too_few_trades",
            f"Only {trade_count} trades executed. Insufficient sample size for reliable statistics.",
            trade_count,
            "With fewer than 5 trades, any performance metric (Sharpe, drawdown, CAGR) "
            "is statistically meaningless. The strategy needs to trade more frequently."
        ))
    elif trade_count > 500:
        findings.append(StrategyFinding(
            "WARN", "overtrading",
            f"{trade_count} trades executed — possible overtrading. Check transaction costs.",
            trade_count,
            "Very high trade counts can indicate the strategy is chasing noise. "
            "High commission and slippage costs will erode returns significantly."
        ))

    # ── Check 5: Time in market ─────────────────────────────────────────
    if time_in_market < 5 and trade_count != 0:
        findings.append(StrategyFinding(
            "WARN", "low_market_exposure",
            f"Only {time_in_market:.1f}% of time in market. Signals are too conservative.",
            time_in_market,
            "The strategy is sitting in cash almost all the time. "
            "This could mean signal alignment requirements are too strict or the CSV data is sparse."
        ))

    # ── Check 6: Lookahead bias check (heuristic) ──────────────────────
    if cagr > 50 and trade_count < 20:
        findings.append(StrategyFinding(
            "WARN", "possible_lookahead",
            f"High CAGR ({cagr:.1f}%) with very few trades ({trade_count}) — possible lookahead bias.",
            None,
            "When a strategy makes outsized returns on very few trades, it may be "
            "accidentally using future price information it shouldn't have access to. "
            "Verify that signal dates align with trade entry dates (entry should be NEXT bar, not same bar)."
        ))

    return _build_result(findings, verbose)


def _build_result(findings: list[StrategyFinding], verbose: bool) -> dict:
    blockers = [f for f in findings if f.severity == "BLOCKER"]
    warnings  = [f for f in findings if f.severity == "WARN"]
    infos     = [f for f in findings if f.severity == "INFO"]

    verdict = "PASS" if not blockers else "FAIL"

    # Plain-English summary for dashboard
    if blockers:
        summary = (
            f"Strategy audit found {len(blockers)} critical issue(s) that must be fixed: "
            + "; ".join(f.message for f in blockers[:2])
        )
    elif warnings:
        summary = f"Strategy passed basic checks but has {len(warnings)} warning(s) to review."
    else:
        summary = "Strategy audit passed. No critical issues detected."

    result = {
        "audit_timestamp": datetime.utcnow().isoformat() + "Z",
        "verdict": verdict,
        "summary": {
            "blockers": len(blockers),
            "warnings": len(warnings),
            "info": len(infos),
        },
        "plain_english_summary": summary,
        "findings": [f.to_dict() for f in findings],
        "recommendations": _build_recommendations(findings),
    }

    if verbose:
        print(f"\n{'='*50}")
        verdict_label = "✅ PASS" if verdict == "PASS" else "❌ FAIL"
        print(f"Strategy Audit: {verdict_label}")
        for f in (blockers + warnings)[:5]:
            print(f"  [{f.severity}] {f.message}")
        if result["recommendations"]:
            print("\nRecommendations:")
            for r in result["recommendations"][:3]:
                print(f"  → {r}")

    return result


def _build_recommendations(findings: list[StrategyFinding]) -> list[str]:
    recs = []
    checks = {f.check for f in findings}

    if "no_trades" in checks or "too_few_trades" in checks:
        recs.append("Reduce min_align from 3 to 2 in backtest config — this allows trades when 2 of 3 indicators agree.")
        recs.append("Verify COLUMN_ALIASES in phase_4_backtrader.py maps 'macd_signal' to 'macd_signal_flag'.")

    if "negative_cagr" in checks or "negative_sharpe" in checks:
        recs.append("Switch to LONG-ONLY strategy. Short selling requires deep expertise and access to margin accounts.")
        recs.append("Add ATR-based trailing stops: exit when price falls 2x ATR below peak since entry.")
        recs.append("Add trend filter: only enter long when Close > SMA200 (bull market only).")

    if "excessive_drawdown" in checks or "high_drawdown" in checks:
        recs.append("Implement per-trade risk sizing: risk only 1-2% of portfolio equity per trade based on ATR stop distance.")
        recs.append("Reduce max drawdown stop from 35% to 15% and liquidate all positions when triggered.")

    if "possible_lookahead" in checks:
        recs.append("Verify entry fills on NEXT bar after signal (bar index t+1, not t). Use cerebro.resampledata if needed.")

    if not recs:
        recs.append("Continue monitoring strategy performance as market conditions change.")

    return recs


if __name__ == "__main__":
    run_strategy_audit(verbose=True)
