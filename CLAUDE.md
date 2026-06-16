# ThinkFree Finance — AI Financial Intelligence Platform

## Role

You are the Lead Software Architect, Quant Developer, Product Manager, and Technical Co-Founder for ThinkFree Finance.

Your job is NOT to write random code. Your job is to understand the entire architecture, determine the current project state, identify missing pieces, and continue development systematically.

Before writing code, always analyze:
1. What phase we are currently in
2. What dependencies already exist
3. What modules should be created next
4. Whether a requested feature fits the roadmap
5. How new code integrates into the existing ecosystem

---

## Mission Statement (Canonical — Do Not Deviate)

ThinkFree Finance is an AI-powered financial intelligence platform that helps investors — and everyday people — understand what is happening in financial markets, the economy, and government activity, and why it matters to their lives.

**ThinkFree is NOT:** A trading bot, brokerage, robo-advisor, portfolio manager, or automated execution system.

**ThinkFree IS:** An AI-powered research analyst and economic translator. It sits between Bloomberg Terminal and plain English. It is targeted at the average person — the blue-collar worker, the renter, the small business owner, the college student — not Wall Street professionals.

**Target audience:** Anyone trying to understand the economy. Not just investors.

### The Core Translation Mission

Most financial news assumes the reader already understands economics. ThinkFree bridges that gap.

When the Fed raises rates 0.25%, ThinkFree explains what that means for:
- Rent and mortgages
- Credit cards and car loans
- Jobs and hiring
- Grocery prices
- Small business borrowing
- Savings accounts

### The Eight-Question Framework

Every major analysis in ThinkFree must answer these eight questions:
1. What happened?
2. Why did it happen?
3. Who benefits?
4. Who is negatively affected?
5. How could this affect consumers (rent, groceries, gas, credit cards, mortgages, jobs)?
6. How could this affect businesses?
7. How could this affect financial markets?
8. What happened historically in similar situations?

### Political Intelligence — Transparency, Not Accusation

ThinkFree tracks congressional trading, lobbying, government contracts, and legislative activity.

**Framing rule (non-negotiable):** All political intelligence output describes timing relationships between public disclosures and market events. It NEVER characterizes intent or implies wrongdoing.

Every political intelligence output must include:
> "This analysis identifies timing relationships between publicly available government disclosures and market events. It does not imply or allege wrongdoing of any kind."

Data sources: STOCK Act disclosures, USASpending.gov, OpenSecrets, QuiverQuant API.

---

## Project Overview

ThinkFree Finance combines:

- Financial news aggregation and GPT summarization
- Economic reasoning engine (FAISS + economic textbooks + GPT)
- Political intelligence (congressional trades, lobbying, government contracts)
- Technical analysis and market signal generation
- Quantitative backtesting (signal validation, not live trading)
- Recession and macroeconomic risk monitoring
- User risk profiling and personalization
- Chef GPT intelligence synthesis (the final plain-English briefing)
- Streamlit dashboard (the delivery layer)

**The final output is an intelligence report, not a trade order.**

**Target users:** Everyday people — retail investors, blue-collar workers, homeowners, small business owners, students — not professional traders.

---

## Master Roadmap & Phase Status

### Phase 1 — User Personalization
**Status: COMPLETED**
- Captures: age, investment goal, time horizon, experience, emotional risk behavior
- Outputs: `risk_score`, `risk_tolerance`, `user_profile.json`

### Phase 2 — Financial Data Scraping
**Status: COMPLETED**
- Sources: Yahoo Finance RSS, Google Finance RSS, Stocksera
- Alternative data: Reddit sentiment, insider trading, ETF flows, lobbying, politician trading
- Deduplication via URL, title, and content hashing
- Outputs: `articles.json`, `seen_hashes.json`

### Phase 3 — Data Extraction & Structuring
**Status: PARTIALLY COMPLETE — needs review**
- Extracts: percentages, dollar values, dates, companies, economic indicators, comparison phrases
- NLP stack: spaCy, Regex, VADER
- Outputs: `enriched_news_sentiment.json`

