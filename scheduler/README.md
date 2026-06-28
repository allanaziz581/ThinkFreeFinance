# ThinkFree Data-Refresh Scheduler

Drives the data builders on **per-source cadences** (not one global rate), then
runs the aggregate + export step so fresh data reaches the gated
`/api/data/*` endpoints the UI reads.

## Cadence (matched to how often each upstream actually updates)

| Job | Builders | Cadence | Upstream freshness |
|-----|----------|---------|--------------------|
| `prices` | `build_prices.py` | **5 min market hours**, 30 min after-hours, 60 min weekend | Finnhub real-time |
| `federal_legislation` | `congress_bills.py`, `build_member_bills.py` | every 6 h | Congress.gov ~daily |
| `state_legislation` | `build_legiscan.py`, `build_openstates.py` | daily | LegiScan/OpenStates ~daily |
| `campaign_finance` | `build_fec.py`, `build_usaspending.py` | daily | FEC ~daily; USASpending weeks-lagged |
| `macro` | `build_states.py`, `recession_signals.py` | daily | FRED weekly/monthly |
| `trades` | `build_trades.py`, `politician_performance.py`, `build_data.py` | **hourly** | QuiverQuant /live updates ~daily; trades carry a 2-45 day STOCK Act disclosure lag |
| `news_intel` | `build_news_intel.py` | **OFF by default** (6 h) | OpenAI-metered; opt-in |

After every job the export step (`scripts/extract_data_to_json.py`) regenerates
`private_data/*.json` so the backend serves the new data.

> **No fake real-time.** Legislative sources are scheduled at the fastest rate
> the upstream actually refreshes (~daily). Only prices ride the 5-minute tier.

## Start / stop

```bash
# Foreground (runs forever; Ctrl-C to stop):
tf_env/bin/python scheduler/run_scheduler.py

# Background:
nohup tf_env/bin/python scheduler/run_scheduler.py > scheduler/logs/out.log 2>&1 &
#   PID is written to scheduler/scheduler.pid — stop with:  kill "$(cat scheduler/scheduler.pid)"

# Run all due jobs once and exit (good for cron / manual refresh):
tf_env/bin/python scheduler/run_scheduler.py --once

# Force specific jobs now (ignores cadence):
tf_env/bin/python scheduler/run_scheduler.py --run prices,federal_legislation

# List jobs:
tf_env/bin/python scheduler/run_scheduler.py --list
```

## Config / toggles (env vars)

- `TF_SCHED_NEWS_INTEL=1` — enable the OpenAI news-summary job (default OFF so the
  scheduler never spends money on its own).
- `TF_SCHED_DISABLE=state_legislation,campaign_finance` — disable jobs by name.

Edit the `JOBS` table at the top of `run_scheduler.py` to change cadences/scripts.

## Robustness notes

- Jobs are **serialized** (one global lock) so two builders never hit the same
  provider at once; builders also self-throttle.
- Each job is **staggered** on startup so they don't all fire together.
- Builders run via `subprocess` **list-form, `shell=False`** — no shell parsing,
  no command-injection surface. Script paths are hard-coded, never from input.
- Every run is logged with timestamp, duration, and exit code to
  `scheduler/logs/scheduler.log`.
- **In-process state.** Single process is fine for now. For multi-host you'd run
  this on one worker (the builders write shared files) and keep the per-user
  `/live` cadence gate (see `server/data.py`) — which needs Redis for multi-worker
  API serving, tracked separately.
