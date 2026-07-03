"""Item 7: the phase-3 voter must be a clean 3-indicator MOMENTUM signal (RSI + MACD +
SMA trend) with OBV/ADX/CCI dropped, and the RSI/MACD it consumes must match TA-Lib.
"""
import importlib

import numpy as np
import pandas as pd
import pytest

sig = importlib.import_module("Module_2_Technical_Analysis.phase_3_signal")
ta = importlib.import_module("Module_2_Technical_Analysis.ta_analysis")


# --- momentum vote uses only RSI + MACD + SMA, max magnitude 3 --------------------------

def test_all_bullish_momentum_is_buy():
    s, conf, sup, _ = sig.momentum_vote(rsi=25, macd=1.0, macd_signal=0.0, sma50=110, sma200=100)
    assert s == "BUY"
    assert conf == 3          # exactly three indicators can vote, not six


def test_all_bearish_momentum_is_sell():
    s, conf, _, _ = sig.momentum_vote(rsi=75, macd=0.0, macd_signal=1.0, sma50=90, sma200=100)
    assert s == "SELL"
    assert conf == -3


def test_neutral_is_hold_and_confidence_never_exceeds_three():
    s, conf, _, _ = sig.momentum_vote(rsi=50, macd=None, macd_signal=None, sma50=None, sma200=None)
    assert s == "HOLD" and conf == 0
    # even maximally bullish, the tally caps at 3 (proof OBV/ADX/CCI were removed)
    _, conf_max, _, _ = sig.momentum_vote(rsi=10, macd=5.0, macd_signal=0.0, sma50=200, sma200=100)
    assert abs(conf_max) <= 3


def test_analyze_row_ignores_obv_adx_cci_columns():
    # momentum is neutral, but OBV/ADX/CCI carry "bullish-looking" values. If any still
    # voted, this would not be HOLD. It must be HOLD.
    row = pd.Series({
        "ticker": "TEST", "date": "2026-01-01",
        "rsi": 50.0, "macd": np.nan, "macd_signal_line": np.nan,
        "sma_50": np.nan, "sma_200": np.nan,
        "obv": 999999.0, "adx": 55.0, "cci": 250.0,
    })
    out = sig.analyze_row(row)
    assert out["final_signal"] == "HOLD"
    assert out["confidence_score"] == 0


# --- the RSI / MACD feeding the voter match TA-Lib to 4 decimals ------------------------

def test_rsi_macd_match_talib_to_4dp():
    if not getattr(ta, "_TALIB", False):
        pytest.skip("TA-Lib not available in this environment")
    import talib
    close = pd.Series([100 + 10 * np.sin(i / 5.0) + i * 0.1 for i in range(300)])
    ind = ta.compute_indicators(close)
    arr = np.ascontiguousarray(close.values.astype(float))
    rsi_tl = talib.RSI(arr)
    macd_tl, macd_sig_tl, _ = talib.MACD(arr)
    assert round(float(ind["rsi"].iloc[-1]), 4) == round(float(rsi_tl[-1]), 4)
    assert round(float(ind["macd"].iloc[-1]), 4) == round(float(macd_tl[-1]), 4)
    assert round(float(ind["macd_signal_line"].iloc[-1]), 4) == round(float(macd_sig_tl[-1]), 4)
