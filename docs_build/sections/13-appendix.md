# Part 13 — Appendices

## Appendix A — Project file index (non-vendored)

### Backend (`server/`)
| File | Lines | Role |
|------|------:|------|
| `main.py` | 110 | App, middleware, static serving, health, data-file blocking |
| `auth.py` | 288 | bcrypt + JWT auth, signup/login/logout/profile/a11y, rate limiting |
| `data.py` | 111 | Gated `/api/data/*` (bundle/state/live), per-tier cadence, market pause |
| `db.py` | 107 | stdlib SQLite user store, JWT revocation column |
| `config.py` | 63 | Env loading, tiers, secret-placeholder guard |

### Runtime verification agents (`agents/`)
| File | Lines | Role |
|------|------:|------|
| `data_quality.py` | 449 | Data-integrity gate after scraping/extraction |
| `security_audit.py` | 403 | Secret/CVE/static-analysis gate (CI-blocking) |
| `strategy_audit.py` | 277 | Backtest sanity gate (lookahead, Sharpe, drawdown) |
| `verification_runner.py` | 161 | Orchestrates the agents at checkpoints |

### Core intelligence pipeline (repo root)
| File | Lines | Phase |
|------|------:|-------|
| `controller.py` | 451 | 12 — orchestration / human-in-the-loop |
| `chef_gpt.py` | 469 | 11 — final intelligence briefing |
| `recession_signals.py` | 429 | 13 — recession risk score |
| `congress_bills.py` | 409 | 6.5 — political intelligence |
| `phase4_clustering.py` | 383 | 4 — clustering |
| `portfolio_tracker.py` | 334 | 10 — mock portfolio |
| `phase3_extraction.py` | 333 | 3 — extraction |
| `historical_correlation.py` | 400 | 7 — historical analogs |
| `quantlib_metrics.py` | 326 | 8 — quant metrics |
| `opportunity_score.py` | 314 | 8 — opportunity scoring |
| `politician_performance.py` | 290 | 6.5 — politician tracking |
| `validate_env.py` | 249 | env/config validation |

### Supporting engines
| File | Lines | Area |
|------|------:|------|
| `Module_2_Technical_Analysis/phase_4_backtrader.py` | 1149 | Backtesting (Phase 9) |
| `GPT_Economy/Reasoning_Report.py` | 200 | Economic reasoning report |
| `Profile/GPT_article_clustering_summary.py` | 187 | GPT cluster summaries |
| `Module_2_Technical_Analysis/ta_analysis.py` | 165 | Technical indicators |
| `Module_2_Technical_Analysis/pipeline_alpha.py` | 158 | Alpha pipeline |
| `Module_2_Technical_Analysis/phase_3_signal.py` | 142 | Signal generation |
| `Profile/article_clustering.py` | 118 | Embedding clustering |
| `GPT_Economy/economic_engine.py` | 101 | FAISS economic engine |

### Offline data build scripts (`webapp/`)
`build_data.py` (824), `build_legiscan.py` (280), `build_secbulk.py` (164),
`build_influence.py` (174), `build_states.py` (155), `build_fec.py` (153),
`build_usaspending.py` (148), `build_prices.py` (145), `build_relationships.py`
(146), `build_nonprofits.py` (139), `build_openstates.py` (133),
`build_census.py` (131), `build_quant.py` (121), `build_sec.py` (119),
`build_bea.py` (103), `build_bls.py` (98), `fetch_politician_photos.py` (83),
`build_sp500.py` (81), `build_member_bills.py` (74), `minify_data.py` (60),
`scripts/extract_data_to_json.py` (78).

### Frontend (`webapp/js/`)
| File | Lines | Role |
|------|------:|------|
| `app.js` | 1847 | Router, page rendering, modals, search, refresh |
| `influenceweb.js` | 1201 | Interactive relationship graph |
| `auth.js` | 594 | Dual-mode gate, quiz, tiers, signup integrity |
| `congress.js` | 582 | Political-intelligence views |
| `genimpact.js` | 337 | Generational-impact scoring |
| `predictions.js` | 323 | Predictive market signals |
| `scoreinfo.js` | 302 | Progressive score explanations |
| `scores.js` | 211 | Score display |
| `boot.js` | 148 | Mode detection + script injection |
| `glossary.js` | 95 | Jargon annotation |
| `*_data.js` | (generated) | 17 datasets (Part 12) |

