"""Phase 8.5 (experimental) qlib alpha pipeline.

DISABLED. This qlib LGBModel branch is NOT wired into controller.py (the controller's
phase 8.5 runs phase_3_signal.py, and phase 8.7 runs quantlib_metrics.py); this script
has zero downstream consumers and qlib is not installed in the pipeline env. It stays
in the repo for reference but does nothing on import: set RUN_PIPELINE_ALPHA = True to
run it, which requires qlib + a formatted qlib_data pickle.

Two statistical bugs it had (now fixed and testable):
  * The next-day return label used close.pct_change() on the whole stacked column, so a
    return bled across ticker boundaries (the first row of one instrument became a
    "return" off the last row of the previous instrument). Fixed to group by instrument.
  * The train/test split set train_end == test_start (both dates[-2]), leaking the
    boundary day into both sets. Fixed to a strictly chronological, gapped split.

The two fixes are pure pandas helpers (next_day_returns, time_split) so they can be
tested without importing qlib.
"""
from __future__ import annotations

import pandas as pd

# Disable flag: the whole qlib run only executes when this is True AND run as a script.
RUN_PIPELINE_ALPHA = False


def next_day_returns(df_feat: pd.DataFrame) -> pd.Series:
    """Next-day close return PER INSTRUMENT.

    df_feat has a MultiIndex (datetime, instrument) and a MultiIndex column
    ('feature', 'close'). Grouping by the instrument level means pct_change and the
    -1 shift never cross ticker boundaries, so no return bleeds from one ticker's last
    day into another ticker's first day.
    """
    close = df_feat["feature"]["close"]
    daily = close.groupby(level="instrument").pct_change()          # today's return, within ticker
    return daily.groupby(level="instrument").shift(-1)              # label = tomorrow's return


def time_split(dates, val_frac: float = 0.15, test_frac: float = 0.15, gap: int = 1) -> dict:
    """Chronological train / validation / test split by date, with a GAP so no train or
    validation date is on or after the first test date. Returns {seg: (start, end)}.

    The old code used train_end = test_start = dates[-2], which overlapped the boundary
    day. Here train strictly precedes validation (with a gap), which strictly precedes
    test, so there is no look-ahead leak across the split.
    """
    idx = pd.DatetimeIndex(pd.to_datetime(pd.Index(dates))).unique().sort_values()
    n = len(idx)
    if n < 5:
        return {"train": (idx[0], idx[0]), "validation": (idx[0], idx[0]), "test": (idx[-1], idx[-1])}
    n_test = max(1, int(round(n * test_frac)))
    n_val = max(1, int(round(n * val_frac)))
    test_start_i = n - n_test
    val_start_i = max(1, test_start_i - n_val)
    train_end_i = max(0, val_start_i - 1 - gap)     # gap trading days before validation
    return {
        "train":      (idx[0], idx[train_end_i]),
        "validation": (idx[val_start_i], idx[test_start_i - 1]),
        "test":       (idx[test_start_i], idx[-1]),
    }


def run() -> None:
    """The original qlib LGBModel pipeline, with the two fixes applied. Lazy imports so
    this module is importable (and testable) without qlib installed."""
    import os
    from typing import cast
    import qlib
    from qlib.config import REG_US
    from qlib.data.dataset.loader import StaticDataLoader
    from qlib.data.dataset.handler import DataHandlerLP
    from qlib.data.dataset import DatasetH
    from qlib.contrib.model.gbdt import LGBModel

    provider_uri = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "qlib_data")
    # US region (the securities are US equities; the old code used REG_CN, the wrong calendar).
    qlib.init(provider_uri=provider_uri, region=REG_US)

    data_path = os.path.join(provider_uri, "formatted", "data.pkl")
    df = pd.read_pickle(data_path)
    print(f"Loaded DataFrame: shape={df.shape}, index.names={df.index.names}")

    if not pd.api.types.is_datetime64_any_dtype(df.index.get_level_values("datetime")):
        dates = pd.to_datetime(df.index.get_level_values("datetime"))
        insts = df.index.get_level_values("instrument")
        df.index = pd.MultiIndex.from_arrays([dates, insts], names=["datetime", "instrument"])

    if not isinstance(df.columns, pd.MultiIndex) or "label" not in df.columns.get_level_values(0):
        feat_cols = df.columns.tolist()
        df_feat = df[feat_cols].copy()
        df_feat.columns = pd.MultiIndex.from_product([["feature"], feat_cols])
        df_label = next_day_returns(df_feat).to_frame("label")      # FIX: per-instrument, no bleed
        df_label.columns = pd.MultiIndex.from_product([["label"], ["label"]])
        df = pd.concat([df_feat, df_label], axis=1)

    data_loader = StaticDataLoader(config=df)
    min_dt = df.index.get_level_values("datetime").min()
    max_dt = df.index.get_level_values("datetime").max()
    to_iso = lambda v: v.date().isoformat() if hasattr(v, "date") else str(v)
    handler = DataHandlerLP(
        instruments=None, start_time=to_iso(min_dt), end_time=to_iso(max_dt),
        data_loader=data_loader,
        infer_processors=[{"class": "Fillna", "kwargs": {"fields_group": "feature"}}],
        learn_processors=[{"class": "DropnaLabel", "kwargs": {}}],
        process_type="append",
    )

    dates = df.index.get_level_values("datetime").unique().sort_values()
    segments = time_split(dates)                                    # FIX: non-overlapping, gapped
    print(f"Segments: train={segments['train']} validation={segments['validation']} test={segments['test']}")

    dataset = DatasetH(handler=handler, segments=segments)
    model = LGBModel()
    model.fit(dataset)
    preds = model.predict(dataset)                                  # test-segment predictions only
    print(f"Predictions: shape={preds.shape}")
    return preds


if __name__ == "__main__":
    if RUN_PIPELINE_ALPHA:
        run()
    else:
        print("pipeline_alpha is DISABLED (RUN_PIPELINE_ALPHA=False). Not wired to the controller; no consumers.")
