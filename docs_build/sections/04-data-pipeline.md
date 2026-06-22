# Part 4 — Offline Data Build Pipeline

This document is an exhaustive technical reference for every Python script that constitutes the ThinkFree offline data build pipeline. These scripts fetch external data and emit the `webapp/js/*_data.js` bundles (each assigned to a `window.NAME` global) consumed by the static front-end, as well as `private_data/` JSON files served by the authenticated FastAPI backend.

All scripts live under `/Users/allanaziz/Desktop/ThinkFree/ThinkFree-main/webapp/` unless noted otherwise.

---

## Summary Table

| Script | Data Source | Output File | Env Var / API Key |
|---|---|---|---|
| `build_data.py` | Local JSON outputs (ThinkFree pipeline) | `webapp/js/data.js` (`window.TF_DATA`) | None (reads project JSON) |
| `build_states.py` | FRED (St. Louis Fed) | `webapp/js/states_data.js` (`window.STATES_DATA`) | `FRED_API_KEY` |
| `build_census.py` | U.S. Census Bureau ACS 1-Year API | `webapp/js/states_data.js` (enriches) | `CENSUS_API_KEY` |
| `build_bea.py` | BEA Regional Price Parities API | `webapp/js/states_data.js` (enriches) | `BEA_API_KEY` |
| `build_bls.py` | BLS Regional CPI API v2 | `webapp/js/states_data.js` (enriches) | `BLS_API_KEY` |
| `build_fec.py` | OpenFEC API (api.open.fec.gov) | `webapp/js/fec_data.js` (`window.FEC_DATA`) | `FEC_API_KEY` |
| `build_influence.py` | LittleSis bulk dump (.gz) | `webapp/js/influence_data.js` (`window.IW_DATA`) | None (local files) |
| `build_legiscan.py` | LegiScan Public API | `webapp/js/legiscan_data.js` (`window.LEGISCAN_DATA`) | `LEGISCAN_API_KEY` |
| `build_member_bills.py` | Congress.gov API v3 | `webapp/js/member_bills.js` (`window.MEMBER_BILLS`) | `CONGRESS_API_KEY` |
| `build_news_intel.py` | OpenAI Chat API (via local pre-processing) | `webapp/js/news_intel.js` (`window.NEWS_INTEL`) | `OPENAI_API_KEY` |
| `build_nonprofits.py` | ProPublica Nonprofit Explorer API | `webapp/js/nonprofit_data.js` (`window.NP_DATA`) | None (public API) |
| `build_openstates.py` | Open States / Plural API v3 | `webapp/js/openstates_data.js` (`window.OPENSTATES_DATA`) | `OPENSTATES_API_KEY` |
| `build_prices.py` | Finnhub REST API | `webapp/js/prices_data.js` (`window.PRICES_DATA`) | `FINNHUB_API_KEY` |
| `build_quant.py` | yfinance (via `quantlib_metrics.py`) + `ta` library | `webapp/js/quant_data.js` (`window.QUANT_DATA`) | None (yfinance) |
| `build_relationships.py` | U.S. Senate LDA API (anonymous) | `webapp/js/relationships_data.js` (`window.RELATIONSHIPS`) | None (anonymous) |
| `build_sec.py` | sec-api.io REST API | `webapp/js/sec_data.js` (`window.SEC_DATA`) | `SECAPI_IO_KEY` |
| `build_secbulk.py` | SEC EDGAR bulk ZIPs (local) | `webapp/js/secbulk_data.js` (`window.SECBULK_DATA`) | None (local files) |
| `build_sp500.py` | GitHub datasets/s-and-p-500-companies CSV | `webapp/js/sp500_data.js` (`window.SP500`) | None |
| `build_usaspending.py` | USASpending.gov API v2 | `webapp/js/usaspending_data.js` (`window.USA_DATA`) | None (public API) |
| `fetch_politician_photos.py` | unitedstates/images GitHub Pages | `webapp/assets/politicians/{bioguide}.jpg` | None |
| `minify_data.py` | Local `webapp/js/*.js` files | Overwrites all data `.js` files in-place | None |
| `scripts/extract_data_to_json.py` | Local `webapp/js/*_data.js` files | `private_data/*.json` + `private_data/manifest.json` | None |

---

## Pipeline Execution Order

The scripts form a dependency chain. The correct build sequence is:

```
build_sp500.py
build_states.py         # requires FRED
build_census.py         # enriches states_data.js; requires Census
build_bea.py            # enriches states_data.js; requires BEA
build_bls.py            # enriches states_data.js; requires BLS
build_influence.py      # requires LittleSis .gz files in ~/Downloads
build_secbulk.py        # requires SEC EDGAR ZIPs in ~/Downloads + influence_data.js
build_usaspending.py    # requires sp500_data.js, prices_data.js, influence_data.js
build_sec.py            # requires influence_data.js; SECAPI_IO_KEY
build_fec.py            # requires politician_performance.json; FEC_API_KEY
build_data.py           # requires all project JSON outputs (pipeline phases 1-13)
build_legiscan.py       # LEGISCAN_API_KEY
build_openstates.py     # OPENSTATES_API_KEY; enriches LegiScan roster
build_member_bills.py   # requires data.js (for bioguide IDs); CONGRESS_API_KEY
build_nonprofits.py     # no key
build_relationships.py  # requires influence_data.js, prices_data.js, sp500_data.js
build_prices.py         # requires sp500_data.js, secbulk_data.js, influence_data.js,
                        #   usaspending_data.js, data.js; FINNHUB_API_KEY
build_quant.py          # requires data.js, prices_data.js; yfinance + ta
build_news_intel.py     # requires data.js, quant_data.js, prices_data.js,
                        #   signal_output_phase3.json, sector_summaries.json,
                        #   economic_reasoning_summary.json; OPENAI_API_KEY
fetch_politician_photos.py   # requires politician_parties.json
minify_data.py               # final step; run before deploy
scripts/extract_data_to_json.py  # run after all JS files written; creates private_data/
```

---

## `build_data.py`

**File:** `webapp/build_data.py`
**Purpose:** The central aggregator. Reads all upstream ThinkFree pipeline JSON outputs (recession signals, politician trades, congress bills, news summaries, historical events, portfolio snapshot, opportunity scores) and emits `webapp/js/data.js` as `window.TF_DATA = {...}`. This is the primary data bundle consumed by the static front-end and is a prerequisite for most other build scripts.

**Data source:** Local project JSON files only — no external API calls.

**Env vars / API keys:** None.

**Output:** `webapp/js/data.js` — `window.TF_DATA`

### Output shape (top-level keys)

```json
{
  "generated_at": "<ISO-8601 UTC>",
  "user": {"name": "Allan", "plan": "Free Plan"},
  "disclaimer": "<STOCK Act disclaimer string>",
  "market_ticker": [...],
  "recession": {...},
  "portfolio": {...},
  "politicians": [...],
  "recent_trades": [...],
  "sectors": [...],
  "tickers_opp": [...],
  "parallels": [...],
  "events": [...],
  "bills": [...],
  "correlation": {...},
  "news": [...],
  "means": [...],
  "everyday": [...]
}
```

### Input files read

| File (relative to repo root) | Used for |
|---|---|
| `politician_performance.json` | Politician trade summary, trade detail, disclaimer |
| `politician_parties.json` | Bioguide ID map (for photo lookups) |
| `portfolio_snapshot.json` | Portfolio metrics and positions |
| `recession_signals_output.json` | Recession score, factors, raw indicators |
| `opportunity_scores.json` | Sector and ticker opportunity scoring |
| `historical_parallels.json` | Historical analog periods |
| `news_output/summaries.json` | Summarized news articles |
| `news_output/clustered_summaries.json` | Clustered article summaries ("what this means for you") |
| `news_output/enriched_news_sentiment.json` | Source, sentiment, credibility for each article |
| `congress_bills.json` | Bill correlations and correlated trades |
| `historical_events_db.json` | 20-event historical library (Tulip mania → AI boom) |

### Functions

#### `load(name, default=None)`
Loads a JSON file by path relative to the repo root. Returns `default` (or `{}`) on any error, so missing upstream files degrade gracefully instead of crashing the build.

#### `money(n: float) -> str`
Formats a raw number into a human-readable currency string (`$1.23B`, `$4.5M`, `$1.2K`, `$123`). Used throughout the data to pre-format all monetary values for display.

