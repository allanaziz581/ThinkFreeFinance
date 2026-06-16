#!/usr/bin/env python3
"""
ThinkFree Finance — Pipeline Controller (Phase 12)

Runs the full intelligence pipeline from data collection through to the
Chef GPT final report. Each phase is run in sequence. Failed phases are
logged but do not block downstream phases that can run with partial data.

Usage:
  python controller.py                    # Run the full pipeline
  python controller.py --phase 6         # Run only Phase 6
  python controller.py --from-phase 4    # Resume from Phase 4
  python controller.py --chef-only       # Only run Chef GPT with existing data
  python controller.py --list            # List all phases
  python controller.py --audit           # Run pipeline verification audit only
  python controller.py --skip-audit      # Skip security/data quality checkpoints

Setup:
  1. Copy .env.example to .env and fill in your API keys
  2. pip install -r requirements.txt
  3. python controller.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).parent
STATE_FILE = BASE_DIR / "pipeline_state.json"


# ------------------------------------------------------------------
# Pipeline definition
# ------------------------------------------------------------------

PIPELINE = [
    {
        "id": 1,
        "name": "User Personalization",
        "description": "Captures your investment profile (run once; skip if profile exists)",
        "script": BASE_DIR / "# phase1_user_personalization.py",
        "output_check": BASE_DIR / "user_profile.json",
        "skip_if_output_exists": True,
        "required": False,
        "audit_checkpoint": None,
    },
    {
        "id": 2,
        "name": "News Scraping",
        "description": "Collects financial news, Finnhub data, and alternative market data",
        "script": BASE_DIR / "Profile" / "# phase2_data_scraping.py",
        "output_check": BASE_DIR / "news_output",
        "skip_if_output_exists": False,
        "required": True,
        "audit_checkpoint": "data",  # Run DataQualityAgent after this phase
    },
    {
        "id": 3,
        "name": "Data Extraction & Enrichment",
        "description": "Extracts financial figures, sentiment scores, and named entities from articles",
        "script": BASE_DIR / "phase3_extraction.py",
        "output_check": BASE_DIR / "news_output" / "enriched_news_sentiment.json",
        "skip_if_output_exists": False,
        "required": True,
        "audit_checkpoint": "data",
    },
    {
        "id": 4,
        "name": "Article Clustering",
        "description": "Groups similar news articles to reduce information overload; scores by impact",
        "script": BASE_DIR / "phase4_clustering.py",
        "output_check": BASE_DIR / "news_output" / "clustered_summaries.json",
        "skip_if_output_exists": False,
        "required": True,
        "audit_checkpoint": None,
    },
    {
        "id": 5,
        "name": "GPT Summarization",
        "description": "Summarizes clustered articles using GPT — preserves all financial data",
        "script": BASE_DIR / "Profile" / "GPT_article_clustering_summary.py",
        "output_check": BASE_DIR / "news_output" / "sector_summaries.json",
        "skip_if_output_exists": False,
        "required": True,
        "audit_checkpoint": None,
    },
    {
        "id": 6,
        "name": "Economic Reasoning Engine",
        "description": "Explains WHY market events matter using economic textbook knowledge",
        "script": BASE_DIR / "GPT_Economy" / "Reasoning_Report.py",
        "output_check": BASE_DIR / "news_output" / "economic_reasoning_summary.json",
        "skip_if_output_exists": False,
        "required": True,
        "audit_checkpoint": None,
    },
    {
        "id": "6.5",
        "name": "Political Intelligence",
        "description": "Analyzes congressional trades, government contracts, and lobbying activity",
        "script": BASE_DIR / "GPT_Economy" / "Intelligence_layer (IN PROGRESS)" / "economic_engine_insider.py",
        "output_check": BASE_DIR / "GPT_Economy" / "Intelligence_layer (IN PROGRESS)" / "final_reasoning_report.json",
        "skip_if_output_exists": False,
        "required": False,
        "audit_checkpoint": None,
    },
    {
        "id": 7,
        "name": "Historical Correlation Engine",
        "description": "Finds historical market analogues — what happened last time this occurred?",
        "script": BASE_DIR / "historical_correlation.py",
        "output_check": BASE_DIR / "historical_parallels.json",
        "skip_if_output_exists": False,
        "required": False,
        "audit_checkpoint": None,
    },
    {
        "id": 8,
        "name": "Technical Analysis",
        "description": "Computes RSI, MACD, and trend signals for relevant tickers",
        "script": BASE_DIR / "Module_2_Technical_Analysis" / "ta_analysis.py",
        "output_check": BASE_DIR / "Module_2_Technical_Analysis" / "ta_analysis_detailed.csv",
        "skip_if_output_exists": False,
        "required": False,
        "audit_checkpoint": None,
    },
    {
        "id": "8.5",
        "name": "Signal Generation",
        "description": "Generates BUY / SELL / HOLD signals from technical indicators",
        "script": BASE_DIR / "Module_2_Technical_Analysis" / "phase_3_signal.py",
        "output_check": BASE_DIR / "Module_2_Technical_Analysis" / "signal_output_phase3.json",
        "skip_if_output_exists": False,
        "required": False,
        "audit_checkpoint": None,
    },
    {
        "id": "8.7",
        "name": "QuantLib Risk Metrics",
        "description": "Black-Scholes probability of profit, VaR (95%), and Kelly position sizing per ticker",
        "script": BASE_DIR / "quantlib_metrics.py",
        "output_check": BASE_DIR / "quantlib_metrics.json",
        "skip_if_output_exists": False,
        "required": False,
        "audit_checkpoint": None,
    },
    {
        "id": "8.9",
        "name": "Opportunity Scoring",
        "description": "Ranks sectors and tickers 0–10 based on all available signals",
        "script": BASE_DIR / "opportunity_score.py",
        "output_check": BASE_DIR / "opportunity_scores.json",
        "skip_if_output_exists": False,
        "required": False,
        "audit_checkpoint": None,
    },
    {
        "id": 9,
        "name": "Backtesting Engine",
        "description": "Validates trading signals against historical price data",
        "script": BASE_DIR / "Module_2_Technical_Analysis" / "phase_4_backtrader.py",
        "output_check": BASE_DIR / "Module_2_Technical_Analysis" / "results_run" / "summary_metrics.json",
        "skip_if_output_exists": False,
        "required": False,
        "audit_checkpoint": None,
    },
    {
        "id": 13,
        "name": "Recession Signals",
        "description": "Computes recession risk score (0–10) from yield curve, VIX, and macro data",
        "script": BASE_DIR / "recession_signals.py",
        "output_check": BASE_DIR / "recession_signals_output.json",
        "skip_if_output_exists": False,
        "required": False,
        "audit_checkpoint": None,
    },
    {
        "id": 10,
        "name": "Portfolio Tracker",
        "description": "Simulated paper trading portfolio — tracks positions, P&L, and exposure based on signals",
        "script": BASE_DIR / "portfolio_tracker.py",
        "output_check": BASE_DIR / "portfolio_snapshot.json",
        "skip_if_output_exists": False,
        "required": False,
        "audit_checkpoint": None,
    },
    {
        "id": 11,
        "name": "Chef GPT — Intelligence Synthesis",
        "description": "Synthesizes all data into your personalized plain-English intelligence briefing",
        "script": BASE_DIR / "chef_gpt.py",
        "output_check": BASE_DIR / "intelligence_report.json",
        "skip_if_output_exists": False,
        "required": True,
        "audit_checkpoint": None,
    },
]


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def output_exists(step: dict) -> bool:
    check = step.get("output_check")
    if check is None:
        return False
    return Path(check).exists()


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"completed": [], "failed": [], "last_run": None}


def save_state(state: dict) -> None:
    state["last_run"] = datetime.utcnow().isoformat() + "Z"
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def run_phase(step: dict, state: dict) -> bool:
    phase_id = str(step["id"])
    script = Path(step["script"])

    print()
    print("=" * 65)
    print(f"  Phase {step['id']} — {step['name']}")
    print(f"  {step['description']}")
    print("=" * 65)

    if not script.exists():
        log(f"[SKIP] Script not found: {script.name}")
        return True  # Non-blocking skip

    if step.get("skip_if_output_exists") and output_exists(step):
        log(f"[SKIP] Output already exists. Skipping Phase {step['id']}.")
        return True

    log(f"Starting: {script.name}")
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(BASE_DIR),
        capture_output=False,
    )

    success = result.returncode == 0
    if success:
        log(f"✅ Phase {step['id']} completed successfully.")
        if phase_id not in state["completed"]:
            state["completed"].append(phase_id)
        if phase_id in state["failed"]:
            state["failed"].remove(phase_id)
    else:
        log(f"❌ Phase {step['id']} failed (exit code {result.returncode}).")
        if phase_id not in state["failed"]:
            state["failed"].append(phase_id)

    save_state(state)
    return success


def run_audit_checkpoint(agent: str) -> bool:
    """Run a verification agent checkpoint. Returns True if PASS or agent unavailable."""
    agent_script = BASE_DIR / "agents" / "verification_runner.py"
    if not agent_script.exists():
        return True  # Agents not yet installed — non-blocking

    log(f"Running {agent} verification checkpoint...")
    result = subprocess.run(
        [sys.executable, str(agent_script), "--phase", agent, "--quiet"],
        cwd=str(BASE_DIR),
        capture_output=False,
    )
    if result.returncode != 0:
        log(f"⚠️  {agent} checkpoint flagged issues. Check pipeline_audit.json for details.")
        return False
    log(f"✅ {agent} checkpoint passed.")
    return True


def check_env() -> bool:
    """Warn if critical API keys are missing."""
    from dotenv import load_dotenv
    load_dotenv()

    warnings = []
    if not os.getenv("OPENAI_API_KEY"):
        warnings.append("OPENAI_API_KEY — required for GPT summarization and Chef GPT")
    if not os.getenv("FINNHUB_API_KEY"):
        warnings.append("FINNHUB_API_KEY — required for financial data scraping")
    if not os.getenv("QUIVERQUANT_API_KEY"):
        warnings.append("QUIVERQUANT_API_KEY — required for political intelligence layer")

    if warnings:
        print("\n⚠️  MISSING API KEYS — Some phases will be skipped or fail:")
        for w in warnings:
            print(f"   • {w}")
        print("   Add these to your .env file. See .env.example for guidance.\n")
        return False
    return True


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ThinkFree Finance — Full Pipeline Controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python controller.py                   Run the full pipeline
  python controller.py --chef-only       Generate report from existing data
  python controller.py --phase 6         Run only the Economic Reasoning engine
  python controller.py --from-phase 13   Start from Recession Signals onward
  python controller.py --list            Show all pipeline phases
        """,
    )
    p.add_argument("--phase", type=str, help="Run a single specific phase by ID")
    p.add_argument("--from-phase", type=str, dest="from_phase", help="Run from this phase ID onward")
    p.add_argument("--chef-only", action="store_true", help="Run only Chef GPT using existing data")
    p.add_argument("--skip-scraping", action="store_true", help="Skip Phase 2 (use cached news data)")
    p.add_argument("--list", action="store_true", help="List all pipeline phases and exit")
    p.add_argument("--audit", action="store_true", help="Run pipeline verification audit only and exit")
    p.add_argument("--skip-audit", action="store_true", help="Skip security/data quality checkpoints")
    return p.parse_args()


