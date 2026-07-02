# Part 2B — Statistical Methodology and Corrections

This part documents the **current statistical methodology** for the quantitative
engine, incorporating the corrections from an in-progress statistical audit. It
is written as the **updated, intended approach** so it can be reviewed before the
implementing code merges. Where a correction replaces a prior method, the prior
method is described only to make the change legible. Nothing here quotes a live
point figure, because those change with the data and are computed at run time.

## 2B.0 Why this section exists

The engine was audited for statistical honesty: places where a formula returned a
subtly wrong quantity, where a model number was presented as if it were a fact,
or where an output read like advice. The corrections below make every number mean
exactly what it says, state its lookback and assumptions, and stop short of
anything that resembles a recommendation. The theme is **honesty over
impressiveness**: fewer numbers, each one defensible.

## 2B.1 Expected return uses the true mean, not the median

- **Correction.** Expected return is computed as the true expected price,
  `E[S_T] = S_0 * exp(r * T)`, where `S_0` is spot, `r` the drift, and `T` the
  horizon. Expected return is `E[S_T] / S_0 - 1`.
- **What was wrong.** The prior lognormal expression returned the **median**
  terminal price, `S_0 * exp((r - sigma^2 / 2) * T)`, and labeled it the expected
  (mean) return. For a lognormal, the mean exceeds the median, so the old figure
  understated the expected value by the volatility-drag term. The label now
  matches the quantity.

## 2B.2 Probability of a move is an honest historical frequency

- **Correction.** "Probability of a +5% move" (and similar thresholds) is reported
  as the **historical frequency**: over the past five years of **rolling 21-day
  windows**, the fraction of windows in which the asset gained 5% or more. The
  lookback is stated alongside the number. No confidence interval is attached,
  because a single realized-path frequency does not carry one.
- **What was wrong.** The prior figure was the risk-neutral `N(d2)` from the
  Black-Scholes world. That is a pricing-measure probability, not a real-world
  chance of the event, and presenting it as "the probability you make 5%" is
  misleading. The historical frequency answers the question a person actually asks
  ("how often has this happened before?") and is transparent about its window.

## 2B.3 Kelly sizing removed from user-facing outputs

- **Correction.** Kelly "percent of portfolio" is **removed from every user-facing
  output, briefing, and LLM prompt**. Kelly may remain an internal research
  quantity, but it is never shown to a user and never fed to the language model.
- **What was wrong.** Kelly fractions estimated from roughly one year of samples
  are unstable, and a "put X percent of your portfolio here" number reads as
  individualized financial advice, which the platform must not give. Removing it
  keeps the product on the research-analyst side of the line.

## 2B.4 Backtest is walk-forward and point-in-time

- **Correction.** The backtest is **walk-forward** and free of look-ahead:
  - The universe is **frozen at the backtest start** from **point-in-time S&P 500
    constituents**, so membership is what it was then, not today's survivors.
  - Data is split by **time** into train, validation, and test windows.
  - Only **test-window** metrics are ever reported; train and validation results
    are diagnostic and are not surfaced.
- **What was wrong.** Earlier backtests were contaminated by survivorship bias
  (today's index members applied to the past) and by fitting and reporting on the
  same period. Those **old backtest numbers are archived and suppressed**; they no
  longer appear in any output.

## 2B.5 Recession trigger uses the Sahm rule

- **Correction.** The recession trigger uses the **Sahm rule**: it fires when the
  three-month average unemployment rate rises **0.5 percentage points** above its
  **lowest three-month average of the prior twelve months**. When an input series
  is short or partially available, the engine **discloses the reduced-data
  reweighting** it applied rather than silently substituting.
- **Why.** The Sahm rule is a published, well-understood real-time recession
  indicator with a clear, reproducible definition, which suits a transparency-first
  product better than an ad hoc composite.

## 2B.6 Politician scoreboard ranks on excess return

- **Correction.** The congressional-trading scoreboard ranks members on **excess
  return versus SPY over the identical holding window** (the member's return minus
  the market's return over the same dates), not on raw dollars.
- **Sells are framed honestly.** A sale is described as **avoided or foregone**
  exposure ("avoided a subsequent decline"), and is **never summed together with
  buy profit-and-loss** into one number, because a sale's counterfactual is not the
  same quantity as a realized gain.
- **Totals are ranges.** Dollar totals are shown as **ranges**, reflecting that
  disclosures report brackets rather than exact amounts.
- The political-intelligence framing rule (timing relationships, not intent) still
  governs every line of this output.

## 2B.7 One clean signal definition

- **Correction.** The trading signal is a **single, clearly stated momentum
  definition**. Any "phantom" indicators (terms that were named in explanations
  but not actually computed, or double-counted) are removed. What the signal says
  it uses is exactly what it computes.

## 2B.8 Opportunity score separates outlook from suitability

- **Correction.** The opportunity score presents **two separate axes**:
  - **Outlook** — the model's directional read and its strength.
  - **Suitability** — how the idea fits the user's stated risk profile.
- These are shown side by side and are **not multiplied into a single inflated
  composite**. The prior "times ten" composite conflated a market view with a
  personal-fit judgment and exaggerated small differences.

## 2B.9 Every LLM number is validated against source

- **Correction.** Any number that appears in language-model output is **validated
  by set membership against the source values**: the figure must match a value that
  the deterministic engine actually produced, or it is rejected and regenerated. The
  language model may phrase numbers, never invent them.
- **Prompt change.** The prompt line that asked the model **"what stocks to buy"**
  is **removed**. The model translates and explains; it does not recommend
  purchases.

## 2B.10 Degradation flag on incomplete inputs

- **Correction.** When a briefing is assembled from **incomplete inputs** (a feed
  was stale, an API returned partial data, a metric could not be computed), a
  **degradation flag surfaces in the briefing itself**, so the reader knows the
  output was built on reduced data rather than assuming full coverage.

## 2B.11 Recent corrections, in one line each

- Expected return now uses the mean `S_0 * exp(r T)`, not the lognormal median.
- Probability of a move is a stated-lookback historical frequency, not `N(d2)`.
- Kelly percent removed from all user-facing outputs and prompts.
- Backtest is walk-forward, point-in-time universe, test-window metrics only; old
  numbers archived.
- Recession trigger is the Sahm rule with disclosed reduced-data reweighting.
- Scoreboard ranks on excess-vs-SPY; sells framed as avoided, never summed with
  buys; totals as ranges.
- One clean momentum signal, no phantom indicators.
- Opportunity score splits outlook from suitability, no times-ten composite.
- LLM numbers validated by set membership; the "what to buy" prompt line removed.
- A degradation flag appears on any briefing built from incomplete inputs.
