# Part 3 — System Architecture

## 3.1 High-level topology

ThinkFree separates a heavy **offline data/intelligence pipeline** (runs on a
build machine or schedule, in Python) from a **lightweight delivery layer** (what
the user touches). The browser receives only a UI shell; everything sensitive
stays server-side in the hosted configuration.

```
                         OFFLINE (build machine / schedule)
  +-------------------------------------------------------------------------+
  |  External APIs & gov disclosures                                        |
  |  (Finnhub, LegiScan, Open States, FEC, Census, BEA, BLS, SEC EDGAR,     |
  |   USASpending, QuiverQuant, OpenAI, LittleSis dumps, Yahoo/RSS)         |
  |        |                                                                |
  |        v                                                                |
  |  webapp/build_*.py  ---->  webapp/js/*_data.js   (window.NAME = {...})  |
  |        |                                                                |
  |  13-phase intelligence pipeline (root .py)  ---->  enriched JSON        |
  |        |                                                                |
  |  agents/*.py verification gates  ---->  pass/fail + audit logs          |
  |        |                                                                |
  |  scripts/extract_data_to_json.py  ---->  private_data/*.json + manifest |
  +-------------------------------------------------------------------------+
                                   |
                                   v
                         ONLINE (hosted)
  +-------------------------------------------------------------------------+
  |  FastAPI (server/)                                                      |
  |   - /api/auth/*   bcrypt + JWT httpOnly cookie + SQLite users.db        |
  |   - /api/data/*   gated datasets from private_data/ (per-tier cadence)  |
  |   - serves the static shell (css/js) but hard-404s any *_data.js path   |
  |   - security headers, HTTPS redirect, CORS, rate limiting              |
  +-------------------------------------------------------------------------+
                                   |
                                   v
  +-------------------------------------------------------------------------+
  |  Browser: webapp/ shell                                                 |
  |   boot.js -> detect mode -> auth.js gate -> app.js render               |
  |   feature modules (influenceweb, congress, predictions, scores, ...)    |
  +-------------------------------------------------------------------------+
```

## 3.2 The two delivery modes

The same `webapp/` shell runs in two modes with no code fork. `boot.js` decides
at startup by probing `GET /api/healthz`.

| Concern | Static mode | Server mode |
|---------|-------------|-------------|
| Trigger | No backend responds to `/api/healthz` | Backend responds with `{ready:true}` |
| Auth | localStorage + `cyrb53` soft gate | `/api/auth/*`, bcrypt + JWT cookie |
| Data | `js/*_data.js` injected directly | `/api/data/bundle|state|live` fetched, then `Object.assign(window, json)` |
| Secrets | none present (data is public) | keys/Python/data never sent to browser |
| Use case | local dev / offline demo | secure beta + production |

The hard ordering constraint: logic modules read their data at eval time, so
`boot.js` injects data globals *before* the logic scripts in both modes.

## 3.3 Request lifecycle (server mode)

```
1. Browser GET /                -> FastAPI serves index.html (the shell)
2. boot.js GET /api/healthz     -> {ready, mode}  => mode = "server"
3. boot.js GET /api/auth/me     -> 401 (not logged in)  => show gate
4. User submits login           -> POST /api/auth/login
                                   bcrypt verify -> set httpOnly JWT cookie
5. boot.ensureAppLoaded()       -> GET /api/data/bundle (+ /api/data/live)
                                   Object.assign(window, json); inject logic JS
6. app.js init()                -> render Dashboard (window.TF.home)
7. State Legislature view       -> GET /api/data/state (lazy)
8. Periodic refresh (per tier)  -> GET /api/data/live (429 / {paused} handled)
```

## 3.4 The 13-phase intelligence pipeline (logical view)

The blueprint defines a 13-phase roadmap. The pipeline is orchestrated by
`controller.py` (Phase 12) and culminates in `chef_gpt.py` (Phase 11), which only
runs after the upstream phases complete for a cycle.