#### `source_credibility(source: str) -> float`
Looks up a numeric credibility score (0–1) for a news source string against a hardcoded `CREDIBILITY` dict. Scores range from 0.97 (Reuters/AP) down to 0.38 (AccessWire). Sources scoring below `MIN_CREDIBILITY = 0.45` are dropped entirely from the news feed.

#### `credibility_tier(score: float) -> str`
Maps a credibility score to a display label: `"Trusted"` (≥ 0.9), `"Reliable"` (≥ 0.75), `"Mixed"` (≥ 0.6), `"Low / Opinion"` (≥ 0.45), `"Unreliable"` (< 0.45).

#### `_clean_str(s: str) -> str`
Strips em dashes and en dashes from a string (replacing with commas or hyphens), collapses double spaces, and removes orphaned punctuation. The front-end prohibits the `—` character.

#### `strip_dashes(obj)`
Recursively walks any nested JSON structure (dict, list, str) and applies `_clean_str` to all string values. Called on the entire `data` dict just before writing.

#### `ordinal(n) -> str`
Converts an integer to its ordinal string (`1st`, `2nd`, `3rd`, `119th`, etc.) for use in Congress.gov URLs.

#### `bill_url(bill_id: str) -> str`
Converts a ThinkFree bill ID of the form `"HR1234-119"` or `"S2393-119"` into a congress.gov canonical URL. Supports HR, S, HRES, SRES, HJRES, SJRES, HCONRES, SCONRES bill types.

#### `quiver_url(name: str, bg: str) -> str`
Builds a QuiverQuant politician trading URL by URL-encoding the politician's name and appending their bioguide ID.