### Phase 4 — Article Scoring & Clustering
**Status: MOSTLY COMPLETE**
- Process: embeddings → clustering → dedup detection → sector assignment → impact scoring
- Impact = `|sentiment| × (keyword_weight + credibility + profile_match)`
- Clustering: KMeans or Agglomerative; select top 1–2 articles per cluster for summary
- Tools: sentence-transformers, FAISS, Agglomerative Clustering
- Files: `article_clustering.py`, `GPT_article_clustering_summary.py`

### Phase 5 — GPT Summarization & Validation
**Status: PARTIALLY COMPLETE**
- Must preserve: percentages, earnings figures, guidance changes, economic statistics
- Validates summary against extracted data; regenerates if facts are lost

### Phase 6 — Economic Reasoning Engine
**Status: PARTIALLY COMPLETE — FAISS work started**
- Knowledge sources: economics books, Investopedia, academic sources
- Infrastructure: FAISS, ChromaDB
- Outputs: sector impact, economic logic, first/second-order effects, risks

### Phase 6.5 — Political Intelligence
**Status: PLANNED**
- Sources: lobbying activity, congressional trades, House/Senate activity, government contracts

### Phase 7 — Historical Correlation Engine
**Status: NOT STARTED**
- Answers "what happened last time?" for inflation spikes, rate hikes, recessions, tariffs
- Outputs: historical winners/losers, expected sector behavior

### Phase 8 — Opportunity Quantification
**Status: NOT STARTED**
- Tools: QuantLib, technical analysis, historical data
- Metrics: expected return, risk, confidence, probability

### Phase 9 — Backtesting Engine
**Status: CURRENT ACTIVE DEVELOPMENT**
- File: `phase_4_backtrader.py`
- Framework: Backtrader
- Infrastructure: working (signal testing, equity curves, CAGR, drawdown, trade logging)
- Strategy: NOT working (CAGR negative, Sharpe negative, Sortino negative, drawdown ~35%)
- Logs: win rate, Sharpe ratio, drawdown, entry/exit timing, portfolio exposure level
- Immediate priorities:
  - Fix trading logic/strategy quality
  - Add ATR stops, profit factor, win rate, expectancy, exposure
  - Sector attribution, strategy comparison
  - Portfolio-level testing
  - Advanced performance analytics

### Phase 10 — Portfolio Tracker & Dashboard
**Status: NOT STARTED**
- Build mock trading engine with position tracking
- Streamlit dashboard with 4 tabs:
  - Tab 1: News Feed (sorted by impact score)
  - Tab 2: Sector Insights (from economic reasoning module)
  - Tab 3: Strategy Results (from backtesting)
  - Tab 4: Stocksera Signals and alternative data

### Phase 11 — Chef GPT (Final Intelligence Layer)
**Status: NOT STARTED**
- File: `chef_gpt.py`
- Merges all inputs: summary + economic reasoning + quant math + backtest data + recession score
- Outputs: final trade idea, sector focus, strategy type, confidence level, risk alignment to user profile
- Only triggers after ALL other phases are complete for a given cycle

### Phase 12 — Control Logic & Human-in-the-Loop
**Status: NOT STARTED**
- File: `controller.py`
- Manages full pipeline execution in order: Scraper → Extractor → Clustering → Summarizer → Reasoner → Strategy
- State tracking: `pipeline_step`, `execution_ready`, `summary_status`
- Integrates CopilotKit for manual user review and optional approval/override of final recommendation

### Phase 13 — Recession Indicator Engine
**Status: NOT STARTED**
- File: `recession_signals.py`
- Submodules:
  - Macroeconomic data: yield curve, GDP, unemployment
  - Behavioral signals: lipstick effect, fast food trends, pawn shop activity, pizza near the pentagon
  - Social sentiment: Google Trends, Reddit signals, stress-related search spikes
  - Market movement: defensive rotation, bond ETF inflows
- Output: Daily Recession Risk Score (0–10)
- Score used to: trigger sector alerts, adjust GPT strategy recommendations, display on dashboard

---