| Phase | Name | Primary file(s) | Status per blueprint |
|------:|------|-----------------|----------------------|
| 1 | User personalization | `Profile/`, quiz in `auth.js` | Complete |
| 2 | Financial data scraping | `Z_Old_versions/News/`, RSS sources | Complete |
| 3 | Data extraction & structuring | `phase3_extraction.py` | Partial |
| 4 | Article scoring & clustering | `phase4_clustering.py`, `Profile/article_clustering.py` | Mostly complete |
| 5 | GPT summarization & validation | `Profile/GPT_article_clustering_summary.py` | Partial |
| 6 | Economic reasoning engine | `GPT_Economy/economic_engine.py`, `Reasoning_Report.py` | Partial (FAISS) |
| 6.5 | Political intelligence | `congress_bills.py`, `politician_performance.py`, `webapp/build_*` | Built (web) |
| 7 | Historical correlation | `historical_correlation.py` | Implemented |
| 8 | Opportunity quantification | `opportunity_score.py`, `quantlib_metrics.py` | Implemented |
| 9 | Backtesting engine | `Module_2_Technical_Analysis/phase_4_backtrader.py` | Active dev |
| 10 | Portfolio tracker & dashboard | `portfolio_tracker.py`, `dashboard/app.py` | Prototype |
| 11 | Chef GPT (final layer) | `chef_gpt.py` | Implemented |
| 12 | Control logic / human-in-the-loop | `controller.py` | Implemented |
| 13 | Recession indicator engine | `recession_signals.py` | Implemented |

Each phase is documented function-by-function in Parts 7A and 7B.

## 3.5 Verification-agent layer (cross-cutting)

A set of independent Python agents validate concerns at pipeline checkpoints and
return a pass/fail verdict; a failed verdict halts the step and is logged. These
are documented in Part 8. The blueprint also defines additional planned agents
(financial-fact, economic-reasoning, recession-signal) not yet implemented; the
gap is noted in Part 8.

## 3.6 The AI sub-agent layer (development-time)

Separate from the runtime Python agents, a **Claude Code sub-agent** assists
development: an attacker-perspective cybersecurity reviewer defined in
`.claude/agents/cybersecurity-agent.md` and trained on an extracted knowledge
base in `.claude/agents/cybersecurity-kb/`. This is documented in full in Part 9.

## 3.7 Repository map

```
ThinkFree-main/
  CLAUDE.md                  # the canonical blueprint
  DEPLOY.md                  # hosting + security guide
  requirements.txt           # pipeline Python deps
  controller.py              # Phase 12 orchestrator
  chef_gpt.py                # Phase 11 final briefing
  recession_signals.py       # Phase 13
  opportunity_score.py / quantlib_metrics.py   # Phase 8
  historical_correlation.py  # Phase 7
  phase3_extraction.py / phase4_clustering.py  # Phases 3-4
  portfolio_tracker.py       # Phase 10
  congress_bills.py / politician_performance.py # Phase 6.5
  validate_env.py            # env/config validation
  agents/                    # runtime verification agents (Part 8)
  GPT_Economy/               # economic reasoning engine (Part 7B)
  Profile/                   # personalization + clustering (Part 7B)
  Module_2_Technical_Analysis/  # TA + backtesting (Part 7B)
  server/                    # FastAPI backend (Part 5)
  scripts/extract_data_to_json.py  # data extractor (Part 4)
  webapp/
    index.html               # the shell
    css/styles.css
    js/                      # boot/auth/app + feature modules + *_data.js (Parts 6A/6B/12)
    build_*.py               # offline data build scripts (Part 4)
  private_data/              # gitignored gated datasets (server mode)
  dashboard/app.py           # legacy Streamlit prototype (kept)
  iphone-app/                # SwiftUI client (not build-verified)
  .claude/agents/            # the cybersecurity sub-agent + KB (Part 9)
```
