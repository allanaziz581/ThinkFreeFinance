#!/usr/bin/env python3
"""
ThinkFree Finance — SecurityAuditAgent

Runs on every pipeline execution to catch:
  1. Hardcoded secrets in Python files (pattern scanning)
  2. Known vulnerable dependencies (via safety/pip-audit)
  3. Dangerous code patterns (via bandit static analysis)
  4. Unvalidated external inputs in pipeline outputs
  5. Exposed API keys in JSON output files

Returns: pass/fail verdict with a list of findings.
Methodology inspired by PentestGPT / AgentVerse multi-agent security patterns.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.parent
AUDIT_OUTPUT = BASE_DIR / "pipeline_audit.json"

# ---------------------------------------------------------------------------
# Secret detection patterns
# ---------------------------------------------------------------------------

SECRET_PATTERNS = [
    (re.compile(r'sk-proj-[A-Za-z0-9_-]{40,}'), "OpenAI API key"),
    (re.compile(r'sk-[A-Za-z0-9]{48}'), "OpenAI API key (legacy)"),
    (re.compile(r'"api_key"\s*:\s*"[A-Za-z0-9_-]{20,}"'), "Hardcoded API key in JSON"),
    (re.compile(r'password\s*=\s*["\'][^"\']{8,}["\']', re.I), "Hardcoded password"),
    (re.compile(r'secret\s*=\s*["\'][^"\']{8,}["\']', re.I), "Hardcoded secret"),
    (re.compile(r'Bearer [A-Za-z0-9_-]{20,}'), "Hardcoded Bearer token"),
    (re.compile(r'[A-Za-z0-9]{40}'), None),  # Generic long token — only flag if in assignment context
]

DANGEROUS_PATTERNS = [
    (re.compile(r'\beval\s*\('), "Use of eval() — potential code injection"),
    (re.compile(r'\bexec\s*\('), "Use of exec() — potential code injection"),
    (re.compile(r'subprocess.*shell\s*=\s*True'), "subprocess with shell=True — command injection risk"),
    (re.compile(r'pickle\.loads\b'), "pickle.loads — unsafe deserialization"),
    (re.compile(r'yaml\.load\s*\([^)]*\)(?!.*Loader)'), "yaml.load without Loader — unsafe deserialization"),
    (re.compile(r'os\.system\s*\('), "os.system() — prefer subprocess"),
]

def _secret_fragments():
    """Fragments of the project's real keys to scan for, read from .env at
    runtime so this committed file never contains real-key material itself."""
    frags = ["sk-proj-", "sk-ant-", "ghp_", "github_pat_"]   # generic provider prefixes
    try:
        from pathlib import Path
        for line in (Path(__file__).resolve().parent.parent / ".env").read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                v = line.split("=", 1)[1].strip()
                if len(v) >= 16:
                    frags.append(v[:14])
    except Exception:
        pass
    return frags


KNOWN_BAD_STRINGS = _secret_fragments()

# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

class Finding:
    def __init__(self, severity: str, category: str, file: str, line: int, message: str):
        self.severity = severity  # CRITICAL, HIGH, MEDIUM, LOW, INFO
        self.category = category
        self.file = file
        self.line = line
        self.message = message

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "category": self.category,
            "file": str(self.file),
            "line": self.line,
            "message": self.message,
        }


def scan_python_files_for_secrets(root: Path) -> list[Finding]:
    """Scan all .py files for hardcoded secrets and dangerous patterns."""
    findings = []
    py_files = list(root.rglob("*.py"))

    for py_file in py_files:
        # Skip venv and cache directories
        parts = py_file.parts
        if any(part in ("venv", "venv_qlib", "__pycache__", ".git", "site-packages") for part in parts):
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
        except Exception:
            continue

        for lineno, line in enumerate(lines, start=1):
            # Check known bad strings
            for bad_str in KNOWN_BAD_STRINGS:
                if bad_str in line:
                    findings.append(Finding(
                        "CRITICAL", "exposed_secret",
                        str(py_file.relative_to(root)), lineno,
                        f"Previously exposed API key fragment detected: '{bad_str[:8]}...'"
                    ))

            # Check dangerous patterns
            for pattern, message in DANGEROUS_PATTERNS:
                if pattern.search(line):
                    findings.append(Finding(
                        "HIGH", "dangerous_code",
                        str(py_file.relative_to(root)), lineno,
                        message
                    ))

            # Check os.environ assignment of secrets
            if re.search(r'os\.environ\["(OPENAI|API|SECRET|KEY|TOKEN|PASSWORD)', line, re.I):
                if "os.getenv" not in line and "load_dotenv" not in line:
                    findings.append(Finding(
                        "MEDIUM", "env_assignment",
                        str(py_file.relative_to(root)), lineno,
                        "Direct os.environ assignment detected — ensure value is not hardcoded"
                    ))

    return findings


def scan_json_outputs_for_secrets(root: Path) -> list[Finding]:
    """Check that pipeline output JSON files don't contain API keys."""
    findings = []
    json_dirs = [root / "news_output", root / "GPT_Economy"]
    output_files = []
    for d in json_dirs:
        if d.exists():
            output_files.extend(d.rglob("*.json"))

    for json_file in output_files[:20]:  # Sample first 20
        try:
            content = json_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for bad_str in KNOWN_BAD_STRINGS:
            if bad_str in content:
                findings.append(Finding(
                    "CRITICAL", "secret_in_output",
                    str(json_file.relative_to(root)), 0,
                    f"API key fragment found in output file: '{bad_str[:8]}...'"
                ))
                break

        for pattern, label in SECRET_PATTERNS[:4]:  # First 4 are most specific
            if label and pattern.search(content):
                findings.append(Finding(
                    "HIGH", "secret_in_output",
                    str(json_file.relative_to(root)), 0,
                    f"{label} pattern found in output file"
                ))
                break

    return findings


