"""In-process background data refresher.

Re-runs the lightweight, network-only economy builder (FRED API) on a timer and
writes the fresh dataset to the PERSISTENT DISK, so the served ECONOMY data stays
current without a redeploy or a git commit. This matters because the daily
git-commit refresh cron is blocked (the deploy token lacks push access), so the
web service refreshes itself instead.

Design notes:
  * Runs in a daemon thread, so it never blocks request handling.
  * Low footprint: ~55 small FRED calls, ~90 KB JSON, safe on the 512 MB instance.
  * Writes to {persistent disk}/refresh/ECONOMY.json and clears the data cache, so
    /api/data/bundle serves the fresh pull. data._load prefers this file over the
    build-time snapshot in private_data/.
  * Survives restarts: the file lives on the persistent disk (TF_DB_PATH's dir).

Honest source cadence: FRED/BLS publish the eggs/CPI series MONTHLY (gas and
mortgage weekly). So "as fast as possible" means polling the source often and
updating the moment a new value is published, not minute-by-minute. The poll
interval below is the source-appropriate floor.
"""
from __future__ import annotations

import json
import sys
import threading
import time
import traceback

import config

WEBAPP_DIR = config.WEBAPP_DIR
REFRESH_DIR = config.DB_PATH.parent / "refresh"   # e.g. /var/data/refresh on Render
ECONOMY_INTERVAL = 2 * 3600                        # 2h: catches a new monthly/weekly release fast without hammering


def _write(name: str, doc: object) -> None:
    REFRESH_DIR.mkdir(parents=True, exist_ok=True)
    tmp = REFRESH_DIR / f"{name}.json.tmp"
    tmp.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(REFRESH_DIR / f"{name}.json")      # atomic swap


def _refresh_economy() -> None:
    if str(WEBAPP_DIR) not in sys.path:
        sys.path.insert(0, str(WEBAPP_DIR))
    import build_economy
    doc, _missing = build_economy.build_doc()      # network-only FRED pull, no file IO
    if not doc:
        print("[refresher] economy: nothing sourced this cycle; keeping previous data")
        return
    _write("ECONOMY", doc)
    import data
    data._load.cache_clear()                       # next bundle request re-reads the fresh file
    n = sum(len(c.get("indicators", [])) for c in doc.get("categories", []))
    print(f"[refresher] economy refreshed: {n} indicators, generated_at={doc.get('generated_at', '?')}")


def _loop() -> None:
    while True:
        try:
            _refresh_economy()
        except Exception:                          # never let a transient source error kill the thread
            print("[refresher] economy refresh failed:")
            traceback.print_exc()
        time.sleep(ECONOMY_INTERVAL)


def start() -> None:
    """Launch the background refresher. Runs one refresh immediately on startup,
    then every ECONOMY_INTERVAL. Idempotent guard avoids a double-start."""
    if getattr(start, "_started", False):
        return
    start._started = True
    threading.Thread(target=_loop, daemon=True, name="tf-economy-refresher").start()
    print(f"[refresher] started: economy every {ECONOMY_INTERVAL}s -> {REFRESH_DIR}")
