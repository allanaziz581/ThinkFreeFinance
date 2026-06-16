#!/usr/bin/env python3
"""
ThinkFree Finance — Technical Analysis Engine
Downloads 1-year OHLCV data for bullish/bearish sector tickers,
computes TA indicators, and saves ta_analysis_detailed.csv.
"""

from __future__ import annotations

import json
import os
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from tqdm import tqdm

try:
    import talib as _talib
    _TALIB = True
except ImportError:
    _TALIB = False
    import ta as _ta

warnings.simplefilter(action="ignore", category=FutureWarning)

BASE_DIR   = Path(__file__).parent.parent
OUTPUT_DIR = Path(__file__).parent                      # Module_2_Technical_Analysis/
RAW_DATA_DIR = BASE_DIR / "raw_data"

MAPPING_PATH   = BASE_DIR / "Profile" / "flat-ui__data-Sun Jun 15 2025.csv"
REASONING_PATH = BASE_DIR / "news_output" / "economic_reasoning_summary.json"
OUTPUT_CSV     = OUTPUT_DIR / "ta_analysis_detailed.csv"

LOOKBACK_DAYS = 365


def load_sector_mapping() -> pd.DataFrame:
    df = pd.read_csv(MAPPING_PATH)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={"Symbol": "ticker", "GICS Sector": "sector"})
    df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)
    return df


def load_bullish_bearish() -> tuple[list[str], list[str]]:
    if REASONING_PATH.exists():
        try:
            with open(REASONING_PATH, "r", encoding="utf-8") as f:
                r = json.load(f)
            return r.get("bullish_sectors", []), r.get("bearish_sectors", [])
        except Exception:
            pass
    return [], []


def save_raw_csv(ticker: str, df_raw: pd.DataFrame) -> None:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df_raw.to_csv(RAW_DATA_DIR / f"{ticker}.csv", index=True)


def compute_indicators(df_close: pd.Series) -> pd.DataFrame:
    s = df_close.astype(float)

    if _TALIB:
        close = np.ascontiguousarray(s.values)
        macd_line, macd_signal_line, _ = _talib.MACD(close)
        rsi_arr     = _talib.RSI(close)
        sma_50_arr  = _talib.SMA(close, timeperiod=50)
        sma_200_arr = _talib.SMA(close, timeperiod=200)
        df_ind = pd.DataFrame(
            {"macd": macd_line, "macd_signal_line": macd_signal_line,
             "rsi": rsi_arr, "sma_50": sma_50_arr, "sma_200": sma_200_arr},
            index=s.index,
        )
    else:
        macd_obj = _ta.trend.MACD(s)
        df_ind = pd.DataFrame(
            {
                "macd": macd_obj.macd().values,
                "macd_signal_line": macd_obj.macd_signal().values,
                "rsi": _ta.momentum.RSIIndicator(s).rsi().values,
                "sma_50": _ta.trend.SMAIndicator(s, window=50).sma_indicator().values,
                "sma_200": _ta.trend.SMAIndicator(s, window=200).sma_indicator().values,
            },
            index=s.index,
        )

    df_ind["rsi_signal"]   = np.where(df_ind["rsi"] > 70, -1, np.where(df_ind["rsi"] < 30, 1, 0))
    df_ind["macd_signal"]  = np.where(df_ind["macd"] > df_ind["macd_signal_line"], 1, -1)
    df_ind["trend_signal"] = np.where(df_ind["sma_50"] > df_ind["sma_200"], 1, -1)
    return df_ind


def run_ta_analysis(ticker: str) -> pd.DataFrame | None:
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if df is None or df.empty:
            return None
        save_raw_csv(ticker, df)

        if isinstance(df.columns, pd.MultiIndex):
            try:
                close_section = df.xs("Close", axis=1, level=0)
            except KeyError:
                return None
            df_close = close_section.iloc[:, 0] if isinstance(close_section, pd.DataFrame) else close_section
        else:
            if "Close" not in df.columns:
                return None
            df_close = df["Close"]

        df_close = df_close.dropna()
        if df_close.empty:
            return None

        df_ind    = compute_indicators(df_close)
        df_recent = df_ind.tail(LOOKBACK_DAYS).copy()
        df_recent.insert(0, "ticker", ticker)
        return df_recent
    except Exception:
        return None


def main():
    ticker_sector_df = load_sector_mapping()
    bullish_sectors, bearish_sectors = load_bullish_bearish()

    if bullish_sectors or bearish_sectors:
        bulls   = ticker_sector_df[ticker_sector_df["sector"].isin(bullish_sectors)]["ticker"].unique().tolist()
        bears   = ticker_sector_df[ticker_sector_df["sector"].isin(bearish_sectors)]["ticker"].unique().tolist()
        tickers = sorted(set(bulls + bears))
        print(f"Running TA for {len(tickers)} tickers from bullish/bearish sectors...")
    else:
        tickers = sorted(ticker_sector_df["ticker"].dropna().unique().tolist())
        print(f"No sector filter found — running TA for all {len(tickers)} S&P 500 tickers...")

    dfs: list[pd.DataFrame] = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(run_ta_analysis, t): t for t in tickers}
        for future in tqdm(as_completed(futures), total=len(futures)):
            result = future.result()
            if result is not None:
                dfs.append(result)

    if dfs:
        combined = pd.concat(dfs).dropna(how="all")
        combined = combined.reset_index().rename(columns={"index": "Date"})
        # Ensure date column is lowercase 'date' for downstream compatibility
        if "Date" in combined.columns:
            combined = combined.rename(columns={"Date": "date"})

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        combined.to_csv(OUTPUT_CSV, index=False)
        print(f"Saved TA results ({LOOKBACK_DAYS} days) to {OUTPUT_CSV}")
        print(f"Rows: {len(combined)}  Tickers: {combined['ticker'].nunique()}")
    else:
        print("No TA data to save.")


if __name__ == "__main__":
    main()
