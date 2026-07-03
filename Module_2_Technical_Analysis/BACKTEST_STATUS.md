# Backtest status: SUPPRESSED pending a clean point-in-time re-run

## Why the old results are archived

`results_run/summary_metrics.json` (Sharpe 2.21, CAGR 46.7%, Max DD 10.2%) was produced by
a look-ahead-contaminated run and must not be cited to users. Two leaks:

1. **Universe look-ahead / survivorship.** The tested tickers were drawn from *today's*
   sector membership and then backtested over the past year. A strategy in the past could
   not have known which names would still be in the index (or still solvent) today.
   Winners survive into the sampled universe; losers and delistings silently drop out.
2. **No held-out test window.** Signal thresholds were effectively tuned on the same span
   they were scored on, so the metrics describe the fit, not out-of-sample performance.

The file is moved to `results_run/archived_contaminated/summary_metrics.CONTAMINATED.json`
and is no longer read by `chef_gpt.py`. Until a clean run exists, the intelligence
briefing cites no backtest CAGR/Sharpe (the "Strategy Validation" section was removed from
the Chef GPT prompt, and "Backtest Results" was removed from its data-source list).

## Documented follow-up: a clean run

A future clean backtest must:

1. **Freeze the universe at the backtest START.** Use a point-in-time constituent list.
   If a true point-in-time S&P source is unavailable, use a fixed, hand-curated large-cap
   list frozen at the start date and state that limitation in the output.
2. **Chronological train / validation / test split** with a gap (reuse the pattern in
   `pipeline_alpha.time_split`). Tune only on train, select on validation.
3. **Cite ONLY test-window metrics** to users. Never report in-sample numbers.
4. **Span 5+ years** so the sample crosses more than one regime.

Only after such a run may the Chef GPT "Strategy Validation" section and its data-source
label be restored.
