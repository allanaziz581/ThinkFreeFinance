#!/usr/bin/env python3
"""Offline repository secret checks; findings never contain matched secret values.

This is one gate, not a security certification. CI separately runs Bandit,
pip-audit and regression tests. Runtime credentials belong in ignored environment
files or injected variables and are intentionally never read by this scanner.
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
AUDIT_OUTPUT = BASE_DIR / "pipeline_audit.json"
SECRET_PATTERNS = [
    (re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{40,}"), "provider API key"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), "GitHub token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}"), "GitHub fine-grained token"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private key"),
]
TEXT_SUFFIXES = {".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml", ".sh", ".md", ".txt", ".html"}

class Finding:
    def __init__(self, severity, category, file, line, message):
        self.severity, self.category = severity, category
        self.file, self.line, self.message = str(file), line, message
    def to_dict(self):
        return vars(self)


def repository_files(root: Path) -> list[Path]:
    result = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                            capture_output=True, check=True, timeout=30)
    return [root / name for name in dict.fromkeys(result.stdout.decode().split("\0")) if name]


def scan_repository(root: Path) -> list[Finding]:
    findings = []
    for path in repository_files(root):
        relative = path.relative_to(root)
        # A tracked credential store is itself a failure; do not read its values.
        if path.name == ".env" or path.suffix in {".pem", ".key"} or path.name == "users.db":
            findings.append(Finding("CRITICAL", "credential_file", relative, 0, "Credential store is tracked or not ignored"))
            continue
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for pattern, label in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(Finding("CRITICAL", "exposed_secret", relative, number,
                                            f"Possible {label}; matched value redacted"))
    return findings


def run_security_audit(verbose: bool = True) -> dict:
    try:
        findings = scan_repository(BASE_DIR)
        verdict = "FAIL" if findings else "PASS"
    except (OSError, subprocess.SubprocessError, UnicodeError):
        findings = [Finding("HIGH", "scan_error", ".", 0, "Repository scan did not complete")]
        verdict = "ERROR"
    result = {
        "audit_timestamp": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "scope": "repository credential patterns only; see CI for dependency/static-analysis results",
        "summary": {"critical": sum(f.severity == "CRITICAL" for f in findings),
                    "high": sum(f.severity == "HIGH" for f in findings), "total": len(findings)},
        "findings": [f.to_dict() for f in findings],
    }
    AUDIT_OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if verbose:
        print(f"Repository credential scan: {verdict} ({len(findings)} findings; values redacted)")
    return result


def exit_code(result: dict) -> int:
    return 0 if result.get("verdict") == "PASS" else 1

if __name__ == "__main__":
    sys.exit(exit_code(run_security_audit()))
