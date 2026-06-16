# ThinkFree InfluenceWeb + Accountability Platform Roadmap

The long-term vision: evolve ThinkFree from a financial dashboard into an
Economic, Political, Corporate & Public Accountability Intelligence Platform.
Neutral, data-driven, relationship-focused. Transparency, not accusation.

## Built (v1)

### InfluenceWeb graph (`webapp/js/influenceweb.js`)
- Canvas graph: Congress (hub) -> Sectors -> Companies -> Board/Execs + Politicians + Bills.
- Solar-system entry layout; gentle zoom-in on load; floating + breathing nodes; animated relationship flow.
- Zoom-to-cursor (wheel), drag-to-pan, single-click focus (centers, expands, opens side panel, fades unrelated).
- Progressive disclosure: nodes appear only when a parent is expanded.
- Breadcrumb navigation (Congress > Sector > Company > ...), click any crumb to jump back.
- Relationship color system: structural (gray-blue), financial (teal), legislative (purple), revolving (amber), high-sensitivity (red). Line thickness = strength.
- Sector Influence Density score (0-100) on hover/panel.
- High-sensitivity flag when a company overlaps congressional trading + related bills + sector lobbying.

### Real data
- Company board members / executives / owners / donors: extracted from the **LittleSis** dump
  (`webapp/build_influence.py` streams entities.json.gz + relationships.json.gz from ~/Downloads,
  matches our tickers, writes `webapp/js/influence_data.js`). 105 companies have real board/exec data.
- Sectors, companies (tickers), politicians, bills, lobbying: from existing `data.js`.

## Planned (not yet built) — feature backlog from product spec

These are designed but NOT implemented. Each should be data-driven and plain-English.

- **Impact Engine** — per story/bill/order: what happened, why it matters, who benefits, who's hurt, how it affects me.
- **Influence Score™ (per company)** — contracts + PAC + lobbying + congressional ownership + regulatory exposure + bill mentions + subsidies + agency ties.
- **Government Dependency Score™ (company + industry)** — reliance on contracts/spending/regulation/funding.
- **PAC & Lobbying Tracker** — top recipients, top spenders, committee money, industry rankings.
- **Industry Intelligence Dashboards** — Oil & Gas, Pharma, Defense, Banking, Tech, Healthcare, Real Estate, Telecom, Energy.
- **Accountability Platform™** — per politician: trade performance, trade-timing, constituent prosperity, alignment, PAC/industry exposure.
- **Constituent Prosperity Score™** — district/state economic health (cost of living, housing, wages, inflation, savings, small-biz).
- **Alignment Score™** — constituent outcomes vs. official's financial success (100 aligned … 0 diverged). Not a corruption score.
- **Trade Timing Score™** — how well trades were timed vs. contracts/bills/orders/regulatory actions.
- **Trust Index™** — consistency: promises vs. statements vs. votes vs. actions.
- **Corporate Political Exposure™** — per company political footprint.
- **Conflict View™** — pick an industry, see related politicians/committees/ownership/PAC/lobbying/contracts/legislation.
- **Generational Impact Engine™** — impact by cohort (Gen Z, Millennials, … renters, homeowners, retirees, small biz).
- **State Performance Rankings** — all 50 states on housing/cost of living/wages/inflation/savings/jobs.
- **Personal Exposure Engine™** — translate events into personal cost (gas, groceries, mortgage, loans, utilities). (Partial: see "What This Means For You" everyday impact.)
- **Money Flow Map™** — Bill -> funding -> agency -> contract -> company -> lobbying -> PAC -> recipients.
- **Influence Density Score™** — concentration of influence across entities. (Partial: sector density implemented.)

## Data sources to wire for the above
- LittleSis (relationships, donations, lobbying) — partially used.
- OpenSecrets / FEC (PAC + campaign finance).
- USASpending.gov (federal contracts) — `fedspending_id` present in LittleSis entities.
- Senate LDA (lobbying filings) — `lda_registrant_id` present in LittleSis entities.
- FRED / Census (state + district economic metrics).
