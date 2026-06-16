#!/usr/bin/env python3
"""
ThinkFree Finance — Environment Validation Script

Checks:
  1. All required API keys are set in .env
  2. Critical Python imports work
  3. Output directories exist
  4. Key pipeline scripts are present
  5. Optional: tests OpenAI API connectivity

Usage:
  python validate_env.py
  python validate_env.py --test-api    (actually pings OpenAI)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent


def load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
    except ImportError:
        print("[WARN] python-dotenv not installed. Reading OS environment only.")


def check(label: str, passed: bool, detail: str = "") -> bool:
    icon = "✅" if passed else "❌"
    line = f"  {icon}  {label}"
    if detail:
        line += f"  — {detail}"
    print(line)
    return passed


def section(title: str) -> None:
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")


# -----------------------------------------------------------
# API Keys
# -----------------------------------------------------------
def validate_api_keys() -> list[str]:
    section("API Keys")
    failures = []

    keys = [
        ("OPENAI_API_KEY",       "Required for GPT summarization, Chef GPT (Phases 5, 11)"),
        ("FINNHUB_API_KEY",      "Required for news scraping (Phase 2)"),
        ("SEC_API_KEY",          "Optional — SEC Edgar filings"),
        ("QUANDL_API_KEY",       "Optional — macro data (Phase 6)"),
        ("QUIVERQUANT_API_KEY",  "Required for political intelligence (Phase 6.5)"),
        ("FRED_API_KEY",         "Optional — FRED macro data (Phase 13)"),
    ]

    for key, description in keys:
        value = os.getenv(key, "")
        is_set = bool(value and value != f"your_{key.lower()}_here" and "your_" not in value)
        required = "Required" in description
        if not check(key, is_set, description):
            if required:
                failures.append(key)
    return failures


# -----------------------------------------------------------
# Python imports
# -----------------------------------------------------------
def validate_imports() -> list[str]:
    section("Python Package Imports")
    failures = []

    packages = [
        ("dotenv",                    "python-dotenv",   True,  "Core: API key management"),
        ("openai",                    "openai",          True,  "Core: GPT summarization"),
        ("streamlit",                 "streamlit",       True,  "Core: Dashboard"),
        ("pandas",                    "pandas",          True,  "Core: Data handling"),
        ("numpy",                     "numpy",           True,  "Core: Numerical operations"),
        ("yfinance",                  "yfinance",        True,  "Core: Market data"),
        ("feedparser",                "feedparser",      True,  "Core: RSS news scraping"),
        ("requests",                  "requests",        True,  "Core: HTTP requests"),
        ("vaderSentiment.vaderSentiment", "vaderSentiment", False, "Optional: Sentiment analysis"),
        ("sklearn",                   "scikit-learn",    False, "Optional: Clustering algorithms"),
        ("faiss",                     "faiss-cpu",       False, "Optional: Vector search"),
        ("backtrader",                "backtrader",      False, "Optional: Backtesting engine"),
        ("fredapi",                   "fredapi",         False, "Optional: FRED macro data"),
        ("plotly",                    "plotly",          False, "Optional: Charts"),
    ]

    for module, package, required, description in packages:
        try:
            __import__(module)
            check(package, True, description)
        except ImportError:
            if not check(package, False, description):
                if required:
                    failures.append(f"pip install {package}")

    # sentence_transformers import is slow (loads torch) — check via pip metadata instead
    import importlib.metadata
    try:
        ver = importlib.metadata.version("sentence-transformers")
        check("sentence-transformers", True, f"Optional: Article embeddings (v{ver})")
    except importlib.metadata.PackageNotFoundError:
        check("sentence-transformers", False, "Optional: Article embeddings — pip install sentence-transformers==2.7.0")

    return failures


# -----------------------------------------------------------
# File structure
# -----------------------------------------------------------
def validate_files() -> list[str]:
    section("Key Pipeline Files")
    failures = []

    scripts = [
        (BASE_DIR / "phase3_extraction.py",      "Phase 3 — Data extraction",         True),
        (BASE_DIR / "phase4_clustering.py",       "Phase 4 — Article clustering",       True),
        (BASE_DIR / "recession_signals.py",       "Phase 13 — Recession signals",       True),
        (BASE_DIR / "historical_correlation.py",  "Phase 7 — Historical correlation",   True),
        (BASE_DIR / "opportunity_score.py",       "Phase 8.9 — Opportunity scoring",    True),
        (BASE_DIR / "chef_gpt.py",                "Phase 11 — Chef GPT synthesis",      True),
        (BASE_DIR / "controller.py",              "Phase 12 — Pipeline controller",     True),
        (BASE_DIR / "dashboard" / "app.py",       "Dashboard — Streamlit app",          True),
        (BASE_DIR / "agents" / "security_audit.py",    "Security audit agent",           False),
        (BASE_DIR / "agents" / "data_quality.py",      "Data quality agent",             False),
        (BASE_DIR / "agents" / "verification_runner.py","Verification runner",           False),
        (BASE_DIR / ".env",                       ".env — API keys config",             True),
        (BASE_DIR / "requirements.txt",           "requirements.txt",                   True),
    ]

    for path, description, required in scripts:
        exists = path.exists()
        if not check(str(path.name), exists, description):
            if required:
                failures.append(str(path.relative_to(BASE_DIR)))

    return failures


# -----------------------------------------------------------
# Output directories
# -----------------------------------------------------------
def validate_directories() -> None:
    section("Output Directories")

    dirs = [
        BASE_DIR / "news_output",
        BASE_DIR / "Module_2_Technical_Analysis" / "results_run",
        BASE_DIR / "agents",
    ]

    for d in dirs:
        exists = d.exists()
        if not exists:
            d.mkdir(parents=True, exist_ok=True)
        check(d.name, True, f"{'exists' if exists else 'created'}: {d.relative_to(BASE_DIR)}")


# -----------------------------------------------------------
# OpenAI connectivity test
# -----------------------------------------------------------
def test_openai_api() -> bool:
    section("OpenAI API Connectivity Test")
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        check("OpenAI ping", False, "OPENAI_API_KEY not set — skipping")
        return False

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=5,
        )
        passed = bool(response.choices[0].message.content)
        check("OpenAI API", passed, "Connection successful")
        return passed
    except Exception as e:
        check("OpenAI API", False, str(e)[:80])
        return False


# -----------------------------------------------------------
# Main
# -----------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="ThinkFree Finance — Environment Validation")
    parser.add_argument("--test-api", action="store_true", help="Test actual OpenAI API connectivity")
    args = parser.parse_args()

    print("\n" + "=" * 55)
    print("  ThinkFree Finance — Environment Validation")
    print("=" * 55)

    load_env()

    key_failures   = validate_api_keys()
    import_failures = validate_imports()
    file_failures  = validate_files()
    validate_directories()

    if args.test_api:
        test_openai_api()

    # Summary
    print(f"\n{'='*55}")
    all_passed = not key_failures and not import_failures and not file_failures

    if all_passed:
        print("  ✅ All checks passed! You're ready to run the pipeline.")
        print("\n  Start with:")
        print("    python controller.py --list")
        print("    python controller.py")
        print("    streamlit run dashboard/app.py")
    else:
        print("  ❌ Some checks failed. Fix these before running the pipeline:")
        if key_failures:
            print("\n  Missing API keys (add to .env):")
            for k in key_failures:
                print(f"    {k}=<your key here>")
        if import_failures:
            print("\n  Missing packages:")
            for p in import_failures:
                print(f"    {p}")
        if file_failures:
            print("\n  Missing files:")
            for f in file_failures:
                print(f"    {f}")

    print("=" * 55 + "\n")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
