# The Money Trail Detective Engine

The Money Trail Detective Engine upgrades the old timing-only "suspicion score"
into a chain-of-evidence **Case File**. Instead of asking only "how many trades
happened before this law passed," it scores each law as a **CASE STRENGTH** built
from six evidence links, and leans **multiplicative on the two critical links** so
a case cannot score high on trade volume alone.

## The 6-link model

Each link returns a strength in `0..1`.

1. **The Law.** What economic action the bill takes (funds, authorizes, awards
   contracts, changes a rule or tariff). Where does money flow. Source: bill title
   and latest-action text (Congress.gov).
2. **The Beneficiary (materiality). CRITICAL.** The specific companies whose
   revenue depends on the law, not a keyword sector tag. Source: a curated
   materiality map for high-impact areas (defense, energy, health, tech); falls
   back to keyword-matched tickers (clearly labeled lower-confidence).
3. **The Access. CRITICAL.** Did a trader sponsor or cosponsor the bill, or sit on
   the committee of jurisdiction. Sources: Congress.gov sponsors/cosponsors, and
   committee rosters from the unitedstates/congress-legislators project.
4. **The Trade.** Did access holders trade the beneficiary companies **before the
   committee/markup milestone** (re-anchored timing), not just before final
   passage. Sources: Congress.gov action timeline, plus the correlated trades.
5. **The Payoff.** Abnormal return, not raw profit. Each pre-milestone trade's
   market-adjusted return (QuiverQuant `excess_return`, winsorized) is compared to
   the member's own baseline (median), and the abnormal portion is scored.
6. **The Pattern.** Cross-law repetition per member and clustering of multiple
   members trading the same beneficiary before the same milestone.

## Scoring formula and weights

```
CASE STRENGTH = round(100 * gate * evidence)

gate     = (0.15 + 0.85 * Beneficiary) * (0.15 + 0.85 * Access)   # critical, multiplicative
evidence = 0.20*Law + 0.35*Trade + 0.25*Payoff + 0.20*Pattern      # supporting, additive (sums to 1)
```

The `gate` collapses toward ~0.02 when either critical link is absent, so the
score is capped in the single digits regardless of how many trades exist. Access
weights: sponsor `1.0`, cosponsor `0.8`, committee-of-jurisdiction `0.7`, none
`0.1`. Tier bands (UI): Strong case `>=70`, Notable `45-69`, Emerging `25-44`,
Thin `<25`.

## Data sources per link

| Link | Source | Endpoint / file |
|------|--------|-----------------|
| Law | Congress.gov | bill title + latest-action text (already in `congress_bills.json`) |
| Beneficiary | curated map + keyword fallback | `MATERIALITY` in `build_money_trail.py` |
| Access | Congress.gov + congress-legislators | `/bill/{c}/{type}/{n}/committees`, `.../cosponsors`, bill `sponsors`; `committee-membership-current.json` |
| Trade | Congress.gov timeline | `/bill/.../actions` parsed into milestones, re-anchored to markup/committee |
| Payoff | QuiverQuant | `/bulk/congresstrading` `excess_return`, winsorized, vs per-member median baseline |
| Pattern | derived | computed across the full case set |

Keys (`CONGRESS_API_KEY`, `QUIVERQUANT_API_KEY`) are read from `.env`, never logged
or written to output.

## File and function map

- `webapp/build_money_trail.py` -- the engine.
  - `class MoneyTrailDetectiveEngine` -- `link_law`, `link_beneficiary`,
    `link_access`, `link_trade`, `link_payoff`, `link_pattern`, `score_case`.
  - `fetch_bill_evidence(bill_id)` -- Phase 1+2: actions timeline, committees,
    sponsors, cosponsors.
  - `load_committee_rosters()` / `committee_member_names()` -- Phase 2 access.
  - `load_excess_index()` -- Phase 3: excess-return index + per-member baseline.
  - `MATERIALITY` -- Phase 4 curated beneficiary map.
  - `infer_beneficiaries_via_gpt()` -- Phase 4 gpt-4o scaffold (NOT enabled).
  - `verdict_sentence()` -- the plain-language verdict.
  - Output: `webapp/js/money_trail_data.js` (`window.MONEY_TRAIL`), exported to
    `private_data/MONEY_TRAIL.json` (core bundle), refreshed by the scheduler
    `money_trail` job (daily).
- `webapp/js/app.js` -- front end.
  - `mtCaseFor`, `lawScore`, `caseTier` -- leaderboard scoring from the engine.
  - `lawLeaderboard` / `renderMarkets` -- the entry-point leaderboard.
  - `caseFile(billId)` -- the Case File modal.
  - `caseTimeline(c)` -- the SVG milestone-plus-trades timeline.
  - `caseEvidenceCards(c)` -- the six evidence-board cards.

## The Case File UI

The leaderboard ("The Money Trail Detective" screen) is the entry point: every
tracked law ranked by case strength, with a tier pill and quick stats
(beneficiaries, access level, abnormal return). Clicking a row opens the Case
File:

- A plain-language **verdict** at the top, plus an honest note on the weakest or
  missing link so it reads as evidence, not accusation.
- A centerpiece **timeline**: one track for the bill with milestone markers; trades
  plotted below as points, colored by buy/sell and sized by disclosed amount, so
  pre-markup clustering is visually obvious. The anchor milestone is highlighted.
- The **chain of evidence** as six cards (The Law, Who It Pays, Who Knew, Who
  Traded, The Payoff, The Pattern), each with its own strength bar and a short
  "why this matters."

UI copy uses no emojis and no em dashes, and color comes only from the semantic
theme tokens (`--info`, `--warning`, `--danger`, `--success`); pink is reachable
only through Customize Display.

## Phase 4: gpt-4o materiality (scaffolded, not run)

`infer_beneficiaries_via_gpt()` is a scaffold for extending materiality to every
law by reading bill text and proposing the specific beneficiaries, labeled
**model-inferred**. It is disabled by default to avoid spend. Estimated cost of a
full run with gpt-4o: roughly **$0.40 to $1.70** sending titles and summaries
(80 to 322 laws), or **$2 to $8** sending fuller bill text. Enable only after
approving that spend.

## Known limitations (evidenced vs inferred)

- **Beneficiary** is evidenced only for the curated areas (defense, energy,
  health, tech). Outside those, it is keyword-inferred and the case is labeled and
  capped accordingly. The gpt-4o path (above) would close this gap.
- **Access** is evidenced for sponsors, cosponsors, and current committee rosters.
  Historical committee membership (for older trades) and leadership roles are not
  yet wired.
- **Trade timing** uses the milestones Congress.gov exposes in the action log;
  true non-public markup dates can lag the public action text.
- **Payoff** uses QuiverQuant `excess_return` (market-adjusted) winsorized to
  +/-100 points against a per-member median baseline. It is an estimate, not a
  full event study with a fitted factor model.
- **Name matching** between QuiverQuant trader names and Congress.gov rosters is
  fuzzy; a missed match understates access (conservative, not inflating).

Everything the engine outputs is a timing relationship between public disclosures,
legislative milestones, and market-adjusted returns. It does not imply or allege
wrongdoing of any kind.