#### `make_donors(name: str) -> list`
Generates a deterministic (seeded by the character sum of the politician's name) list of 6 sample donor PAC records. **These are sample data, clearly labeled as such in the UI**, intended to be replaced with real OpenSecrets/FEC API data when a key is available.

#### `make_supporters(name: str) -> list`
Generates a deterministic list of 4 sample outside-spending group records (Support/Oppose stance). Same seeding approach as `make_donors`.

#### `lobby_for(sectors: list) -> list`
Maps a list of sector names to associated industry lobbying groups (from the hardcoded `_SECTOR_LOBBY` dict) and returns up to 6 `{"org": ..., "sector": ...}` records. Falls back to `"Multi-industry coalition"` if no sector match is found.

#### `plain_bill(title: str, sectors, tickers) -> str`
Generates a best-effort plain-English explanation of what a bill does, based on keyword matching in the title (e.g., "chips" → "boosts U.S. semiconductor manufacturing"). Returns a fallback explanation referencing the matched sectors and tickers if no keyword matches.

#### `build_everyday(raw: dict, oil_price: float, rec: dict) -> list`
Translates market and economic indicators into a list of plain-English "What This Means for You" items across eight categories: Rent & Mortgages, Credit Cards & Auto Loans, Gas Prices, Groceries, Utilities & Electricity, Jobs & Hiring, Consumer Goods & Tariffs, Savings & CDs. Each item has `category`, `dir` (`"up"` / `"down"` / `"neutral"`), `impact` (one-line headline), and `detail` (2–3 sentence plain-English explanation). This is the core ThinkFree translation-for-everyday-people feature.

#### `enrich(nm: str, p_meta: dict) -> dict`
Builds a rich per-politician record including: a plain-English narrative summary, top traded tickers by count, estimated portfolio value and net-worth range, donor PAC list, outside-spending group list, related correlated bills, a full chronological trade timeline (with associated bill, days-delta, and P&L), and a count of trades that preceded a bill action ("influenced count").

#### `build() -> None`
The main orchestration function. Calls all of the above in sequence, assembles the final `data` dict, applies `strip_dashes`, and writes `webapp/js/data.js`.

**Credibility-filtered news assembly:** For each article in `summaries.json`, the function joins it with `enriched_news_sentiment.json` by URL, computes a credibility-weighted impact score (`cred × (0.5 + |compound|) × (1 + min(richness, 1))`), drops sources below `MIN_CREDIBILITY`, and round-robins across tickers for diversity before sorting by `(credibility, impact)` descending. Up to 160 articles are kept.

**Conflict index:** Computes a 0–100 "Conflict Index" from three components: breadth (45% — share of related bills that had trades opened beforehand), intensity (35% — share of correlated trades placed before the action), and lead (20% — advance positioning capped at 90 days).

---

## `build_states.py`

**File:** `webapp/build_states.py`
**Purpose:** Fetches per-state economic indicators from the FRED API and computes two ThinkFree-specific scores — Constituent Prosperity Score and Constituent Pressure Score — for all 50 states plus DC. Writes the initial `webapp/js/states_data.js`. Must be run first in the four-part states chain (`build_states` → `build_census` → `build_bea` → `build_bls`).

**Data source:** FRED (Federal Reserve Bank of St. Louis) — `api.stlouisfed.org/fred/series/observations`

**Env vars / API keys:** `FRED_API_KEY` (read from `.env`)

**Output:** `webapp/js/states_data.js` — `window.STATES_DATA`

**Rate limiting:** `time.sleep(0.15)` between states (≈340 calls for 51 jurisdictions × 4 series each). No explicit rate limit documented by FRED; 0.15s provides conservative headroom.

### FRED Series Used

| Series pattern | Metric |
|---|---|
| `{ST}UR` | Unemployment rate (4 observations) |
| `{ST}STHPI` | All-transactions house price index (8 observations) |
| `{ST}PCPI` | Per-capita personal income (6 observations) |
| `MEHOINUS{ST}A672N` | Real median household income (3 observations) |

### Output shape (`byState` entry)

```json
{
  "name": "California",
  "unemployment": 4.8,
  "house_price_index": 542.1,
  "house_price_growth": 3.2,
  "per_capita_income": 74200,
  "income_growth": 1.8,
  "median_household_income": 85300,
  "prosperity_score": 62,
  "pressure_score": 41
}
```

### Functions

#### `fred(series: str, limit: int = 8) -> list`
Fetches observations from the FRED API for a given series ID, returning up to `limit` observations in descending order. Returns an empty list on any error.

#### `latest(obs: list) -> tuple[float | None, str | None]`
Returns the first valid `(float(value), date)` pair from a FRED observations list, skipping non-numeric entries.

#### `yoy(obs: list) -> float | None`
Computes the year-over-year percentage change using the most recent value vs. approximately 4 quarters back (index position 4 in descending order). Returns `None` if fewer than 5 observations are available.

#### `clamp(v, lo=0, hi=100) -> float`
Clamps a value to `[lo, hi]`.

#### `main() -> None`
Iterates over all 51 jurisdictions, fetches 4 FRED series per state, computes prosperity and pressure scores (relative scoring across the full 51-jurisdiction set), and writes `states_data.js`.

**Prosperity score formula:** `(income_rank × 45) + (clamp((7 - unemp) / 7 × 35, 0, 35)) + (clamp(incg × 3, −10, 20))`

**Pressure score formula:** `clamp((hpi_growth − income_growth) × 6, 0, 60) + clamp((unemp − 3.5) × 6, 0, 25) + clamp(hpi_growth × 1.2, 0, 15)`

---

## `build_census.py`

**File:** `webapp/build_census.py`
**Purpose:** Enriches `webapp/js/states_data.js` with housing and affordability data from the U.S. Census Bureau ACS 1-Year API. Adds median home value, median rent, median household income, poverty rate, population, price-to-income ratio, affordability score, and rent burden percentage. Then recomputes prosperity and pressure scores incorporating affordability. Must run after `build_states.py`.

**Data source:** Census ACS 1-Year API — `api.census.gov/data/{YEAR}/acs/acs1` (year hardcoded to 2023)

**Env vars / API keys:** `CENSUS_API_KEY` (read from `.env`)

**Output:** `webapp/js/states_data.js` — `window.STATES_DATA` (in-place enrichment)

**Rate limiting:** One API call for all states simultaneously (single batch request using `for=state:*`). No `sleep` needed.

### ACS Variables Fetched

| ACS variable | Field added |
|---|---|
| `B19013_001E` | `median_household_income` |
| `B25077_001E` | `median_home_value` |
| `B25064_001E` | `median_rent` |
| `B17001_002E` | `poverty_count` (used to derive `poverty_rate`) |
| `B01003_001E` | `population` |

### Derived fields

| Field | Formula |
|---|---|
| `poverty_rate` | `poverty_count / population × 100` |
| `price_to_income` | `median_home_value / median_household_income` |
| `affordability` | `clamp((9 − (home_value / income)) / 7 × 100, 0, 100)` — 100 = most affordable (≤ 2× income), 0 = least (≥ 9×) |
| `rent_burden_pct` | `median_rent × 12 / median_household_income × 100` |

### Functions

#### `main() -> None`
Reads the current `states_data.js`, parses the JSON payload, makes a single Census API call for all states using FIPS-to-postal mapping (`FIPS` dict), derives the computed fields above, recomputes prosperity and pressure scores with affordability included, and rewrites `states_data.js`.

**Updated prosperity score formula:** `(affordability × 0.30) + (clamp((7 − unemp) / 7 × 30, 0, 30)) + (clamp((18 − poverty_rate) / 18 × 25, 0, 25)) + clamp(incg × 2, −8, 15)`

**Updated pressure score formula:** `((100 − affordability) × 0.45) + clamp((hpg − incg) × 4, 0, 30) + clamp((rent_burden_pct − 25) × 1.5, 0, 25)`

---

## `build_bea.py`

**File:** `webapp/build_bea.py`
**Purpose:** Adds BEA Regional Price Parities (RPP, US = 100) to each state in `states_data.js`. RPP measures cost of living relative to the national average. Also computes `real_purchasing_power` (nominal income adjusted for local price level) and folds cost of living into the prosperity and pressure scores. Must run after `build_census.py`.

**Data source:** BEA Regional API — `apps.bea.gov/api/data?datasetname=Regional&TableName=SARPP&LineCode=1&GeoFips=STATE` (year hardcoded to 2023)

**Env vars / API keys:** `BEA_API_KEY` (read from `.env`)

**Output:** `webapp/js/states_data.js` — `window.STATES_DATA` (in-place enrichment)

**Rate limiting:** One API call covers all states. No `sleep` needed.

### Fields added per state

| Field | Description |
|---|---|
| `cost_of_living` | RPP value (US = 100; e.g., Hawaii ≈ 118, Mississippi ≈ 84) |
| `real_purchasing_power` | `median_household_income / (rpp / 100)` — inflation-adjusted income |

### Score adjustment logic

- `pressure_score` += `clamp((rpp − 100) × 1.2, 0, 18)` — above-average cost of living adds up to 18 pressure points.
- `prosperity_score` += `clamp((real_purchasing_power − 70000) / 70000 × 10, −8, 8)` — real income vs. $70k baseline.

### Functions

#### `main() -> None`
Reads `states_data.js`, fetches BEA SARPP data for all states, maps state names to postal abbreviations using `NAME_TO_AB` dict, adds RPP and derived fields, adjusts scores, and rewrites the file.

---

## `build_bls.py`

**File:** `webapp/build_bls.py`
**Purpose:** Adds year-over-year CPI inflation by U.S. Census region (Northeast, Midwest, South, West) to each state in `states_data.js` and folds regional inflation into the Pressure score. Must run after `build_bea.py`.

**Data source:** BLS Public API v2 — `api.bls.gov/publicAPI/v2/timeseries/data/` (POST, JSON body). Series IDs 2023–2025, 4 regional series.

**Env vars / API keys:** `BLS_API_KEY` (read from `.env`)

**Output:** `webapp/js/states_data.js` — `window.STATES_DATA` (in-place enrichment, final states enrichment step)

**Rate limiting:** One API call fetches all 4 regional series in a single POST. No `sleep` needed.

### Regional CPI Series

| Region | BLS Series ID |
|---|---|
| Northeast | `CUUR0100SA0` |
| Midwest | `CUUR0200SA0` |
| South | `CUUR0300SA0` |
| West | `CUUR0400SA0` |

### Fields added per state

| Field | Description |
|---|---|
| `region` | Census region name (`"Northeast"`, `"Midwest"`, `"South"`, `"West"`) |
| `inflation` | YoY CPI % change for the state's region |

### Score adjustment

`pressure_score` += `clamp((inflation − 2.0) × 6, 0, 16)` — inflation above the 2% target adds up to 16 pressure points.

### Functions

#### `main() -> None`
Reads `states_data.js`, fetches BLS regional CPI (YoY computed from index position 0 vs. 12), maps each state to its region via `STATE_REGION` dict, adds `region` and `inflation` fields, adjusts pressure scores, and rewrites the file with the final combined source label.

---

## `build_fec.py`

**File:** `webapp/build_fec.py`
**Purpose:** Fetches real campaign-finance data for every politician tracked in ThinkFree (from `politician_performance.json`) via the OpenFEC API. Retrieves total receipts, individual contributions, PAC contributions, disbursements, cash on hand, and (for the top 30 by estimated P&L) a top-contributor breakdown by employer. Writes `webapp/js/fec_data.js`.

**Data source:** OpenFEC API — `api.open.fec.gov/v1/` (endpoints: `candidates/search/`, `candidate/{cid}/totals/`, `schedules/schedule_a/by_employer/`)

**Env vars / API keys:** `FEC_API_KEY` (read from `.env`)

**Output:** `webapp/js/fec_data.js` — `window.FEC_DATA`

**Rate limiting:** `time.sleep(0.25)` between each politician (≈ 240 calls/min on 2 calls per politician). The FEC API has rate limits not publicly documented; 0.25s is conservative.

### Output shape (`byName` entry)

```json
{
  "CandidateName": {
    "candidate_id": "H8CA01234",
    "fec_name": "PELOSI, NANCY",
    "party": "DEM",
    "office": "U.S. House",
    "url": "https://www.fec.gov/data/candidate/H8CA01234/",
    "cycle": 2024,
    "receipts": 4500000,
    "receipts_fmt": "$4.5M",
    "from_individuals": 3200000,
    "from_individuals_fmt": "$3.2M",
    "from_pacs": 800000,
    "from_pacs_fmt": "$800K",
    "disbursements": 3800000,
    "disbursements_fmt": "$3.8M",
    "cash": 1200000,
    "cash_fmt": "$1.2M",
    "top_employers": [
      {"employer": "University of California", "total_fmt": "$42K"}
    ]
  }
}
```

### Functions

#### `get(path: str, **params) -> dict`
Appends `api_key` to params and makes a GET request to the OpenFEC base URL. Returns parsed JSON.

#### `money(n) -> str | None`
Formats a number to a display currency string (B/M/K suffixes). Returns `None` for falsy input.

#### `politicians() -> list`
Reads `politician_performance.json` from the repo root and returns the `politician_summary` list.

#### `find_candidate(name: str, chamber: str, state: str) -> dict | None`
Searches the FEC `candidates/search/` endpoint for a politician by name and optionally by office (`H` for House, `S` for Senate). Sorts results by state match, presence of principal committees, and recency of last filing. Returns the best candidate match or `None`.

#### `main() -> None`
Loads all politicians, sorts by estimated P&L (descending) to identify the top 30 for employer breakdown, then for each politician: finds the FEC candidate record, fetches cycle totals, and optionally fetches top-employer breakdown. Writes `fec_data.js`.

---

## `build_influence.py`

**File:** `webapp/build_influence.py`
**Purpose:** Extracts the slice of the LittleSis relationship database that connects to companies already referenced in ThinkFree (tickers found in `data.js` bills, trades, and correlation data). Streams two large compressed files (`entities.json.gz` ~73 MB, `relationships.json.gz` ~105 MB) via `ijson` to avoid loading them entirely into memory, and writes only the matching board members, executives, owners, and donors.

**Data source:** LittleSis bulk data dump — `entities.json.gz` and `relationships.json.gz` (expected in `~/Downloads/`). No network call at runtime.

**Env vars / API keys:** None. Files must be manually downloaded.

**Local file requirements:**
- `~/Downloads/entities.json.gz`
- `~/Downloads/relationships.json.gz`

**Output:** `webapp/js/influence_data.js` — `window.IW_DATA`

**Rate limiting:** N/A (local file reads). Scans all entities (~millions of records) and relationships sequentially.

### LittleSis Category IDs Used

| Category | ID |
|---|---|
| `CAT_POSITION` | 1 (board member / executive) |
| `CAT_DONATION` | 5 |
| `CAT_OWNERSHIP` | 10 |
| `CAT_LOBBYING` | 7 (defined but not currently extracted) |

### Output shape (`companies` entry)

```json
{
  "AAPL": {
    "name": "Apple Inc.",
    "entity_id": 12345,
    "blurb": "...",
    "website": "https://apple.com",
    "domain": "apple.com",
    "employees": 165000,
    "revenue": 383285000000,
    "fedspending_id": "...",
    "lda_registrant_id": "...",
    "board": [{"name": "Tim Cook", "title": "CEO", "current": true}],
    "executives": [...],
    "owners": [...],
    "donors_in": [...]
  }
}
```

Caps: board ≤ 14 members, executives ≤ 10, owners ≤ 8, donors_in ≤ 8.

### Functions

#### `norm(t: str) -> str`
Normalizes a ticker by stripping all non-alphanumeric characters and uppercasing — used for fuzzy ticker matching against LittleSis `PublicCompany.ticker` field.

#### `our_tickers() -> set`
Reads `webapp/js/data.js` and extracts all ticker symbols referenced in bills, recent trades, and correlation top bills. Returns a set of ticker strings.

#### `domain_of(url: str) -> str`
Extracts the bare domain name from a URL (strips `http(s)://www.`).

#### `main() -> None`
Two-pass algorithm:
1. **Pass 1 (entities):** Streams `entities.json.gz` with `ijson`, identifies entities with a `PublicCompany.ticker` that matches one of the ThinkFree tickers, records entity ID → ticker mapping and company metadata.
2. **Pass 2 (relationships):** Streams `relationships.json.gz` with `ijson`, for each relationship involving a matched company entity extracts position (board/executive), ownership, or donation data and appends to the company's record.

Writes `influence_data.js` with all matched companies.

---

## `build_legiscan.py`

**File:** `webapp/build_legiscan.py`
**Purpose:** Fetches real state-legislative data for all 50 states plus DC from the LegiScan Public API. For each jurisdiction: retrieves the current session, the full bill master list with session-wide status breakdown, the most recently-active economically-relevant bills (tagged with ThinkFree topics), deep bill details (sponsors + roll-call votes) for the top 6 most recent relevant bills, and the full legislator roster with party/chamber composition. Writes `webapp/js/legiscan_data.js`.

**Data source:** LegiScan API — `api.legiscan.com/` (operations: `getSessionList`, `getMasterList`, `getBill`, `getSessionPeople`)

**Env vars / API keys:** `LEGISCAN_API_KEY` (read from `.env`)

**Output:** `webapp/js/legiscan_data.js` — `window.LEGISCAN_DATA`

**Rate limiting:** `SLEEP = 0.3` seconds between API calls. Budget: the build spends approximately 51 × 3 calls (session list + master list + people) plus up to 51 × 6 deep-dive calls ≈ ~460 total, well within the 30,000-query monthly free-tier limit.

### Economic Topic Tags

Bills are matched against 10 topic categories by keyword scanning the bill title:

| Topic | Sample Keywords |
|---|---|
| Taxes | tax, taxation, revenue, levy |
| Budget | appropriat, budget, spending, fund transfer |
| Housing | housing, rent, tenant, landlord, eviction, mortgage |
| Wages & Labor | minimum wage, wage, labor, employ, overtime, union |
| Healthcare | health, medicaid, medicare, insurance, prescription |
| Energy & Utilities | energy, utility, electric, natural gas, fuel |
| Education | education, school, tuition, student, university |
| Consumer & Credit | consumer, credit, loan, lending, debt, payday |
| Benefits | unemployment, snap, benefit, pension, retirement |
| Business | business, small business, commerce, license, regulation |

### Output shape (`byState` entry)

```json
{
  "CA": {
    "state": "CA",
    "name": "California",
    "session": {
      "id": 1789,
      "name": "2023-2024 Regular Session",
      "year_start": 2023,
      "year_end": 2024,
      "special": false
    },
    "bill_total": 4182,
    "status_breakdown": {"Introduced": 2100, "Engrossed": 800, ...},
    "relevant_count": 40,
    "bills": [
      {
        "bill_id": 1234567,
        "number": "SB 567",
        "url": "...",
        "title": "Tenant Protections Act",
        "status": "Engrossed",
        "status_code": 2,
        "last_action_date": "2024-03-15",
        "last_action": "Read second time",
        "topics": ["Housing", "Wages & Labor"],
        "sponsors": [...],
        "votes": [...]
      }
    ],
    "legislator_total": 118,
    "composition": {"Senate": {"D": 31, "R": 8, "I": 1, "Other": 0}, "House": {...}},
    "legislators": [...]
  }
}
```

### Functions

#### `get(**params) -> dict`
Makes a GET request to the LegiScan API with the given parameters plus `key`. Raises `RuntimeError` if the response status is not `"OK"`.

#### `topics_for(text: str) -> list`
Lowercases the input and checks for keyword matches against `TOPICS`. Returns a list of matching topic strings.

#### `pick_session(sessions: list) -> dict`
Selects the most recent regular (non-special) session from the LegiScan session list. Falls back to most recent overall session if no regular session exists.

#### `clean_people(raw: list) -> list`
Filters out committee sponsors (`committee_sponsor == 1`) and roles other than `"Sen"` / `"Rep"`, then trims each legislator record to: `people_id`, `name`, `party`, `chamber`, `district`, `ballotpedia`, `votesmart_id`.

#### `composition(legislators: list) -> dict`
Counts D/R/I/Other legislators per chamber (Senate/House) and returns a nested breakdown dict.

#### `deep_dive(bill_id: int) -> dict | None`
Fetches full bill detail via `getBill`, extracts sponsors (up to 8, with party/role/district) and the 5 most recent roll-call vote summaries (date, description, yea/nay counts, passed flag, chamber, URL). Returns `None` on error.

#### `build_state(abbr: str) -> dict | None`
Orchestrates the full data fetch for one state: session list → master list → status breakdown → topic tagging → sort by recency → cap at `RELEVANT_CAP = 40` bills → deep-dive top `DEEP_DIVE = 6` → legislators → composition. Returns the assembled state dict.

#### `main() -> None`
Iterates over all 51 jurisdictions, calls `build_state`, logs progress, and writes `legiscan_data.js`.

---

## `build_member_bills.py`

**File:** `webapp/build_member_bills.py`
**Purpose:** Fixes an accuracy problem in the politician hover cards: the original `data.js` showed 0–1 bills per member (only trade-correlated bills). This script fetches each tracked member's real sponsored and co-sponsored legislation counts from the Congress.gov API v3, keyed by bioguide ID, so the UI shows true legislative activity.

**Data source:** Congress.gov API v3 — `api.congress.gov/v3/member/{bioguide}/sponsored-legislation` and `.../cosponsored-legislation` (pagination count only, `limit=1`)

**Env vars / API keys:** `CONGRESS_API_KEY` (read from `.env`)

**Output:** `webapp/js/member_bills.js` — `window.MEMBER_BILLS`

**Rate limiting:** `SLEEP = 0.25` seconds between each API call (2 calls per member — sponsored + cosponsored).

### Output shape

```json
{
  "source": "Congress.gov API",
  "byBioguide": {
    "P000197": {"sponsored": 423, "cosponsored": 1892, "total": 2315}
  },
  "count": 47
}
```

### Functions

#### `politicians() -> list`
Reads the `webapp/js/data.js` file (already built by `build_data.py`), parses `window.TF_DATA`, and returns the `politicians` list.

#### `count(bioguide: str, kind: str) -> int`
Fetches the Congress.gov endpoint for `kind` (`"sponsored-legislation"` or `"cosponsored-legislation"`) with `limit=1` and returns the `pagination.count` value — an efficient count-only query that avoids pulling all bill records.

#### `main() -> None`
Filters politicians to those with a non-empty `bioguide` field, fetches sponsored and cosponsored counts for each, and writes `member_bills.js`.

---

## `build_news_intel.py`

**File:** `webapp/build_news_intel.py`
**Purpose:** The "Chef GPT" news intelligence pipeline for the webapp. Uses a cost-conscious two-phase design: heavy analysis is done locally (no API cost) and only a thin translation step calls the OpenAI API.

**Phase 1 (local, no API cost):** Groups already-fetched news by sector, attaches each ticker's technical signal (from `signal_output_phase3.json`), QuantLib metrics (from `quant_data.js`), and sector economic-reasoning summaries (from `news_output/sector_summaries.json`). Selects the top 8 most important stories per sector using a `credibility × |impact|` importance score.

**Phase 2 (one batched Chef GPT call per sector, ~8 total):** Sends the condensed brief (news + signals + context) to `gpt-4o-mini` (or the model in `THINKFREE_NEWS_MODEL` env var). The prompt asks for a 3–4 sentence plain-English sector summary plus a per-ticker `summary` + `what_it_means` for each mentioned ticker.

**Data source:** OpenAI Chat Completions API — `api.openai.com/v1/chat/completions`

**Env vars / API keys:**
- `OPENAI_API_KEY` (read from `.env`)
- `THINKFREE_NEWS_MODEL` (optional, default `gpt-4o-mini`)

**Local file dependencies:**
- `webapp/js/data.js` (news articles with credibility/sentiment)
- `webapp/js/quant_data.js` (QuantLib + TA signals per ticker)
- `webapp/js/prices_data.js` (company names for relevance filtering)
- `Module_2_Technical_Analysis/signal_output_phase3.json` (technical signals)
- `news_output/sector_summaries.json` (sector economic context)
- `news_output/economic_reasoning_summary.json` (overall economic context)

**Output:** `webapp/js/news_intel.js` — `window.NEWS_INTEL`

**CLI flag:** `--limit-sectors N` limits to the top N sectors by article count (useful for testing).

### Output shape

```json
{
  "source": "ThinkFree pipeline: local TA/QuantLib/economic analysis -> Chef GPT translation",
  "model": "gpt-4o-mini",
  "api_calls": 8,
  "bySector": {
    "Information Technology": {"summary": "...", "stories": 23}
  },
  "byTicker": {
    "NVDA": {"summary": "...", "what_it_means": "...", "sector": "Information Technology"}
  },
  "disclaimer": "Plain-English summary generated from public data and our models. Not financial advice."
}
```

### Functions

#### `chat_json(system: str, user: str, model: str, timeout: int = 60) -> dict`
Makes a POST to the OpenAI Chat Completions API with `response_format: {"type": "json_object"}` and `temperature: 0.3`. Returns the parsed JSON content of the first choice message.

#### `load_window(fname: str, marker: str) -> dict`
Parses a `window.NAME = {...};` data file from the `webapp/js/` directory by splitting on the `marker` string.

#### `load_json(p: Path, default) -> dict | list`
Loads any JSON file with a fallback default on error.

#### `norm_sector(s: str) -> str`
Normalizes sector names using `SECTOR_ALIASES` so news sector labels (e.g., `"Technology"`, `"Healthcare"`) map to GICS standard names (`"Information Technology"`, `"Health Care"`).

#### `news_relevant(item: dict, tk: str, names: dict) -> bool`
Filters out common-word ticker mismatches (e.g., `ON`, `IT`, `DD`). Returns `True` only if the article text actually mentions the company name or the ticker symbol in a recognizable format (`$TICK` or `(TICK)`).

#### `importance(n: dict) -> float`
Scores a news item for sector ranking: `impact × 2 + credibility`.

#### `main() -> None`
Groups news by normalized sector, selects top 8 by importance, builds a condensed brief with TA signals and QuantLib metrics attached, calls OpenAI once per sector, and writes `news_intel.js`.

---

## `build_nonprofits.py`

**File:** `webapp/build_nonprofits.py`
**Purpose:** Fetches IRS Form 990 financial data for the lobbying and advocacy organizations shown in InfluenceWeb (the `_SECTOR_LOBBY` and `_OUTSIDE_GROUPS` constants in `build_data.py`). Uses ProPublica's Nonprofit Explorer API — completely free, no authentication. Writes `webapp/js/nonprofit_data.js`.

**Data source:** ProPublica Nonprofit Explorer API — `projects.propublica.org/nonprofits/api/v2` (endpoints: `search.json`, `organizations/{ein}.json`)

**Env vars / API keys:** None. The API is public and unauthenticated.

**Output:** `webapp/js/nonprofit_data.js` — `window.NP_DATA`

**Rate limiting:** `time.sleep(0.3)` between each organization (2 calls per org: search + detail).

### Hardcoded Organizations (24 total)

Industry trade groups (e.g., PhRMA, American Petroleum Institute, National Association of Realtors) and political 501(c)(4) advocacy groups (e.g., League of Conservation Voters, Americans for Prosperity, Club for Growth).

### Output shape (`byName` entry)

```json
{
  "American Petroleum Institute": {
    "ein": "13-5467760",
    "name": "American Petroleum Institute",
    "city": "Washington",
    "state": "DC",
    "ntee": "S41",
    "ntee_label": "Community/Economic Dev.",
    "revenue": 284000000,
    "revenue_fmt": "$284.0M",
    "expenses": 278000000,
    "expenses_fmt": "$278.0M",
    "assets": 320000000,
    "assets_fmt": "$320.0M",
    "year": 2022,
    "url": "https://projects.propublica.org/nonprofits/organizations/..."
  }
}
```

### Functions

#### `get(url: str) -> dict`
Simple GET request with `ThinkFree/1.0` user-agent. Returns parsed JSON.

#### `best_match(query: str) -> dict | None`
Searches ProPublica by organization name and returns the first result, or `None` if no match.

#### `latest_financials(ein: str) -> tuple[dict, dict]`
Fetches the full organization record for an EIN. Returns `(org_record, best_filing)` where `best_filing` is the most recent filing with non-zero `totrevenue`, or the most recent filing overall.

#### `money(n) -> str | None`
Formats a number to a currency display string.

#### `main() -> None`
For each of the 24 hardcoded organizations: searches by display query, fetches financials for the matched EIN, extracts NTEE classification, and writes `nonprofit_data.js`.

---

## `build_openstates.py`

**File:** `webapp/build_openstates.py`
**Purpose:** Secondary source complementing LegiScan. Open States v3 provides clean, normalized legislator records with photos, email addresses, and Open States profile links. The front-end cross-references these against the LegiScan roster by name to show legislator headshots and contact info for accountability. The script degrades gracefully — states that fail to fetch (common due to Open States gateway 502s) are skipped and listed in `skipped`.

**Data source:** Open States / Plural API v3 — `v3.openstates.org/people` (paginated, 50 per page)

**Env vars / API keys:** `OPENSTATES_API_KEY` (read from `.env`)

**Output:** `webapp/js/openstates_data.js` — `window.OPENSTATES_DATA`

**Rate limiting:** `RATE = 1.15` seconds between each API call (≥ 1 request/sec as required by the free tier). Up to `MAX_PAGES = 12` pages per state, `PER_PAGE = 50` records. Each failed call retries up to `RETRIES = 4` times with linear backoff.

### Output shape

```json
{
  "source": "Open States / Plural (openstates.org) API v3",
  "byState": {
    "CA": {
      "name": "California",
      "legislators": [
        {
          "name": "Toni G. Atkins",
          "party": "D",
          "chamber": "Senate",
          "district": "39",
          "image": "https://...",
          "email": "senator.atkins@senate.ca.gov",
          "openstates_url": "https://openstates.org/person/..."
        }
      ]
    }
  },
  "count": 49,
  "skipped": ["WY"]
}
```

### Functions

#### `fetch_page(jurisdiction: str, page: int) -> dict`
Fetches one page of legislators for a jurisdiction name (full state name, e.g., `"California"`). Retries up to 4 times with linear backoff on any error (502, 429, timeout).

#### `build_state(abbr: str) -> list`
Paginates through all pages for a state, extracting `name`, `party` (normalized to D/R/I), `chamber` (normalized to Senate/House/Legislature), `district`, `image`, `email`, and `openstates_url` for each legislator. Stops at `MAX_PAGES`.

#### `main() -> None`
Iterates all 51 jurisdictions, calls `build_state`, counts legislators with photos, and writes `openstates_data.js`.

---

## `build_prices.py`

**File:** `webapp/build_prices.py`
**Purpose:** Fetches live price, daily change, market cap, company name, industry, exchange, logo, and website URL from Finnhub for every unique ticker referenced anywhere in the ThinkFree webapp. This creates the lookup table used by the ticker/company popup throughout the front-end. Two Finnhub calls per ticker (quote + profile2).

**Data source:** Finnhub REST API — `finnhub.io/api/v1/` (endpoints: `quote`, `stock/profile2`)

**Env vars / API keys:** `FINNHUB_API_KEY` (read from `.env`)

**Output:** `webapp/js/prices_data.js` — `window.PRICES_DATA`

**Rate limiting:** `SLEEP = 1.1` seconds between tickers (2 calls per ticker → approximately 55 tickers/minute on the free tier's 60 calls/minute cap). Tickers with no quote (price = 0 or None) are skipped after one call.

### Ticker Universe Assembly

`ticker_universe()` collects tickers from all previously-built JS bundles:
1. `sp500_data.js` — full S&P 500 (≈ 503 tickers)
2. `secbulk_data.js` — LittleSis-matched companies
3. `influence_data.js` — InfluenceWeb companies
4. `usaspending_data.js` — government contract recipients
5. `data.js` — congressional trade tickers and bill tickers and news symbols

Only tickers matching `[A-Z]{1,5}` (1–5 uppercase letters, no digits, no dots) are included — index labels and non-equity symbols are discarded.

### Output shape (`byTicker` entry)

```json
{
  "NVDA": {
    "price": 875.23,
    "change": 12.45,
    "change_pct": 1.44,
    "market_cap": 2160000000000,
    "market_cap_fmt": "$2.16T",
    "name": "NVIDIA Corporation",
    "industry": "Semiconductors",
    "exchange": "NASDAQ NMS - GLOBAL MARKET",
    "logo": "https://...",
    "weburl": "https://www.nvidia.com"
  }
}
```

### Functions

#### `_load_window(fname: str, var: str) -> dict`
Parses a `window.NAME = {...};` file by finding `var` in the text. Returns `{}` if the file does not exist.

#### `ticker_universe() -> list`
Collects all ticker strings from all existing JS data files and returns a sorted, deduplicated, filtered list of valid equity tickers.

#### `get(path: str, **params) -> dict`
Makes a GET request to the Finnhub API endpoint, appending the API token.

#### `money(n) -> str | None`
Formats a number to a display string with T/B/M suffixes.

#### `main() -> None`
Fetches quote and profile2 for every ticker in the universe, skips tickers with no price data, and writes `prices_data.js`.

---

## `build_quant.py`

**File:** `webapp/build_quant.py`
**Purpose:** The quantitative heart of the Predictive Market Signals engine. Computes real QuantLib-style metrics (Black-Scholes N(d2) probability, annualized volatility, 95% VaR, lognormal expected return, Kelly fraction) from `quantlib_metrics.py`, AND computes technical indicators (RSI, MACD, SMA-50/SMA-200 crossovers) via the `ta` library on live yfinance price history. Writes `webapp/js/quant_data.js` which feeds `predictions.js` and `build_news_intel.py`.

**Data source:** yfinance (Yahoo Finance) price history via `quantlib_metrics.fetch_recent_prices()`. No additional API key required.

**Env vars / API keys:** None. yfinance is unauthenticated.

**Output:** `webapp/js/quant_data.js` — `window.QUANT_DATA`

**Rate limiting:** Inherits yfinance's rate limiting. No explicit `sleep` in the script.

**CLI:** `./tf_env/bin/python webapp/build_quant.py [TICKER ...]` — explicit tickers override the automatic candidate selection.

### Output shape (`byTicker` entry)

```json
{
  "NVDA": {
    "price": 875.23,
    "volatility": 42.1,
    "var95": -3.21,
    "prob_up": 38.5,
    "prob_down": 18.2,
    "exp_return_1mo": 1.43,
    "kelly": 12.3,
    "sharpe": 1.84,
    "rsi": 68.4,
    "rsi_signal": "neutral",
    "macd": 2.341,
    "macd_signal_line": 1.982,
    "macd_cross": "bullish",
    "sma50": 820.11,
    "sma200": 750.33,
    "trend": "golden",
    "ta_score": 78,
    "ta_signal": "BUY",
    "ql_signal": "BUY"
  }
}
```

### Functions

#### `candidates(n: int = 22) -> list`
Selects up to 22 candidate tickers for analysis. Scores tickers by frequency: each news article mention = 1 point, each congressional trade = 0.5 points. Filters to only tickers present in `prices_data.js` and matching `[A-Z]+` (alphabetic only). Returns the top-n most-mentioned.

#### `sharpe(prices: list) -> float`
Computes the annualized Sharpe ratio from log returns: `(mean_daily_log_return × 252 − RISK_FREE_RATE) / (daily_std × √252)`.

#### `ta_block(prices: list) -> dict`
Computes technical indicators using the `ta` library on a pandas Series:
- **RSI** (14-period): signals `"oversold"` (< 30), `"overbought"` (> 70), `"neutral"`
- **MACD** (12/26/9): signals `"bullish"` (MACD > signal line) or `"bearish"`
- **SMA-50 / SMA-200 crossover**: `"golden"` (SMA-50 > SMA-200) or `"death"` cross

Composite `ta_score` (0–100): starts at 50, adds/subtracts 12 for RSI, ±14 for MACD, ±14 for trend. Maps score to `ta_signal`: `"BUY"` if ≥ 60, `"SELL"` if ≤ 40, `"HOLD"` otherwise.

#### `main() -> None`
Gets the ticker list (CLI args or `candidates()`), for each ticker fetches ≥ 30 days of price history, runs QuantLib metrics, runs `ta_block`, derives `ql_signal` from expected return and probability balance, and writes `quant_data.js`.

**QuantLib metrics reused** (imported from `quantlib_metrics.py`):
- `compute_annualized_vol(prices)` — annualized historical volatility
- `compute_var_95(prices)` — 95% Value-at-Risk (as % move)
- `bs_prob_above_target(spot, target, vol)` — Black-Scholes N(d2) probability
- `expected_return_lognormal(spot, vol)` — lognormal price expectation
- `kelly_fraction(prices)` — Kelly criterion fraction
- `RISK_FREE_RATE` — risk-free rate constant

---

## `build_relationships.py`

**File:** `webapp/build_relationships.py`
**Purpose:** Fetches federal lobbying relationships for every tracked company from the U.S. Senate Lobbying Disclosure Act (LDA) database. For each company: identifies the lobbying firms hired, individual lobbyists, issue areas lobbied, specific bills mentioned in lobbying descriptions, and total lobbying spend. This is purely a relationship graph — who hires whom and for what. The LDA API is anonymous (no key required).

**Data source:** U.S. Senate LDA API — `lda.senate.gov/api/v1/filings/` (GET, anonymous, ~15 requests/minute)

**Env vars / API keys:** None. The LDA API is fully public.

**Output:** `webapp/js/relationships_data.js` — `window.RELATIONSHIPS`

**Rate limiting:** `SLEEP = 4.2` seconds between each company (anonymous LDA limit ≈ 15 requests/minute). Large runs benefit from `--limit N`.

**CLI flags:**
- `--year 2024` — fiscal year for lobbying data (default 2024)
- `--limit N` — process only the first N companies (for testing)

**Input file dependencies:** `webapp/js/influence_data.js`, `webapp/js/prices_data.js` (for names), `webapp/js/sp500_data.js` (for names)

### Output shape (`byTicker` entry)

```json
{
  "MSFT": {
    "client": "Microsoft Corporation",
    "filings": 48,
    "spend_fmt": "$8.5M",
    "firms": ["Covington & Burling LLP", "Squire Patton Boggs"],
    "lobbyists": ["John Smith", "Jane Doe"],
    "issues": ["Technology", "Tax", "Trade (International)"],
    "bills": ["H.R. 1234", "S. 567"]
  }
}
```

### Functions

#### `load_window(fname: str, marker: str) -> dict`
Parses a `window.NAME = {...};` file from `webapp/js/`.

#### `search_name(name: str) -> str`
Strips common generic corporate suffixes (Inc, Corp, Ltd, Holdings, etc.) from a company name to produce a cleaner LDA search term. Falls back to the original name if stripping leaves nothing.

#### `get(url: str) -> dict`
Simple GET request with JSON Accept header.

#### `fetch_company(name: str, year: int) -> tuple[dict | None, str | None]`
Queries the LDA API for filings by `client_name` and `filing_year` (up to 25 results). Aggregates: lobbying firms (Counter), individual lobbyists (set), issue codes (Counter), bill numbers (regex-extracted from lobbying descriptions using `BILL_RE`), and total spend (income + expenses summed across filings). Returns `(record, None)` on success or `(None, error_message)` on failure.

#### `_money(n: float) -> str | None`
Formats a spend amount.

#### `main() -> None`
Merges company names from S&P 500, Finnhub, and LittleSis datasets (LittleSis legal names take precedence), fetches LDA data for each ticker, and writes `relationships_data.js`.

---

## `build_sec.py`

**File:** `webapp/build_sec.py`
**Purpose:** Fetches current board/director records and the latest 10-K filing metadata for each company in InfluenceWeb via the sec-api.io commercial API. Implements resume logic: if `sec_data.js` already exists, previously-fetched companies are preserved and only new ones are fetched. Stops immediately and prints a warning on HTTP 429 rate-limit responses.

**Data source:** sec-api.io — `api.sec-api.io/directors-and-board-members?token=KEY` (POST) and `api.sec-api.io?token=KEY` (POST for 10-K query)

**Env vars / API keys:** `SECAPI_IO_KEY` (read from `.env`)

**Output:** `webapp/js/sec_data.js` — `window.SEC_DATA`

**Rate limiting:** `time.sleep(0.15)` between companies. The sec-api.io free tier has strict rate limits; the resume logic allows incremental runs across multiple sessions.

### Output shape (`byTicker` entry)

```json
{
  "AAPL": {
    "entityName": "APPLE INC",
    "filedAt": "2024-11-01",
    "board": [
      {
        "name": "Tim Cook",
        "position": "CEO and Director",
        "age": 63,
        "since": "2011",
        "committees": ["Audit"],
        "independent": false
      }
    ],
    "latest_10k": {
      "filedAt": "2024-11-01",
      "url": "https://..."
    }
  }
}
```

### Functions

#### `post(url: str, payload: dict) -> dict`
Makes a POST request with JSON body. Handles gzip-compressed responses by checking for the `\x1f\x8b` magic bytes.

#### `tickers() -> list`
Reads `webapp/js/influence_data.js` and returns the list of matched company tickers.

#### `main() -> None`
Reads any existing `sec_data.js` to resume (preserving already-fetched companies), fetches board members and 10-K metadata for each new company, stops on 429, and writes the accumulated result.

---

## `build_secbulk.py`

**File:** `webapp/build_secbulk.py`
**Purpose:** Extracts XBRL financial data and filing metadata from the SEC EDGAR bulk datasets (`companyfacts.zip` and `submissions.zip`) for companies matched in InfluenceWeb. Completely offline — no network calls, no rate limits. These are large official SEC downloads (~multi-GB compressed) that must be placed in `~/Downloads/` manually.

**Data source:** SEC EDGAR bulk data — `companyfacts.zip` and `submissions.zip` (from `https://www.sec.gov/dera/data/`)

**Env vars / API keys:** None.

**Local file requirements:**
- `~/Downloads/companyfacts.zip`
- `~/Downloads/submissions.zip`

**Output:** `webapp/js/secbulk_data.js` — `window.SECBULK_DATA`

### Two-Pass Algorithm

**Pass 1 (submissions.zip):** Walks every `CIK*.json` file in the submissions ZIP, looking for CIK files whose `tickers` list intersects with the ThinkFree ticker set. Extracts company name, SIC description, exchange, EIN, filing activity summary (total filings, last filing date, form type counts), and builds the ticker-to-CIK map.

**Pass 2 (companyfacts.zip):** For each matched CIK, opens `CIK{padded_10}.json` in the companyfacts ZIP and extracts the latest annual XBRL values for:

| XBRL Concepts | Field |
|---|---|
| `RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, `SalesRevenueNet` | `revenue` |
| `Assets` | `assets` |
| `NetIncomeLoss`, `ProfitLoss` | `net_income` |
| `Liabilities` | `liabilities` |

### Output shape (`byTicker` entry)

```json
{
  "MSFT": {
    "cik": "789019",
    "name": "MICROSOFT CORP",
    "sic": "Prepackaged Software",
    "exchange": "Nasdaq",
    "ein": "91-1144442",
    "filings_total": 1247,
    "last_filing": "2024-10-25",
    "form_counts": {"10-Q": 142, "8-K": 380, "10-K": 38, ...},
    "revenue": 211915000000,
    "revenue_fmt": "$211.9B",
    "assets": 512163000000,
    "assets_fmt": "$512.2B",
    "net_income": 72361000000,
    "net_income_fmt": "$72.4B",
    "liabilities": 243686000000,
    "liabilities_fmt": "$243.7B",
    "fy": 2024,
    "xbrl_concepts": 612,
    "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=789019&type=10-K"
  }
}
```

### Functions

#### `load_ciks() -> dict`
Currently returns an empty dict — placeholder. CIK resolution is done via the submissions ZIP scan instead.

#### `fmt(n) -> str | None`
Formats a number to T/B/M/K currency string.

#### `latest_fact(us: dict, concepts: list) -> tuple[float | None, int | None, str | None]`
Searches the `us-gaap` XBRL facts dict for the most recent annual value among the given concept list. Prefers 10-K/20-F forms; falls back to any form. Returns `(value, fiscal_year, unit_key)`.

#### `our_tickers() -> set`
Reads `webapp/js/influence_data.js` and returns the set of company ticker keys.

#### `main() -> None`
Opens both ZIPs, runs the two-pass algorithm, and writes `secbulk_data.js`.

---

## `build_sp500.py`

**File:** `webapp/build_sp500.py`
**Purpose:** Downloads the S&P 500 constituent list (ticker, company name, GICS sector, GICS sub-industry) from the public GitHub `datasets/s-and-p-500-companies` repository and maps each company to one of ThinkFree's InfluenceWeb sector categories. Requires no API key.

**Data source:** GitHub raw CSV — `raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv` (public domain)

**Env vars / API keys:** None.

**Output:** `webapp/js/sp500_data.js` — `window.SP500`

**Rate limiting:** One HTTP request for the CSV. No delays needed.

### GICS to ThinkFree Sector Mapping

| GICS Sector | ThinkFree Sector (selected rules) |
|---|---|
| Industrials (Aerospace & Defense sub) | Defense |
| Industrials (Transport sub-industries) | Transportation |
| Industrials (other) | Industrials |
| Information Technology | Technology |
| Health Care (pharma/biotech/life sci.) | Pharmaceuticals |
| Health Care (other) | Healthcare |
| Financials | Financial Services |
| Energy | Oil & Gas |
| Utilities | Energy |
| Communication Services | Telecommunications |
| Real Estate | Real Estate |
| Consumer Discretionary / Staples | Consumer Goods |
| Materials | Materials |

### Output shape (`byTicker` entry)

```json
{
  "NVDA": {
    "name": "NVIDIA Corporation",
    "sector": "Technology",
    "gics": "Information Technology",
    "sub": "Semiconductors & Semiconductor Equipment"
  }
}
```

### Functions

#### `tf_sector(gics: str, sub: str) -> str`
Maps a GICS sector + sub-industry string to one of ThinkFree's 12 custom sector labels using a chain of `if`/`elif` checks with `in` substring matching on the lowercased sub-industry.

#### `main() -> None`
Fetches the CSV, parses it with `csv.DictReader`, maps each row, and writes `sp500_data.js`. Prints a per-sector count after writing.

---

## `build_usaspending.py`

**File:** `webapp/build_usaspending.py`
**Purpose:** Fetches total federal contract award dollars (2020–2025) and the top awarding agencies for each company tracked across all ThinkFree datasets (full S&P 500 + Finnhub names + LittleSis companies). Uses the public USASpending.gov API — no authentication required. Implements resume logic: companies already in `usaspending_data.js` are preserved across runs.

**Data source:** USASpending.gov API v2 — `api.usaspending.gov/api/v2/search/spending_by_category/awarding_agency/` (POST)

**Env vars / API keys:** None.

**Output:** `webapp/js/usaspending_data.js` — `window.USA_DATA`

**Rate limiting:** `time.sleep(0.5)` between companies. Uses SSL via `certifi` where available, falls back to no-verify SSL context.

**Award types:** `["A", "B", "C", "D"]` — federal contracts only (excludes grants and loans).

**Date range:** 2020-01-01 to 2025-12-31.

### Output shape (`byTicker` entry)

```json
{
  "LMT": {
    "recipient": "Lockheed Martin",
    "total_contracts": 47200000000,
    "total_contracts_fmt": "$47.2B",
    "top_agencies": [
      {"agency": "Department of Defense", "amount": 43100000000, "amount_fmt": "$43.1B"}
    ],
    "url": "https://www.usaspending.gov/search?keyword=Lockheed+Martin"
  }
}
```

### Functions

#### `company_names() -> dict`
Builds a `ticker → company_name` map from three sources in priority order (each overwrites earlier): S&P 500 names → Finnhub names → LittleSis legal names (highest priority). Strips common suffixes (", Inc.", " Inc.", ",") from all names before searching.

#### `post(url: str, payload: dict) -> dict`
Makes a POST request with JSON body using the SSL context.

#### `fmt(n) -> str | None`
Formats a number to a T/B/M/K/$ currency string.

#### `fetch(name: str) -> tuple[float, list]`
Posts the spending-by-awarding-agency query for a given recipient name. Returns `(total_dollars, agencies_list)` where `agencies_list` contains up to 6 agencies with name, amount, and formatted amount.

#### `main() -> None`
Assembles the company name map, loads any existing `usaspending_data.js` for resume, fetches data for new companies, and writes the result.

---

## `fetch_politician_photos.py`

**File:** `webapp/fetch_politician_photos.py`
**Purpose:** Downloads official public-domain congressional portrait photos for every politician tracked in ThinkFree. Uses the `@unitedstates/images` GitHub Pages collection, keyed by bioguide ID — the same IDs already stored in `politician_parties.json`. Photos are saved as `webapp/assets/politicians/{bioguide}.jpg`. Skips already-downloaded files (idempotent).

**Data source:** `unitedstates.github.io/images/congress/450x550/{bg}.jpg` (primary) with fallback to `raw.githubusercontent.com/unitedstates/images/gh-pages/congress/450x550/{bg}.jpg`. Public domain / no key required.

**Env vars / API keys:** None.

**Output:** `webapp/assets/politicians/{bioguide}.jpg` (one file per politician)

**Rate limiting:** `time.sleep(0.15)` between each download. The GitHub CDN has no documented rate limit at this cadence.

### Functions

#### `bioguide_ids() -> dict`
Reads `politician_parties.json` and extracts a `{bioguide_id: politician_name}` dict for all politicians that have a `bioguide` field.

#### `fetch(bg: str) -> bytes | None`
Tries each URL template in `SOURCES`, returns raw image bytes if the response is HTTP 200 and `len(data) > 1000` bytes. Returns `None` if all sources fail.

#### `main() -> None`
Creates `webapp/assets/politicians/` if needed, iterates all bioguide IDs, skips files already on disk with size > 1000 bytes, and downloads missing photos. Reports totals: downloaded, cached (skipped), missing.

---

## `minify_data.py`

**File:** `webapp/minify_data.py`
**Purpose:** Production optimization step. The build scripts emit pretty-printed (indented) JSON for readability during development. This script recompacts every `window.*_DATA` assignment in `webapp/js/*.js` to strip all whitespace, achieving approximately 30–40% size reduction. It is safe and idempotent: it only changes whitespace, never data. Code files (`app.js`, `scores.js`, etc.) are explicitly excluded. Run this once as the final step before deploying.

**Data source:** Local `webapp/js/*.js` files.

**Env vars / API keys:** None.

**Output:** Overwrites data `.js` files in `webapp/js/` in place.

### Excluded Code Files

`app.js`, `scores.js`, `genimpact.js`, `scoreinfo.js`, `predictions.js`, `glossary.js`, `congress.js`, `influenceweb.js`

### Functions

#### `compact(txt: str) -> str`
Uses Python's `json.JSONDecoder.raw_decode()` to find each `window.NAME = {...}` assignment in the file text, re-serializes the JSON value with `json.dumps(..., separators=(",", ":"))` (no whitespace), and reconstructs the file text. Handles files with multiple window assignments.

#### `main() -> None`
Iterates all `*.js` files in `webapp/js/` that contain `"window."` and are not in the `CODE` exclusion set, applies `compact`, overwrites the file if the result is smaller, and reports the size savings.

---

## `scripts/extract_data_to_json.py`

**File:** `scripts/extract_data_to_json.py`
**Purpose:** One-time (repeatable) migration step that converts the public `webapp/js/*_data.js` bundles into plain JSON files under `private_data/`, which the FastAPI backend server serves only to authenticated users. Also writes a `manifest.json` classifying each dataset as `core` (needed immediately after login), `lazy` (large, loaded on demand), or `live` (refreshed on a cadence). Does **not** delete the originals from `webapp/js/` so the current static app keeps working during the transition.

**Data source:** Local `webapp/js/*.js` files.

**Env vars / API keys:** None (stdlib only).

**Output:**
- `private_data/{GLOBAL_NAME}.json` — one file per dataset (minified JSON, no `window.` prefix)
- `private_data/manifest.json` — classification of all datasets

### Category Classification

| Category | Files | Rationale |
|---|---|---|
| `core` | `data.js`, `influence_data.js`, `relationships_data.js`, `nonprofit_data.js`, `fec_data.js`, `sec_data.js`, `secbulk_data.js`, `usaspending_data.js`, `states_data.js`, `sp500_data.js`, `quant_data.js`, `member_bills.js` | Must render app right after login |
| `lazy` | `legiscan_data.js`, `openstates_data.js` | Large; fetched only when State Legislature view is opened |
| `live` | `prices_data.js`, `news_intel.js` | Refreshed on user's subscription cadence |

### Manifest shape

```json
{
  "core": ["TF_DATA", "IW_DATA", "RELATIONSHIPS", "NP_DATA", "FEC_DATA", "SEC_DATA", "SECBULK_DATA", "USA_DATA", "STATES_DATA", "SP500", "QUANT_DATA", "MEMBER_BILLS"],
  "lazy": ["LEGISCAN_DATA", "OPENSTATES_DATA"],
  "live": ["PRICES_DATA", "NEWS_INTEL"]
}
```

### Functions

#### `extract_one(js_path: Path) -> tuple[str, object]`
Reads one `window.NAME = <json>;` file, applies a regex (`ASSIGN_RE`) to extract the global name and JSON value string, and calls `json.loads()` to validate and parse the value. Raises `ValueError` if the file is not in the expected format.

#### `main() -> None`
Creates `private_data/` directory, iterates all categories and files, calls `extract_one`, writes the compact JSON output (using `separators=(",", ":`)` — no whitespace), accumulates the manifest, and writes `manifest.json`.

---

## Environment Variables Reference

The following environment variables must be present in the `.env` file at the repository root. No API keys are ever written to any output file or log.

| Env Var | Required By | External Service |
|---|---|---|
| `FRED_API_KEY` | `build_states.py` | Federal Reserve Bank of St. Louis FRED API |
| `CENSUS_API_KEY` | `build_census.py` | U.S. Census Bureau ACS API |
| `BEA_API_KEY` | `build_bea.py` | Bureau of Economic Analysis Regional API |
| `BLS_API_KEY` | `build_bls.py` | Bureau of Labor Statistics Public API v2 |
| `FEC_API_KEY` | `build_fec.py` | OpenFEC (Federal Election Commission) |
| `LEGISCAN_API_KEY` | `build_legiscan.py` | LegiScan State Legislature API |
| `CONGRESS_API_KEY` | `build_member_bills.py` | Congress.gov API v3 |
| `OPENAI_API_KEY` | `build_news_intel.py` | OpenAI Chat Completions API |
| `OPENSTATES_API_KEY` | `build_openstates.py` | Open States / Plural API v3 |
| `FINNHUB_API_KEY` | `build_prices.py` | Finnhub REST API |
| `SECAPI_IO_KEY` | `build_sec.py` | sec-api.io (SEC EDGAR commercial API) |
| `THINKFREE_NEWS_MODEL` | `build_news_intel.py` (optional) | OpenAI model override (default `gpt-4o-mini`) |

Scripts with no env var requirement: `build_data.py`, `build_influence.py`, `build_nonprofits.py`, `build_relationships.py` (LDA is anonymous), `build_secbulk.py`, `build_sp500.py`, `build_usaspending.py`, `fetch_politician_photos.py`, `minify_data.py`, `scripts/extract_data_to_json.py`.

---

## Local File Prerequisites (Non-API)

Some scripts require large files that must be downloaded manually and are not committed to the repository.

| File | Location | Required By | Source |
|---|---|---|---|
| `entities.json.gz` | `~/Downloads/` | `build_influence.py` | LittleSis bulk data exports |
| `relationships.json.gz` | `~/Downloads/` | `build_influence.py` | LittleSis bulk data exports |
| `companyfacts.zip` | `~/Downloads/` | `build_secbulk.py` | SEC EDGAR (`https://www.sec.gov/dera/data/`) |
| `submissions.zip` | `~/Downloads/` | `build_secbulk.py` | SEC EDGAR (`https://www.sec.gov/dera/data/`) |
