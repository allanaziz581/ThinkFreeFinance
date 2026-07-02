"""Item 6: max drawdown must respect time order (peak-to-subsequent-trough), not the
global min/max which ignores when the trough occurred."""
import importlib

hc = importlib.import_module("historical_correlation")


def test_max_drawdown_respects_time_order():
    # Dip BEFORE the peak: true peak-to-trough is the early 100 -> 80 (-20%).
    # The old (min-max)/max formula gave (80-120)/120 = -33.3% (never happened in order).
    assert hc.max_drawdown_pct([100, 80, 120]) == -20.0


def test_max_drawdown_monotonic_up_is_zero():
    # A series that only rises has NO drawdown. The old formula gave (100-120)/120 = -16.7%.
    assert hc.max_drawdown_pct([100, 110, 120]) == 0.0


def test_max_drawdown_trough_after_peak_matches_naive():
    # When the trough follows the peak both agree: peak 120 -> trough 60 = -50%.
    assert hc.max_drawdown_pct([100, 120, 60]) == -50.0


def test_max_drawdown_is_non_positive_and_worst_of_multiple_dips():
    # Running peak stays 100 (90 and 45 never exceed it): worst is 100 -> 45 = -55%.
    assert hc.max_drawdown_pct([100, 70, 90, 45]) == -55.0
