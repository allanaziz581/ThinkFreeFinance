"""ThinkFree scheduler - extra data-refresh jobs (feature branch).

These two jobs were added on the `feature/data-centers-and-hedge-fund` branch and
are kept in a SEPARATE module on purpose: the core JOBS list in run_scheduler.py
is maintained by a different work-stream, so isolating these here means they can
be merged without touching that list.

Integration (already wired in this branch's run_scheduler.py, one line):

    from extra_jobs import EXTRA_JOBS
    JOBS += EXTRA_JOBS

Each entry uses the exact same schema as the core JOBS list:
  name     - unique job id
  scripts  - builder scripts run in order (LIST form -> shell=False, no injection)
  export   - run scripts/extract_data_to_json.py afterwards (push to private_data)
  interval - seconds between runs
  stagger  - first-run offset so jobs don't all fire at once on startup
  enabled  - on/off

Both upstreams update about once a day:
  * OFR Hedge Fund Monitor - Form PF aggregates, refreshed ~daily as filings post.
  * EIA + Census + curated locations - EIA/Census are daily/periodic; the curated
    location seed changes rarely, so a daily rebuild is plenty.
"""
from __future__ import annotations

DAY = 24 * 3600

EXTRA_JOBS = [
    {
        "name": "hedge_funds",
        "scripts": ["webapp/build_hedgefund.py"],
        "export": True,
        "interval": DAY,            # OFR Hedge Fund Monitor updates ~daily
        "stagger": 420,
        "enabled": True,
    },
    {
        "name": "data_centers",
        "scripts": ["webapp/build_datacenters.py"],
        "export": True,
        "interval": DAY,            # EIA/Census periodic; curated locations rarely
        "stagger": 480,
        "enabled": True,
    },
    {
        # Presidential actions & news (Federal Register + Congress.gov + RSS).
        # Every 6h: the Federal Register publishes on business days and Congress.gov
        # updates ~daily, so 6h catches each daily drop without hammering. EOs appear
        # in the FR a few days after signing (statutory publication lag), so this is
        # a daily-freshness feed, not real-time.
        "name": "presidential",
        "scripts": ["webapp/build_presidential.py"],
        "export": True,
        "interval": 6 * 3600,
        "stagger": 540,
        "enabled": True,
    },
    {
        # Economic / cost-of-living indicators (FRED, which mirrors BLS/BEA/Census/
        # Freddie Mac/UMich series). CPI components publish monthly, weekly rates
        # weekly; a daily rebuild keeps the "since Jan 2025" cards current without
        # hammering. Free FRED key, no OpenAI, so it is cheap to run on the cron.
        "name": "economy_tracker",
        "scripts": ["webapp/build_economy.py"],
        "export": True,
        "interval": DAY,
        "stagger": 600,
        "enabled": True,
    },
]
