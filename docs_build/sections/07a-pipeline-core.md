# Part 7A — Core Intelligence Pipeline (Phases 3-13)

This document is an exhaustive technical reference for every Python module in the ThinkFree Finance core intelligence pipeline. Each file section documents the module's role, its place in the 13-phase roadmap, and every function it contains — including exact signatures, parameters, return values, step-by-step behavior, file I/O, external libraries used, GPT/LLM prompts, and scoring formulas reproduced verbatim from the source code.

---

## Table of Contents

1. [controller.py — Phase 12: Pipeline Orchestration](#controllerpy--phase-12-pipeline-orchestration)
2. [chef_gpt.py — Phase 11: Intelligence Synthesis](#chef_gptpy--phase-11-intelligence-synthesis)
3. [recession_signals.py — Phase 13: Recession Signals Engine](#recession_signalspy--phase-13-recession-signals-engine)
4. [opportunity_score.py — Phase 8.9: Opportunity Scoring Engine](#opportunity_scorepy--phase-89-opportunity-scoring-engine)
5. [quantlib_metrics.py — Phase 8.7: QuantLib Risk Metrics](#quantlib_metricspy--phase-87-quantlib-risk-metrics)
6. [historical_correlation.py — Phase 7: Historical Correlation Engine](#historical_correlationpy--phase-7-historical-correlation-engine)
7. [phase3_extraction.py — Phase 3: NLP Data Extraction](#phase3_extractionpy--phase-3-nlp-data-extraction)
8. [phase4_clustering.py — Phase 4: Article Scoring & Clustering](#phase4_clusteringpy--phase-4-article-scoring--clustering)
9. [portfolio_tracker.py — Phase 10: Portfolio Tracker](#portfolio_trackerpy--phase-10-portfolio-tracker)
10. [congress_bills.py — Phase 6.5 Supplement: Congress Bills Intelligence](#congress_billspy--phase-65-supplement-congress-bills-intelligence)
11. [politician_performance.py — Phase 6.5 Supplement: Politician Trading Performance](#politician_performancepy--phase-65-supplement-politician-trading-performance)

---

## controller.py — Phase 12: Pipeline Orchestration

**File:** `controller.py`
**Phase:** 12 — Controller / Human-in-the-Loop
**Role:** The master entry point for the entire ThinkFree pipeline. Defines the ordered sequence of all pipeline phases as a list of step descriptors, then runs them in sequence (or selectively) via subprocess calls. Tracks pass/fail state per phase in a JSON state file. Runs security and data-quality audit checkpoints between phases. Provides a full CLI with flags for single-phase execution, resume-from-phase, chef-only mode, and audit-only mode.

**Key constants:**

| Name | Value | Purpose |
|---|---|---|
| `BASE_DIR` | `Path(__file__).parent` | Root of the project |
| `STATE_FILE` | `BASE_DIR / "pipeline_state.json"` | Persisted run state |

**Pipeline definition (`PIPELINE`):** A module-level list of dicts (`controller.py:43`). Each dict has:

| Key | Type | Meaning |
|---|---|---|
| `id` | `int` or `str` | Phase identifier (e.g. `1`, `"6.5"`, `"8.7"`) |
| `name` | `str` | Human-readable phase name |
| `description` | `str` | One-line description shown during run |
| `script` | `Path` | Absolute path to the phase script |
| `output_check` | `Path` | Path whose existence signals "phase already ran" |
| `skip_if_output_exists` | `bool` | If True and output exists, skip silently |
| `required` | `bool` | If True and the phase fails, the pipeline halts |
| `audit_checkpoint` | `str or None` | Which verification agent to run after this phase |

**Phases in pipeline order (controller.py:43–203):**

| Phase ID | Name | Required | Audit Checkpoint |
|---|---|---|---|
| 1 | User Personalization | False | None |
| 2 | News Scraping | True | `"data"` |
| 3 | Data Extraction & Enrichment | True | `"data"` |
| 4 | Article Clustering | True | None |
| 5 | GPT Summarization | True | None |
| 6 | Economic Reasoning Engine | True | None |
| 6.5 | Political Intelligence | False | None |
| 7 | Historical Correlation Engine | False | None |
| 8 | Technical Analysis | False | None |
| 8.5 | Signal Generation | False | None |
| 8.7 | QuantLib Risk Metrics | False | None |
| 8.9 | Opportunity Scoring | False | None |
| 9 | Backtesting Engine | False | None |
| 13 | Recession Signals | False | None |
| 10 | Portfolio Tracker | False | None |
| 11 | Chef GPT — Intelligence Synthesis | True | None |

---

### `log(msg: str) -> None`

**Location:** `controller.py:211`

**Parameters:**
- `msg` (`str`): The message to print.

**Returns:** `None`

**Behavior:** Prepends an `HH:MM:SS` timestamp to `msg` and prints to stdout with `flush=True`.

**External libs:** `datetime`

---

### `output_exists(step: dict) -> bool`

**Location:** `controller.py:216`

**Parameters:**
- `step` (`dict`): A pipeline step descriptor dict from `PIPELINE`.

**Returns:** `bool` — `True` if the step's `output_check` path exists on disk.

**Behavior:**
1. Reads `step.get("output_check")`. If `None`, returns `False`.
2. Returns `Path(check).exists()`.

**External libs:** `pathlib.Path`

---

### `load_state() -> dict`

**Location:** `controller.py:223`

**Parameters:** None

**Returns:** `dict` with keys `completed` (list), `failed` (list), `last_run` (str or None).

**Behavior:**
1. Checks if `STATE_FILE` (`pipeline_state.json`) exists.
2. If yes, opens and parses it as JSON.
3. If file missing or parse error, returns `{"completed": [], "failed": [], "last_run": None}`.

**Files read:** `pipeline_state.json`
**External libs:** `json`, `pathlib`

---

### `save_state(state: dict) -> None`

**Location:** `controller.py:233`

**Parameters:**
- `state` (`dict`): Current pipeline state dict.

**Returns:** `None`

**Behavior:**
1. Sets `state["last_run"]` to current UTC ISO timestamp with `"Z"` suffix.
2. Writes state dict to `pipeline_state.json` as pretty-printed JSON (indent=2).

**Files written:** `pipeline_state.json`
**External libs:** `json`, `datetime`

---

### `run_phase(step: dict, state: dict) -> bool`

**Location:** `controller.py:239`

**Parameters:**
- `step` (`dict`): A pipeline step descriptor dict from `PIPELINE`.
- `state` (`dict`): Current pipeline state dict (mutated in-place).

**Returns:** `bool` — `True` if the phase succeeded or was skipped, `False` if it failed.

**Behavior (step by step):**
1. Extracts `phase_id = str(step["id"])` and `script = Path(step["script"])`.
2. Prints a formatted header banner showing phase id, name, and description.
3. If the script file does not exist on disk, logs `[SKIP] Script not found` and returns `True` (non-blocking).
4. If `skip_if_output_exists` is `True` and `output_exists(step)` is `True`, logs skip and returns `True`.
5. Runs the script using `subprocess.run([sys.executable, str(script)], cwd=str(BASE_DIR), capture_output=False)`. Output streams to the terminal directly.
6. Checks `result.returncode == 0` for success.
7. If success: appends `phase_id` to `state["completed"]`, removes from `state["failed"]` if present.
8. If failure: appends `phase_id` to `state["failed"]`.
9. Calls `save_state(state)`.
10. Returns success boolean.

**Files written:** `pipeline_state.json` (via `save_state`)
**External libs:** `subprocess`, `sys`, `pathlib`

---

### `run_audit_checkpoint(agent: str) -> bool`

**Location:** `controller.py:280`

**Parameters:**
- `agent` (`str`): The audit agent name (e.g. `"security"`, `"data"`).

**Returns:** `bool` — `True` if passed or agent unavailable, `False` if flagged issues.

**Behavior:**
1. Checks for `agents/verification_runner.py`. If not found, returns `True` (non-blocking).
2. Runs `verification_runner.py --phase <agent> --quiet` via `subprocess.run`.
3. If returncode != 0, logs a warning and points to `pipeline_audit.json`. Returns `False`.
4. If returncode == 0, logs pass. Returns `True`.

**External libs:** `subprocess`, `sys`, `pathlib`

---

### `check_env() -> bool`

**Location:** `controller.py:299`

**Parameters:** None

**Returns:** `bool` — `True` if all critical API keys are present, `False` if any are missing.

**Behavior:**
1. Calls `load_dotenv()` to load `.env` file.
2. Checks for `OPENAI_API_KEY`, `FINNHUB_API_KEY`, `QUIVERQUANT_API_KEY` via `os.getenv`.
3. Prints a warning list for any missing keys.
4. Returns `False` if any warnings; `True` if all present.

**External libs:** `python-dotenv`, `os`

---

### `parse_args() -> argparse.Namespace`

**Location:** `controller.py:325`

**Parameters:** None

**Returns:** `argparse.Namespace` with attributes:
- `phase` (`str | None`): Run a single specific phase by ID.
- `from_phase` (`str | None`): Resume from this phase ID onward.
- `chef_only` (`bool`): Run only Chef GPT.
- `skip_scraping` (`bool`): Skip Phase 2.
- `list` (`bool`): List all phases and exit.
- `audit` (`bool`): Run verification audit only and exit.
- `skip_audit` (`bool`): Skip security/data quality checkpoints.

**External libs:** `argparse`

---

### `list_phases() -> None`

**Location:** `controller.py:348`

**Parameters:** None

**Returns:** `None`

**Behavior:** Iterates over `PIPELINE`, printing each phase's id and name. If the phase's `output_check` path exists, prints a checkmark; otherwise blank.

---

### `main() -> None`

**Location:** `controller.py:358`

**Parameters:** None (reads `sys.argv` via `parse_args`)

**Returns:** `None`

**Behavior (full run flow):**
1. Calls `parse_args()` and `list_phases()` if `--list`.
2. Prints startup banner.
3. Calls `check_env()` (non-blocking warning only).
4. Calls `load_state()`.
5. If `--audit`: imports and calls `run_all_agents(verbose=True)` from `agents.verification_runner`; exits with code 0 (PASS) or 1 (FAIL).
6. If `--chef-only`: finds Phase 11 step, runs it, exits.
7. If `--phase`: finds the matching step, runs it, exits.
8. Determines `steps_to_run`: full `PIPELINE` or sliced from `--from-phase` index.
9. Runs security audit checkpoint (unless `--skip-audit`).
10. Iterates `steps_to_run`:
    - If `--skip-scraping` and phase is 2, skips.
    - Calls `run_phase(step, state)`.
    - If success and `audit_checkpoint` is set (and not `--skip-audit`), calls `run_audit_checkpoint(checkpoint)`.
    - If phase failed and `required=True`, logs error, sets `failed_required=True`, breaks loop.
11. Prints final summary: either "completed with errors" or "Pipeline complete" with the path to `intelligence_report.json` and the Streamlit launch command.

**Files written:** `pipeline_state.json` (via `run_phase` → `save_state`)

---

## chef_gpt.py — Phase 11: Intelligence Synthesis

**File:** `chef_gpt.py`
**Phase:** 11 — Chef GPT Final Intelligence Layer
**Role:** The final synthesis layer. Reads every prior phase's output JSON, assembles them into a single structured prompt, sends it to GPT-4o (or configured model), and writes the plain-English intelligence report. Implements the eight-question framework as the core analytical structure. Output is the final deliverable: `intelligence_report.json`.

**Key constants:**

| Name | Value |
|---|---|
| `BASE_DIR` | `Path(__file__).parent` |
| `OUTPUT_PATH` | `BASE_DIR / "intelligence_report.json"` |
| `OPENAI_MODEL` | `os.getenv("THINKFREE_MODEL", "gpt-4o")` |

**LLM used:** OpenAI `gpt-4o` (or override via `THINKFREE_MODEL` env var)
**LLM temperature:** `0.3`
**LLM response format:** `{"type": "json_object"}`

---

### `load_json(path: Path, default: Any = None) -> Any`

**Location:** `chef_gpt.py:44`

**Parameters:**
- `path` (`Path`): Filesystem path to a JSON file.
- `default` (`Any`): Value returned if file is missing or malformed. Default: `None`.

**Returns:** Parsed JSON value, or `default`.

**Behavior:** Opens `path` in UTF-8 mode, calls `json.load`. On `FileNotFoundError` or `json.JSONDecodeError`, silently returns `default`.

**External libs:** `json`, `pathlib`

---

### `assemble_inputs() -> dict`

**Location:** `chef_gpt.py:56`

**Parameters:** None

**Returns:** `dict` with keys mapping data source names to their loaded contents (or empty defaults).

**Behavior:** Calls `load_json` for each of the following files:

| Key | File path | Default |
|---|---|---|
| `user_profile` | `user_profile.json` | `{}` |
| `economic_reasoning` | `news_output/economic_reasoning_summary.json` | `{}` |
| `sector_summaries` | `news_output/sector_summaries.json` | `{}` |
| `technical_signals` | `Module_2_Technical_Analysis/signal_output_phase3.json` | `[]` |
| `backtest_metrics` | `Module_2_Technical_Analysis/results_run/summary_metrics.json` | `{}` |
| `recession_data` | `recession_signals_output.json` | `{}` |
| `political_trades` | `GPT_Economy/Intelligence_layer (IN PROGRESS)/intelligence_output.json` | `{}` |
| `historical_parallels` | `historical_parallels.json` | `{}` |
| `opportunity_scores` | `opportunity_scores.json` | `{}` |
| `quantlib_metrics` | `quantlib_metrics.json` | `{}` |

**Returns** the assembled dict directly. Missing files silently become empty defaults — the pipeline tolerates partial data.

---

### `build_prompt(inputs: dict) -> str`

**Location:** `chef_gpt.py:106`

**Parameters:**
- `inputs` (`dict`): The dict returned by `assemble_inputs()`.

**Returns:** `str` — the complete GPT prompt (typically 2,000–5,000 characters).

**Behavior (section by section):**

**Profile section (`chef_gpt.py:107–128`):**
Extracts `age`, `risk_tolerance`, `investment_goal`, `timeline`, `emotional_response` from `inputs["user_profile"]` with string defaults. Builds:
```
"The reader is {age} years old with a {risk} risk tolerance.
Their investment goal is {goal} over a {timeline} horizon.
When markets drop, they tend to {emotional}."
```

**Economic summary section (`chef_gpt.py:131–137`):**
Reads `economic_reasoning.summary`, `bullish_sectors`, `bearish_sectors`. Builds:
```
"{econ_summary}\n\nBullish sectors: {...}\nBearish sectors: {...}"
```

**Sector text section (`chef_gpt.py:139–145`):**
Iterates over up to 5 entries in `sector_summaries`. For each, takes the `sector_summary` field truncated at 400 characters.

**Technical signals section (`chef_gpt.py:147–156`):**
Filters signals for `final_signal == "BUY"` (top 3) and `"SELL"` (top 3). Formats as:
```
"{ticker}: BUY signal (confidence: {confidence_score})"
"{ticker}: SELL signal (confidence: {confidence_score})"
```
Fallback: `"No strong buy or sell signals detected today."`

**Backtest section (`chef_gpt.py:158–166`):**
If `backtest_metrics` has data:
```
"Historical backtest on current signals: CAGR {CAGR %}%, Sharpe ratio {Sharpe}, Max drawdown {Max Drawdown %}%."
```

**Recession section (`chef_gpt.py:168–182`):**
Reads `recession_risk.score`, `recession_risk.label`, `recession_risk.plain_english_summary`, `real_world_impact.{mortgages,credit_cards,jobs,savings}`. Formats a multi-line block.

**Political intelligence section (`chef_gpt.py:184–208`):**
If `political_trades` dict has `congressional_trade_links` or `housing_trades`:
- Iterates up to 5 `trade_links` items: `"{ticker}: {events[0][:200]}"`
- Iterates up to 3 `housing_trades`: `"{rep} — {tx} {ticker}"`
- Appends mandatory disclaimer.

**Historical parallels section (`chef_gpt.py:210–244`):**
If `historical_parallels` is non-empty, iterates up to 3 parallels, each showing event type, period name/dates, narrative (400 chars), winners and losers with return percentages.

**Opportunity scores section (`chef_gpt.py:246–260`):**
Reads `sector_opportunities` (top 5) and `ticker_opportunities` (BUY signals, top 3). Formats:
```
"Top scoring sectors: {sector} ({score}/10 {emoji}), ..."
"Top buy-signal tickers: {ticker} ({score}/10), ..."
"Recession discount applied: {recession_risk_used}/10"
```

**QuantLib section (`chef_gpt.py:308–326`):**
If `quantlib_metrics.ticker_metrics` has data, takes top 5 and formats:
```
"- {ticker} ({signal}): P(+5% in 1mo)={prob:.0f}%  Vol={vol:.0f}%/yr  Daily VaR(95%)={var95:.2f}%  Kelly={kelly:.1f}% of portfolio"
```

**Output schema (`chef_gpt.py:263–305`):** A JSON template (serialized as string) defining the exact structure GPT must return:

```json
{
  "generated_at": "<ISO timestamp>",
  "profile_match": "<one sentence>",
  "headline": "<one compelling sentence>",
  "market_overview": {
    "what_happened": "<2-3 sentences, plain English>",
    "why_it_happened": "<2-3 sentences>",
    "who_benefits": "<list>",
    "who_is_hurt": "<list>"
  },
  "consumer_impact": {
    "summary": "<2-3 sentences>",
    "rent_and_housing": "<one sentence>",
    "groceries_and_gas": "<one sentence>",
    "credit_cards_and_loans": "<one sentence>",
    "jobs_and_income": "<one sentence>"
  },
  "sector_outlook": {
    "bullish": ["<sector>"],
    "bearish": ["<sector>"],
    "why": "<one paragraph>"
  },
  "political_intelligence": {
    "summary": "<2-3 sentences>",
    "notable_events": ["<event 1>", "<event 2>"],
    "disclaimer": "This analysis identifies timing relationships..."
  },
  "market_signals": {
    "summary": "<plain English>",
    "top_opportunities": ["<ticker: plain English>"],
    "caution_flags": ["<ticker: plain English>"]
  },
  "historical_context": "<2-3 sentences>",
  "recession_risk": {
    "score": "<0-10>",
    "label": "<Low/Moderate/Elevated/High/Very High>",
    "plain_english": "<one paragraph>",
    "what_to_watch": "<one sentence>"
  },
  "what_it_means_for_you": "<2-3 sentences tailored to user>",
  "bottom_line": "<one sentence>",
  "disclaimer": "ThinkFree provides financial intelligence..."
}
```

**GPT system prompt (`chef_gpt.py:428–436`):**
```
"You are ThinkFree's AI financial analyst. You translate complex financial events
into plain English for everyday people. You always write at a level that someone
with no financial background can understand. You never use jargon without immediately
explaining it. You are informative, objective, and always honest about uncertainty."
```

**GPT user prompt instruction section (`chef_gpt.py:327–378`):** Includes the eight-question framework explicitly:
```
For every major event, apply the 8-question framework:
1. What happened? (plain facts)
2. Why did it happen? (economic cause, explained simply)
3. Who benefits? (specific groups, companies, sectors)
4. Who is negatively affected? (specific groups who may be hurt)
5. How does this affect consumers? (rent, groceries, gas, credit cards, loans, jobs)
6. How does this affect businesses? (which types win or lose)
7. How does this affect markets? (sectors, stocks, bonds — plain English)
8. What happened historically? (use the historical parallels data above — cite actual periods and measured returns)
```

---

### `run_chef_gpt() -> dict`

**Location:** `chef_gpt.py:387`

**Parameters:** None

**Returns:** `dict` — the parsed intelligence report.

**Behavior (step by step):**
1. Reads `OPENAI_API_KEY` from environment; raises `RuntimeError` if missing.
2. Calls `assemble_inputs()` to load all phase outputs.
3. Checks which data sources are non-empty and prints a summary list.
4. Calls `build_prompt(inputs)` to construct the full prompt.
5. Instantiates `OpenAI(api_key=api_key)` client.
6. Calls `client.chat.completions.create(model=OPENAI_MODEL, messages=[system_msg, user_msg], temperature=0.3, response_format={"type": "json_object"})`.
7. Extracts `response.choices[0].message.content`.
8. Parses JSON; on `json.JSONDecodeError` falls back to `{"raw_response": raw, "parse_error": "..."}`.
9. Stamps `generated_at` (UTC ISO), `data_sources_used`, and `user_profile` onto the report.
10. Writes to `intelligence_report.json` (UTF-8, indent=2).
11. Prints the headline and bottom_line fields to stdout.
12. Returns the report dict.

**Files read:** All 10 files listed in `assemble_inputs`.
**Files written:** `intelligence_report.json`
**External libs:** `openai`, `python-dotenv`, `json`

---

## recession_signals.py — Phase 13: Recession Signals Engine

**File:** `recession_signals.py`
**Phase:** 13 — Recession Indicator Engine
**Role:** Downloads live macroeconomic data from Yahoo Finance (yield curve via `^TNX`/`^IRX`, VIX via `^VIX`) and FRED (unemployment rate `UNRATE`, GDP growth `A191RL1Q225SBEA`). Computes a graduated 0–10 recession risk score from these indicators. Generates plain-English explanations of each factor and translates the score into personal-finance impact guidance. Output is `recession_signals_output.json`, consumed by both `opportunity_score.py` (for the recession discount) and `chef_gpt.py` (for the briefing).

**Key constants:**

| Name | Value |
|---|---|
| `BASE_DIR` | `Path(__file__).parent` |
| `OUTPUT_PATH` | `BASE_DIR / "recession_signals_output.json"` |

---

### `fetch_yield_curve() -> dict`

**Location:** `recession_signals.py:38`

**Parameters:** None

**Returns:** `dict` with keys `ten_year` (float|None), `three_month` (float|None), `spread` (float|None), `inverted` (bool).

**Behavior:**
1. Downloads `["^TNX", "^IRX"]` via `yf.download(period="3mo", interval="1d")`.
2. Extracts the most recent non-null Close value for each ticker.
3. `spread = ten_yr - three_mo` (10-year minus 3-month Treasury yield).
4. `inverted = spread < 0`.
5. Returns rounded values; on any exception returns all `None` with `inverted=False`.

**External libs:** `yfinance`, `pandas`

---

### `fetch_vix() -> dict`

**Location:** `recession_signals.py:67`

**Parameters:** None

**Returns:** `dict` with keys `vix` (float|None), `stress_level` (str).

**Behavior:**
1. Downloads `"^VIX"` via `yf.download(period="5d", interval="1d")`.
2. Extracts most recent Close value.
3. Maps VIX level to stress label:

| VIX range | Label |
|---|---|
| < 15 | `"Low — markets are calm"` |
| 15–19 | `"Normal — typical market conditions"` |
| 20–29 | `"Elevated — investors are nervous"` |
| 30–39 | `"High — significant market stress"` |
| ≥ 40 | `"Extreme — market panic conditions"` |

**External libs:** `yfinance`, `pandas`

---

### `_fetch_fred_csv(series_id: str) -> pd.Series | None`

**Location:** `recession_signals.py:96`

**Parameters:**
- `series_id` (`str`): FRED series identifier (e.g. `"UNRATE"`, `"A191RL1Q225SBEA"`).

**Returns:** `pd.Series` of numeric values with date index, or `None` on failure.

**Behavior:**
1. Constructs URL: `https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}`.
2. GETs with 10-second timeout.
3. Parses CSV with two columns: `["date", "value"]`.
4. Coerces `value` to numeric, drops NaN.
5. Returns the `value` Series.

**External libs:** `requests`, `pandas`, `io`

---

### `fetch_fred_indicators() -> dict`

**Location:** `recession_signals.py:115`

**Parameters:** None

**Returns:** `dict` with keys:
- `available` (bool)
- `unemployment_rate` (float|None)
- `unemployment_rising` (bool)
- `gdp_growth` (float|None)
- `gdp_negative` (bool)

**Behavior:**
1. First attempts public FRED CSV endpoint via `_fetch_fred_csv`:
   - `"UNRATE"` → unemployment rate (monthly %)
   - `"A191RL1Q225SBEA"` → real GDP growth rate (quarterly %)
2. Computes `unemployment_rising = unemployment > unemp_prev` (last two observations).
3. Computes `gdp_negative = gdp_growth < 0`.
4. If public CSV fails, checks `FRED_API_KEY` env var; if present, uses `fredapi.Fred` library for the same series.
5. If both fail, returns `{"available": False, ...}`.

**External libs:** `requests`, `pandas`, `fredapi` (optional), `python-dotenv`

---

### `compute_recession_score(yield_curve: dict, vix_data: dict, fred: dict) -> dict`

**Location:** `recession_signals.py:170`

**Parameters:**
- `yield_curve` (`dict`): Output of `fetch_yield_curve()`.
- `vix_data` (`dict`): Output of `fetch_vix()`.
- `fred` (`dict`): Output of `fetch_fred_indicators()`.

**Returns:** `dict` with keys `score` (float 0–10), `max_score` (10), `label` (str), `plain_english_summary` (str), `factors` (list[str]).

**Scoring formula (reproduced from `recession_signals.py:170–318`):**

The function accumulates `score` and `max_possible` as each indicator is evaluated. All partial scores use a `clamp(x, lo=0.0, hi=1.0)` helper.

**Component 1 — Yield Curve (up to 4 points, `recession_signals.py:186–218`):**

`max_possible += 4`

- **Inverted** (`spread < 0`): `curve_score = min(4.0, 4.0 × |spread| / 1.5)`
- **Not inverted**: `curve_risk = clamp((1.3 - spread) / 1.3)` — risk decays from 1.0 at spread=0 to 0.0 at spread≥1.3%; `curve_score = 4.0 × curve_risk`

Plain-English thresholds for non-inverted curve:
- `spread < 0.5%`: "very flat"
- `spread < 1.0%`: "flattening"
- `spread >= 1.0%`: "normal"

**Component 2 — VIX (up to 3 points, `recession_signals.py:221–234`):**

`max_possible += 3`

`vix_risk = clamp((vix - 14) / (40 - 14))`
`vix_contribution = 3.0 × vix_risk`

Zero risk at VIX ≤ 14; full 3 points at VIX ≥ 40.

**Component 3 — FRED indicators (up to 3 points, `recession_signals.py:237–287`):**

`max_possible += 3` (only if `fred["available"]`)

*GDP sub-component (up to 1.5 points):*
- `gdp_negative`: `+1.5`
- Otherwise: `gdp_risk = clamp((2.5 - gdp) / 2.5)`, `contribution = 1.5 × gdp_risk`

*Unemployment sub-component (up to 1.5 points):*
- `unemp_rising and unemp > 5.0%`: `+1.5`
- `unemp_rising and unemp ≤ 5.0%`: `+0.75`
- Stable: `level_risk = clamp((unemp - 4.5) / 2.0)`, `contribution = 0.75 × level_risk`

**Normalization (`recession_signals.py:289–294`):**
```
normalized = round((score / max_possible) × 10, 1)
```

**Label mapping (`recession_signals.py:296–310`):**

| Score | Label | Plain English |
|---|---|---|
| 0–2 | Low | "The economy shows no significant recession warning signs right now." |
| 2.1–4 | Moderate | "There are some warning signs but no imminent recession signal." |
| 4.1–6 | Elevated | "Multiple warning signs are flashing." |
| 6.1–8 | High | "Strong recession indicators present." |
| 8.1–10 | Very High | "Almost all recession warning signals are active." |

---

### `explain_real_world_impact(score: float, yield_inverted: bool, vix: float | None) -> dict`

**Location:** `recession_signals.py:325`

**Parameters:**
- `score` (`float`): The normalized recession risk score (0–10).
- `yield_inverted` (`bool`): Whether the yield curve is inverted.
- `vix` (`float | None`): Current VIX level.

**Returns:** `dict` with keys `mortgages`, `credit_cards`, `jobs`, `groceries_gas`, `savings` — each a plain-English string.

**Behavior:** Returns one of three pre-written impact dictionaries based on score thresholds:
- `score <= 3`: Low-risk messaging (stable, build emergency fund)
- `score <= 6`: Elevated-risk messaging (consider locking in fixed rate, pay down debt, 3-6 month savings)
- `score > 6`: High-risk messaging (recession-level warnings on credit, layoffs, cash reserves)

---

### `run_recession_signals() -> dict`

**Location:** `recession_signals.py:387`

**Parameters:** None

**Returns:** `dict` — the full output structure written to disk.

**Behavior:**
1. Calls `fetch_yield_curve()`, `fetch_vix()`, `fetch_fred_indicators()` in sequence.
2. Calls `compute_recession_score(yield_curve, vix_data, fred)`.
3. Calls `explain_real_world_impact(score, inverted, vix)`.
4. Assembles output dict:
```json
{
  "generated_at": "<UTC ISO>",
  "recession_risk": { score, max_score, label, plain_english_summary, factors },
  "raw_indicators": { yield_curve, vix, fred },
  "real_world_impact": { mortgages, credit_cards, jobs, groceries_gas, savings }
}
```
5. Writes to `recession_signals_output.json` (indent=2).
6. Prints score and label to stdout.

**Files written:** `recession_signals_output.json`
**External libs:** `yfinance`, `pandas`, `numpy`, `requests`, `fredapi` (optional), `python-dotenv`

---

## opportunity_score.py — Phase 8.9: Opportunity Scoring Engine

**File:** `opportunity_score.py`
**Phase:** 8.9 — Opportunity Scoring (labeled Phase 8 in the roadmap)
**Role:** Combines sector economic outlook, technical signals, and recession risk into a ranked 0–10 opportunity score for every sector and for individual tickers with signals. Applies user-profile multipliers. Output is consumed by `chef_gpt.py` and `portfolio_tracker.py`.

**Key constants:**

| Name | Value |
|---|---|
| `BASE_DIR` | `Path(__file__).parent` |
| `OUTPUT_PATH` | `BASE_DIR / "opportunity_scores.json"` |

**`HIGH_GROWTH_SECTORS`:** `{"Information Technology", "Consumer Discretionary", "Communication Services"}`
**`DEFENSIVE_SECTORS`:** `{"Health Care", "Utilities", "Consumer Staples"}`
**`INCOME_SECTORS`:** `{"Real Estate", "Utilities", "Financials"}`

---

### `load_json(path: Path, default: Any = None) -> Any`

**Location:** `opportunity_score.py:33`

Identical pattern to `chef_gpt.load_json`. Opens path, parses JSON, returns `default` on failure.

---

### `score_sector_outlook(sector: str, bullish_sectors: list, bearish_sectors: list) -> float`

**Location:** `opportunity_score.py:41`

**Parameters:**
- `sector` (`str`): Sector name (GICS standard).
- `bullish_sectors` (`list`): Bullish sector list from economic reasoning.
- `bearish_sectors` (`list`): Bearish sector list from economic reasoning.

**Returns:** `float` in `{0.0, 0.5, 1.0}`.

**Formula:**
```
if sector in bullish_sectors → 1.0
if sector in bearish_sectors → 0.0
else                         → 0.5  (neutral)
```

---

### `score_technical_signal(ticker: str, signals: list[dict]) -> float`

**Location:** `opportunity_score.py:50`

**Parameters:**
- `ticker` (`str`): Ticker symbol.
- `signals` (`list[dict]`): List of technical signal dicts from Phase 8.5.

**Returns:** `float` in `[0.0, 1.0]`.

**Formula:**
```
BUY:  min(1.0, 0.5 + confidence × 0.1)
SELL: max(0.0, 0.5 - confidence × 0.1)
HOLD: 0.5
No signal found: 0.5
```
`confidence` = `abs(sig.get("confidence_score", 0))`

---

### `recession_discount(recession_score: float) -> float`

**Location:** `opportunity_score.py:64`

**Parameters:**
- `recession_score` (`float`): Score from `recession_signals_output.json` (0–10).

**Returns:** `float` multiplier applied to opportunity scores.

**Formula (step function):**

| Recession Score | Multiplier |
|---|---|
| ≤ 2 | 1.00 (no discount) |
| > 2 and ≤ 4 | 0.90 |
| > 4 and ≤ 6 | 0.75 |
| > 6 and ≤ 8 | 0.60 |
| > 8 | 0.45 |

---

### `profile_multiplier(sector: str, profile: dict) -> float`

**Location:** `opportunity_score.py:77`

**Parameters:**
- `sector` (`str`): Sector name.
- `profile` (`dict`): User profile dict (keys: `risk_tolerance`, `investment_goal`).

**Returns:** `float` multiplier, capped at `1.5`.

**Formula:**
```
multiplier = 1.0
if risk == "high" and sector in HIGH_GROWTH_SECTORS:   multiplier = 1.2
elif risk == "low" and sector in DEFENSIVE_SECTORS:    multiplier = 1.2
elif risk == "moderate":                               multiplier = 1.0 (unchanged)

if goal == "income" and sector in INCOME_SECTORS:      multiplier *= 1.15

return min(1.5, multiplier)
```

---

### `build_sector_scores(bullish_sectors, bearish_sectors, signals, recession_risk_score, profile, sector_summaries) -> list[dict]`

**Location:** `opportunity_score.py:101`

**Parameters:**
- `bullish_sectors` (`list`): From economic reasoning.
- `bearish_sectors` (`list`): From economic reasoning.
- `signals` (`list[dict]`): Technical signals.
- `recession_risk_score` (`float`): From recession signals.
- `profile` (`dict`): User profile.
- `sector_summaries` (`dict`): Sector summaries from Phase 5.

**Returns:** `list[dict]` sorted by `opportunity_score` descending.

**Behavior:**
1. Builds `all_sectors` as the union of bullish + bearish + sector_summaries keys. If empty, uses the 11 standard GICS sectors as defaults.
2. For each sector:

**Full sector scoring formula (`opportunity_score.py:122–130`):**
```
outlook   = score_sector_outlook(sector, bullish_sectors, bearish_sectors)  # 0/0.5/1
rec_adj   = outlook × recession_discount(recession_risk_score)
pm        = profile_multiplier(sector, profile)
raw_score = rec_adj × pm
final     = min(10.0, raw_score × 10)
```

**Direction labels:**
- `final >= 7.0`: Bullish
- `final >= 5.0`: Neutral
- `final < 5.0`: Bearish

3. Each output record includes:
```json
{
  "sector": "...",
  "opportunity_score": 0.0–10.0,
  "direction": "Bullish/Neutral/Bearish",
  "direction_emoji": "📈/➡️/📉",
  "components": {
    "economic_outlook": ...,
    "recession_discount": ...,
    "profile_match": ...
  },
  "rationale": "..."
}
```
4. Sorts by `opportunity_score` descending.

---

### `build_ticker_scores(signals, bullish_sectors, bearish_sectors, recession_risk_score, profile, sector_summaries) -> list[dict]`

**Location:** `opportunity_score.py:177`

**Parameters:** Same as `build_sector_scores`.

**Returns:** `list[dict]` sorted by `opportunity_score` descending, capped at top 25.

**Ticker scoring formula (`opportunity_score.py:198–209`):**
```
tech_score = score_technical_signal(ticker, signals)   # 0.0–1.0
base       = tech_score × recession_discount(recession_risk_score)

if risk == "low"  and final_sig == "BUY":  base *= 0.85
if risk == "high" and final_sig == "SELL": base *= 0.85

final = min(10.0, base × 10)
```

**Direction labels:**
- `final >= 7.0`: Buy Signal
- `final >= 5.0`: Neutral / Hold
- `final < 5.0`: Sell Signal

Each record includes a `plain_english_signal` from `_signal_to_plain_english`.

---

### `_signal_to_plain_english(ticker: str, signal: str, confidence: int, reasoning: str) -> str`

**Location:** `opportunity_score.py:235`

**Parameters:**
- `ticker` (`str`)
- `signal` (`str`): `"BUY"`, `"SELL"`, or `"HOLD"`.
- `confidence` (`int`): Confidence score (1–5).
- `reasoning` (`str`): Signal reasoning text.

**Returns:** `str` — plain-English explanation of the signal. Three pre-written templates, one per signal type. Includes the disclaimer "This is a signal to watch, not a guarantee."

---

### `run_opportunity_scoring() -> dict`

**Location:** `opportunity_score.py:255`

**Parameters:** None

**Returns:** `dict` — the full output written to disk.

**Behavior:**
1. Loads: `economic_reasoning_summary.json`, `signal_output_phase3.json`, `recession_signals_output.json`, `user_profile.json`, `sector_summaries.json`.
2. Extracts `bullish_sectors`, `bearish_sectors` from economic reasoning; `recession_score` from recession risk dict (default 3.0 if not found).
3. Calls `build_sector_scores(...)` and `build_ticker_scores(...)`.
4. Assembles output:
```json
{
  "generated_at": "...",
  "recession_risk_used": ...,
  "user_profile_id": "...",
  "sector_opportunities": [...],
  "ticker_opportunities": [...],
  "methodology": "..."
}
```
5. Writes to `opportunity_scores.json`.

**Files read:** `economic_reasoning_summary.json`, `signal_output_phase3.json`, `recession_signals_output.json`, `user_profile.json`, `sector_summaries.json`
**Files written:** `opportunity_scores.json`
**External libs:** `json`, `python-dotenv`, `pathlib`

---

## quantlib_metrics.py — Phase 8.7: QuantLib Risk Metrics

**File:** `quantlib_metrics.py`
**Phase:** 8.7 (a sub-phase within Phase 8 — Opportunity Quantification)
**Role:** Computes rigorous risk-adjusted metrics for each ticker with a BUY or SELL signal. Uses Black-Scholes for probability of profit, parametric VaR at 95%, continuous Kelly criterion for position sizing, and annualized historical volatility. Falls back to pure numpy if QuantLib is unavailable. Output feeds into `chef_gpt.py`'s QuantLib section.

**Key constants:**

| Name | Value | Meaning |
|---|---|---|
| `RISK_FREE_RATE` | `0.05` | 5% annual risk-free rate |
| `LOOKBACK_DAYS` | `252` | 1 trading year of history |
| `TARGET_HORIZON` | `21` | 1 calendar month (~21 trading days) |
| `OUTPUT_PATH` | `BASE_DIR / "quantlib_metrics.json"` | |

**Optional imports:**
- `QuantLib` (`_QL_AVAILABLE`): Used for Black-Scholes engine; falls back to numpy if unavailable.
- `yfinance` (`_YF_AVAILABLE`): Used for price history fetch.

---

### `compute_annualized_vol(prices: list[float]) -> float`

**Location:** `quantlib_metrics.py:49`

**Parameters:**
- `prices` (`list[float]`): Ordered list of daily close prices.

**Returns:** `float` — annualized volatility as a decimal (e.g. 0.30 = 30%).

**Formula:**
```
log_returns = diff(log(prices))       # daily log returns
σ_daily     = std(log_returns, ddof=1)
σ_annual    = σ_daily × sqrt(252)
```

Default: `0.30` if fewer than 10 prices or fewer than 5 valid log returns.

**External libs:** `numpy`

---

### `bs_prob_above_target(spot, target, vol, risk_free=0.05, time_years=21/252) -> float`

**Location:** `quantlib_metrics.py:63`

**Parameters:**
- `spot` (`float`): Current price.
- `target` (`float`): Target price (e.g. `spot × 1.05` for 5% upside).
- `vol` (`float`): Annualized volatility (decimal).
- `risk_free` (`float`): Risk-free rate. Default: `RISK_FREE_RATE` (0.05).
- `time_years` (`float`): Horizon in years. Default: `21/252 ≈ 0.0833`.

**Returns:** `float` in `[0, 1]` — the risk-neutral probability that `S_T > target`.

**Formula (Black-Scholes N(d2)):**
```
d1 = (ln(spot / target) + (risk_free + 0.5 × vol²) × T) / (vol × √T)
d2 = d1 - vol × √T
P(S_T > target) = N(d2)    # standard normal CDF
```

**Implementation:** If QuantLib is available, sets up a full `BlackScholesMertonProcess` with flat vol and rate term structures, prices a European call, then computes N(d2) analytically via `scipy.special.ndtr`. Falls back to pure numpy/math `_norm_cdf(d2)`.

**Edge case:** Returns `0.5` if any input is ≤ 0.

**External libs:** `QuantLib` (optional), `scipy.special.ndtr`, `math`

---

### `_norm_cdf(x: float) -> float`

**Location:** `quantlib_metrics.py:125`

**Parameters:**
- `x` (`float`): Input value.

**Returns:** `float` — standard normal CDF at `x`.

**Formula:** `0.5 × (1 + erf(x / √2))`

**External libs:** `math.erf`

---

### `compute_var_95(prices: list[float]) -> float`

**Location:** `quantlib_metrics.py:131`

**Parameters:**
- `prices` (`list[float]`): Daily close prices.

**Returns:** `float` — daily parametric VaR at 95% confidence as a decimal fraction (e.g. 0.025 = 2.5% of position).

**Formula:**
```
σ_annual = compute_annualized_vol(prices)
σ_daily  = σ_annual / √252
VaR_95   = 1.645 × σ_daily
```

The 1.645 factor is the 95th percentile of the standard normal distribution.

**External libs:** `math`

---

### `expected_return_lognormal(spot, vol, risk_free=0.05, horizon_years=21/252) -> float`

**Location:** `quantlib_metrics.py:141`

**Parameters:**
- `spot` (`float`): Current price.
- `vol` (`float`): Annualized volatility (decimal).
- `risk_free` (`float`): Risk-free drift. Default: 0.05.
- `horizon_years` (`float`): Time horizon. Default: `21/252`.

**Returns:** `float` — expected price under lognormal model.

**Formula (risk-neutral drift):**
```
E[S_T] = spot × exp((risk_free - 0.5 × vol²) × T)
```

Returns `spot` unchanged if inputs are invalid (≤ 0).

**External libs:** `math.exp`

---

### `kelly_fraction(prices: list[float], risk_free: float = 0.05) -> float`

**Location:** `quantlib_metrics.py:155`

**Parameters:**
- `prices` (`list[float]`): Daily close prices.
- `risk_free` (`float`): Annual risk-free rate. Default: 0.05.

**Returns:** `float` — fraction of portfolio to allocate, in `[0.0, 0.25]` (0–25%).

**Formula (continuous Kelly):**
```
log_returns = diff(log(prices))
μ_annual    = mean(log_returns) × 252
σ_annual    = std(log_returns, ddof=1) × √252
f*          = (μ_annual - risk_free) / σ_annual²
f_capped    = max(0.0, min(0.25, f*))   # quarter-Kelly cap for safety
```

Returns `0.0` if fewer than 10 prices or `σ_annual <= 0`.

**External libs:** `numpy`, `math`

---

### `fetch_recent_prices(ticker: str, days: int = 252) -> list[float]`

**Location:** `quantlib_metrics.py:176`

**Parameters:**
- `ticker` (`str`): Ticker symbol.
- `days` (`int`): Maximum number of trading days to return. Default: `LOOKBACK_DAYS` (252).

**Returns:** `list[float]` — most recent `days` close prices, or `[]` if yfinance unavailable or error.

**Behavior:** Calls `yf.download(ticker, period="1y", interval="1d", auto_adjust=True)`. Squeezes multi-level columns. Returns last `days` values from the Close column.

**External libs:** `yfinance`

---

### `compute_ticker_metrics(ticker: str, signal: dict) -> dict`

**Location:** `quantlib_metrics.py:194`

**Parameters:**
- `ticker` (`str`): Ticker symbol.
- `signal` (`dict`): Signal dict from Phase 8.5 (must have `final_signal` key).

**Returns:** `dict` — complete metrics record for this ticker.

**Behavior:**
1. Calls `fetch_recent_prices(ticker)`.
2. If ≥ 10 prices:
   - `spot = prices[-1]`
   - `vol = compute_annualized_vol(prices)`
   - `var_95 = compute_var_95(prices)`
   - `target_bull = spot × 1.05` (5% upside target)
   - `target_bear = spot × 0.95` (5% downside target)
   - `prob_up = bs_prob_above_target(spot, target_bull, vol)`
   - `prob_down = 1 - bs_prob_above_target(spot, target_bear, vol)`
   - `exp_price = expected_return_lognormal(spot, vol)`
   - `exp_return_pct = ((exp_price / spot) - 1) × 100`
   - `kelly = kelly_fraction(prices)`
3. If < 10 prices: uses defaults (`vol=0.30`, `var_95=0.025`, etc.)
4. Returns:
```json
{
  "ticker": "...",
  "current_price": 0.0,
  "annualized_volatility": 0.0,    // as %
  "var_95_daily": 0.0,             // as % of position
  "prob_5pct_upside_1mo": 0.0,     // as %
  "prob_5pct_downside_1mo": 0.0,   // as %
  "expected_return_1mo_pct": 0.0,
  "kelly_fraction": 0.0,           // as % of portfolio
  "technical_signal": "BUY/SELL/HOLD",
  "plain_english": "...",
  "disclaimer": "QuantLib metrics are theoretical estimates..."
}
```

---

### `_plain_english_ql(ticker, signal, vol, prob_up, var_95, kelly) -> str`

**Location:** `quantlib_metrics.py:232`

**Parameters:** All floats/strings from `compute_ticker_metrics`.

**Returns:** `str` — plain-English summary of the ticker's risk metrics, one of three templates based on `signal` (`"BUY"`, `"SELL"`, or neutral).

BUY template includes: volatility label + %, theoretical 5%-gain probability, daily VaR, suggested Kelly position size.
SELL template: volatility label + %, theoretical upside probability, daily VaR.
Neutral: volatility, upside probability, no strong conviction statement.

---

### `run_quantlib_metrics() -> dict`

**Location:** `quantlib_metrics.py:266`

**Parameters:** None

**Returns:** `dict` — the full output written to disk.

**Behavior:**
1. Prints QuantLib availability status.
2. Loads `signal_output_phase3.json`. On missing file, warns and uses empty list.
3. Filters to BUY and SELL signals only; sorts by `|confidence_score|` descending; takes top 15.
4. If no BUY/SELL signals: falls back to first 10 signals.
5. For each ticker, calls `compute_ticker_metrics(ticker, sig)` and appends result.
6. Assembles output:
```json
{
  "generated_at": "...",
  "quantlib_version": "...",
  "risk_free_rate_used": 0.05,
  "horizon_trading_days": 21,
  "ticker_metrics": [...],
  "methodology": "..."
}
```
7. Writes to `quantlib_metrics.json`.

**Files read:** `Module_2_Technical_Analysis/signal_output_phase3.json`
**Files written:** `quantlib_metrics.json`
**External libs:** `QuantLib` (optional), `yfinance`, `numpy`, `scipy`, `math`

---

## historical_correlation.py — Phase 7: Historical Correlation Engine

**File:** `historical_correlation.py`
**Phase:** 7 — Historical Correlation Engine
**Role:** Answers "What happened last time?" for current market events. Detects which historical event types are relevant to today's news by keyword scanning, then fetches sector ETF performance data from those historical periods via yfinance. Produces ranked winners/losers and a plain-English narrative for each event type. Output is consumed by `chef_gpt.py`'s `historical_context` field.

**Key constants:**

| Name | Value |
|---|---|
| `BASE_DIR` | `Path(__file__).parent` |
| `OUTPUT_PATH` | `BASE_DIR / "historical_parallels.json"` |

**`HISTORICAL_EVENTS`** (`historical_correlation.py:40`): A module-level list of 8 event type dicts, each containing:
- `event_type` (`str`): Internal identifier
- `label` (`str`): Human-readable name
- `trigger_keywords` (`list[str]`): Keywords that trigger detection
- `historical_periods` (`list[dict]`): List of dicts with `label`, `start`, `end`, `context`
- `plain_english` (`str`): Pre-written explanation of the event

**Event types defined:**

| event_type | Label | # Historical Periods |
|---|---|---|
| `fed_rate_hike` | Federal Reserve Rate Hike Cycle | 3 (2022, 2018, 2004–2006) |
| `fed_rate_cut` | Federal Reserve Rate Cut | 3 (2020 COVID, 2008, 2019) |
| `inflation_spike` | Inflation Surge | 2 (2021–2022, 1979–1982) |
| `tariff_announcement` | Tariff / Trade War | 2 (2018–2019, 2002 Steel) |
| `recession` | Economic Recession | 3 (2020 COVID, 2008–2009, 2001) |
| `ai_boom` | AI / Technology Boom | 2 (2023–2024, 1995–2000) |
| `energy_shock` | Energy / Oil Price Shock | 3 (2022 Ukraine, 2014, 1973 OPEC) |
| `defense_spending` | Defense / Military Spending Increase | 2 (Post-9/11, Ukraine War) |

**`SECTOR_ETFS`** (`historical_correlation.py:151`): Maps 14 sector/asset labels to ETF tickers (XLK, XLV, XLF, XLE, XLY, XLP, XLI, XLB, XLRE, XLU, XLC, SPY, TLT, GLD).

---

### `detect_current_events(economic_summary: str, enriched_articles: list[dict]) -> list[dict]`

**Location:** `historical_correlation.py:172`

**Parameters:**
- `economic_summary` (`str`): Text from `economic_reasoning_summary.json["summary"]`.
- `enriched_articles` (`list[dict]`): Up to 50 articles from `enriched_news_sentiment.json`.

**Returns:** `list[dict]` — filtered subset of `HISTORICAL_EVENTS` where at least one trigger keyword is found.

**Behavior:**
1. Concatenates `economic_summary` + titles + summaries of first 50 articles, all lowercased.
2. For each event in `HISTORICAL_EVENTS`, checks if `any(kw in combined_text for kw in event["trigger_keywords"])`.
3. Returns matching events.

---

### `measure_period_performance(ticker: str, start: str, end: str) -> dict | None`

**Location:** `historical_correlation.py:191`

**Parameters:**
- `ticker` (`str`): ETF or stock ticker.
- `start` (`str`): ISO date string `"YYYY-MM-DD"`.
- `end` (`str`): ISO date string `"YYYY-MM-DD"`.

**Returns:** `dict` or `None` if insufficient data.

**Behavior:**
1. Downloads price history via `yf.download(ticker, start=start, end=end, auto_adjust=True)`.
2. Returns `None` if empty or fewer than 5 trading days.
3. Computes:

```
start_price  = close.iloc[0]
end_price    = close.iloc[-1]
peak_price   = close.max()
trough_price = close.min()
total_return = (end_price - start_price) / start_price × 100
max_drawdown = (trough_price - peak_price) / peak_price × 100
```

4. Returns:
```json
{
  "ticker": "...",
  "start_price": ...,
  "end_price": ...,
  "total_return_pct": ...,
  "max_drawdown_pct": ...,
  "trading_days": ...
}
```

**External libs:** `yfinance`, `pandas`

---

### `analyze_historical_period(period: dict) -> dict`

**Location:** `historical_correlation.py:222`

**Parameters:**
- `period` (`dict`): One historical period dict with `label`, `start`, `end`, `context`.

**Returns:** `dict` — the input period augmented with `sector_performance`, `winners`, `losers`.

**Behavior:**
1. Defines a sample of 8 ETFs: `{"Broad Market": "SPY", "Technology": "XLK", "Energy": "XLE", "Financials": "XLF", "Health Care": "XLV", "Consumer Staples": "XLP", "Bonds": "TLT", "Gold": "GLD"}`.
2. Calls `measure_period_performance` for each.
3. Ranks all sectors by `total_return_pct` descending.
4. Sets `winners` = top 3 as `"{label} ({ret:+.1f}%)"` strings.
5. Sets `losers` = bottom 3 in same format.

---

### `generate_historical_narrative(event: dict, analyzed_periods: list[dict]) -> str`

**Location:** `historical_correlation.py:269`

**Parameters:**
- `event` (`dict`): An `HISTORICAL_EVENTS` entry.
- `analyzed_periods` (`list[dict]`): Output of `analyze_historical_period` for each period.

**Returns:** `str` — Markdown-formatted narrative.

**Behavior:** Builds a multi-paragraph string including:
- Event label as H2 header
- `event["plain_english"]` overview
- For each analyzed period: period label, context, SPY return direction/magnitude, best and worst performers

---

### `run_historical_correlation() -> dict`

**Location:** `historical_correlation.py:301`

**Parameters:** None

**Returns:** `dict` — full output written to disk.

**Behavior:**
1. Loads `economic_reasoning_summary.json` and `enriched_news_sentiment.json` (both optional — warns if missing).
2. Calls `detect_current_events(economic_summary, enriched_articles)`.
3. If no events detected, defaults to `HISTORICAL_EVENTS[0]` (Fed Rate Hike context).
4. Iterates over detected events (up to 3):
   - For each event, iterates over its `historical_periods` (up to 2).
   - Calls `analyze_historical_period` for each.
   - Calls `generate_historical_narrative(event, analyzed_periods)`.
   - Appends result dict to `results`.
5. Assembles output:
```json
{
  "generated_at": "...",
  "events_analyzed": ...,
  "historical_parallels": [...]
}
```
6. Writes to `historical_parallels.json`.

**Files read:** `news_output/economic_reasoning_summary.json`, `news_output/enriched_news_sentiment.json`
**Files written:** `historical_parallels.json`
**External libs:** `yfinance`, `pandas`, `numpy`, `python-dotenv`

---

### `_extract_key_takeaway(event_type: str, periods: list[dict]) -> str`

**Location:** `historical_correlation.py:373`

**Parameters:**
- `event_type` (`str`): Event type identifier.
- `periods` (`list[dict]`): Analyzed historical periods.

**Returns:** `str` — a single-sentence takeaway about average market direction.

**Behavior:**
1. Extracts SPY `total_return_pct` from each period's `sector_performance`.
2. Computes simple average of available returns.
3. Maps to directional string:
   - `avg > 10%`: "markets generally rose an average of {avg:.1f}%"
   - `avg < -10%`: "markets generally fell an average of {|avg|:.1f}%"
   - Otherwise: "markets were mixed, averaging {avg:+.1f}%"
4. Appends disclaimer: "Past outcomes do not guarantee future results."

---

## phase3_extraction.py — Phase 3: NLP Data Extraction

**File:** `phase3_extraction.py`
**Phase:** 3 — Data Extraction & Structuring
**Role:** Reads raw scraped articles and applies NLP and regex to extract structured financial intelligence: percentages, dollar values, dates, economic indicator mentions, comparison phrases, company names (via spaCy NER), and VADER sentiment scores. Outputs a sorted list of enriched article dicts. The output is the primary input to Phase 4 clustering.

**Key paths:**

| Name | Value |
|---|---|
| `BASE_DIR` | `Path(__file__).parent` |
| `NEWS_DIR` | `BASE_DIR / "news_output"` |
| `INPUT_PATH` | `NEWS_DIR / "articles_*.json"` (latest) |
| `OUTPUT_PATH` | `NEWS_DIR / "enriched_news_sentiment.json"` |

**Optional imports (graceful degradation):**
- `vaderSentiment.vaderSentiment.SentimentIntensityAnalyzer` → `VADER_AVAILABLE`
- `spacy` (model `en_core_web_sm`) → `SPACY_AVAILABLE`, `NLP`

**Regex patterns (`phase3_extraction.py:61–69`):**

| Pattern | Expression | Matches |
|---|---|---|
| `PERCENT_RE` | `[-+]?\d+(?:\.\d+)?\s*%` | Signed/unsigned percentages |
| `DOLLAR_RE` | `\$\s*\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:\s*(?:billion|million|trillion|B|M|T))?` | Dollar amounts with optional scale |
| `DATE_RE` | Complex alternation | `MM/DD/YYYY`, month-name dates, `Q1 2024`, `FY2024` |

**`ECON_INDICATORS`** (`phase3_extraction.py:71`): Dict of 10 named patterns (cpi, gdp, unemployment, fed_rate, inflation, interest_rate, recession, earnings, tariff, layoff) each mapped to a compiled case-insensitive regex.

**`COMPARISON_PHRASES`** (`phase3_extraction.py:84`): 16 exact phrases (e.g. "beat expectations", "missed estimates", "raised guidance", "record high").

**`SENTIMENT_KEYWORDS`** (`phase3_extraction.py:96`): Dict with `"positive"` (19 words) and `"negative"` (22 words) for keyword-based fallback sentiment.

---

### `extract_percentages(text: str) -> list[str]`

**Location:** `phase3_extraction.py:113`

**Returns:** All regex matches of `PERCENT_RE` in `text`.

---

### `extract_dollar_values(text: str) -> list[str]`

**Location:** `phase3_extraction.py:117`

**Returns:** All regex matches of `DOLLAR_RE` in `text`.

---

### `extract_dates(text: str) -> list[str]`

**Location:** `phase3_extraction.py:121`

**Returns:** All regex matches of `DATE_RE` in `text`.

---

### `extract_economic_indicators(text: str) -> list[str]`

**Location:** `phase3_extraction.py:125`

**Returns:** List of indicator names (keys from `ECON_INDICATORS`) whose regex patterns match in `text`.

---

### `extract_comparison_phrases(text: str) -> list[str]`

**Location:** `phase3_extraction.py:133`

**Returns:** All case-insensitive matches of `COMPARISON_RE` (union of all 16 phrases) in `text`.

---

### `extract_companies_spacy(text: str) -> list[str]`

**Location:** `phase3_extraction.py:137`

**Parameters:**
- `text` (`str`): Article text (processed only up to first 5,000 characters).

**Returns:** `list[str]` — up to 20 unique `ORG` entities extracted by spaCy NER. Returns `[]` if spaCy unavailable.

**External libs:** `spacy`

---

### `score_sentiment_vader(text: str) -> dict`

**Location:** `phase3_extraction.py:145`

**Parameters:**
- `text` (`str`): Full article text.

**Returns:** `dict` with keys `compound` (float in [-1,1]), `pos`, `neg`, `neu` (floats in [0,1]).

**Behavior:** Instantiates `SentimentIntensityAnalyzer()` and calls `polarity_scores(text)`. Returns `{"compound": 0.0, "pos": 0.0, "neg": 0.0, "neu": 1.0}` if VADER unavailable.

**External libs:** `vaderSentiment`

---

### `score_sentiment_keyword(text: str) -> dict`

**Location:** `phase3_extraction.py:152`

**Parameters:**
- `text` (`str`): Article text.

**Returns:** `dict` with keys `compound`, `pos`, `neg`, `neu`.

**Formula (keyword fallback):**
```
pos   = count of positive keywords in text_lower
neg   = count of negative keywords in text_lower
total = max(pos + neg, 1)
compound = (pos - neg) / total
pos_ratio = pos / total
neg_ratio = neg / total
neu       = 1 - |compound|
```

---

### `determine_sentiment_label(compound: float) -> str`

**Location:** `phase3_extraction.py:167`

**Returns:**
- `"positive"` if `compound >= 0.05`
- `"negative"` if `compound <= -0.05`
- `"neutral"` otherwise

---

### `find_latest_articles_file() -> Path | None`

**Location:** `phase3_extraction.py:179`

**Returns:** Most recently modified `articles_*.json` file in `news_output/`, or `None`.

**Behavior:** Uses `Path.glob("articles_*.json")`, sorts by `stat().st_mtime` descending.

---

### `load_articles(path: Path) -> list[dict]`

**Location:** `phase3_extraction.py:189`

**Parameters:**
- `path` (`Path`): Path to an articles JSON file.

**Returns:** `list[dict]` — normalized article dicts.

**Behavior:** Handles three input formats:
1. **Finnhub nested format**: `[{"symbol": ..., "finnhub": {"company_news": [...], ...}}]` — extracts `headline`, `summary`, `url`, `datetime`, `source`, `symbol` fields.
2. **Headline-keyed format**: `[{"headline": ..., ...}]` — copies record with `"title"` alias.
3. **Plain format**: `[{"title": ..., ...}]` — appended as-is.

---

### `load_articles_with_fallback() -> list[dict]`

**Location:** `phase3_extraction.py:226`

**Returns:** `list[dict]` — articles loaded from the best available source.

**Behavior:**
1. Tries `find_latest_articles_file()` → `load_articles()`.
2. If result is empty, falls back to `news_output/summaries.json`.
3. Returns `[]` if both fail.

---

### `enrich_article(article: dict) -> dict`

**Location:** `phase3_extraction.py:245`

**Parameters:**
- `article` (`dict`): Raw article dict with `title` and `summary` keys.

**Returns:** `dict` — original article augmented with `extracted`, `sentiment`, `data_richness_score`, `enriched_at`.

**Behavior:**
1. Concatenates `title + ". " + summary` as `full_text`.
2. Calls all extraction functions on `full_text`.
3. Runs VADER sentiment (or keyword fallback).
4. Computes sentiment label via `determine_sentiment_label`.
5. Computes data richness score:

**Data richness formula (`phase3_extraction.py:267`):**
```
richness_items = len(percentages) + len(dollar_vals) + len(dates) + len(indicators) × 2
richness_score = min(1.0, richness_items / 10.0)
```

6. Returns enriched dict with structure:
```json
{
  "...original fields...",
  "extracted": {
    "percentages": [...],
    "dollar_values": [...],
    "dates": [...],
    "economic_indicators": [...],
    "comparison_phrases": [...],
    "companies_mentioned": [...]
  },
  "sentiment": {
    "compound": ...,
    "positive": ...,
    "negative": ...,
    "neutral": ...,
    "label": "positive/negative/neutral"
  },
  "data_richness_score": ...,
  "enriched_at": "..."
}
```

---

### `run_extraction() -> list[dict]`

**Location:** `phase3_extraction.py:292`

**Parameters:** None

**Returns:** `list[dict]` — all enriched articles, sorted by `|sentiment.compound|` descending (most impactful first).

**Behavior:**
1. Calls `load_articles_with_fallback()`.
2. Iterates all articles, calling `enrich_article` for each with try/except per article.
3. Sorts by `abs(a["sentiment"]["compound"])` descending.
4. Creates `news_output/` directory if needed.
5. Writes to `enriched_news_sentiment.json` (UTF-8, indent=2).
6. Prints summary: total articles, positive/negative/neutral counts, NLP mode (spaCy/keyword).

**Files read:** `news_output/articles_*.json` or `news_output/summaries.json`
**Files written:** `news_output/enriched_news_sentiment.json`
**External libs:** `vaderSentiment` (optional), `spacy` (optional), `json`, `re`, `pathlib`

---

## phase4_clustering.py — Phase 4: Article Scoring & Clustering

**File:** `phase4_clustering.py`
**Phase:** 4 — Article Scoring & Clustering
**Role:** Takes enriched articles from Phase 3, generates sentence embeddings, clusters similar articles (reducing information overload), assigns GICS sector labels, scores each article by impact, and selects top representative articles per cluster for downstream GPT summarization. Outputs `clustered_summaries.json`.

**Key paths:**

| Name | Value |
|---|---|
| `BASE_DIR` | `Path(__file__).parent` |
| `NEWS_DIR` | `BASE_DIR / "news_output"` |
| `INPUT_PATH` | `NEWS_DIR / "enriched_news_sentiment.json"` |
| `OUTPUT_PATH` | `NEWS_DIR / "clustered_summaries.json"` |

**Optional imports:**
- `sentence_transformers.SentenceTransformer` → `EMBEDDINGS_AVAILABLE`
- `sklearn.cluster.AgglomerativeClustering`, `sklearn.metrics.pairwise.cosine_similarity` → `SKLEARN_AVAILABLE`

**`GICS_SECTORS`** (`phase4_clustering.py:59`): Dict mapping 11 GICS sector names to keyword lists (3–20 keywords each) used for sector classification.

**`CREDIBILITY_SCORES`** (`phase4_clustering.py:109`): Dict mapping source names to credibility scores:

| Source | Score |
|---|---|
| reuters, bloomberg | 0.95 |
| wsj, wall street journal | 0.90 |
| ft, financial times | 0.90 |
| cnbc | 0.85 |
| marketwatch | 0.80 |
| finnhub | 0.75 |
| yahoo | 0.70 |
| seekingalpha | 0.65 |
| default | 0.60 |

**`HIGH_IMPACT_KEYWORDS`** (`phase4_clustering.py:124`): 28 high-impact financial keywords (earnings, fed, inflation, gdp, acquisition, merger, ipo, bankruptcy, tariff, layoff, etc.).

---

### `assign_sector(text: str) -> str`

**Location:** `phase4_clustering.py:137`

**Parameters:**
- `text` (`str`): Combined article title + summary.

**Returns:** `str` — GICS sector name, or `"General Market"` if no match.

**Behavior:** For each GICS sector, counts keyword hits in `text_lower`. Returns the sector with the highest count; ties broken by dict order.

---

### `get_credibility(source: str) -> float`

**Location:** `phase4_clustering.py:149`

**Parameters:**
- `source` (`str`): Article source name.

**Returns:** `float` — credibility score from `CREDIBILITY_SCORES`. Falls back to `0.60` ("default").

---

### `keyword_weight(text: str) -> float`

**Location:** `phase4_clustering.py:157`

**Parameters:**
- `text` (`str`): Combined article text.

**Returns:** `float` in `[0.0, 1.0]`.

**Formula:** `min(1.0, keyword_hits / 5.0)` where `keyword_hits` is the count of `HIGH_IMPACT_KEYWORDS` found in `text_lower`.

---

### `profile_match_score(article: dict, profile: dict) -> float`

**Location:** `phase4_clustering.py:163`

**Parameters:**
- `article` (`dict`): Enriched article dict.
- `profile` (`dict`): User profile dict.

**Returns:** `float` in `[0.0, 1.0]`.

**Behavior:**
- Base score: `0.5`
- If `risk_tolerance == "high"` and text contains growth/momentum/tech/ai/innovation terms: `+0.3`
- If `risk_tolerance == "high"` and text contains volatile/speculative/high-risk terms: `+0.2`
- If `risk_tolerance == "low"` and text contains dividend/stable/utility/bond/defensive terms: `+0.3`
- If `risk_tolerance == "low"` and text contains recession/safe haven/gold/treasury terms: `+0.2`
- If `risk_tolerance == "moderate"`: stays at `0.5`
- If `goal == "income"` and text contains dividend/yield/income/payout: `+0.2`
- If `goal == "growth"` and text contains growth/expansion/revenue growth/market share: `+0.2`
- Final: `min(1.0, score)`

---

### `compute_impact_score(article: dict, profile: dict) -> float`

**Location:** `phase4_clustering.py:197`

**Parameters:**
- `article` (`dict`): Enriched article dict.
- `profile` (`dict`): User profile dict.

**Returns:** `float` in `[0.0, 1.0]`.

**Formula (reproduced from `phase4_clustering.py:206–209`):**
```
sentiment    = |article.sentiment.compound|
credibility  = get_credibility(article.source)
kw           = keyword_weight(title + " " + summary)
pm           = profile_match_score(article, profile)
richness     = article.data_richness_score

impact = sentiment × credibility × (kw × 0.4 + pm × 0.3 + richness × 0.3)
return min(1.0, round(impact, 4))
```

The composite weight factor is `kw × 0.4 + pm × 0.3 + richness × 0.3`, ensuring that keyword relevance (40%), user-profile alignment (30%), and data richness (30%) all contribute to impact.

---

### `embed_articles(articles: list[dict]) -> np.ndarray | None`

**Location:** `phase4_clustering.py:216`

**Parameters:**
- `articles` (`list[dict]`): All enriched articles.

**Returns:** `np.ndarray` of shape `(n_articles, embedding_dim)` as float32, or `None` if embeddings unavailable.

**Behavior:**
1. Constructs text strings: `(title + " " + summary)[:512]` for each article.
2. Loads `SentenceTransformer("all-MiniLM-L6-v2")`.
3. Encodes with `batch_size=64`, `show_progress_bar=False`.
4. Casts to `float32`.

**External libs:** `sentence-transformers`

---

### `cluster_with_embeddings(articles: list[dict], embeddings: np.ndarray) -> dict[int, list[int]]`

**Location:** `phase4_clustering.py:230`

**Parameters:**
- `articles` (`list[dict]`): All enriched articles.
- `embeddings` (`np.ndarray`): Embedding matrix.

**Returns:** `dict[int, list[int]]` — mapping cluster label → list of article indices.

**Behavior:**
1. Computes `n_clusters = max(5, min(n // 10, 50))` — between 5 and 50.
2. Fits `AgglomerativeClustering(n_clusters=n_clusters, metric="cosine", linkage="average")`.
3. Maps labels to index lists.

**External libs:** `scikit-learn`

---

### `cluster_by_sector(articles: list[dict]) -> dict[int, list[int]]`

**Location:** `phase4_clustering.py:248`

**Parameters:**
- `articles` (`list[dict]`): Articles with `gics_sector` already assigned.

**Returns:** `dict[int, list[int]]` — groups articles by their `gics_sector` field.

**Behavior:** Fallback when ML clustering is unavailable. Groups indices by sector string, converts to integer-keyed dict.

---

### `deduplicate_within_cluster(cluster_articles: list[dict]) -> list[dict]`

**Location:** `phase4_clustering.py:259`

**Parameters:**
- `cluster_articles` (`list[dict]`): Articles in a single cluster.

**Returns:** `list[dict]` — deduplicated articles.

**Behavior:**
1. Normalizes each title: lowercase, removes non-alphanumeric characters.
2. Converts to word frozensets.
3. Compares new article against all previously seen titles using Jaccard-like overlap:
   ```
   overlap = |words ∩ seen_words| / max(|words|, |seen_words|)
   is_dupe = overlap > 0.7
   ```
4. Skips duplicates; adds unique articles to result.

---

### `re_sub_helper(pattern: str, repl: str, text: str) -> str`

**Location:** `phase4_clustering.py:283`

A thin wrapper around `re.sub`. Used internally for title normalization.

---

### `run_clustering() -> dict`

**Location:** `phase4_clustering.py:291`

**Parameters:** None

**Returns:** `dict` — cluster-id → list of article dicts (written to disk).

**Behavior:**
1. Loads `enriched_news_sentiment.json`.
2. Loads `user_profile.json` if available.
3. For each article: assigns `gics_sector` via `assign_sector`, computes `impact_score` via `compute_impact_score`.
4. Chooses clustering method:
   - If both `EMBEDDINGS_AVAILABLE` and `SKLEARN_AVAILABLE`: calls `embed_articles` → `cluster_with_embeddings`. Method label: `"embedding+agglomerative"`.
   - Otherwise: calls `cluster_by_sector`. Method label: `"sector_fallback"`.
5. For each cluster:
   - Calls `deduplicate_within_cluster`.
   - Sorts by `impact_score` descending.
   - Assigns cluster-level sector as the most common `gics_sector` in the cluster (plurality vote).
   - Selects top 2 articles as representatives (for Phase 5 GPT summarization).
   - Tags all articles with `cluster_id` and `cluster_sector`.
6. Writes output as `{cluster_id: [article_dicts]}` to `clustered_summaries.json`.
7. Prints: total clusters, articles retained, clustering method.

**Files read:** `news_output/enriched_news_sentiment.json`, `user_profile.json`
**Files written:** `news_output/clustered_summaries.json`
**External libs:** `sentence-transformers`, `scikit-learn`, `numpy`, `python-dotenv`

---

## portfolio_tracker.py — Phase 10: Portfolio Tracker

**File:** `portfolio_tracker.py`
**Phase:** 10 — Portfolio Tracker / Dashboard
**Role:** A simulated paper-trading engine that tracks mock positions based on Phase 8.9 opportunity scores and Phase 8.5 signals. Opens new long positions when a ticker's opportunity score exceeds the minimum threshold, updates existing positions with current prices (sourced from QuantLib metrics to avoid extra API calls), closes positions that hit stop-loss or take-profit targets, and computes aggregate portfolio metrics. Educational simulation only — no live trading.

**Key constants:**

| Name | Value | Meaning |
|---|---|---|
| `STARTING_CASH` | `100_000.0` | Initial simulated portfolio value |
| `MAX_POSITIONS` | `10` | Maximum concurrent open positions |
| `RISK_PCT` | `0.02` | 2% of portfolio risked per trade |
| `MIN_SCORE` | `6.5` | Minimum opportunity score to open position |
| `STOP_LOSS_PCT` | `0.08` | 8% stop loss below entry |
| `TAKE_PROFIT` | `0.15` | 15% take profit above entry |
| `OUTPUT_PATH` | `BASE_DIR / "portfolio_snapshot.json"` | |
| `PORTFOLIO_LOG` | `BASE_DIR / "portfolio_log.json"` | (defined but not currently written) |

---

### `load_json(path: Path, default: Any = None) -> Any`

Same pattern as other modules. Returns `default` on `FileNotFoundError` or `JSONDecodeError`.

---

### `load_existing_portfolio() -> dict`

**Location:** `portfolio_tracker.py:38`

**Returns:** `dict` — existing portfolio snapshot or fresh starting state.

**Behavior:** Calls `load_json(OUTPUT_PATH)`. If present, returns it. Otherwise returns:
```json
{
  "cash": 100000.0,
  "positions": {},
  "closed_trades": [],
  "inception_date": "<today>"
}
```

---

### `fetch_current_price(ticker: str, quantlib_metrics: list[dict]) -> float | None`

**Location:** `portfolio_tracker.py:50`

**Parameters:**
- `ticker` (`str`): Ticker symbol.
- `quantlib_metrics` (`list[dict]`): List of QuantLib metric records (from `quantlib_metrics.json["ticker_metrics"]`).

**Returns:** `float` or `None`.

**Behavior:** Searches `quantlib_metrics` for a matching ticker (case-insensitive). Returns `current_price` as float if positive; else `None`. This avoids redundant yfinance calls since QuantLib already fetched prices.

---

### `compute_position_size(portfolio_value: float, price: float) -> int`

**Location:** `portfolio_tracker.py:59`

**Parameters:**
- `portfolio_value` (`float`): Total current portfolio value (cash + open positions).
- `price` (`float`): Current stock price.

**Returns:** `int` — number of shares to buy.

**Formula (risk-based position sizing, `portfolio_tracker.py:62–70`):**
```
dollar_risk     = portfolio_value × RISK_PCT      (2% of portfolio)
stop_loss_price = price × (1 - STOP_LOSS_PCT)     (price × 0.92)
risk_per_share  = price - stop_loss_price          (8% of price)
shares_by_risk  = floor(dollar_risk / risk_per_share)

max_by_value    = floor(portfolio_value × 0.10 / price)  (cap: 10% of portfolio per position)
shares          = min(shares_by_risk, max_by_value)
```

Returns `0` if `price <= 0` or `risk_per_share <= 0`.

---

### `open_position(portfolio, ticker, price, opportunity_score, signal_reasoning) -> bool`

**Location:** `portfolio_tracker.py:74`

**Parameters:**
- `portfolio` (`dict`): Current portfolio state (mutated in-place).
- `ticker` (`str`): Ticker symbol.
- `price` (`float`): Current price.
- `opportunity_score` (`float`): Score from `opportunity_scores.json`.
- `signal_reasoning` (`str`): Plain-text reasoning (truncated to 200 chars).

**Returns:** `bool` — `True` if position was opened.

**Behavior:**
1. Returns `False` if ticker already in `positions` or `len(positions) >= MAX_POSITIONS`.
2. Computes `portfolio_value = cash + sum(shares × last_price)`.
3. Calls `compute_position_size(portfolio_value, price)`.
4. If `cost > cash`: recalculates as `floor(cash × 0.10 / price)` shares.
5. Deducts `cost = shares × price` from `portfolio["cash"]`.
6. Adds position record to `portfolio["positions"][ticker]`:
```json
{
  "ticker": "...",
  "shares": N,
  "entry_price": ...,
  "last_price": ...,
  "entry_date": "YYYY-MM-DD",
  "cost_basis": ...,
  "opportunity_score": ...,
  "stop_loss": price × 0.92,
  "take_profit_target": price × 1.15,
  "unrealized_pnl": 0.0,
  "unrealized_pnl_pct": 0.0,
  "signal_reasoning": "...",
  "status": "OPEN"
}
```

---

### `update_position(pos: dict, current_price: float) -> dict`

**Location:** `portfolio_tracker.py:116`

**Parameters:**
- `pos` (`dict`): Open position record (mutated in-place).
- `current_price` (`float`): Latest price.

**Returns:** `dict` — updated position.

**Formulas:**
```
unrealized_pnl     = (current_price - entry_price) × shares
unrealized_pnl_pct = (current_price - entry_price) / entry_price × 100

if current_price <= stop_loss:         exit_signal = "STOP_LOSS"
elif current_price >= take_profit:     exit_signal = "TAKE_PROFIT"
else:                                  exit_signal = None
```

---

### `close_position(portfolio: dict, ticker: str, current_price: float, reason: str) -> dict | None`

**Location:** `portfolio_tracker.py:135`

**Parameters:**
- `portfolio` (`dict`): Portfolio state (mutated).
- `ticker` (`str`): Ticker to close.
- `current_price` (`float`): Exit price.
- `reason` (`str`): `"STOP_LOSS"` or `"TAKE_PROFIT"`.

**Returns:** `dict` — closed trade record, or `None` if ticker not in positions.

**Formulas:**
```
proceeds    = shares × current_price
pnl         = proceeds - cost_basis
pnl_pct     = (current_price - entry_price) / entry_price × 100
```

Adds `proceeds` back to `portfolio["cash"]`. Appends closed trade record to `portfolio["closed_trades"]`.

---

### `compute_portfolio_metrics(portfolio: dict) -> dict`

**Location:** `portfolio_tracker.py:162`

**Parameters:**
- `portfolio` (`dict`): Portfolio state dict.

**Returns:** `dict` with aggregate performance metrics.

**Formulas:**
```
open_value         = sum(shares × last_price) for all open positions
total_value        = cash + open_value

total_return       = total_value - STARTING_CASH
total_return_pct   = total_return / STARTING_CASH × 100

win_rate_pct       = len(winning_trades) / len(all_closed_trades) × 100
gross_profit       = sum(pnl for winning trades)
gross_loss         = |sum(pnl for losing trades)|
profit_factor      = gross_profit / gross_loss  (∞ if no losses)

exposure_pct       = open_value / total_value × 100
```

Returns all values rounded to 2 decimal places.

---

### `run_portfolio_tracker() -> dict`

**Location:** `portfolio_tracker.py:204`

**Parameters:** None

**Returns:** `dict` — full portfolio snapshot written to disk.

**Behavior:**
1. Loads: `signal_output_phase3.json`, `opportunity_scores.json`, `quantlib_metrics.json`, `user_profile.json`.
2. Builds `opp_lookup` (ticker → opportunity_score) and `sig_lookup` (ticker → signal dict).
3. Calls `load_existing_portfolio()`.
4. **Update cycle**: For each open position, fetches current price from QuantLib metrics; calls `update_position`; if `exit_signal` triggered, adds to close list.
5. **Close cycle**: Closes all positions in close list; prints P&L for each.
6. **Open cycle**: Filters signals for `final_signal == "BUY"`, sorts by opportunity score descending.
   - Adjusts `min_score` by risk profile:
     - `"low"`: `7.5` (conservative)
     - `"high"`: `5.5` (aggressive)
     - `"moderate"`: `6.5` (default)
   - Skips tickers below `min_score` or with no valid price.
   - Calls `open_position` for qualifying tickers.
7. Calls `compute_portfolio_metrics`.
8. Assembles snapshot dict (portfolio state + metrics + settings + disclaimer).
9. Writes to `portfolio_snapshot.json` (using `default=str` for date serialization).

**Files read:** `signal_output_phase3.json`, `opportunity_scores.json`, `quantlib_metrics.json`, `user_profile.json`, `portfolio_snapshot.json` (existing)
**Files written:** `portfolio_snapshot.json`
**External libs:** `json`, `datetime`, `pathlib`

---

### `reset_portfolio()`

**Location:** `portfolio_tracker.py:316`

**Behavior:** Writes a fresh portfolio state with `STARTING_CASH = $100,000`, empty positions and trades, today as inception date. Invoked with `python portfolio_tracker.py --reset`.

---

## congress_bills.py — Phase 6.5 Supplement: Congress Bills Intelligence

**File:** `congress_bills.py`
**Phase:** 6.5 — Political Intelligence (supplement to the main economic_engine_insider.py)
**Role:** Fetches recently enacted laws and pending bills from the Congress.gov API (119th Congress, 2025–2027). Correlates bill content with congressional stock trade disclosures by matching company and sector keywords against bill titles and action text, within a ±90-day time window. Adds politician party/state metadata via `politician_parties.json`. Outputs `congress_bills.json` for use in the political intelligence layer.

**Key constants:**

| Name | Value |
|---|---|
| `BASE_DIR` | `Path(__file__).parent` |
| `OUTPUT_FILE` | `BASE_DIR / "congress_bills.json"` |
| `CONGRESS_API_KEY` | `os.getenv("CONGRESS_API_KEY", "")` |
| `CURRENT_CONGRESS` | `119` |
| `LOOKBACK_DAYS` | `180` |
| `BASE_URL` | `"https://api.congress.gov/v3"` |

**`TICKER_KEYWORDS`** (`congress_bills.py:45`): Dict mapping 80+ ticker symbols to lists of keywords (company names, product names, policy topics) to search in bill text. Covers tech (AAPL, MSFT, NVDA, META, etc.), telecom (T, VZ), finance (JPM, BAC, GS), health care (JNJ, UNH, LLY), energy (XOM, CVX, NEE), industrials/defense (LMT, RTX, BA), and consumer sectors.

**`SECTOR_KEYWORDS`** (`congress_bills.py:142`): Dict mapping 10 sector names to keyword lists for sector-level bill matching (e.g. "Technology" → ["artificial intelligence", "AI", "semiconductor", "chip", ...]).

**`DISCLAIMER`** (`congress_bills.py:38`):
> "This analysis identifies timing relationships between publicly available government disclosures and market events. It does not imply or allege wrongdoing of any kind."

---

### `_headers() -> dict`

**Location:** `congress_bills.py:156`

**Returns:** Empty `dict`. Congress.gov API uses `api_key` as a query parameter rather than an HTTP header.

---

### `_paginated_get(endpoint: str, params: dict, max_items: int = 250) -> list[dict]`

**Location:** `congress_bills.py:160`

**Parameters:**
- `endpoint` (`str`): API endpoint path (e.g. `"/law/119"`).
- `params` (`dict`): Additional query parameters.
- `max_items` (`int`): Maximum records to retrieve. Default: 250.

**Returns:** `list[dict]` — up to `max_items` records.

**Behavior:**
1. Iterates with `offset` pagination, fetching `limit = min(250, max_items)` records per request.
2. Appends `limit`, `offset`, `format="json"`, `api_key` to params.
3. Reads `data.get("bills", data.get("laws", []))` as the batch.
4. Stops when batch is empty, `offset >= total`, or `len(batch) < limit`.
5. Returns `items[:max_items]`.

**External libs:** `requests`

---

### `fetch_enacted_laws(since_days: int = 180) -> list[dict]`

**Location:** `congress_bills.py:189`

**Parameters:**
- `since_days` (`int`): Lookback window in days. Default: `LOOKBACK_DAYS` (180).

**Returns:** `list[dict]` — enacted laws with `latestAction.actionDate` within the lookback window.

**Behavior:**
1. Calls `_paginated_get(f"/law/{CURRENT_CONGRESS}", params={}, max_items=500)`.
2. Filters results: keeps laws where `latestAction.actionDate` is within `since_days` days of now. Includes laws with missing dates.
3. Prints count of matching laws.

**API endpoint:** `GET https://api.congress.gov/v3/law/119`

---

### `fetch_recent_bills(since_days: int = 180) -> list[dict]`

**Location:** `congress_bills.py:211`

**Parameters:**
- `since_days` (`int`): Lookback window in days.

**Returns:** `list[dict]` — recently updated pending bills.

**Behavior:** Calls `_paginated_get(f"/bill/{CURRENT_CONGRESS}", params={"sort": "updateDate+desc", "fromDateTime": since_iso}, max_items=500)`.

**API endpoint:** `GET https://api.congress.gov/v3/bill/119`

---

### `_text_matches(title: str, action_text: str, keywords: list[str]) -> bool`

**Location:** `congress_bills.py:224`

**Parameters:**
- `title` (`str`): Bill title.
- `action_text` (`str`): Latest action text.
- `keywords` (`list[str]`): Keywords to search.

**Returns:** `bool` — `True` if any keyword appears in the combined lowercased string.

---

### `correlate_bills_to_tickers(all_bills: list[dict], trades: list[dict]) -> list[dict]`

**Location:** `congress_bills.py:229`

**Parameters:**
- `all_bills` (`list[dict]`): Combined list of enacted laws + recent bills.
- `trades` (`list[dict]`): Congressional trade records from `intelligence_output.json["housing_trades"]`.

**Returns:** `list[dict]` — sorted list of correlation records (most recent first).

**Behavior:**
1. Loads `politician_parties.json` for name → `{party, party_abbr, state}` mapping.
2. Builds `ticker_trades` dict: ticker → list of trade records (with politician name, party, chamber, transaction, amount, date).
3. For each bill:
   - Parses `latestAction.actionDate`.
   - For each ticker in `TICKER_KEYWORDS` that has trades AND whose keywords match the bill text: adds to `matched_tickers`.
   - For each sector in `SECTOR_KEYWORDS` whose keywords match: adds to `matched_sectors`.
   - Skips bills with no matches.
   - Finds correlated trades within ±90 days of `bill_dt`. Deduplicates by `politician|ticker|date`.
   - Builds correlation record:
```json
{
  "bill_id": "...",
  "title": "...",
  "action_date": "...",
  "action_text": "...",
  "is_enacted": true/false,
  "matched_tickers": [...],
  "matched_sectors": [...],
  "correlated_trades": [
    {
      "politician": "...",
      "party": "...",
      "party_abbr": "...",
      "state": "...",
      "chamber": "...",
      "transaction": "...",
      "ticker": "...",
      "trade_date": "...",
      "amount": "...",
      "days_delta": N
    }
  ]
}
```
4. Sorts results by `action_date` descending.

**Files read:** `politician_parties.json`

---

### `main()`

**Location:** `congress_bills.py:342`

**Parameters:** None (reads env vars)

**Behavior:**
1. Raises `RuntimeError` if `CONGRESS_API_KEY` is not set.
2. Calls `fetch_enacted_laws` and `fetch_recent_bills`.
3. Loads `intelligence_output.json` for trade data.
4. Calls `correlate_bills_to_tickers(all_bills, trades)`.
5. Assembles output:
```json
{
  "disclaimer": "...",
  "generated_at": "...",
  "congress": 119,
  "lookback_days": 180,
  "enacted_laws": N,
  "recent_bills": N,
  "correlations": [...],
  "raw_laws": [
    { "title", "action_date", "action_text", "type", "number" }
  ]
}
```
6. Writes to `congress_bills.json`.
7. Prints top 5 correlations preview with `days_delta` direction ("before"/"after" bill).

**Files read:** `GPT_Economy/Intelligence_layer (IN PROGRESS)/intelligence_output.json`, `politician_parties.json`
**Files written:** `congress_bills.json`
**External libs:** `requests`, `python-dotenv`, `json`, `re`, `datetime`

---

## politician_performance.py — Phase 6.5 Supplement: Politician Trading Performance

**File:** `politician_performance.py`
**Phase:** 6.5 — Political Intelligence (supplement)
**Role:** Pre-computes estimated P&L for every congressional stock trade using the midpoint of the disclosed dollar range and historical price data from yfinance (5-year history per ticker, one batch download per ticker to avoid rate limits). Aggregates by politician: total invested estimate, total estimated P&L, trade counts (buys/sells), and return percentage. Output is `politician_performance.json`, used by the political intelligence web UI.

**Key paths:**

| Name | Value |
|---|---|
| `BASE_DIR` | `Path(__file__).parent` |
| `OUTPUT_FILE` | `BASE_DIR / "politician_performance.json"` |

---

### `_parse_range_midpoint(range_str: str) -> float`

**Location:** `politician_performance.py:34`

**Parameters:**
- `range_str` (`str`): Disclosed dollar range string from STOCK Act filing.

**Returns:** `float` — estimated midpoint in dollars.

**Behavior (in order):**
1. Tries `float(cleaned_str)` — handles plain numeric Amount fields.
2. Matches `"Over $X"` pattern: returns `X` as floor.
3. Matches `"$X - $Y"` pattern: returns `(X + Y) / 2`.
4. If only one number found: returns it.
5. Returns `0.0` if unparseable.

**Examples:**
```
"$1,001 - $15,000"        → 8000.5
"$50,001 - $100,000"      → 75000.5
"$1,000,001 - $5,000,000" → 3000000.5
"Over $5,000,000"         → 5000000.0
```

---

### `_build_ticker_history(tickers: list[str]) -> dict[str, pd.Series]`

**Location:** `politician_performance.py:71`

**Parameters:**
- `tickers` (`list[str]`): All unique tickers across all trades.

**Returns:** `dict` mapping ticker → `pd.Series` of daily close prices (5-year history, date index).

**Behavior:**
1. For each ticker: calls `yf.download(ticker, period="5y", interval="1d", auto_adjust=True)`.
2. Squeezes multi-level column if needed.
3. Stores `close.dropna()` as the Series.
4. Rate limiting: 0.3-second sleep between calls; 1.0-second sleep every 10 tickers.
5. On error: stores empty `pd.Series`.

This single-batch-per-ticker approach avoids the per-trade-date API calls that would cause rate limiting.

**External libs:** `yfinance`, `pandas`, `time`

---

### `_price_on_date(series: pd.Series, date_str: str) -> float | None`

**Location:** `politician_performance.py:104`

**Parameters:**
- `series` (`pd.Series`): Pre-fetched price history for a ticker.
- `date_str` (`str`): Target date string.

**Returns:** `float | None` — closing price on or nearest-before the target date.

**Behavior:**
1. Filters `series` to dates `<= pd.Timestamp(date_str)`.
2. Returns `float(available.iloc[-1])` — the most recent price on or before the trade date.
3. If no dates precede target (trade predates history), uses earliest available price.
4. Returns `None` on any exception.

**External libs:** `pandas`

---

### `main()`

**Location:** `politician_performance.py:120`

**Parameters:** None

**Behavior:**

**[LOAD_TRADES] (`politician_performance.py:122–143`):**
1. Loads `intelligence_output.json["housing_trades"]`.
2. Loads `politician_parties.json` (name → party/state dict).
3. Filters to trades that have both `ticker` and `representative` fields.

**[PRICE_FETCH] (`politician_performance.py:146–157`):**
4. Collects unique tickers across all trades.
5. Calls `_build_ticker_history(unique_tickers)` — one download per ticker.

**[COMPUTE] (`politician_performance.py:159–205`):** For each trade:
```
midpoint      = _parse_range_midpoint(range_str)
price_then    = _price_on_date(series, date_str)
price_now     = series.iloc[-1]

raw_return    = (price_now - price_then) / price_then
if is_sale:   raw_return = -raw_return    # sold positions invert gains

pct_return    = raw_return × 100
est_pnl       = midpoint × raw_return
```

Produces a `trade_record` dict per trade with: politician, party, state, chamber, ticker, transaction, date, range_disclosed, midpoint_est, price_at_trade, price_current, pct_return, est_pnl.

**[AGGREGATE] (`politician_performance.py:209–244`):** Groups by politician using `defaultdict`. For each politician accumulates:
- `total_invested_est`: sum of `midpoint_est` for all trades
- `total_est_pnl`: sum of `est_pnl` for all trades
- `trade_count`, `buy_count`, `sell_count`

Computes per-politician estimated return:
```
pct = total_est_pnl / total_invested_est × 100
```

Sorts `summary_rows` by `Est. P&L ($)` descending.

**[SAVE] (`politician_performance.py:265–276`):**
Writes:
```json
{
  "disclaimer": "All figures are ESTIMATES based on midpoint of disclosed ranges...",
  "generated_at": "...",
  "politician_summary": [...sorted by P&L...],
  "trade_detail": [...all individual trades...]
}
```
to `politician_performance.json`.

**Files read:** `GPT_Economy/Intelligence_layer (IN PROGRESS)/intelligence_output.json`, `politician_parties.json`
**Files written:** `politician_performance.json`
**External libs:** `yfinance`, `pandas`, `json`, `re`, `datetime`, `collections.defaultdict`

---

## Cross-Module Data Flow Summary

```
Phase 2 (Scraping)
  └── news_output/articles_*.json
        └── Phase 3 (phase3_extraction.py)
              └── news_output/enriched_news_sentiment.json
                    └── Phase 4 (phase4_clustering.py)
                          └── news_output/clustered_summaries.json
                                └── Phase 5 (GPT summarization — external)
                                      └── news_output/sector_summaries.json

Phase 6 (Economic Reasoning — external)
  └── news_output/economic_reasoning_summary.json

Phase 6.5 (Political Intelligence — economic_engine_insider.py)
  └── intelligence_output.json
        ├── congress_bills.py → congress_bills.json
        └── politician_performance.py → politician_performance.json

Phase 7 (historical_correlation.py)
  ├── reads: economic_reasoning_summary.json + enriched_news_sentiment.json
  └── writes: historical_parallels.json

Phase 8.7 (quantlib_metrics.py)
  ├── reads: signal_output_phase3.json
  └── writes: quantlib_metrics.json

Phase 8.9 (opportunity_score.py)
  ├── reads: economic_reasoning_summary.json, signal_output_phase3.json,
  │          recession_signals_output.json, user_profile.json, sector_summaries.json
  └── writes: opportunity_scores.json

Phase 9 (Backtesting — external backtrader script)
  └── results_run/summary_metrics.json

Phase 10 (portfolio_tracker.py)
  ├── reads: signal_output_phase3.json, opportunity_scores.json,
  │          quantlib_metrics.json, user_profile.json, portfolio_snapshot.json
  └── writes: portfolio_snapshot.json

Phase 13 (recession_signals.py)
  ├── reads: FRED public CSV + yfinance (live data)
  └── writes: recession_signals_output.json

Phase 11 (chef_gpt.py) — FINAL SYNTHESIS
  ├── reads: user_profile.json, economic_reasoning_summary.json,
  │          sector_summaries.json, signal_output_phase3.json,
  │          summary_metrics.json, recession_signals_output.json,
  │          intelligence_output.json, historical_parallels.json,
  │          opportunity_scores.json, quantlib_metrics.json
  └── writes: intelligence_report.json  ← THE FINAL DELIVERABLE

Phase 12 (controller.py) — ORCHESTRATES ALL ABOVE
  ├── reads/writes: pipeline_state.json
  └── invokes all scripts above via subprocess
```

---

*Generated 2026-06-21. All line numbers reference the source files as they exist on that date. Formulas and prompts are reproduced verbatim from the code — nothing is invented.*
