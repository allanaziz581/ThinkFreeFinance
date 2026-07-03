"""Item 4: politician performance must be EXCESS return vs SPY over the same window,
disclosed dollars must be a RANGE not a midpoint, and sells must be framed separately
(forewent gain / avoided loss), never summed into buy-side P&L.
"""
import importlib

pp = importlib.import_module("politician_performance")


# --- disclosed amounts are a range, not a single midpoint -------------------------------

def test_parse_range_bounds_returns_low_high():
    assert pp.parse_range_bounds("$1,001 - $15,000") == (1001.0, 15000.0)
    assert pp.parse_range_bounds("$50,001 - $100,000") == (50001.0, 100000.0)


def test_parse_range_bounds_over_and_plain():
    assert pp.parse_range_bounds("Over $5,000,000") == (5000000.0, 5000000.0)
    assert pp.parse_range_bounds("1001.0") == (1001.0, 1001.0)
    assert pp.parse_range_bounds("") == (0.0, 0.0)


# --- excess return vs SPY over the identical window -------------------------------------

def test_excess_vs_benchmark_subtracts_spy():
    # stock 100 -> 120 (+20%), SPY 100 -> 110 (+10%): excess = +10 points = 0.10
    ex = pp.excess_vs_benchmark(100.0, 120.0, 100.0, 110.0)
    assert abs(ex - 0.10) < 1e-9


def test_excess_is_negative_when_stock_lags_market():
    # stock +5%, market +15% -> excess = -10 points, even though the raw return is positive
    ex = pp.excess_vs_benchmark(100.0, 105.0, 100.0, 115.0)
    assert abs(ex - (-0.10)) < 1e-9


def test_excess_none_on_missing_data():
    assert pp.excess_vs_benchmark(None, 120.0, 100.0, 110.0) is None
    assert pp.excess_vs_benchmark(100.0, 120.0, 0.0, 110.0) is None


# --- sells are framed separately, never as buy P&L --------------------------------------

def test_sell_framing_forewent_gain():
    # sold at 100, now 130: they gave up a +30% gain
    f = pp.sell_framing(100.0, 130.0)
    assert f["stance"] == "forewent_gain"
    assert f["return_since_sale_pct"] == 30.0


def test_sell_framing_avoided_loss():
    # sold at 100, now 70: they dodged a -30% loss
    f = pp.sell_framing(100.0, 70.0)
    assert f["stance"] == "avoided_loss"
    assert f["return_since_sale_pct"] == -30.0


def test_simple_return_guards_zero_and_none():
    assert pp.simple_return(0.0, 10.0) is None
    assert pp.simple_return(None, 10.0) is None
    assert abs(pp.simple_return(100.0, 110.0) - 0.10) < 1e-9