def list_phases() -> None:
    print("\nThinkFree Pipeline Phases:")
    print("-" * 65)
    for step in PIPELINE:
        exists = "✅" if output_exists(step) else "  "
        print(f"  {exists} Phase {step['id']:>4} — {step['name']}")
        print(f"              {step['description']}")
    print()


def main() -> None:
    args = parse_args()

    if args.list:
        list_phases()
        return

    print("\n" + "=" * 65)
    print("  ThinkFree Finance — AI Intelligence Platform")
    print("  Pipeline Controller")
    print("=" * 65)

    check_env()
    state = load_state()

    # --audit: run verification suite and exit
    if args.audit:
        try:
            from agents.verification_runner import run_all_agents
            result = run_all_agents(verbose=True)
            sys.exit(0 if result.get("overall_verdict") == "PASS" else 1)
        except ImportError:
            log("Verification agents not available. Run from project root.")
            sys.exit(1)

    # --chef-only: run only the final synthesis
    if args.chef_only:
        chef_step = next(s for s in PIPELINE if s["id"] == 11)
        run_phase(chef_step, state)
        print("\n✅ Chef GPT complete. Launch dashboard: streamlit run dashboard/app.py")
        return

    # --phase: run a single phase
    if args.phase:
        target_id = args.phase
        step = next((s for s in PIPELINE if str(s["id"]) == target_id), None)
        if not step:
            print(f"Phase '{target_id}' not found. Use --list to see available phases.")
            sys.exit(1)
        run_phase(step, state)
        return

    # Determine which phases to run
    steps_to_run = PIPELINE
    if args.from_phase:
        ids = [str(s["id"]) for s in PIPELINE]
        if args.from_phase not in ids:
            print(f"Phase '{args.from_phase}' not found.")
            sys.exit(1)
        start_idx = ids.index(args.from_phase)
        steps_to_run = PIPELINE[start_idx:]

    # Run security audit before pipeline begins (non-blocking)
    if not args.skip_audit:
        run_audit_checkpoint("security")

    log("Starting full pipeline run...")
    failed_required = False

    for step in steps_to_run:
        if args.skip_scraping and step["id"] == 2:
            log("Skipping Phase 2 (--skip-scraping flag set).")
            continue

        success = run_phase(step, state)

        # Run audit checkpoint after this phase if configured
        checkpoint = step.get("audit_checkpoint")
        if success and checkpoint and not args.skip_audit:
            run_audit_checkpoint(checkpoint)

        if not success and step.get("required", False):
            log(f"\nRequired phase {step['id']} failed. Pipeline halted.")
            log("Fix the issue above and re-run, or use --from-phase to resume.")
            failed_required = True
            break

    print()
    print("=" * 65)
    if failed_required:
        print("  Pipeline completed with errors. Check output above.")
    else:
        print("  Pipeline complete.")
        print()
        print("  Your intelligence report is ready:")
        print(f"  {BASE_DIR / 'intelligence_report.json'}")
        print()
        print("  Launch the dashboard:")
        print("  streamlit run dashboard/app.py")
    print("=" * 65)


if __name__ == "__main__":
    main()
