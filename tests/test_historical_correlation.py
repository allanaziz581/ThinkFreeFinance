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


# --- Event detection: 2+ keywords + non-negated sentence -------------------------------

def test_event_match_requires_two_distinct_keywords():
    kws = ["rate hike", "hawkish", "tightening"]
    # a single keyword is not enough evidence
    assert hc.event_matches("The Fed signalled a rate hike today.", kws) is False
    # two distinct keywords in an affirmative sentence -> match
    assert hc.event_matches("A hawkish Fed delivered a rate hike amid tightening.", kws) is True


def test_event_match_rejects_negated_sentence():
    kws = ["rate hike", "hawkish"]
    # both keywords present but the only sentence mentioning them is negated
    txt = "The Fed did not signal a rate hike and was not hawkish this month."
    assert hc.event_matches(txt, kws) is False


def test_event_match_affirmative_beats_negated_elsewhere():
    kws = ["rate hike", "hawkish", "tightening"]
    # one negated sentence, but a separate affirmative sentence carries two keywords
    txt = "Officials were not dovish. A hawkish tone accompanied the rate hike."
    assert hc.event_matches(txt, kws) is True


# --- Pre-ETF handling ------------------------------------------------------------------

def test_broad_market_proxy_switches_at_spy_inception():
    assert hc.broad_market_proxy("1979-01-01") == "^GSPC"   # pre-SPY
    assert hc.broad_market_proxy("2020-01-01") == "SPY"


def test_sector_data_unavailable_before_etf_inception():
    assert hc.sector_data_available("1980-01-01") is False
    assert hc.sector_data_available("2020-01-01") is True


# --- Key takeaway reports per period, never an average ---------------------------------

def _period(label, spy_ret):
    return {"label": label, "sector_performance": {"Broad Market": {"total_return_pct": spy_ret}}}


def test_key_takeaway_reports_range_not_average():
    periods = [_period("2022 Cycle", 20.0), _period("2018 Cycle", -10.0)]
    out = hc._extract_key_takeaway("fed_rate_hike", periods)
    # The old code averaged (+5.0%); the new text must never claim an average and must
    # show BOTH episodes and the range endpoints.
    assert "average" not in out.lower()
    assert "20.0%" in out and "10.0%" in out
    assert "-10.0%" in out and "+20.0%" in out
