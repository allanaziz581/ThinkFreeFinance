#!/usr/bin/env python3
"""ThinkFree data-refresh scheduler.

Drives the data builders on per-source cadences that match how often each
upstream actually updates — NOT one global rate — then runs the aggregate +
export step so fresh data reaches the gated /api/data/* endpoints (the UI).

Design goals (all satisfied here, no third-party scheduler required):
  * Per-source cadence (prices fast during market hours; legislative daily; etc.)
  * No stampede: each job is staggered and never overlaps itself (per-job lock).
  * Respects rate limits: builders self-throttle; we also serialize jobs so two
    builders never hammer the same provider at once.
  * Market-hours aware: the prices job idles to a slow cadence when US equities
    are closed; legislative/macro jobs run on a fixed daily clock regardless.
  * Logs every run with a timestamp, duration, and exit code.
  * Safe execution: builders are launched with subprocess in LIST form and
    shell=False, so nothing in a job definition is ever interpreted by a shell
    (no command injection surface). Paths are hard-coded, never from input.
  * Secrets: builders read keys from .env themselves; this runner never reads,
    logs, or passes any secret value.

Usage:
  Start (runs forever, foreground):
     tf_env/bin/python scheduler/run_scheduler.py
  Run every DUE job once and exit (manual refresh / cron-driven):
     tf_env/bin/python scheduler/run_scheduler.py --once
  Force-run specific jobs once, ignoring cadence:
     tf_env/bin/python scheduler/run_scheduler.py --run prices,federal_legislation
  List the configured jobs and exit:
     tf_env/bin/python scheduler/run_scheduler.py --list

Stop: Ctrl-C (foreground). If started in the background, kill the PID written to
scheduler/scheduler.pid. To run it as a managed service, point systemd/launchd
(or a host scheduler) at the --once mode on a 1-minute timer, or at the
long-running default.

Config: edit JOBS below, or toggle groups via env vars:
  TF_SCHED_NEWS_INTEL=1   enable the OpenAI news-summary job (OFF by default -
                          it spends money; left disabled so nothing auto-bills).
  TF_SCHED_DISABLE=a,b     comma-separated job names to disable.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable                      # the tf_env interpreter running us
LOG_DIR = ROOT / "scheduler" / "logs"
PID_FILE = ROOT / "scheduler" / "scheduler.pid"


# --------------------------------------------------------------------------
# Market-hours helper (mirrors server/data.py so cadence matches entitlements).
# --------------------------------------------------------------------------
def market_open(now: dt.datetime | None = None) -> bool:
    """US equities: Mon-Fri 09:30-16:00 America/New_York (DST-aware)."""
    try:
        from zoneinfo import ZoneInfo
        now = now or dt.datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return False
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 570 <= minutes < 960


def is_weekend(now: dt.datetime | None = None) -> bool:
    try:
        from zoneinfo import ZoneInfo
        now = now or dt.datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        now = now or dt.datetime.utcnow()
    return now.weekday() >= 5


def prices_interval_seconds() -> int:
    """Adaptive cadence for the prices job: 5 min while the market is open,
    30 min in weekday after-hours, 60 min on weekends."""
    if market_open():
        return 5 * 60
    if is_weekend():
        return 60 * 60
    return 30 * 60


# --------------------------------------------------------------------------
# Job registry. Each job runs one or more builder scripts in sequence, then
# (optionally) the export step. `interval` is seconds; if `interval_fn` is set
# it overrides `interval` dynamically. `stagger` offsets the first run so jobs
# don't all fire together on startup.
# --------------------------------------------------------------------------
HOUR = 3600
DAY = 24 * HOUR

JOBS = [
    {
        "name": "prices",
        "scripts": ["webapp/build_prices.py"],
        "export": True,                       # push fresh prices to private_data
        "interval": 5 * 60,
        "interval_fn": prices_interval_seconds,
        "stagger": 0,
        "market_hours_note": "5m open / 30m after-hours / 60m weekend",
        "enabled": True,
    },
    {
        "name": "federal_legislation",
        "scripts": ["congress_bills.py", "webapp/build_member_bills.py"],
        "export": True,
        "interval": 6 * HOUR,                 # Congress.gov updates ~daily
        "stagger": 60,
        "enabled": True,
    },
    {
        "name": "state_legislation",
        "scripts": ["webapp/build_legiscan.py", "webapp/build_openstates.py"],
        "export": True,
        "interval": DAY,                      # state APIs update ~daily
        "stagger": 120,
        "enabled": True,
    },
    {
        "name": "campaign_finance",
        "scripts": ["webapp/build_fec.py", "webapp/build_usaspending.py"],
        "export": True,
        "interval": DAY,                      # filings daily; contracts weeks-lagged
        "stagger": 180,
        "enabled": True,
    },
    {
        "name": "macro",
        "scripts": ["webapp/build_states.py", "recession_signals.py"],
        "export": True,
        "interval": DAY,                      # FRED weekly/monthly series
        "stagger": 240,
        "enabled": True,
    },
    {
        # Live congressional trades from QuiverQuant -> P&L -> aggregate -> export.
        # Hourly: QuiverQuant's /live feed only updates as new STOCK Act disclosures
        # are filed (a few times a day at most), and trades already carry a 2-45 day
        # statutory disclosure lag, so hourly captures every new filing with margin.
        "name": "trades",
        "scripts": ["webapp/build_trades.py", "politician_performance.py", "webapp/build_data.py"],
        "export": True,
        "interval": HOUR,
        "stagger": 300,
        "enabled": True,
    },
    {
        # The Money Trail Detective Engine: chain-of-evidence case files per law
        # (Congress.gov milestones + committee rosters + QuiverQuant excess return).
        # Daily: the upstreams (Congress.gov, QuiverQuant) update ~daily and a full
        # run takes a few minutes, so daily keeps cases fresh without churn.
        "name": "money_trail",
        "scripts": ["webapp/build_money_trail.py"],
        "export": True,
        "interval": DAY,
        "stagger": 600,
        "enabled": True,
    },
    {
        # Presidential actions & news (Federal Register + Congress.gov + RSS).
        # Every 6h: the Federal Register publishes on business days and EOs appear
        # a few days after signing; Congress.gov updates ~daily. Daily-freshness,
        # not real-time.
        "name": "presidential",
        "scripts": ["webapp/build_presidential.py"],
        "export": True,
        "interval": 6 * HOUR,
        "stagger": 540,
        "enabled": True,
    },
    {
        # OpenAI-metered news summaries. DISABLED by default so the scheduler
        # never spends money on its own. Enable with TF_SCHED_NEWS_INTEL=1.
        "name": "news_intel",
        "scripts": ["webapp/build_news_intel.py"],
        "export": True,
        "interval": 6 * HOUR,
        "stagger": 360,
        "enabled": os.environ.get("TF_SCHED_NEWS_INTEL", "0") == "1",
    },
]

# Feature-branch jobs (data centers + hedge fund) live in a separate module so
# they merge without touching the core JOBS list above. See scheduler/extra_jobs.py.
try:
    from extra_jobs import EXTRA_JOBS
    JOBS += EXTRA_JOBS
except Exception:  # pragma: no cover - scheduler still runs without the extras
    pass

EXPORT_SCRIPT = "scripts/extract_data_to_json.py"


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------
_run_lock = threading.Lock()   # serialize all job runs => never stampede a provider


def log(msg: str) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / "scheduler.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _run_script(rel_path: str, timeout: int = 1800) -> int:
    """Run one builder as a subprocess (LIST form, shell=False => no injection)."""
    script = ROOT / rel_path
    if not script.exists():
        log(f"  [skip] missing script: {rel_path}")
        return 0
    t0 = time.time()
    try:
        proc = subprocess.run(
            [PY, str(script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        dur = time.time() - t0
        tail = (proc.stdout or "").strip().splitlines()[-1:] or [""]
        log(f"  {rel_path} -> exit {proc.returncode} in {dur:.0f}s | {tail[0][:120]}")
        if proc.returncode != 0:
            err = (proc.stderr or "").strip().splitlines()[-1:] or [""]
            log(f"    stderr: {err[0][:160]}")
        return proc.returncode
    except subprocess.TimeoutExpired:
        log(f"  {rel_path} -> TIMEOUT after {timeout}s")
        return 124


def run_job(job: dict) -> None:
    """Run a job's scripts in order, then the export step. Serialized so two
    jobs never run at once (protects shared files + provider rate limits)."""
    with _run_lock:
        log(f"JOB {job['name']}: starting ({len(job['scripts'])} script(s))")
        ok = True
        for s in job["scripts"]:
            if _run_script(s) != 0:
                ok = False
        if job.get("export"):
            _run_script(EXPORT_SCRIPT)
        log(f"JOB {job['name']}: done ({'ok' if ok else 'with errors'})")


def active_jobs() -> list[dict]:
    disabled = {x.strip() for x in os.environ.get("TF_SCHED_DISABLE", "").split(",") if x.strip()}
    return [j for j in JOBS if j.get("enabled", True) and j["name"] not in disabled]


def serve_forever() -> None:
    PID_FILE.write_text(str(os.getpid()))
    jobs = active_jobs()
    log(f"Scheduler up (pid {os.getpid()}). Active jobs: {', '.join(j['name'] for j in jobs) or 'none'}")
    # next_run[name] = epoch seconds when the job should next fire.
    now = time.time()
    next_run = {j["name"]: now + j.get("stagger", 0) for j in jobs}
    try:
        while True:
            now = time.time()
            for j in jobs:
                if now >= next_run[j["name"]]:
                    try:
                        run_job(j)
                    except Exception as e:
                        log(f"JOB {j['name']}: ERROR {type(e).__name__}: {str(e)[:160]}")
                    interval = j["interval_fn"]() if j.get("interval_fn") else j["interval"]
                    next_run[j["name"]] = time.time() + interval
            time.sleep(15)
    except KeyboardInterrupt:
        log("Scheduler stopping (KeyboardInterrupt).")
    finally:
        try:
            PID_FILE.unlink()
        except Exception:
            pass


def run_once(only: set[str] | None = None) -> None:
    jobs = [j for j in active_jobs() if (only is None or j["name"] in only)]
    log(f"--once: running {', '.join(j['name'] for j in jobs) or 'no matching jobs'}")
    for j in jobs:
        run_job(j)


def main() -> None:
    ap = argparse.ArgumentParser(description="ThinkFree data-refresh scheduler")
    ap.add_argument("--once", action="store_true", help="run every due job once, then exit")
    ap.add_argument("--run", help="comma-separated job names to run once now (ignores cadence)")
    ap.add_argument("--list", action="store_true", help="list configured jobs and exit")
    args = ap.parse_args()

    if args.list:
        print("Configured jobs:")
        for j in JOBS:
            state = "on" if j.get("enabled", True) else "off"
            iv = "adaptive" if j.get("interval_fn") else f"{j['interval'] // 60}min"
            print(f"  [{state:3}] {j['name']:20} every {iv:9} -> {', '.join(j['scripts'])}")
        return
    if args.run:
        run_once(only={x.strip() for x in args.run.split(",") if x.strip()})
        return
    if args.once:
        run_once()
        return
    serve_forever()


if __name__ == "__main__":
    main()