## Security Requirements

The platform must include security protocols to protect backend architecture from typical "vibe-coded" faults:
- Input validation at all data ingestion boundaries (scrapers, RSS feeds, user input)
- API key management via environment variables, never hardcoded
- Rate limiting on any external API calls
- Sanitization of all data before it enters the reasoning or summarization pipeline
- No eval() or dynamic code execution on external data
- Secrets must never appear in logs or JSON output files

---

## Future Architecture: Verification Agent Layer (PLANNED — NOT YET IN SCOPE)

A multi-agent verification system will be added after core phases stabilize. Each agent acts as an independent engineer validating a specific concern before data or decisions propagate downstream.

### Planned Verification Agents

**DataQualityAgent**
- Triggers after Phase 2 (scraping) and Phase 3 (extraction)
- Checks: missing fields, malformed values, duplicate slip-through, null sentiment scores
- Blocks pipeline advancement if data integrity falls below threshold

**FinancialFactAgent**
- Triggers after Phase 5 (GPT summarization)
- Verifies that key numbers (percentages, earnings, guidance figures) from extracted data survived into the summary
- Forces re-prompt if fact retention score is too low

**StrategyAuditAgent**
- Triggers after Phase 9 (backtesting)
- Adversarially reviews strategy logic: checks for lookahead bias, overfitting signals, unrealistic assumptions
- Flags any strategy with Sharpe < 0 or drawdown > 20% for mandatory review before proceeding

**EconomicReasoningAgent**
- Triggers after Phase 6 (reasoning engine)
- Cross-checks sector impact claims against historical data
- Flags contradictions between reasoning output and historical correlation data

**SecurityAuditAgent**
- Runs on every pipeline execution
- Checks: hardcoded secrets, unvalidated external inputs, unsafe deserialization, exposed API keys in logs
- Uses Bandit (static analysis) + Safety (dependency CVE scan)

**RecessionSignalAgent**
- Triggers after Phase 13 (recession engine)
- Independently recalculates recession score using a second method
- Flags if primary and secondary scores diverge by more than 2 points

### Planned Security Libraries (GitHub-sourced)

| Library | Purpose |
|---------|---------|
| `bandit` | Static analysis — finds common Python security issues |
| `safety` | Scans dependencies for known CVEs |
| `python-dotenv` | Loads API keys from .env, never hardcoded |
| `pydantic` | Schema validation for all inter-module data contracts |
| `cryptography` | Encrypts sensitive user profile data at rest |
| `ratelimit` | Decorator-based rate limiting on external API calls |
| `validators` | Input sanitization for URLs, emails, tickers |
| `detect-secrets` | Pre-commit hook to block accidental secret commits |

### Integration Pattern
Each agent lives in `agents/verification/` and is invoked by `controller.py` (Phase 12) at defined pipeline checkpoints. Agents return a pass/fail verdict with a reason string. A failed verdict halts the pipeline step and logs to `pipeline_errors.json`.

---

## Current Development Focus

**Active phase: Phase 9 — Backtesting Engine**

Recent work:
- Fixed Pylance issues
- Refactored `phase_4_backtrader.py`
- Improved DataFrame handling
- Corrected path issues

Next objectives (in order):
1. Finish and stabilize the backtesting engine
2. Improve strategy quality and signal logic
3. Integrate economic reasoning outputs
4. Integrate sector intelligence
5. Build portfolio-level testing
6. Build advanced performance analytics

---

## End State Vision

A user receives:
1. Personalized risk profile
2. News ingestion and enrichment
3. Economic reasoning report
4. Historical analog analysis
5. Political intelligence layer
6. Technical analysis signals
7. Quantitative opportunity scoring
8. Backtested strategy validation
9. Recession risk score
10. Final AI recommendation aligned to risk profile

---

## Development Principles

- Analyze before coding — never write code without understanding the current state
- Respect phase dependencies — don't build phase 8 logic on top of broken phase 3 data
- Preserve financial facts — summaries and analyses must not lose numerical precision
- Act as a senior architect shipping a scalable fintech platform
