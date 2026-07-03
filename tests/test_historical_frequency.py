"""Item 5: the 1-month 5% probability shown to users must be an empirical HISTORICAL
FREQUENCY (fraction of past rolling 21-day windows that met the move), not the
Black-Scholes N(d2) risk-neutral probability. And Kelly must be gone from the output.
"""
import importlib

qm = importlib.import_module("quantlib_metrics")


def test_frequency_counts_rolling_windows_up():
    # A clean +1%/day ramp: every 21-day window gains well over 5%, so frequency = 100%.
    prices = [100.0 * (1.01 ** i) for i in range(60)]
    freq, n = qm.historical_move_frequency(prices, horizon_days=21, threshold=0.05, direction="up")
    assert n == len(prices) - 21
    assert freq == 1.0


def test_frequency_zero_when_flat():
    prices = [100.0] * 60
    freq_up, _ = qm.historical_move_frequency(prices, 21, 0.05, "up")
    freq_dn, _ = qm.historical_move_frequency(prices, 21, 0.05, "down")
    assert freq_up == 0.0 and freq_dn == 0.0


def test_frequency_half_up_half_down():
    # 21 flat days, then a jump to +10%: exactly the windows that straddle the jump qualify.
    # Build a series where precisely half the windows clear +5%.
    # 22 points flat at 100, then 21 points at 110: windows starting at index 0..21.
    prices = [100.0] * 22 + [110.0] * 21           # length 43 -> 22 windows (0..21)
    freq, n = qm.historical_move_frequency(prices, 21, 0.05, "up")
    assert n == 22
    # windows starting at i land on i+21; those landing in the 110 block clear +5%.
    # i+21 >= 22  -> i >= 1, so 21 of 22 windows qualify.
    assert round(freq, 4) == round(21 / 22, 4)


def test_frequency_none_when_too_short():
    freq, n = qm.historical_move_frequency([100.0, 101.0], 21, 0.05, "up")
    assert freq is None and n == 0


def test_direction_down_counts_drops():
    # steady -1%/day: every 21-day window loses well over 5%
    prices = [100.0 * (0.99 ** i) for i in range(60)]
    freq_dn, _ = qm.historical_move_frequency(prices, 21, 0.05, "down")
    freq_up, _ = qm.historical_move_frequency(prices, 21, 0.05, "up")
    assert freq_dn == 1.0 and freq_up == 0.0


def test_kelly_not_in_ticker_metric_output_schema():
    # compute_ticker_metrics with a too-short/empty price path (no network) still returns
    # the schema; it must not carry a kelly key, and must carry historical-frequency keys.
    import quantlib_metrics as m
    orig = m.fetch_recent_prices
    orig_hist = m.fetch_history
    m.fetch_recent_prices = lambda *a, **k: []       # force the short-history branch
    m.fetch_history = lambda *a, **k: []             # no network
    try:
        rec = m.compute_ticker_metrics("TEST", {"final_signal": "HOLD"})
    finally:
        m.fetch_recent_prices = orig
        m.fetch_history = orig_hist
    assert "kelly_fraction" not in rec
    assert "prob_5pct_upside_1mo" not in rec
    assert "hist_freq_up_5pct_1mo" in rec
    assert "hist_lookback_years" in rec
