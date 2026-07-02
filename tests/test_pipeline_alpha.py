"""Item 1: pipeline_alpha next-day-return label must not bleed across tickers, and the
time split must not leak the boundary day. Pure-pandas helpers, no qlib needed."""
import importlib
import math

import numpy as np
import pandas as pd

pa = importlib.import_module("Module_2_Technical_Analysis.pipeline_alpha")


def _two_ticker_feat():
    idx = pd.MultiIndex.from_tuples(
        [
            (pd.Timestamp("2024-01-01"), "AAA"),
            (pd.Timestamp("2024-01-02"), "AAA"),
            (pd.Timestamp("2024-01-03"), "AAA"),
            (pd.Timestamp("2024-01-01"), "BBB"),
            (pd.Timestamp("2024-01-02"), "BBB"),
        ],
        names=["datetime", "instrument"],
    )
    df = pd.DataFrame({("feature", "close"): [10.0, 11.0, 12.0, 100.0, 90.0]}, index=idx)
    df.columns = pd.MultiIndex.from_tuples([("feature", "close")])
    return df


def test_next_day_returns_no_cross_ticker_bleed():
    lab = pa.next_day_returns(_two_ticker_feat())
    d1, d2, d3 = pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")

    # within AAA: returns 0.1 then 0.0909..., last day has no "tomorrow" -> NaN
    assert abs(lab.loc[(d1, "AAA")] - 0.10) < 1e-9
    assert abs(lab.loc[(d2, "AAA")] - (12.0 / 11.0 - 1.0)) < 1e-9
    assert math.isnan(lab.loc[(d3, "AAA")]), "AAA last day bled into BBB (cross-ticker return)"

    # BBB's first labelled day is its own -10%, NOT a return off AAA's last close (12 -> 100)
    assert abs(lab.loc[(d1, "BBB")] - (-0.10)) < 1e-9
    assert math.isnan(lab.loc[(d2, "BBB")])

    # the buggy stacked pct_change would have produced ~ +7.33 at the AAA->BBB seam
    assert not any(v > 1.0 for v in lab.dropna().values), "a >100% return implies cross-ticker bleed"


def test_time_split_is_chronological_and_gapped():
    dates = pd.bdate_range("2020-01-01", periods=200)
    seg = pa.time_split(dates, val_frac=0.15, test_frac=0.15, gap=1)

    tr_s, tr_e = seg["train"]
    va_s, va_e = seg["validation"]
    te_s, te_e = seg["test"]

    # strictly increasing, non-overlapping segments
    assert tr_s <= tr_e < va_s <= va_e < te_s <= te_e
    # a real gap between train and validation (no boundary-day overlap like the old code)
    assert va_s > tr_e
    # NO training or validation date is on or after the first test date (no look-ahead)
    assert tr_e < te_s and va_e < te_s
    # every segment non-empty and covers to the last date
    assert te_e == dates[-1]
