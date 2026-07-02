# Part 12B — Current State of the Live Application

This part documents the platform **as it runs in production today** at
`thinkfree.onrender.com`. It captures the subsystems and changes that shipped
after the earlier parts were first written, so the reference reflects the live
product. It records capabilities and design, not live point figures.

## 12B.1 Deployment on Render

The application is deployed on **Render** from the `main` branch of the GitHub
repository, described by `render.yaml` (a Blueprint). One **web service** runs the
FastAPI backend, which serves the static front-end and the gated data API. A
**persistent disk** (mounted at `/var/data`) holds the SQLite user store so
accounts and sessions survive redeploys. Secrets are provided as dashboard
environment variables (`sync: false`), never committed. The build reinstalls
backend dependencies, rebuilds `private_data/` from the committed data snapshots,
and compiles the marketing landing bundle.

A separate **daily cron service** runs the free and low-cost data builders and
commits the refreshed `*_data.js` snapshots back to `main`; that push triggers the
web service to redeploy with fresh data. Git is the durable hand-off, because a
cron job and the web service cannot share a Render disk.

## 12B.2 Tiered refresh and pricing

`server/config.py` holds the single source of truth for the tier catalogue. Tiers
differ only in how often a user may pull fresh live data; every tier reads the
same public records and shows the same transparent math. The public tiers are:

| Tier | Refresh cadence | Price |
|------|-----------------|-------|
| Free | Daily briefing | Free |
| Pro, Hourly | Every hour | 5 per month |
| Pro, 30-minute | Every 30 minutes, incl. after hours | 15 per month |
| Pro, 5-minute | Every 5 minutes, incl. after hours | 25 per month |

An internal **beta** tier grants 5-minute access to closed-beta testers and is
never sold. The refresh cadence is **enforced server-side** in the data API, so it
cannot be sped up by editing the browser. Tier keys are stable across pricing
changes because they are persisted on user rows and inside signed tokens.

## 12B.3 The Money Trail engine

The Money Trail engine scores each law on a transparent, six-link **chain of
evidence**: the law, who it pays, who knew, who traded, the payoff, and the
pattern. Every link contributes a visible, weighted component to the score, so a
reader can see exactly how a suspicion score was reached rather than trusting a
black box. The output obeys the political-intelligence framing rule: it describes
**timing relationships** between public disclosures and market events and never
alleges wrongdoing. A cached, no-cost path builds the scores without a paid
language-model step.

## 12B.4 Congressional trading, QuiverQuant, and corrected statistics

Congressional-trade data is sourced from **QuiverQuant** and STOCK Act
disclosures, joined to government-contract files already in the repository. The
politician scoreboard uses the **corrected methodology** in Part 2B: members are
ranked on **excess return versus SPY over the identical holding window**, sales
are framed as **avoided or foregone** exposure rather than summed with buy
profit-and-loss, and dollar totals are shown as **ranges** to reflect the brackets
in the disclosures. This replaces the earlier raw-dollar, buy-and-sell-combined
presentation.

## 12B.5 Scheduler and autonomous refresh

Two mechanisms keep the served data fresh without a manual redeploy:

- An **in-process background refresher** (a FastAPI daemon thread) re-pulls the
  economy series on a timer and writes them to the persistent disk, so the served
  data updates continuously between deploys.
- The **daily cron** (Part 12B.1) refreshes the broader snapshot set and commits
  them back to `main`, triggering a redeploy.

No paid language-model steps run in the scheduled path; the cron runs only the free
and cheap builders.

## 12B.6 OFR Hedge Fund Monitor

A **Hedge Fund Monitor** screen surfaces hedge-fund and leverage indicators from
the U.S. Office of Financial Research (OFR) Hedge Fund Monitor, a free,
no-key public data source. It gives the everyday reader a plain-English read on
where systemic leverage is building.

## 12B.7 Data Centers tracker

A **Data Centers** screen maps and lists U.S. data-center activity by county,
combining public sources (Census, EIA, curated locations, and OpenStreetMap and
FCC coverage) into a browseable, paginated view, framed around what the buildout
means for local power demand, jobs, and costs.

## 12B.8 Economy and cost-of-living tracker

An **Economy** screen tracks the prices people actually pay, groceries, rent, gas,
mortgages, car loans, jobs, and more, against a fixed baseline, using a large set
of FRED indicators. It translates macro moves into what they mean for a household
budget in plain English, which is the platform's core positioning.

## 12B.9 Presidential feed

A **Presidential** feed tracks executive-branch activity relevant to markets and
the economy, presented in the same translate-to-plain-English style as the rest of
the product.

## 12B.10 Security hardening

The backend enforces a real security posture for cloud hosting:

- **Authentication** via bcrypt password hashing and signed PyJWT session tokens in
  an httpOnly cookie, with server-side session records on the persistent disk.
- **Closed-beta invite codes**: single-use codes gate account creation and are
  consumed on redemption, replacing an earlier shared beta key.
- **Gated data**: the datasets are served only through authenticated `/api/data/*`
  endpoints; the raw bulk-data files are blocked from direct download, and the app
  returns unauthorized without a session.
- **Hardening headers on every response**: a Content-Security-Policy, `nosniff`,
  `X-Frame-Options: DENY`, a referrer policy, a permissions policy, and, in
  production, HSTS with an HTTPS redirect.
- **Rate limiting**: a coarse global per-IP throttle under precise per-endpoint
  limits on the auth routes.
- **Self-hosted fonts**: the app fonts are self-hosted and the CSP declares
  `font-src 'self'`, removing an external font dependency.
- Dependency versions are pinned and patched against known advisories, and a
  standing attacker-perspective review runs before changes ship.

## 12B.11 Public landing and app theme

The public **marketing landing** at `/` is a standalone React and Vite bundle,
fully isolated from the application: it imports no application code, data, or auth,
and it is served as static assets. It has its **own scoped Content-Security-Policy**
that applies only to `/` and the landing assets; every application and API route
keeps the original, unchanged application CSP. The landing routes its login and
sign-in actions to the application, which owns the real authentication flow.

The application itself received a **theme-level visual upgrade** delivered entirely
through its central design tokens (color, type scale, spacing, radii, shadows,
motion) plus polish of shared components. It is centralized and reversible, applies
to both light and dark themes and to mobile and desktop, and preserves all
functionality and information architecture. The user-selectable accent presets,
including the pink and purple options, remain available; the default brand accent
stays a single restrained cyan.

The influence-graph nodes render clean local ticker monograms rather than remote
logos, which removed a remote image dependency and eliminated broken-image
placeholders.
