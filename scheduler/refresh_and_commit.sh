#!/usr/bin/env bash
# ThinkFree autonomous live-data refresh (Render Cron Job).
#
# Runs the FREE / CHEAP data builders, recomputes the (free, no-OpenAI) Money
# Trail engine, then commits the refreshed webapp/js/*_data.js (and tracked root
# data) back to `main` via the GITHUB_TOKEN. That push triggers the web service's
# autoDeploy, which rebuilds private_data/ from the new snapshots and serves them.
#
# This persists data correctly (in git) within Render's model: a cron and the web
# service cannot share a persistent disk, so git is the durable handoff.
#
# It NEVER runs the paid OpenAI steps:
#   - build_news_intel.py (Chef-GPT-style summaries) is not invoked.
#   - build_money_trail.py is run WITHOUT --gpt (reuses the cached materiality).
#   - OPENAI_API_KEY is intentionally not provided to this job.
#
# Resilience: each builder runs in its own subprocess with a timeout; a single
# source failing (403, network, flaky yfinance) is logged and skipped, and the
# job still commits whatever refreshed.
#
# Secrets: GITHUB_TOKEN is read from the environment and used only to set the push
# remote at runtime. The token is never printed (no `set -x`, no `git remote -v`).

set +e
set +x   # never echo commands; the git remote line would otherwise expose the token
export PYTHONUNBUFFERED=1

REPO="allanaziz581/ThinkFreeFinance"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
PY="${PYTHON:-python}"
TIMEOUT_BIN="$(command -v timeout || true)"

log() { echo "[refresh $(date -u +%H:%M:%S)] $*"; }

run() {  # run "<label>" <python script> [args...]
  local label="$1"; shift
  log "START $label"
  if [ -n "$TIMEOUT_BIN" ]; then
    "$TIMEOUT_BIN" 900 "$PY" "$@" 2>&1 | tail -2
  else
    "$PY" "$@" 2>&1 | tail -2
  fi
  local rc=${PIPESTATUS[0]}
  if [ "$rc" = "0" ]; then log "OK    $label"; else log "FAIL  $label (rc=$rc), continuing"; fi
}

# ---- 0) make sure we are on the latest main (clean handoff point) ------------
git config user.email "refresh-bot@thinkfree.finance"
git config user.name  "ThinkFree Refresh Bot"
git fetch origin main -q 2>/dev/null
git checkout -B main origin/main 2>/dev/null || git checkout main 2>/dev/null

# ---- 0.5) synthesize .env from the injected env vars -------------------------
# The data builders read API keys from a .env FILE (some have no os.environ
# fallback, and build_prices even errors if the file is missing). On Render the
# keys arrive as environment variables and there is no .env file, so write one
# from them. .env is gitignored and the commit step below only stages *_data.js,
# so this never reaches git. OPENAI_API_KEY and GITHUB_TOKEN are deliberately
# NOT written here (no OpenAI builder runs; the token is used only for git auth).
: > .env
for k in FINNHUB_API_KEY QUIVERQUANT_API_KEY CONGRESS_API_KEY FRED_API_KEY FEC_API_KEY \
         CENSUS_API_KEY LEGISCAN_API_KEY OPENSTATES_API_KEY EIA_API_KEY BEA_API_KEY \
         BLS_API_KEY SECAPI_IO_KEY; do
  v="$(printenv "$k" 2>/dev/null || true)"
  [ -n "$v" ] && printf '%s=%s\n' "$k" "$v" >> .env
done
log "synthesized .env with $(wc -l < .env | tr -d ' ') data-source keys"

# ---- 1) FREE / CHEAP builders (order matters for the aggregators) ------------
run "prices (Finnhub)"            webapp/build_prices.py
run "congress bills + laws"       congress_bills.py
run "member bills"                webapp/build_member_bills.py
run "congress trades (QuiverQuant bulk)" webapp/build_trades.py
run "politician P&L"              politician_performance.py
run "recession signals"           recession_signals.py
run "FEC"                         webapp/build_fec.py
run "USASpending"                 webapp/build_usaspending.py
run "LegiScan"                    webapp/build_legiscan.py
run "OpenStates"                  webapp/build_openstates.py
run "state economics (FRED)"      webapp/build_states.py
run "census"                      webapp/build_census.py
run "hedge fund (OFR)"            webapp/build_hedgefund.py
run "data centers (EIA/Census)"   webapp/build_datacenters.py
run "aggregate -> TF_DATA"        webapp/build_data.py
run "Money Trail engine (free)"   webapp/build_money_trail.py            # no --gpt: zero OpenAI spend
run "export -> private_data"      scripts/extract_data_to_json.py

# ---- 2) commit + push the refreshed data to main ----------------------------
git add \
  webapp/js/prices_data.js webapp/js/data.js webapp/js/member_bills.js \
  webapp/js/presidential_data.js webapp/js/money_trail_data.js \
  webapp/js/fec_data.js webapp/js/usaspending_data.js webapp/js/legiscan_data.js \
  webapp/js/openstates_data.js webapp/js/states_data.js \
  webapp/js/hedgefund_data.js webapp/js/datacenters_data.js \
  congress_bills.json politician_performance.json recession_signals_output.json \
  congress_trade_counts.json 2>/dev/null

if git diff --cached --quiet; then
  log "no data changes this run; nothing to commit"
  exit 0
fi

if [ -z "$GITHUB_TOKEN" ]; then
  log "GITHUB_TOKEN not set; refreshed locally but cannot push. Exiting."
  exit 0
fi

# Set the authenticated push remote without echoing the token.
git remote set-url origin "https://x-access-token:${GITHUB_TOKEN}@github.com/${REPO}.git" >/dev/null 2>&1
git commit -q -m "Auto refresh: live data $(date -u +%Y-%m-%dT%H:%MZ) [skip ci]"
if git push origin HEAD:main >/dev/null 2>&1; then
  log "pushed refreshed data to main; web service will autoDeploy"
else
  log "push failed (auth or non-fast-forward); data refreshed but not pushed"
fi
# scrub the token out of the remote URL so it cannot linger in the checkout
git remote set-url origin "https://github.com/${REPO}.git" >/dev/null 2>&1
log "done"