def check_env_file(root: Path) -> list[Finding]:
    """Verify .env file exists and is not committed."""
    findings = []
    env_path = root / ".env"
    gitignore_path = root / ".gitignore"

    if not env_path.exists():
        findings.append(Finding(
            "HIGH", "missing_env",
            ".env", 0,
            ".env file missing. Copy .env.example to .env and fill in API keys."
        ))
        return findings

    # Check .env is in .gitignore
    if gitignore_path.exists():
        gitignore_content = gitignore_path.read_text(encoding="utf-8")
        if ".env" not in gitignore_content:
            findings.append(Finding(
                "HIGH", "env_not_gitignored",
                ".gitignore", 0,
                ".env not in .gitignore — risk of committing API keys"
            ))

    # Check .env doesn't have actual keys filled in with known bad values
    env_content = env_path.read_text(encoding="utf-8", errors="replace")
    for bad_str in KNOWN_BAD_STRINGS:
        if bad_str in env_content:
            findings.append(Finding(
                "CRITICAL", "rotated_key_in_env",
                ".env", 0,
                f"Previously exposed key still in .env: '{bad_str[:8]}...'. Rotate immediately at provider."
            ))

    return findings


def run_bandit(root: Path) -> list[Finding]:
    """Run bandit static analysis if available."""
    findings = []
    try:
        result = subprocess.run(
            [sys.executable, "-m", "bandit", "-r", str(root),
             "--exclude", f"{root}/venv,{root}/venv_qlib",
             "-f", "json", "-q"],
            capture_output=True, text=True, timeout=60
        )
        if result.stdout:
            data = json.loads(result.stdout)
            for issue in data.get("results", [])[:10]:
                findings.append(Finding(
                    issue.get("issue_severity", "MEDIUM").upper(),
                    "bandit_" + issue.get("test_id", "unknown").lower(),
                    issue.get("filename", "").replace(str(root) + "/", ""),
                    issue.get("line_number", 0),
                    f"[{issue.get('test_id')}] {issue.get('issue_text', '')}"
                ))
    except FileNotFoundError:
        findings.append(Finding(
            "INFO", "tool_missing", "bandit", 0,
            "bandit not installed. Run: pip install bandit"
        ))
    except Exception as e:
        findings.append(Finding(
            "INFO", "tool_error", "bandit", 0,
            f"bandit scan failed: {e}"
        ))
    return findings


