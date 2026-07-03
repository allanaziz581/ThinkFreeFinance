"""Item 8: opportunity scoring must keep OUTLOOK and SUITABILITY separate (not multiplied),
match sectors on canonical GICS names, keep the ticker DIRECTION as the actual signal (no
relabeling), and drop the x10 costume (no 0-10 blended opportunity_score).
"""
import importlib

opp = importlib.import_module("opportunity_score")


# --- GICS canonical matching -----------------------------------------------------------

def test_canonical_sector_maps_aliases():
    assert opp.canonical_sector("Tech") == "Information Technology"
    assert opp.canonical_sector("infotech") == "Information Technology"
    assert opp.canonical_sector("Telecom") == "Communication Services"
    assert opp.canonical_sector("healthcare") == "Health Care"


def test_outlook_matches_via_alias():
    # bullish list uses "Tech"; the sector queried is the canonical "Information Technology"
    assert opp.score_sector_outlook("Information Technology", ["Tech"], []) == 1.0
    assert opp.score_sector_outlook("Telecom", [], ["Communication Services"]) == 0.0


# --- outlook and suitability are separate, not multiplied -------------------------------

def test_outlook_not_dragged_down_by_low_suitability():
    # A bullish sector that is a POOR fit for a low-risk income profile must still show a
    # strong outlook; suitability lives in its own field.
    profile = {"risk_tolerance": "low", "investment_goal": "growth"}
    rows = opp.build_sector_scores(
        bullish_sectors=["Information Technology"], bearish_sectors=[], signals=[],
        recession_risk_score=1.0, profile=profile, sector_summaries={},
    )
    it = next(r for r in rows if r["sector"] == "Information Technology")
    assert it["outlook"]["label"] == "Bullish"
    assert it["outlook"]["conviction"] == 1.0            # full outlook, undiluted by fit
    assert "suitability" in it and "opportunity_score" not in it   # no x10 blended score


def test_no_x10_costume_and_conviction_in_unit_range():
    rows = opp.build_sector_scores(
        ["Energy"], ["Utilities"], [], 3.0, {"risk_tolerance": "moderate"}, {},
    )
    for r in rows:
        assert 0.0 <= r["outlook"]["conviction"] <= 1.0
        assert "opportunity_score" not in r
        assert "direction_emoji" not in r


# --- ticker direction is the real signal, never relabeled from a score -----------------

def test_ticker_direction_is_actual_signal_even_when_discounted():
    # A real BUY under heavy recession risk keeps signal == BUY (old code relabeled it a
    # "Sell Signal" once the discounted score dropped below threshold).
    signals = [{"ticker": "AAA", "final_signal": "BUY", "confidence_score": 3, "reasoning": "x"}]
    rows = opp.build_ticker_scores(signals, [], [], 9.0, {"risk_tolerance": "moderate"}, {})
    aaa = next(r for r in rows if r["ticker"] == "AAA")
    assert aaa["signal"] == "BUY"
    assert "direction_emoji" not in aaa
    assert "opportunity_score" not in aaa
    assert 0.0 <= aaa["signal_conviction"] <= 1.0