### Other
| Path | Role |
|------|------|
| `dashboard/app.py` (3624) | Legacy Streamlit prototype (kept, untouched) |
| `iphone-app/` | SwiftUI client reusing web data (not build-verified) |
| `.claude/agents/cybersecurity-agent.md` + `cybersecurity-kb/` | The AI sub-agent + its training (Part 9) |
| `CLAUDE.md` | The canonical blueprint |
| `DEPLOY.md` | Hosting + security guide |

## Appendix B — Environment variables

| Variable | Used by | Purpose |
|----------|---------|---------|
| `TF_SECRET_KEY` | backend | JWT signing secret (48+ random chars) |
| `TF_BETA_KEY` | backend | Closed-beta invite key |
| `TF_PRODUCTION` | backend | 1 in prod (Secure cookies, HSTS, HTTPS redirect) |
| `TF_ALLOWED_ORIGINS` | backend | CORS allow-list |
| `TF_SESSION_TTL_SECONDS` | backend | Session lifetime |
| `LEGISCAN_API_KEY` | `build_legiscan.py` | State legislation |
| `OPENSTATES_API_KEY` | `build_openstates.py` | State legislators |
| `FINNHUB_API_KEY` | `build_prices.py` | Market prices |
| `FEC_API_KEY` | `build_fec.py` | Campaign finance |
| `CENSUS_API_KEY` | `build_census.py` | Census data |
| `BEA_API_KEY` | `build_bea.py` | Economic accounts |
| `BLS_API_KEY` | `build_bls.py` | Labor statistics |
| `OPENAI_API_KEY` | pipeline / news intel | GPT calls |
| `FRED_API_KEY` | recession signals | Macro series |

(See Part 4 for the authoritative per-script mapping.)

## Appendix C — Glossary

- **Blueprint / `CLAUDE.md`** — the committed project charter that governs mission, framing, roadmap, and constraints.
- **Chef GPT** — the final intelligence layer (Phase 11) that merges all upstream outputs into one plain-English briefing.
- **cyrb53** — a fast non-cryptographic hash used only for the soft static-mode gate; never a real security boundary.
- **Dual-mode** — the front end runs identically as a static site or behind the FastAPI backend, decided at runtime by `boot.js`.
- **Eight-question framework** — the eight questions every major analysis must answer (Part 1).
- **IDOR** — Insecure Direct Object Reference; accessing another user's data by changing an identifier. Prevented by server-side per-user scoping.
- **Intelligence report** — the platform's output. ThinkFree never emits a trade order.
- **Political-intelligence framing rule** — all such output describes timing relationships between public disclosures and market events and never alleges wrongdoing.
- **RLS (Row-Level Security)** — the database-level per-user data isolation concept from the source material; in ThinkFree's FastAPI/SQLite stack it is implemented as server-side authorization on every endpoint.
- **Tier** — a subscription level controlling data-refresh cadence (e.g. beta = 15-minute refresh), enforced server-side.
- **Verification agent** — a runtime Python gate that returns pass/fail at a pipeline checkpoint (Part 8), distinct from the development-time AI sub-agent (Part 9).

## Appendix D — Document provenance

This document was compiled from a direct reading of the source tree (every file
listed in Appendix A), the canonical blueprint (`CLAUDE.md`), the deployment guide
(`DEPLOY.md`), and the security knowledge base in `.claude/agents/cybersecurity-kb/`.
The code-reference parts (4, 5, 6A, 6B, 7A, 7B, 8, 12) were produced by reading the
actual source and reproducing real signatures, formulas, and patterns; where a
subsystem could not be executed end-to-end in the build environment, that is
stated rather than asserted as verified.
