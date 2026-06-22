# Part 12 — Dataset & Data-Source Catalog

This document maps every data bundle consumed by the ThinkFree Finance front-end
to its `window.NAME` global, the file it lives in, the build script that produces
it, the external government or commercial data source it draws from, whether it is
**core** (sent immediately after login), **lazy** (fetched on first State
Legislature view), or **live** (refreshed on each user's tier cadence), and which
UI panels it powers.

> **Political-intelligence framing rule (non-negotiable).**  Every dataset that
> touches congressional trading, lobbying activity, government contracts, campaign
> finance, or legislative action describes *timing relationships between publicly
> available government disclosures and market events*. It does not imply or allege
> wrongdoing of any kind. This framing is enforced in the disclaimer fields embedded
> in each affected data file and is repeated in every UI card that renders the data.

---

## Master Catalog Table

| Global name | Webapp file | Build script | External source | Classification | Powers in UI |
|---|---|---|---|---|---|
| `TF_DATA` | `js/data.js` | `build_data.py` | Congress.gov RSS, QuiverQuant, pipeline JSONs | **core** | Politician trades, bills, news feed, correlation engine, dashboard header |
| `IW_DATA` | `js/influence_data.js` | `build_influence.py` | LittleSis (littlesis.org) bulk dump | **core** | InfluenceWeb graph — board members, executives, donors, owners |
| `RELATIONSHIPS` | `js/relationships_data.js` | `build_relationships.py` | U.S. Senate Lobbying Disclosure Act (LDA) API | **core** | InfluenceWeb relationship edges — lobbying firms, lobbyists, issue areas, bills |
| `NP_DATA` | `js/nonprofit_data.js` | `build_nonprofits.py` | ProPublica Nonprofit Explorer (IRS Form 990) | **core** | InfluenceWeb industry-group nodes — revenue, expenses, assets |
| `FEC_DATA` | `js/fec_data.js` | `build_fec.py` | OpenFEC / Federal Election Commission API | **core** | Politician hover cards — receipts, PAC vs. individual money, top contributors |
| `SEC_DATA` | `js/sec_data.js` | `build_sec.py` | sec-api.io (SEC EDGAR) | **core** | Company detail panel — board members, directors, latest annual filing |
| `SECBULK_DATA` | `js/secbulk_data.js` | `build_secbulk.py` | SEC EDGAR bulk zips (companyfacts + submissions) | **core** | Company financials — revenue, assets, net income, SIC, filing counts |
| `USA_DATA` | `js/usaspending_data.js` | `build_usaspending.py` | USASpending.gov federal awards API (2020-2025) | **core** | Company detail + InfluenceWeb — total federal contracts, top awarding agencies |
| `STATES_DATA` | `js/states_data.js` | `build_states.py` + `build_bea.py` + `build_bls.py` + `build_census.py` | FRED (St. Louis Fed), BEA RPP 2023, BLS CPI, Census ACS | **core** | US Map choropleth, State Accountability panel — Prosperity/Pressure scores |
| `SP500` | `js/sp500_data.js` | `build_sp500.py` | github.com/datasets/s-and-p-500-companies (GICS, public domain) | **core** | Sector membership lists in InfluenceWeb; ticker universe for price lookups |
| `QUANT_DATA` | `js/quant_data.js` | `build_quant.py` | yfinance history + QuantLib (Black-Scholes/VaR/Kelly) + `ta` indicators | **core** | Predictive Market Signals panel — RSI, MACD, SMA, VaR, Kelly, Sharpe |
| `MEMBER_BILLS` | `js/member_bills.js` | `build_member_bills.py` | Congress.gov API | **core** | Politician hover cards — sponsored + cosponsored bill counts |
| `PRICES_DATA` | `js/prices_data.js` | `build_prices.py` | Finnhub (finnhub.io) | **live** | Every ticker popup — price, % change, market cap, industry; Quant signals |
| `NEWS_INTEL` | `js/news_intel.js` | `build_news_intel.py` | ThinkFree pipeline + GPT-4o-mini (Chef GPT) | **live** | News Intelligence panel — per-sector and per-ticker AI summaries |
| `LEGISCAN_DATA` | `js/legiscan_data.js` | `build_legiscan.py` | LegiScan Public API | **lazy** | State Legislature Watch — bills, sponsors, vote breakdowns, economic topics |
| `OPENSTATES_DATA` | `js/openstates_data.js` | `build_openstates.py` | Open States / Plural API v3 | **lazy** | State Legislature Watch — legislator photos, email, party, chamber |
| `US_MAP_PATHS` / `US_MAP_VIEWBOX` | `js/usmap_paths.js` | *(static — not generated)* | Wikimedia Blank US Map SVG (public domain) | **static logic asset** | US Map SVG renderer — 50-state outlines |

> **Classification definitions** (from `scripts/extract_data_to_json.py` and
> `server/data.py`):
> - **core** — sent in a single `GET /api/data/bundle` response immediately after
>   login; populates the globals required by every view.
> - **lazy** — fetched only on first visit to the State Legislature view via
>   `GET /api/data/state`; kept off the initial page load because the two files
>   together are ~3.5 MB.
> - **live** — fetched via `GET /api/data/live`; cadence is enforced per user
>   tier (lower tiers pause during market-closed hours); contains prices and
>   AI-generated news intelligence.
> - **static logic asset** — not a data bundle; always served directly by the
>   static file host (not blocked by the server middleware); contains map geometry,
>   not financial data.

In **static mode** (plain `file://` open without the FastAPI backend) the globals
are set by injecting `<script>` tags for each file in the order defined in
`boot.js`; `legiscan_data.js` and `openstates_data.js` are still lazy-injected on
first State Legislature view. In **server mode** the same `_data.js` files on disk
are blocked by the server middleware (`_BLOCKED_SUFFIXES` in `server/main.py`); the
data arrives only through the authenticated `/api/data/*` routes.

---

## Dataset Groups

### Core — Primary Intelligence Bundle

#### `TF_DATA` — ThinkFree Master Dataset

- **File:** `webapp/js/data.js` (~1.41 MB)
- **Global:** `window.TF_DATA`
- **Build script:** `webapp/build_data.py`
- **Source:** Aggregates from the full ThinkFree Python pipeline — `politician_performance.json`, `enriched_news_sentiment.json`, `signal_output_phase3.json`, `economic_reasoning_summary.json`, `news_output/sector_summaries.json`, `articles.json`, `correlation/top_bills.json`, `bill_correlations/*.json`
- **Top-level keys:** `generated_at`, `user`, `disclaimer`, `news`, `recent_trades`, `politicians`, `bills`, `correlation`, `sectors`
- **Powers:** Every dashboard panel. The `recent_trades` list drives the congressional trading accountability layer; `politicians` populates hover cards and FEC lookups; `news` feeds the News Feed view; `bills` drives legislative activity; `correlation` powers the sector-bill correlation engine.
- **Political-intelligence note:** The `disclaimer` field embedded in `TF_DATA` states: *"This analysis identifies timing relationships between publicly available government disclosures and market events. It does not imply or allege wrongdoing of any kind."* This disclaimer is referenced by `app.js` and reproduced in every politician-trade card.

---

#### `IW_DATA` — InfluenceWeb Relationship Graph

- **File:** `webapp/js/influence_data.js` (~247 KB)
- **Global:** `window.IW_DATA`
- **Build script:** `webapp/build_influence.py`
- **Source:** LittleSis (littlesis.org) bulk entity + relationship dump (two gzip files: `entities.json.gz` ~73 MB, `relationships.json.gz` ~105 MB). Build script streams both files and extracts only companies matched to ThinkFree tickers. LittleSis relationship category IDs used: `CAT_POSITION=1` (board/exec), `CAT_DONATION=5`, `CAT_OWNERSHIP=10`, `CAT_LOBBYING=7`.
- **Top-level keys:** `source`, `companies` (keyed by ticker), each entry containing `name`, `entity_id`, `blurb`, `website`, `board`, `executives`, `donors`, `relationships`
- **Powers:** The InfluenceWeb interactive graph — the centrepiece accountability visual showing board interlocks, executive mobility, and donor networks between corporations, politicians, and industry groups.

---

#### `RELATIONSHIPS` — Federal Lobbying Disclosure Graph

- **File:** `webapp/js/relationships_data.js` (~283 KB)
- **Global:** `window.RELATIONSHIPS`
- **Build script:** `webapp/build_relationships.py`
- **Source:** U.S. Senate Lobbying Disclosure Act (LDA) API (`lda.senate.gov/api/v1/filings/`). Anonymous access, rate-limited to ~15 requests/minute. Year 2024 filings. No API key required.
- **Top-level keys:** `source`, `year`, `disclaimer`, `byTicker` — each ticker entry contains `client`, `filings`, `spend_fmt`, `firms` (lobbying firms), `lobbyists`, `issues`, `bills`
- **Powers:** InfluenceWeb relationship edges — lobbying spend, which firms were hired, which issue areas and specific bills were lobbied on. Cross-referenced with `IW_DATA` for graph rendering.
- **Political-intelligence note:** Embedded `disclaimer` field states: *"Public federal lobbying disclosures. Describes relationships only; does not imply wrongdoing."*

---

#### `NP_DATA` — Industry Group Financials (IRS Form 990)

- **File:** `webapp/js/nonprofit_data.js` (~8 KB)
- **Global:** `window.NP_DATA`
- **Build script:** `webapp/build_nonprofits.py`
- **Source:** ProPublica Nonprofit Explorer API (`projects.propublica.org/nonprofits/api/v2`). No authentication required. Data originates from IRS Form 990 public filings.
- **Top-level keys:** `source`, `byName` — each entry: `ein`, `name`, `city`, `state`, `ntee`, `ntee_label`, `revenue`, `revenue_fmt`, `expenses`, `expenses_fmt`, `assets`, `assets_fmt`, `year`, `url`
- **Organisations covered:** ~24 major lobbying nonprofits and trade associations (e.g., PhRMA, American Petroleum Institute, US Chamber of Commerce, Business Roundtable, Semiconductor Industry Association).
- **Powers:** InfluenceWeb industry-group nodes — shows real financial scale (revenue, assets) of the advocacy organizations that appear in the lobbying graph.

---

#### `FEC_DATA` — Campaign Finance

- **File:** `webapp/js/fec_data.js` (~28 KB)
- **Global:** `window.FEC_DATA`
- **Build script:** `webapp/build_fec.py`
- **Source:** OpenFEC API (`api.open.fec.gov/v1/`). API key read from `.env` as `FEC_API_KEY`, never written to output. Data covers politicians tracked in ThinkFree's `politician_performance.json`.
- **Top-level keys:** `source`, `byName` — each politician entry: `candidate_id`, `fec_name`, `party`, `office`, `url`, `receipts`, `receipts_fmt`, `from_individuals`, `from_pacs`, `disbursements`, `cash_on_hand`, `top_contributors`
- **Powers:** Politician detail panel and hover cards — total fundraising, PAC vs. individual money split, top-contributor employer breakdown. Part of the accountability score pipeline (`scores.js`).
- **Political-intelligence note:** This data describes publicly reported campaign-finance disclosures. It does not imply or allege wrongdoing of any kind.

---

#### `SEC_DATA` — Board & Director Data (sec-api.io)

- **File:** `webapp/js/sec_data.js` (~165 KB)
- **Global:** `window.SEC_DATA`
- **Build script:** `webapp/build_sec.py`
- **Source:** sec-api.io (third-party SEC EDGAR aggregator). API key read from `.env` as `SECAPI_IO_KEY`. Pulls current Directors & Board Members and the latest annual DEF 14A proxy for each InfluenceWeb company. Resume-safe: already-fetched companies are preserved across runs.
- **Top-level keys:** `source`, `byTicker` — each entry: `entityName`, `filedAt`, `board` (array of `{name, position, age, since, committees, independent}`)
- **Powers:** Company detail panel — board composition, director independence, committee memberships, and director age/tenure. Cross-referenced against `IW_DATA` for the InfluenceWeb graph node detail view.

---

#### `SECBULK_DATA` — SEC EDGAR Bulk Financials

- **File:** `webapp/js/secbulk_data.js` (~61 KB)
- **Global:** `window.SECBULK_DATA`
- **Build script:** `webapp/build_secbulk.py`
- **Source:** SEC EDGAR official bulk datasets — `companyfacts.zip` and `submissions.zip` (downloaded manually to `~/Downloads`; multi-GB files, CIK-keyed). Reads only the per-company JSON slices for tracked tickers. No network at runtime; no rate limits.
- **Top-level keys:** `source`, `byTicker` — each entry: `cik`, `name`, `sic`, `exchange`, `ein`, `filings_total`, `last_filing`, `form_counts`, `revenue`, `revenue_fmt`, `fy`, `assets`, `assets_fmt`, `net_income`, `net_income_fmt`, `liabilities`
- **Powers:** Company financials panel — real XBRL balance-sheet figures (revenue, assets, net income), SIC classification, total filing count, filing type breakdown. Also used by `app.js` to resolve company names from tickers (`stockName()`).

---

#### `USA_DATA` — Federal Government Contracts

- **File:** `webapp/js/usaspending_data.js` (~217 KB)
- **Global:** `window.USA_DATA`
- **Build script:** `webapp/build_usaspending.py`
- **Source:** USASpending.gov API (`api.usaspending.gov`). No API key required. Covers federal contract awards types A–D, fiscal years 2020–2025, for every S&P 500 company and all other InfluenceWeb-tracked tickers.
- **Top-level keys:** `source`, `byTicker` — each entry: `recipient`, `total_contracts`, `total_contracts_fmt`, `top_agencies` (array of `{agency, amount, amount_fmt}`), `url`
- **Powers:** Company detail panel, InfluenceWeb contractor view — total dollar value of federal contracts, top awarding agencies (DoD, DHS, HHS, etc.). A key element of the government-industry relationship layer.
- **Political-intelligence note:** This data is drawn from mandatory public federal award disclosures. It identifies which companies received taxpayer-funded contracts and from which agencies. It does not imply or allege wrongdoing of any kind.

---

#### `STATES_DATA` — State Economic Indicators

- **File:** `webapp/js/states_data.js` (~25 KB)
- **Global:** `window.STATES_DATA`
- **Build scripts (pipeline of four):**
  1. `webapp/build_states.py` — FRED series (`{ST}UR`, `{ST}STHPI`, `MEHOINUS{ST}A672N`, `{ST}PCPI`). API key: `FRED_API_KEY`.
  2. `webapp/build_bea.py` — BEA Regional Price Parities 2023. API key: `BEA_API_KEY`.
  3. `webapp/build_bls.py` — BLS regional CPI year-over-year inflation by Census region.
  4. `webapp/build_census.py` — Census ACS 1-year: median home value, median rent, median household income, poverty rate, population.
- **External sources:** Federal Reserve Bank of St. Louis (FRED), Bureau of Economic Analysis (BEA), Bureau of Labor Statistics (BLS), U.S. Census Bureau ACS.
- **Top-level keys:** `source`, `byState` — each state entry: `name`, `unemployment`, `house_price_index`, `house_price_growth`, `per_capita_income`, `income_growth`, `median_household_income`, `prosperity_score`, `pressure_score`, `median_home_value`, `median_rent`, `poverty_count`, `population`, `poverty_rate`, `price_to_income`, `affordability`, `rent_burden_pct`, `cost_of_living`, `real_purchasing_power`
- **Powers:** US Map choropleth (colour-coded by Prosperity or Pressure score), State Accountability panel, and the "how this affects your state" contextualisation layer. All 50 states + DC covered.

---

#### `SP500` — S&P 500 Sector Membership

- **File:** `webapp/js/sp500_data.js` (~56 KB)
- **Global:** `window.SP500`
- **Build script:** `webapp/build_sp500.py`
- **Source:** `github.com/datasets/s-and-p-500-companies` (public domain CSV: ticker, company, GICS sector, GICS sub-industry). No API key required.
- **Top-level keys:** `source`, `byTicker` — each entry: `name`, `sector` (ThinkFree mapped sector), `gics` (original GICS sector), `sub` (GICS sub-industry); also `bySector` summary counts.
- **Sector mapping:** GICS is remapped to ThinkFree's internal sectors (e.g., `Industrials → Defense` if aerospace/defense sub-industry, `Health Care → Pharmaceuticals` if pharma/biotech, `Financials → Financial Services`, etc.).
- **Powers:** InfluenceWeb sector lists ("View All" ticker membership per sector); also the ticker universe seed for `build_prices.py`.

---

#### `QUANT_DATA` — Predictive Market Signals

- **File:** `webapp/js/quant_data.js` (~7 KB)
- **Global:** `window.QUANT_DATA`
- **Build script:** `webapp/build_quant.py`
- **Source:** Live price history via `yfinance`; quantitative math from `quantlib_metrics.py` (Black-Scholes N(d²) probability, annualized volatility, 95% VaR, lognormal expected return, Kelly criterion); technical indicators from the `ta` library (RSI, MACD, SMA-50/200 crossovers). No API keys.
- **Top-level keys:** `source`, `byTicker` — each entry: `price`, `volatility`, `var95`, `prob_up`, `prob_down`, `exp_return_1mo`, `kelly`, `sharpe`, `rsi`, `rsi_signal`, `macd`, `macd_signal_line`, `macd_cross`, `sma50`, `sma200`, `trend`, `ta_score`, `ta_signal`, `ql_signal`
- **Candidate tickers:** Derived from the `TF_DATA` news ticker mentions and recent congressional trades — ~22 most-active tickers with available price data.
- **Powers:** Predictive Market Signals panel in `predictions.js` — RSI, MACD, trend signals, QuantLib probability scores, Kelly fractions, and Sharpe ratios shown per ticker.

---

#### `MEMBER_BILLS` — Congressional Legislative Activity

- **File:** `webapp/js/member_bills.js` (~4.5 KB)
- **Global:** `window.MEMBER_BILLS`
- **Build script:** `webapp/build_member_bills.py`
- **Source:** Congress.gov API (`api.congress.gov/v3/member/`). API key: `CONGRESS_API_KEY`, read from `.env`, never logged. Covers every politician in `TF_DATA.politicians` that has a bioguide ID.
- **Top-level keys:** `source`, `byBioguide` — each entry: `sponsored` (count), `cosponsored` (count), `total`
- **Powers:** Politician hover cards — corrects the misleading "0–1 bills" that appeared when only trade-correlated bills were counted; now shows full real legislative activity.

---

### Live — Tier-Gated Refresh Bundle

#### `PRICES_DATA` — Live Market Prices

- **File:** `webapp/js/prices_data.js` (~186 KB)
- **Global:** `window.PRICES_DATA`
- **Build script:** `webapp/build_prices.py`
- **Source:** Finnhub (`finnhub.io`). API key: `FINNHUB_API_KEY`, read from `.env`, never written to output or logs. Free tier: 60 calls/minute; build sleeps 1.1 s between requests. Covers the full S&P 500 plus all tickers referenced in SEC bulk, InfluenceWeb, USASpending, congressional trades, and bill tickers.
- **Top-level keys:** `source`, `byTicker` — each entry: `price`, `change`, `change_pct`, `market_cap`, `market_cap_fmt`, `name`, `industry`
- **Powers:** Every company popup and ticker card across the app — real-time price, percentage change, market cap, and industry classification. Also seeds the `build_quant.py` candidate ticker selection.

---

#### `NEWS_INTEL` — AI News Intelligence (Chef GPT)

- **File:** `webapp/js/news_intel.js` (~12 KB)
- **Global:** `window.NEWS_INTEL`
- **Build script:** `webapp/build_news_intel.py`
- **Source:** ThinkFree's own pipeline outputs (local, no API): `signal_output_phase3.json` (technical signals), `quant_data.js` (QuantLib metrics), `news_output/sector_summaries.json`, `economic_reasoning_summary.json`. Final plain-English translation: one batched GPT-4o-mini call per sector (~8–10 API calls total). Model configurable via `THINKFREE_NEWS_MODEL` env var.
- **Top-level keys:** `source`, `model`, `api_calls`, `bySector` (sector → `summary`, per-ticker `what_it_means`), `byTicker`
- **Powers:** News Intelligence panel — plain-English sector and per-ticker summaries combining technical signals, QuantLib scores, and economic reasoning, translated by Chef GPT into jargon-free language for the everyday investor.

---

### Lazy — State Legislature Bundle (loaded on first State view)

#### `LEGISCAN_DATA` — State Legislative Activity

- **File:** `webapp/js/legiscan_data.js` (~2.03 MB — largest dataset)
- **Global:** `window.LEGISCAN_DATA`
- **Build script:** `webapp/build_legiscan.py`
- **Source:** LegiScan Public API (`api.legiscan.com`). API key: `LEGISCAN_API_KEY`, read from `.env`. Free-tier budget: 30,000 queries/month; typical build uses ~400 calls. Covers all 50 states + DC.
- **Top-level keys:** `source`, `disclaimer`, `byState` — each state: `state`, `name`, `session` (`id`, `name`, `year_start/end`, `special`), `bill_total`, `status_breakdown`, `relevant_count`, `bills` (array of up to 40 economically-relevant bills with sponsors and roll-call vote summaries for top 6)
- **Economic topic tags:** taxes, housing, wages, health, energy, education, environment, criminal justice, agriculture, infrastructure, trade (applied at build time to classify bills for the "how this affects your life" translation layer).
- **Powers:** State Legislature Watch panel — full state-by-state bill activity, economic relevance scoring, sponsor attribution, vote breakdowns.
- **Political-intelligence note:** Embedded `disclaimer` states: *"This data describes publicly available state-legislative activity. It does not imply or allege wrongdoing of any kind."*

---

#### `OPENSTATES_DATA` — State Legislator Profiles

- **File:** `webapp/js/openstates_data.js` (~1.43 MB)
- **Global:** `window.OPENSTATES_DATA`
- **Build script:** `webapp/build_openstates.py`
- **Source:** Open States / Plural API v3 (`v3.openstates.org/people`). API key: `OPENSTATES_API_KEY`, read from `.env`. Rate-limited to 1 req/sec on the free tier (~500/day). Build degrades gracefully — a state that fails is skipped, not fatal. Covers all 50 states + DC.
- **Top-level keys:** `source`, `byState` — each state: `name`, `legislators` (array of `{name, party, chamber, district, image, email, openstates_url}`)
- **Powers:** State Legislature Watch — legislator photo, email address, party badge, chamber, and district alongside the LegiScan bill data. Cross-referenced by name at render time in `app.js`.

---

### Static Logic Asset

#### `US_MAP_PATHS` / `US_MAP_VIEWBOX` — SVG Map Geometry

- **File:** `webapp/js/usmap_paths.js` (~31 KB)
- **Globals:** `window.US_MAP_VIEWBOX` (string), `window.US_MAP_PATHS` (object keyed by 2-letter state code)
- **Build script:** Not generated — static file, checked into the repo.
- **Source:** Wikimedia-derived Blank US Map SVG (public domain).
- **Top-level keys:** `US_MAP_VIEWBOX` (SVG viewBox string), `US_MAP_PATHS` (state code → SVG path `d` string)
- **Classification:** Loaded as a normal logic script in `boot.js` `LOGIC_SCRIPTS`; not blocked by the server middleware; contains no financial data or personal information.
- **Powers:** The US Map choropleth renderer in `app.js` — draws the clickable 50-state outline and fills each state with the Prosperity/Pressure score colour.

---

## Server-Mode Endpoint Map

When the FastAPI backend (`server/main.py` + `server/data.py`) is active, the data
flows through three authenticated endpoints rather than static `<script>` tags:

| Endpoint | Datasets delivered | Trigger |
|---|---|---|
| `GET /api/data/bundle` | All **core** datasets as a single JSON object keyed by global name | Immediately after login |
| `GET /api/data/state` | `LEGISCAN_DATA` + `OPENSTATES_DATA` (**lazy**) | First visit to State Legislature view |
| `GET /api/data/live` | `PRICES_DATA` + `NEWS_INTEL` (**live**) | Per-tier cadence; paused when market closed for lower tiers |

The manifest that drives this routing is written by
`scripts/extract_data_to_json.py` to `private_data/manifest.json` and read at
runtime by `server/data.py → _manifest()`. The `private_data/` directory is
gitignored entirely (only `.gitignore` is tracked) — the datasets it holds are
never committed to the repository or served statically.

---

## Build Script Reference

| Build script | Output file | Requires `.env` key | Run frequency |
|---|---|---|---|
| `webapp/build_data.py` | `js/data.js` | *(none; reads local pipeline JSONs)* | After each full pipeline run |
| `webapp/build_influence.py` | `js/influence_data.js` | *(none; reads LittleSis bulk gz from `~/Downloads`)* | When LittleSis dump is refreshed |
| `webapp/build_relationships.py` | `js/relationships_data.js` | *(none; Senate LDA is anonymous)* | Quarterly / on demand |
| `webapp/build_nonprofits.py` | `js/nonprofit_data.js` | *(none; ProPublica API is open)* | Annually |
| `webapp/build_fec.py` | `js/fec_data.js` | `FEC_API_KEY` | Election-cycle refresh |
| `webapp/build_sec.py` | `js/sec_data.js` | `SECAPI_IO_KEY` | Quarterly / resume-safe |
| `webapp/build_secbulk.py` | `js/secbulk_data.js` | *(none; reads SEC bulk zips from `~/Downloads`)* | When SEC publishes updated bulk zips |
| `webapp/build_usaspending.py` | `js/usaspending_data.js` | *(none; USASpending API is open)* | Monthly |
| `webapp/build_states.py` | `js/states_data.js` (base) | `FRED_API_KEY` | Monthly |
| `webapp/build_bea.py` | `js/states_data.js` (enriches) | `BEA_API_KEY` | Annually (BEA RPP lags ~12 mo) |
| `webapp/build_bls.py` | `js/states_data.js` (enriches) | *(none)* | Monthly |
| `webapp/build_census.py` | `js/states_data.js` (enriches) | *(none — Census ACS open)* | Annually |
| `webapp/build_sp500.py` | `js/sp500_data.js` | *(none; GitHub CSV)* | When index composition changes |
| `webapp/build_quant.py` | `js/quant_data.js` | *(none; yfinance + local QuantLib)* | Daily |
| `webapp/build_member_bills.py` | `js/member_bills.js` | `CONGRESS_API_KEY` | Weekly |
| `webapp/build_prices.py` | `js/prices_data.js` | `FINNHUB_API_KEY` | Daily / live-tier |
| `webapp/build_news_intel.py` | `js/news_intel.js` | `OPENAI_API_KEY` (or `THINKFREE_NEWS_MODEL` env) | After each news pipeline run |
| `webapp/build_legiscan.py` | `js/legiscan_data.js` | `LEGISCAN_API_KEY` | Weekly (30k/month budget) |
| `webapp/build_openstates.py` | `js/openstates_data.js` | `OPENSTATES_API_KEY` | Monthly (500/day free tier) |
| `webapp/minify_data.py` | *(minifies all _data.js in place)* | *(none)* | Before production deploy |
| `scripts/extract_data_to_json.py` | `private_data/*.json` + `private_data/manifest.json` | *(none)* | Before launching the FastAPI server |