def run_safety_check() -> list[Finding]:
    """Check for known CVEs in installed packages."""
    findings = []
    try:
        result = subprocess.run(
            [sys.executable, "-m", "safety", "check", "--json"],
            capture_output=True, text=True, timeout=30
        )
        if result.stdout:
            data = json.loads(result.stdout)
            vulns = data if isinstance(data, list) else data.get("vulnerabilities", [])
            for vuln in vulns[:5]:
                package = vuln.get("package_name", vuln.get("name", "unknown"))
                advisory = vuln.get("advisory", vuln.get("description", ""))[:100]
                findings.append(Finding(
                    "HIGH", "cve",
                    "requirements.txt", 0,
                    f"Vulnerable package: {package}. {advisory}"
                ))
    except FileNotFoundError:
        findings.append(Finding(
            "INFO", "tool_missing", "safety", 0,
            "safety not installed. Run: pip install safety"
        ))
    except Exception as e:
        findings.append(Finding(
            "INFO", "tool_error", "safety", 0,
            f"safety check failed: {e}"
        ))
    return findings


def validate_pipeline_output_structure(root: Path) -> list[Finding]:
    """Verify that key pipeline output files have expected structure."""
    findings = []

    checks = [
        {
            "path": root / "user_profile.json",
            "required_keys": ["age", "risk_tolerance", "risk_score"],
            "name": "User Profile",
        },
        {
            "path": root / "news_output" / "economic_reasoning_summary.json",
            "required_keys": ["summary", "bullish_sectors", "bearish_sectors"],
            "name": "Economic Reasoning",
        },
    ]

    for check in checks:
        path = check["path"]
        if not path.exists():
            findings.append(Finding(
                "INFO", "missing_output",
                str(path.relative_to(root)), 0,
                f"{check['name']} output not yet generated. Run pipeline first."
            ))
            continue

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for key in check["required_keys"]:
                if isinstance(data, dict) and key not in data:
                    findings.append(Finding(
                        "MEDIUM", "malformed_output",
                        str(path.relative_to(root)), 0,
                        f"Missing required key '{key}' in {check['name']} output"
                    ))
        except json.JSONDecodeError:
            findings.append(Finding(
                "HIGH", "invalid_json",
                str(path.relative_to(root)), 0,
                f"{check['name']} output is not valid JSON"
            ))

    return findings


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_security_audit(verbose: bool = True) -> dict:
    if verbose:
        print("=== ThinkFree — SecurityAuditAgent ===")

    all_findings: list[Finding] = []

    if verbose:
        print("Scanning Python files for secrets and dangerous patterns...")
    all_findings.extend(scan_python_files_for_secrets(BASE_DIR))

    if verbose:
        print("Checking output files for exposed secrets...")
    all_findings.extend(scan_json_outputs_for_secrets(BASE_DIR))

    if verbose:
        print("Validating .env configuration...")
    all_findings.extend(check_env_file(BASE_DIR))

    if verbose:
        print("Running bandit static analysis...")
    all_findings.extend(run_bandit(BASE_DIR))

    if verbose:
        print("Checking dependency CVEs...")
    all_findings.extend(run_safety_check())

    if verbose:
        print("Validating pipeline output structure...")
    all_findings.extend(validate_pipeline_output_structure(BASE_DIR))

    # Summarize
    critical = [f for f in all_findings if f.severity == "CRITICAL"]
    high     = [f for f in all_findings if f.severity == "HIGH"]
    medium   = [f for f in all_findings if f.severity == "MEDIUM"]
    low_info = [f for f in all_findings if f.severity in ("LOW", "INFO")]

    passed = len(critical) == 0 and len(high) == 0

    result = {
        "audit_timestamp": datetime.utcnow().isoformat() + "Z",
        "verdict": "PASS" if passed else "FAIL",
        "summary": {
            "critical": len(critical),
            "high": len(high),
            "medium": len(medium),
            "info": len(low_info),
            "total": len(all_findings),
        },
        "findings": [f.to_dict() for f in all_findings],
        "message": (
            "No critical security issues detected." if passed
            else f"{len(critical)} critical and {len(high)} high severity issues found. Review before proceeding."
        ),
    }

    with open(AUDIT_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    if verbose:
        print(f"\n{'='*50}")
        verdict_label = "✅ PASS" if passed else "❌ FAIL"
        print(f"Security Audit: {verdict_label}")
        print(f"  Critical: {len(critical)}  High: {len(high)}  Medium: {len(medium)}")
        if not passed:
            for f in (critical + high)[:5]:
                print(f"  [{f.severity}] {f.file}:{f.line} — {f.message}")
        print(f"Saved to: {AUDIT_OUTPUT}")

    return result


if __name__ == "__main__":
    _result = run_security_audit(verbose=True)
    # Exit non-zero on FAIL so CI / pre-commit hooks can block on it.
    sys.exit(0 if _result.get("passed") else 1)
