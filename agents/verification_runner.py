#!/usr/bin/env python3
"""
ThinkFree Finance — VerificationRunner

Orchestrates all verification agents and produces a unified pipeline_audit.json.
Called by controller.py at defined pipeline checkpoints.

Usage:
  python agents/verification_runner.py
  python agents/verification_runner.py --phase security
  python agents/verification_runner.py --phase data
  python agents/verification_runner.py --phase all
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
AUDIT_OUTPUT = BASE_DIR / "pipeline_audit.json"

sys.path.insert(0, str(BASE_DIR))

from agents.security_audit import run_security_audit
from agents.data_quality import run_data_quality_check
from agents.strategy_audit import run_strategy_audit


def run_all_agents(verbose: bool = True) -> dict:
    """Run all verification agents and produce combined pipeline_audit.json."""

    if verbose:
        print("\n" + "="*60)
        print("  ThinkFree Finance — Pipeline Verification Suite")
        print("="*60 + "\n")

    results = {}

    # ------------------------------------------------------------------ #
    # Agent 1: SecurityAuditAgent
    # ------------------------------------------------------------------ #
    if verbose:
        print("\n[1/3] Running SecurityAuditAgent...")
    try:
        sec_result = run_security_audit(verbose=verbose)
    except Exception as e:
        sec_result = {
            "verdict": "ERROR",
            "message": f"SecurityAuditAgent crashed: {e}",
            "findings": [],
        }
    results["security"] = sec_result

    # ------------------------------------------------------------------ #
    # Agent 2: DataQualityAgent
    # ------------------------------------------------------------------ #
    if verbose:
        print("\n[2/3] Running DataQualityAgent...")
    try:
        dq_result = run_data_quality_check(verbose=verbose)
    except Exception as e:
        dq_result = {
            "verdict": "ERROR",
            "message": f"DataQualityAgent crashed: {e}",
            "findings": [],
        }
    results["data_quality"] = dq_result

    # ------------------------------------------------------------------ #
    # Agent 3: StrategyAuditAgent
    # ------------------------------------------------------------------ #
    if verbose:
        print("\n[3/3] Running StrategyAuditAgent...")
    try:
        sa_result = run_strategy_audit(verbose=verbose)
    except Exception as e:
        sa_result = {
            "verdict": "ERROR",
            "message": f"StrategyAuditAgent crashed: {e}",
            "findings": [],
        }
    results["strategy_audit"] = sa_result

    # ------------------------------------------------------------------ #
    # Combine into unified verdict
    # ------------------------------------------------------------------ #
    all_verdicts = [r.get("verdict", "UNKNOWN") for r in results.values()]
    any_fail = any(v in ("FAIL", "ERROR") for v in all_verdicts)

    overall = "FAIL" if any_fail else "PASS"

    combined = {
        "pipeline_audit_timestamp": datetime.utcnow().isoformat() + "Z",
        "overall_verdict": overall,
        "agents_run": list(results.keys()),
        "agent_verdicts": {k: v.get("verdict", "UNKNOWN") for k, v in results.items()},
        "agent_results": results,
        "message": (
            "All pipeline verification checks passed. Safe to proceed." if overall == "PASS"
            else "One or more verification agents found blocking issues. Review findings before proceeding."
        ),
    }

    with open(AUDIT_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2)

    if verbose:
        print("\n" + "="*60)
        overall_label = "✅ ALL CLEAR" if overall == "PASS" else "❌ ISSUES FOUND"
        print(f"  Pipeline Audit: {overall_label}")
        for agent, verdict in combined["agent_verdicts"].items():
            icon = "✅" if verdict == "PASS" else "❌"
            print(f"  {icon} {agent}: {verdict}")
        print(f"\n  Full report: {AUDIT_OUTPUT}")
        print("="*60 + "\n")

    return combined


def run_single_agent(agent_name: str, verbose: bool = True) -> dict:
    """Run just one agent by name."""
    if agent_name == "security":
        return run_security_audit(verbose=verbose)
    elif agent_name == "data":
        return run_data_quality_check(verbose=verbose)
    elif agent_name == "strategy":
        return run_strategy_audit(verbose=verbose)
    else:
        print(f"Unknown agent: {agent_name}. Available: security, data, strategy, all")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="ThinkFree Finance — Pipeline Verification Runner")
    parser.add_argument(
        "--phase",
        choices=["security", "data", "strategy", "all"],
        default="all",
        help="Which agent(s) to run (default: all)",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")
    args = parser.parse_args()

    verbose = not args.quiet

    if args.phase == "all":
        result = run_all_agents(verbose=verbose)
    else:
        result = run_single_agent(args.phase, verbose=verbose)  # type: ignore[assignment]

    # Exit 1 if any failures so controller.py can detect issues
    verdict = result.get("overall_verdict", result.get("verdict", "UNKNOWN"))
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
