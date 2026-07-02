# Part 1 — Executive Summary

## What ThinkFree Finance is

ThinkFree Finance is an **AI-powered financial-intelligence platform** that helps
investors — and everyday people — understand what is happening in financial
markets, the economy, and government activity, and **why it matters to their
lives**. It sits between a Bloomberg Terminal and plain English.

It is deliberately **not** a trading bot, brokerage, robo-advisor, portfolio
manager, or automated execution system. It is an **AI research analyst and
economic translator**. The final artifact a user receives is an **intelligence
report**, never a trade order.

**Target audience:** the average person trying to understand the economy — the
blue-collar worker, the renter, the small-business owner, the college student —
not Wall Street professionals.

## The core translation mission

Most financial news assumes the reader already understands economics. ThinkFree
bridges that gap. When the Fed raises rates 0.25%, ThinkFree explains what that
means for rent and mortgages, credit cards and car loans, jobs and hiring,
grocery prices, small-business borrowing, and savings accounts.

## The eight-question framework

Every major analysis answers eight questions:

1. What happened?
2. Why did it happen?
3. Who benefits?
4. Who is negatively affected?
5. How could this affect consumers (rent, groceries, gas, credit cards, mortgages, jobs)?
6. How could this affect businesses?
7. How could this affect financial markets?
8. What happened historically in similar situations?

## Political intelligence — transparency, not accusation

ThinkFree tracks congressional trading, lobbying, government contracts, and
legislative activity. The framing rule is non-negotiable: **all political-
intelligence output describes timing relationships between publicly available
government disclosures and market events. It never characterizes intent or
implies wrongdoing.** Every such output carries the disclaimer:

> "This analysis identifies timing relationships between publicly available
> government disclosures and market events. It does not imply or allege
> wrongdoing of any kind."

Data sources include STOCK Act disclosures, USASpending.gov, OpenSecrets, and
QuiverQuant.

## What this document is

This is a complete architecture-and-methodology reference for engineers. It
documents every subsystem, every Python file and function, every build script,
every backend route, every frontend module, the offline data pipeline, the
13-phase intelligence pipeline, the Python verification-agent layer, the AI
sub-agent (and exactly what it was trained on), every third-party library, the
security model, and the deployment story. It also records the **development
methodology** — how the platform was built from the founder's instructions, the
canonical blueprint (the project's CLAUDE.md), and the prior code base.

## System at a glance

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Delivery (web) | Static HTML/CSS/JS in `webapp/` | The user-facing intelligence UI |
| Delivery (legacy) | Streamlit `dashboard/app.py` | Original prototype dashboard (kept, untouched) |
| Backend | FastAPI in `server/` | Auth, gated data, tier enforcement, rate limiting |
| Identity | bcrypt + PyJWT httpOnly cookie + SQLite | Real authentication for cloud hosting |
| Offline pipeline | ~22 Python build scripts in `webapp/` | Fetch external data → `*_data.js` / `private_data/*.json` |
| Intelligence pipeline | 13 phases across the repo root | Scrape → extract → cluster → reason → quantify → brief |
| Verification | 4 Python agents in `agents/` | Data-quality, security, strategy, orchestration gates |
| AI sub-agent | `.claude/agents/cybersecurity-agent.md` + KB | Attacker-perspective security review |
| Native app | SwiftUI in `iphone-app/` | iOS client reusing the web data (not build-verified) |

## Scale

- ~16,700 lines of project Python across ~60 files (excluding vendored venvs).
- ~5,700 lines of frontend JavaScript across ~10 logic modules.
- 30+ pinned Python libraries for the pipeline; 5 for the backend.
- 17 generated datasets sourced from 11+ external APIs / government disclosures.

## How the numbers are produced (and what AI does)

Every quantitative result is **computed in code** by the Python quant engine, not
by a language model. The AI layer is a **translator**: it turns the deterministic
numbers into plain English and is constrained so it can phrase a figure but never
invent one. This division of labor is central to the product's honesty claims.

## Recent updates and where to find them

- **Part 2B, Statistical Methodology and Corrections**, documents the current,
  audited quant methodology (true-mean expected return, historical-frequency
  probabilities, walk-forward point-in-time backtesting, the Sahm-rule recession
  trigger, the excess-return politician scoreboard, and related corrections). It
  is written as the updated approach for review before the implementing code
  merges.
- **Part 12B, Current State of the Live Application**, documents the production
  deployment on Render, the tiered refresh and pricing, the Money Trail engine,
  the QuiverQuant congressional-trade integration, the scheduler and autonomous
  refresh, the Hedge Fund Monitor, the Data Centers and Economy trackers, the
  Presidential feed, the security hardening, and the public landing plus the app
  theme upgrade.
