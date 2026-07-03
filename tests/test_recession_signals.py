"""Item 9: recession engine must use the Sahm rule (not a naive month-over-month tick),
normalize ^TNX/^IRX to percent so the spread is correct under either yfinance scale, and
DISCLOSE when the score was reweighted because an input was missing.
"""
import importlib

rs = importlib.import_module("recession_signals")


# --- Treasury yield unit normalization -------------------------------------------------

def test_normalize_times_ten_convention():
    assert rs.normalize_treasury_yield(42.5) == 4.25   # times-ten -> percent
    assert rs.normalize_treasury_yield(4.25) == 4.25   # already percent, untouched
    assert rs.normalize_treasury_yield(None) is None


def test_mixed_scales_still_give_correct_inverted_spread():
    ten = rs.normalize_treasury_yield(42.5)    # -> 4.25
    three = rs.normalize_treasury_yield(5.25)  # -> 5.25 (already percent)
    assert round(ten - three, 2) == -1.0       # correctly inverted, not +37


# --- Sahm rule -------------------------------------------------------------------------

def test_sahm_triggers_when_gap_exceeds_half_point():
    # flat at 3.5 for a year, then a clear climb: 3mo avg ends ~0.7 above the low
    vals = [3.5] * 13 + [3.8, 4.2, 4.6]
    gap, triggered = rs.sahm_indicator(vals)
    assert triggered is True
    assert gap >= 0.5


def test_sahm_flat_series_not_triggered():
    gap, triggered = rs.sahm_indicator([4.0] * 15)
    assert triggered is False
    assert gap == 0.0


def test_sahm_needs_history():
    gap, triggered = rs.sahm_indicator([4.0, 4.1])
    assert gap is None and triggered is False


# --- reweighting disclosure ------------------------------------------------------------

def test_missing_fred_is_disclosed_as_degraded():
    out = rs.compute_recession_score(
        yield_curve={"spread": 0.5, "inverted": False},
        vix_data={"vix": 18.0},
        fred={"available": False},
    )
    assert out["degraded"] is True
    assert out["inputs_available"] == 2 and out["inputs_total"] == 3
    assert "2 of 3" in out["degradation_note"]


def test_all_inputs_present_not_degraded():
    out = rs.compute_recession_score(
        yield_curve={"spread": 1.5, "inverted": False},
        vix_data={"vix": 14.0},
        fred={"available": True, "unemployment_rate": 4.0, "sahm_gap": 0.0,
              "sahm_triggered": False, "gdp_growth": 2.6, "gdp_negative": False},
    )
    assert out["degraded"] is False
    assert out["degradation_note"] == ""
    assert out["inputs_available"] == 3
