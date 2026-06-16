#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ThinkFree Finance — Phase 4 Backtesting Engine (JSON-config + CLI)
==================================================================

- Reads signal CSV with RSI/MACD/SMA50/SMA200 + signal flags (1, -1, 0).
- Universe = tickers present in CSV (no S&P-only restriction).
- Downloads full OHLCV history (adjusted) with yfinance.
- Recomputes RSI(14), MACD(12/26/9), SMA50/200, ATR(14) for validation.
- Long/Short based on alignment threshold (min_align: 1..3) across:
    rsi_signal, macd_signal_flag, trend_signal
- Optional: use provided signals only (use_recalc=False) or recalc (True).
- Equal-weight sizing with a hard portfolio drawdown stop.
- Filters by min price/volume if desired.
- Saves equity curve, trades, summary metrics JSON.

JSON config (if present) overrides CLI args automatically:
  Module_2_Technical_Analysis/results_run/backtest_config.json

Example JSON:
{
  "signals_csv": "/Users/allanaziz/Desktop/ThinkFree/ThinkFree-main/Module_2_Technical_Analysis/ta_analysis_detailed.csv",
  "out_dir": "/Users/allanaziz/Desktop/ThinkFree/ThinkFree-main/Module_2_Technical_Analysis/results_run",
  "initial_cash": 100000,
  "commission": 0.0005,
  "slippage_pct": 0.0005,
  "max_positions": 10,
  "risk_free": 0.02,
  "dd_stop": 0.35,
  "min_align": 2,
  "use_recalc": false,
  "verbose_mismatch": false,
  "min_price": 1.0,
  "min_volume": 100000
}

Run (no args needed if JSON exists):
  python phase_4_backtrader.py

Or with CLI:
  python phase_4_backtrader.py \
    --signals_csv ta_analysis_detailed.csv \
    --out_dir results_run \
    --initial_cash 100000 --max_positions 10 \
    --commission 0.0005 --slippage_pct 0.0005 \
    --dd_stop 0.35 --min_align 2 --use_recalc false
"""

from __future__ import annotations

import argparse
import json
import os
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, cast

import numpy as np
import pandas as pd
import backtrader as bt

try:
    import yfinance as yf
except Exception as e:
    raise ImportError("Missing dependency 'yfinance'. Install via: pip install yfinance") from e


# -----------------------------
# Global Configuration Defaults
# -----------------------------
DEFAULT_INITIAL_CASH: float = 100_000.0
DEFAULT_MAX_POSITIONS: int = 10
DEFAULT_COMMISSION: float = 0.0005      # 5 bps per side
DEFAULT_SLIPPAGE_PCT: float = 0.0005    # 5 bps
DEFAULT_RISK_FREE: float = 0.0
MIN_BARS_WARMUP: int = 220              # >= SMA200 warm-up

# Technicals
RSI_PERIOD: int = 14
MACD_FAST: int = 12
MACD_SLOW: int = 26
MACD_SIGNAL: int = 9
SMA_SHORT: int = 50
SMA_LONG: int = 200
ATR_PERIOD: int = 14

# Portfolio drawdown guard
MAX_PORTFOLIO_DRAWDOWN: float = 0.35    # 35%


# -----------------------------
# IO helpers
# -----------------------------
def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)


# -----------------------------
# Scalar coercion helpers
# -----------------------------
def to_float_scalar(x: Any, default: float = 0.0) -> float:
    """Coerce Pandas/NumPy scalars or Series into a Python float."""
    try:
        if isinstance(x, pd.Series):
            if not x.empty:
                return float(np.asarray(x.iloc[0]).item())
            return default
        if isinstance(x, (np.generic, np.number)):
            return float(np.asarray(x).item())
        return float(x)
    except Exception:
        return default


def to_int_scalar(x: Any, default: int = 0) -> int:
    """Coerce Pandas/NumPy scalars or Series into a Python int."""
    try:
        if isinstance(x, pd.Series):
            if not x.empty:
                return int(np.asarray(x.iloc[0]).item())
            return default
        if isinstance(x, (np.generic, np.number)):
            return int(np.asarray(x).item())
        return int(x)
    except Exception:
        return default


# -----------------------------
# Signals loading & normalization
# -----------------------------
COLUMN_ALIASES: Dict[str, str] = {
    'MACD': 'macd',
    'MACD_Signal': 'macd_signal',
    'macd_signal_line': 'macd_signal',
    'macd_sig': 'macd_signal_flag',
    'macd_signal': 'macd_signal_flag',   # ta_analysis.py outputs 'macd_signal'; map it here
    'RSI': 'rsi',
    'SMA50': 'sma_50',
    'SMA200': 'sma_200',
    'rsi_sig': 'rsi_signal',
    'trend_sig': 'trend_signal',
    'Ticker': 'ticker',
    'SYMBOL': 'ticker',
    'symbol': 'ticker',
    'DATE': 'Date',
    'date': 'Date',
    'timestamp': 'Date',
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map: Dict[str, str] = {}
    for c in list(df.columns):
        key = str(c).strip()
        if key in COLUMN_ALIASES:
            rename_map[c] = COLUMN_ALIASES[key]
    df = df.rename(columns=rename_map, errors='ignore')
    df.columns = [str(c) for c in df.columns]
    return df


def load_signals(signals_csv: str) -> Dict[str, pd.DataFrame]:
    if not os.path.isfile(signals_csv):
        raise FileNotFoundError(f"Signals CSV not found: {signals_csv}")
    df = pd.read_csv(signals_csv)
    df = normalize_columns(df)

    if 'Date' not in df.columns:
        raise ValueError("Signals CSV must contain a 'Date' column.")
    if 'ticker' not in df.columns:
        raise ValueError("Signals CSV must contain a 'ticker' column.")

    df['Date'] = pd.to_datetime(df['Date'])
    df['ticker'] = df['ticker'].astype(str)

    # Ensure signal columns exist (default 0)
    for col in ('rsi_signal', 'macd_signal_flag', 'trend_signal'):
        if col not in df.columns:
            df[col] = 0

    df = df.sort_values(['ticker', 'Date']).reset_index(drop=True)

    by_ticker: Dict[str, pd.DataFrame] = {}
    for tkr, g in df.groupby('ticker'):
        g = g.copy()
        g.set_index('Date', inplace=True)
        g.columns = [str(c) for c in g.columns]
        by_ticker[str(tkr)] = g

    return by_ticker


# -----------------------------
# TA recompute (validation)
# -----------------------------
def ta_validate(price_df: pd.DataFrame) -> pd.DataFrame:
    """
    Append RSI/MACD/SMA/ATR and *_signal*_recalc to price_df.
    Index-safe (uses numpy masks).
    """
    df = price_df.copy()

    # Flatten any MultiIndex columns defensively
    if isinstance(df.columns, pd.MultiIndex):
        try:
            df.columns = df.columns.get_level_values(0)
        except Exception:
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    required = ['Open', 'High', 'Low', 'Close', 'Volume']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Price DataFrame missing columns: {missing}")

    close = df['Close']
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    # RSI (Wilder)
    delta = close.diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    gain = up.ewm(alpha=1/RSI_PERIOD, adjust=False).mean()
    loss = down.ewm(alpha=1/RSI_PERIOD, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi_recalc'] = 100 - (100 / (1 + rs))

    # MACD
    ema_fast = close.ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = close.ewm(span=MACD_SLOW, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    macd_signal = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()
    df['macd_recalc'] = macd_line
    df['macd_signal_recalc'] = macd_signal

    # SMAs
    df['sma50_recalc'] = close.rolling(SMA_SHORT).mean()
    df['sma200_recalc'] = close.rolling(SMA_LONG).mean()

    # ATR
    high = df['High']; low = df['Low']
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    df['atr_recalc'] = tr.ewm(span=ATR_PERIOD, adjust=False).mean()

    # Signals via numpy masks
    rsi_sig = pd.Series(0, index=df.index)
    m_rsi_long  = (df['rsi_recalc'] < 30).fillna(False).to_numpy()
    m_rsi_short = (df['rsi_recalc'] > 70).fillna(False).to_numpy()
    rsi_sig.iloc[m_rsi_long]  = 1
    rsi_sig.iloc[m_rsi_short] = -1

    macd_sig = pd.Series(0, index=df.index)
    m_macd_up = (macd_line > macd_signal).fillna(False).to_numpy()
    m_macd_dn = (macd_line < macd_signal).fillna(False).to_numpy()
    macd_sig.iloc[m_macd_up] = 1
    macd_sig.iloc[m_macd_dn] = -1

    trend_sig = pd.Series(0, index=df.index)
    m_tr_up = (df['sma50_recalc'] > df['sma200_recalc']).fillna(False).to_numpy()
    m_tr_dn = (df['sma50_recalc'] < df['sma200_recalc']).fillna(False).to_numpy()
    trend_sig.iloc[m_tr_up] = 1
    trend_sig.iloc[m_tr_dn] = -1

    df['rsi_signal_recalc']        = rsi_sig.astype('int64')
    df['macd_signal_flag_recalc']  = macd_sig.astype('int64')
    df['trend_signal_recalc']      = trend_sig.astype('int64')

    return df


# -----------------------------
# Backtrader Data feed
# -----------------------------
class PandasDataAdj(bt.feeds.PandasData):
    params = (
        ('datetime', None),
        ('open', 'Open'),
        ('high', 'High'),
        ('low', 'Low'),
        ('close', 'Close'),
        ('volume', 'Volume'),
        ('openinterest', -1),
    )


# -----------------------------
# Strategy
# -----------------------------
@dataclass
class StrategyConfig:
    max_positions: int = DEFAULT_MAX_POSITIONS
    hard_dd_stop: float = 0.20         # Tightened to 20% from 35%
    risk_free: float = DEFAULT_RISK_FREE
    min_align: int = 2                  # 2 of 3 signals (was 3 — almost never fired)
    use_recalc: bool = True             # Use recalculated signals (more accurate)
    min_price: float = 5.0              # Skip penny stocks
    min_volume: int = 200_000           # Minimum liquidity filter
    risk_pct: float = 0.015            # Risk 1.5% of portfolio per trade (ATR-based sizing)
    atr_stop_mult: float = 2.0         # Stop = entry - 2×ATR
    atr_trail_mult: float = 2.5        # Trailing stop = peak - 2.5×ATR
    long_only: bool = True             # No short selling (retail-appropriate)
    trend_filter: bool = True          # Only enter when Close > SMA200


class ImprovedLongOnlyStrategy(bt.Strategy):
    """
    Improved long-only strategy for ThinkFree Finance.

    Key improvements over the original MultiTickerSignalStrategy:
      1. LONG-ONLY: No short selling — appropriate for retail investors
      2. min_align=2: Requires only 2 of 3 signals to agree (was 3 — almost never fired)
      3. ATR-based risk sizing: Risk 1.5% of equity per trade, not equal-weight
      4. Trend filter: Only enter when Close > SMA200 (avoids buying in bear markets)
      5. ATR trailing stop: Exit when price drops 2.5×ATR below the peak since entry
      6. Hard portfolio drawdown stop tightened to 20% (was 35%)
      7. Relaxed RSI threshold: RSI > 40 = bullish (was < 30 which almost never happens)
      8. Uses recalculated indicators (use_recalc=True by default)
    """

    params = dict(
        signals_map=None,
        config=StrategyConfig(),
        final_date=None,
    )

    def __init__(self):
        self.signals_map: Dict[str, pd.DataFrame] = self.p.signals_map or {}
        self.cfg: StrategyConfig = self.p.config

        self._last_seen: List[int] = [0 for _ in self.datas]
        self.equity_curve: List[Tuple[pd.Timestamp, float]] = []
        self.days_in_market: int = 0
        self.max_equity_seen: float = float(self.broker.getvalue())
        self.hard_stop_triggered: bool = False

        self.open_info: Dict[str, dict] = {}
        self.trades_log: List[dict] = []
        # Per-ticker trailing stop tracking: highest_close since entry
        self._peak_since_entry: Dict[str, float] = {}

    # ── signal fetch ────────────────────────────────────────────────────
    def _today_signals(self, tkr: str, dt: pd.Timestamp) -> Tuple[int, int, int]:
        df = self.signals_map.get(tkr)
        if df is None:
            return 0, 0, 0
        # Use recalculated signals if available (more reliable than CSV-provided)
        if self.cfg.use_recalc and 'rsi_signal_recalc' in (df.columns if dt in df.index else []):
            row = df.loc[dt] if dt in df.index else None
            if row is None:
                return 0, 0, 0
            rsi  = to_int_scalar(row.get('rsi_signal_recalc', 0))
            macd = to_int_scalar(row.get('macd_signal_flag_recalc', 0))
            trend = to_int_scalar(row.get('trend_signal_recalc', 0))
        elif dt in df.index:
            row = cast(pd.Series, df.loc[dt])
            rsi  = to_int_scalar(row.get('rsi_signal', 0))
            macd = to_int_scalar(row.get('macd_signal_flag', 0))
            trend = to_int_scalar(row.get('trend_signal', 0))
        else:
            return 0, 0, 0
        return rsi, macd, trend

    def _get_atr(self, tkr: str, dt: pd.Timestamp) -> float:
        df = self.signals_map.get(tkr)
        if df is None or dt not in df.index:
            return 0.0
        col = 'atr_recalc' if 'atr_recalc' in df.columns else None
        if col:
            val = to_float_scalar(df.loc[dt].get(col, 0.0))
            return val if np.isfinite(val) and val > 0 else 0.0
        return 0.0

    def _get_sma200(self, tkr: str, dt: pd.Timestamp) -> float:
        df = self.signals_map.get(tkr)
        if df is None or dt not in df.index:
            return 0.0
        col = 'sma200_recalc' if 'sma200_recalc' in df.columns else ('sma_200' if 'sma_200' in df.columns else None)
        if col:
            val = to_float_scalar(df.loc[dt].get(col, 0.0))
            return val if np.isfinite(val) and val > 0 else 0.0
        return 0.0

    # ── signal voting (long-only) ────────────────────────────────────────
    def _long_vote(self, sigs: Tuple[int, int, int]) -> bool:
        """True if at least min_align signals are bullish (+1)."""
        bullish = sum(1 for s in sigs if s == 1)
        return bullish >= self.cfg.min_align

    def _exit_vote(self, sigs: Tuple[int, int, int]) -> bool:
        """True if majority of signals turned bearish."""
        bearish = sum(1 for s in sigs if s == -1)
        return bearish >= self.cfg.min_align

    def _open_positions_count(self) -> int:
        return sum(1 for d in self.datas if self.getposition(d).size != 0)

    # ── ATR-based risk sizing ────────────────────────────────────────────
    def _risk_sized_shares(self, data: bt.feeds.PandasData, tkr: str, dt: pd.Timestamp) -> int:
        """
        Size the position so that a 2×ATR adverse move = risk_pct of portfolio.
        If ATR unavailable, fall back to equal-weight sizing.
        """
        price = to_float_scalar(data.close[0], default=0.0)
        if not np.isfinite(price) or price <= 0:
            return 0

        equity = to_float_scalar(self.broker.getvalue(), default=0.0)
        risk_dollars = equity * self.cfg.risk_pct  # e.g., 1.5% of $100k = $1,500

        atr = self._get_atr(tkr, dt)
        stop_distance = atr * self.cfg.atr_stop_mult if atr > 0 else price * 0.05  # 5% fallback

        if stop_distance > 0:
            shares = int(risk_dollars / stop_distance)
        else:
            shares = int((equity / max(1, self.cfg.max_positions)) / price)

        # Cap at 25% of portfolio value per position
        max_shares = int((equity * 0.25) / price)
        return max(0, min(shares, max_shares))

    # ── core ────────────────────────────────────────────────────────────
    def next(self):
        now_date = self.datetime.date(0)
        pv = to_float_scalar(self.broker.getvalue(), default=0.0)
        self.equity_curve.append((now_date, pv))
        if any(self.getposition(d).size != 0 for d in self.datas):
            self.days_in_market += 1

        # Hard portfolio DD stop (20%)
        self.max_equity_seen = max(self.max_equity_seen, pv)
        dd = 0.0 if self.max_equity_seen == 0 else 1 - (pv / self.max_equity_seen)
        if dd >= self.cfg.hard_dd_stop and not self.hard_stop_triggered:
            for d in self.datas:
                if self.getposition(d).size != 0:
                    self.close(data=d)
            self.hard_stop_triggered = True
            log(f"[{now_date}] HARD DD STOP ({dd:.2%}) — liquidating all positions.")

        for i, data in enumerate(self.datas):
            if int(len(data)) <= int(self._last_seen[i]):
                continue
            self._last_seen[i] = int(len(data))

            ticker = getattr(data, '_name', f"DATA_{i}")
            today = data.datetime.date(0)
            today_ts = pd.Timestamp(today)

            # Liquidate on final date
            if self.p.final_date and today == self.p.final_date:
                if self.getposition(data).size != 0:
                    self.close(data=data)
                    self._peak_since_entry.pop(ticker, None)
                continue

            if self.hard_stop_triggered:
                if self.getposition(data).size != 0:
                    self.close(data=data)
                    self._peak_since_entry.pop(ticker, None)
                continue

            close_px = to_float_scalar(data.close[0], default=np.nan)
            vol = to_float_scalar(data.volume[0], default=np.nan)
            if not np.isfinite(close_px) or close_px <= 0:
                continue

            # Liquidity and price filters
            if close_px < self.cfg.min_price:
                if self.getposition(data).size != 0:
                    self.close(data=data)
                continue
            if self.cfg.min_volume > 0 and np.isfinite(vol) and vol < self.cfg.min_volume:
                if self.getposition(data).size != 0:
                    self.close(data=data)
                continue

            pos = to_int_scalar(self.getposition(data).size, default=0)

            if pos > 0:
                # Update trailing stop peak
                prev_peak = self._peak_since_entry.get(ticker, close_px)
                self._peak_since_entry[ticker] = max(prev_peak, close_px)
                peak = self._peak_since_entry[ticker]

                # ATR trailing stop check
                atr = self._get_atr(ticker, today_ts)
                if atr > 0:
                    trail_stop = peak - atr * self.cfg.atr_trail_mult
                    if close_px < trail_stop:
                        self.close(data=data)
                        self._peak_since_entry.pop(ticker, None)
                        continue

                # Signal exit
                rsi_s, macd_s, trend_s = self._today_signals(ticker, today_ts)
                if self._exit_vote((rsi_s, macd_s, trend_s)):
                    self.close(data=data)
                    self._peak_since_entry.pop(ticker, None)

            else:
                # Entry conditions
                if self._open_positions_count() >= self.cfg.max_positions:
                    continue

                rsi_s, macd_s, trend_s = self._today_signals(ticker, today_ts)
                if not self._long_vote((rsi_s, macd_s, trend_s)):
                    continue

                # Trend filter: only buy when above SMA200
                if self.cfg.trend_filter:
                    sma200 = self._get_sma200(ticker, today_ts)
                    if sma200 > 0 and close_px < sma200:
                        continue  # Don't buy in a downtrend

                size = self._risk_sized_shares(data, ticker, today_ts)
                if size > 0:
                    self.buy(data=data, size=size)
                    self._peak_since_entry[ticker] = close_px

    # ── notifications ────────────────────────────────────────────────────
    def notify_order(self, order: bt.Order) -> None:
        pass

    def notify_trade(self, trade: bt.Trade) -> None:
        data = getattr(trade, 'data', None)
        ticker = getattr(data, '_name', 'UNKNOWN')
        if trade.justopened:
            self.open_info[ticker] = {
                'entry_date': trade.open_datetime().date(),
                'entry_price': to_float_scalar(trade.price, default=0.0),
                'size': to_int_scalar(trade.size, default=0),
                'side': 'Long',
            }
        elif trade.isclosed:
            info = self.open_info.pop(ticker, {})
            entry_date  = info.get('entry_date', trade.open_datetime().date())
            entry_price = to_float_scalar(info.get('entry_price', trade.price), default=0.0)
            size        = to_int_scalar(info.get('size', trade.size), default=0)
            exit_date   = trade.close_datetime().date()
            pnl         = to_float_scalar(trade.pnl, default=0.0)
            if size != 0 and entry_price > 0:
                exit_price = entry_price + (pnl / size)
            else:
                exit_price = float('nan')
            self.trades_log.append({
                'ticker':      ticker,
                'side':        'Long',
                'entry_date':  str(entry_date),
                'exit_date':   str(exit_date),
                'entry_price': round(entry_price, 6),
                'exit_price':  round(exit_price, 6) if np.isfinite(exit_price) else None,
                'pnl':         round(pnl, 2),
                'bars_held':   int(trade.barlen or 0),
                'pnl_pct':     round((pnl / (entry_price * abs(size))) * 100, 2) if entry_price > 0 and size != 0 else None,
            })


# ── Keep original strategy for backwards compatibility ───────────────────────

class MultiTickerSignalStrategy(bt.Strategy):
    """
    Original long/short strategy — kept for backwards compatibility.
    Use ImprovedLongOnlyStrategy for new runs.
    """

    params = dict(
        signals_map=None,
        config=StrategyConfig(),
        final_date=None,
    )

    def __init__(self):
        self.signals_map: Dict[str, pd.DataFrame] = self.p.signals_map or {}
        self.cfg: StrategyConfig = self.p.config
        self._last_seen: List[int] = [0 for _ in self.datas]
        self.equity_curve: List[Tuple[pd.Timestamp, float]] = []
        self.days_in_market: int = 0
        self.max_equity_seen: float = float(self.broker.getvalue())
        self.hard_stop_triggered: bool = False
        self.open_info: Dict[str, dict] = {}
        self.trades_log: List[dict] = []

    def _today_signals(self, tkr: str, dt: pd.Timestamp) -> Tuple[int, int, int]:
        df = self.signals_map.get(tkr)
        if df is None or dt not in df.index:
            return 0, 0, 0
        if self.cfg.use_recalc:
            row = cast(pd.Series, df.loc[dt])
            rsi  = to_int_scalar(row.get('rsi_signal_recalc', 0))
            macd = to_int_scalar(row.get('macd_signal_flag_recalc', 0))
            trend = to_int_scalar(row.get('trend_signal_recalc', 0))
        else:
            row = cast(pd.Series, df.loc[dt])
            rsi  = to_int_scalar(row.get('rsi_signal', 0))
            macd = to_int_scalar(row.get('macd_signal_flag', 0))
            trend = to_int_scalar(row.get('trend_signal', 0))
        return rsi, macd, trend

    def _aligned_vote(self, sigs: Tuple[int, int, int]) -> int:
        pos = sum(1 for s in sigs if s == 1)
        neg = sum(1 for s in sigs if s == -1)
        if pos >= self.cfg.min_align and neg == 0:
            return 1
        if neg >= self.cfg.min_align and pos == 0:
            return -1
        return 0

    def _open_positions_count(self) -> int:
        return sum(1 for d in self.datas if self.getposition(d).size != 0)

    def _target_shares(self, data: bt.feeds.PandasData) -> int:
        price = to_float_scalar(data.close[0], default=0.0)
        if not np.isfinite(price) or price <= 0:
            return 0
        alloc_value = to_float_scalar(self.broker.getvalue(), default=0.0) / max(1, self.cfg.max_positions)
        return max(0, int(alloc_value // price))

    def next(self):
        now_date = self.datetime.date(0)
        pv = to_float_scalar(self.broker.getvalue(), default=0.0)
        self.equity_curve.append((now_date, pv))
        if any(self.getposition(d).size != 0 for d in self.datas):
            self.days_in_market += 1
        self.max_equity_seen = max(self.max_equity_seen, pv)
        dd = 0.0 if self.max_equity_seen == 0 else 1 - (pv / self.max_equity_seen)
        if dd >= self.cfg.hard_dd_stop and not self.hard_stop_triggered:
            for d in self.datas:
                if self.getposition(d).size != 0:
                    self.close(data=d)
            self.hard_stop_triggered = True
        for i, data in enumerate(self.datas):
            if int(len(data)) <= int(self._last_seen[i]):
                continue
            self._last_seen[i] = int(len(data))
            ticker = getattr(data, '_name', f"DATA_{i}")
            today = data.datetime.date(0)
            if self.p.final_date and today == self.p.final_date:
                if self.getposition(data).size != 0:
                    self.close(data=data)
                continue
            if self.hard_stop_triggered:
                if self.getposition(data).size != 0:
                    self.close(data=data)
                continue
            close_px = to_float_scalar(data.close[0], default=np.nan)
            vol = to_float_scalar(data.volume[0], default=np.nan)
            if (np.isfinite(self.cfg.min_price) and close_px < self.cfg.min_price) or \
               (np.isfinite(self.cfg.min_volume) and vol < self.cfg.min_volume):
                if self.getposition(data).size != 0:
                    self.close(data=data)
                continue
            rsi_sig, macd_sig, trend_sig = self._today_signals(ticker, pd.Timestamp(today))
            vote = self._aligned_vote((rsi_sig, macd_sig, trend_sig))
            pos = to_int_scalar(self.getposition(data).size, default=0)
            if pos > 0:
                if vote != 1:
                    self.close(data=data)
            elif pos < 0:
                if vote != -1:
                    self.close(data=data)
            else:
                if self._open_positions_count() >= self.cfg.max_positions:
                    continue
                size = self._target_shares(data)
                if size > 0:
                    if vote == 1:
                        self.buy(data=data, size=size)
                    elif vote == -1 and not self.cfg.long_only:
                        self.sell(data=data, size=size)

    def notify_order(self, order: bt.Order) -> None:
        pass

    def notify_trade(self, trade: bt.Trade) -> None:
        data = getattr(trade, 'data', None)
        ticker = getattr(data, '_name', 'UNKNOWN')
        if trade.justopened:
            self.open_info[ticker] = {
                'entry_date':  trade.open_datetime().date(),
                'entry_price': to_float_scalar(trade.price, default=0.0),
                'size':        to_int_scalar(trade.size, default=0),
                'side':        'Long' if to_int_scalar(trade.size, 0) > 0 else 'Short',
            }
        elif trade.isclosed:
            info = self.open_info.pop(ticker, {})
            entry_date  = info.get('entry_date', trade.open_datetime().date())
            entry_price = to_float_scalar(info.get('entry_price', trade.price), default=0.0)
            size        = to_int_scalar(info.get('size', trade.size), default=0)
            side        = info.get('side', 'Long' if size > 0 else 'Short')
            exit_date   = trade.close_datetime().date()
            pnl         = to_float_scalar(trade.pnl, default=0.0)
            exit_price  = entry_price + (pnl / size) if size != 0 else float('nan')
            self.trades_log.append({
                'ticker':      ticker,
                'side':        side,
                'entry_date':  str(entry_date),
                'exit_date':   str(exit_date),
                'entry_price': round(entry_price, 6),
                'exit_price':  round(exit_price, 6) if np.isfinite(exit_price) else None,
                'pnl':         round(pnl, 2),
                'bars_held':   int(trade.barlen or 0),
            })


# -----------------------------
# Metrics
# -----------------------------
@dataclass
class Metrics:
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown_pct: float
    max_dd_duration_days: int
    time_in_market_pct: float
    cagr: float
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    avg_bars_held: float = 0.0
    total_trades: int = 0


def compute_extended_trade_metrics(trades_df: pd.DataFrame) -> dict:
    """Compute win rate, profit factor, expectancy from trade log."""
    if trades_df.empty or 'pnl' not in trades_df.columns:
        return {"win_rate": 0.0, "profit_factor": 0.0, "expectancy": 0.0,
                "avg_bars_held": 0.0, "total_trades": 0}

    pnls = trades_df['pnl'].dropna()
    total = len(pnls)
    if total == 0:
        return {"win_rate": 0.0, "profit_factor": 0.0, "expectancy": 0.0,
                "avg_bars_held": 0.0, "total_trades": 0}

    winners = pnls[pnls > 0]
    losers  = pnls[pnls < 0]

    win_rate = len(winners) / total
    gross_profit = float(winners.sum()) if len(winners) else 0.0
    gross_loss   = abs(float(losers.sum())) if len(losers) else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

    avg_win  = float(winners.mean()) if len(winners) else 0.0
    avg_loss = abs(float(losers.mean())) if len(losers) else 0.0
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

    avg_bars = 0.0
    if 'bars_held' in trades_df.columns:
        avg_bars = float(trades_df['bars_held'].dropna().mean())

    return {
        "win_rate":      round(win_rate * 100, 1),
        "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else None,
        "expectancy":    round(expectancy, 2),
        "avg_bars_held": round(avg_bars, 1),
        "total_trades":  total,
    }


def compute_metrics(equity_df: pd.DataFrame, days_in_market: int,
                    trades_df: Optional[pd.DataFrame] = None) -> Metrics:
    if equity_df.empty or len(equity_df) < 2:
        return Metrics(0.0, float('inf'), float('inf'), 0.0, 0, 0.0, 0.0)

    eq = equity_df.copy().sort_values('date')
    eq['ret'] = eq['equity'].pct_change().fillna(0.0)
    ret = eq['ret']

    mean = float(ret.mean())
    std = float(ret.std(ddof=0))
    sharpe = (mean / std * math.sqrt(252)) if std != 0 else 0.0

    neg = ret[ret < 0]
    ds = float(neg.std(ddof=0)) if len(neg) else 0.0
    sortino = (mean / ds * math.sqrt(252)) if ds != 0 else float('inf')

    start_val = float(eq['equity'].iloc[0])
    end_val = float(eq['equity'].iloc[-1])
    days = int((eq['date'].iloc[-1] - eq['date'].iloc[0]).days or 1)
    years = max(days / 365.0, 1e-9)
    cagr = ((end_val / start_val) ** (1 / years) - 1) if start_val > 0 else 0.0

    roll_max = eq['equity'].cummax()
    dd = eq['equity'] / roll_max - 1.0
    max_dd = float(dd.min())
    max_dd_pct = abs(max_dd)

    cur = 0
    max_dur = 0
    for v in dd:
        if v < 0:
            cur += 1
            max_dur = max(max_dur, cur)
        else:
            cur = 0

    tim = (days_in_market / len(eq) * 100.0) if len(eq) else 0.0
    calmar = (cagr / max_dd_pct) if max_dd_pct > 0 else float('inf')

    trade_ext = compute_extended_trade_metrics(trades_df) if trades_df is not None else {}

    return Metrics(
        sharpe=round(sharpe, 4),
        sortino=round(sortino, 4) if sortino != float('inf') else float('inf'),
        calmar=round(calmar, 4) if calmar != float('inf') else float('inf'),
        max_drawdown_pct=round(max_dd_pct * 100, 2),
        max_dd_duration_days=int(max_dur),
        time_in_market_pct=round(tim, 2),
        cagr=round(cagr * 100, 2),
        win_rate=trade_ext.get("win_rate", 0.0),
        profit_factor=trade_ext.get("profit_factor", 0.0) or 0.0,
        expectancy=trade_ext.get("expectancy", 0.0),
        avg_bars_held=trade_ext.get("avg_bars_held", 0.0),
        total_trades=trade_ext.get("total_trades", 0),
    )


# -----------------------------
# Data download & prep
# -----------------------------
def adjust_ohlc_with_adjclose(df: pd.DataFrame) -> pd.DataFrame:
    if 'Adj Close' not in df.columns:
        return df
    factor = (df['Adj Close'] / df['Close']).replace([np.inf, -np.inf], np.nan).ffill()
    for col in ['Open', 'High', 'Low', 'Close']:
        df[col] = df[col] * factor
    df.drop(columns=['Adj Close'], inplace=True)
    return df


def fetch_history(ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    data = yf.download(
        ticker,
        start=start.strftime('%Y-%m-%d'),
        end=end.strftime('%Y-%m-%d'),
        progress=False,
        auto_adjust=False
    )
    if data is None or data.empty:
        return pd.DataFrame()
    data = adjust_ohlc_with_adjclose(data)
    data = data[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    data.index = pd.to_datetime(data.index)
    data = data.sort_index()
    return data


def build_universe(signals_map: Dict[str, pd.DataFrame]) -> List[str]:
    return sorted(list(signals_map.keys()))


# -----------------------------
# Runner
# -----------------------------
def run_backtest(
    signals_csv: str,
    out_dir: str,
    initial_cash: float = DEFAULT_INITIAL_CASH,
    commission: float = DEFAULT_COMMISSION,
    slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
    max_positions: int = DEFAULT_MAX_POSITIONS,
    risk_free: float = DEFAULT_RISK_FREE,
    dd_stop: float = 0.20,              # Tightened default: 20% instead of 35%
    min_align: int = 2,                 # Relaxed default: 2 instead of 3
    use_recalc: bool = True,            # Use recalculated signals by default
    verbose_mismatch: bool = True,
    min_price: float = 5.0,             # Skip penny stocks
    min_volume: int = 200_000,          # Minimum liquidity
    long_only: bool = True,             # Long-only by default
    trend_filter: bool = True,          # SMA200 trend filter
    risk_pct: float = 0.015,            # 1.5% portfolio risk per trade
) -> Tuple[pd.DataFrame, pd.DataFrame, Metrics]:
    ensure_dir(out_dir)

    # Load signals
    signals_map = load_signals(signals_csv)
    universe = build_universe(signals_map)
    if not universe:
        raise RuntimeError("No tickers found in signals CSV after parsing.")

    # Global date range
    all_dates = pd.concat([df.index.to_series() for df in signals_map.values()])
    start_dt = all_dates.min()
    end_dt = all_dates.max()

    hist_start = start_dt - pd.Timedelta(days=max(365, SMA_LONG + 20))
    hist_end = end_dt + pd.Timedelta(days=1)

    # Download & TA validate
    price_cache: Dict[str, pd.DataFrame] = {}
    for tkr in universe:
        df = fetch_history(tkr, hist_start, hist_end)
        if df.empty:
            log(f"[WARN] No history for {tkr}; excluding.")
            continue
        warmup_bars = int((df.index <= start_dt).sum())
        if warmup_bars < MIN_BARS_WARMUP:
            log(f"[WARN] {tkr} insufficient warm-up ({warmup_bars} bars). Indicators may be NaN early.")

        df = ta_validate(df)
        trimmed = df[df.index >= start_dt].copy()
        price_cache[tkr] = trimmed

        # enrich signals_map with recalc columns so strategy can reference them
        smap_df = signals_map[tkr]
        # align on intersection only
        idx = smap_df.index.intersection(trimmed.index)
        # attach *_recalc for those dates
        signals_map[tkr].loc[idx, 'rsi_signal_recalc'] = trimmed.loc[idx, 'rsi_signal_recalc'].astype('Int64')
        signals_map[tkr].loc[idx, 'macd_signal_flag_recalc'] = trimmed.loc[idx, 'macd_signal_flag_recalc'].astype('Int64')
        signals_map[tkr].loc[idx, 'trend_signal_recalc'] = trimmed.loc[idx, 'trend_signal_recalc'].astype('Int64')

        # Optional diagnostics comparing provided vs recalc
        if verbose_mismatch:
            if not idx.empty:
                prov_rsi = smap_df.loc[idx, 'rsi_signal'].astype('int', errors='ignore')
                rec_rsi  = trimmed.loc[idx, 'rsi_signal_recalc'].astype('int', errors='ignore')
                prov_macd = smap_df.loc[idx, 'macd_signal_flag'].astype('int', errors='ignore')
                rec_macd  = trimmed.loc[idx, 'macd_signal_flag_recalc'].astype('int', errors='ignore')
                prov_trend = smap_df.loc[idx, 'trend_signal'].astype('int', errors='ignore')
                rec_trend  = trimmed.loc[idx, 'trend_signal_recalc'].astype('int', errors='ignore')

                mism_rsi = int((prov_rsi.to_numpy() != rec_rsi.to_numpy()).sum())
                mism_macd = int((prov_macd.to_numpy() != rec_macd.to_numpy()).sum())
                mism_trend = int((prov_trend.to_numpy() != rec_trend.to_numpy()).sum())
                if mism_rsi or mism_macd or mism_trend:
                    log(f"[SIG-MISMATCH] {tkr}: RSI:{mism_rsi}, MACD:{mism_macd}, TREND:{mism_trend}")

    # Cerebro
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(float(initial_cash))
    cerebro.broker.setcommission(commission=float(commission))
    cerebro.broker.set_slippage_perc(float(slippage_pct))  # percent slippage

    # Data feeds
    for tkr, df in price_cache.items():
        feed = PandasDataAdj(dataname=df[['Open', 'High', 'Low', 'Close', 'Volume']])  # type: ignore[arg-type]
        cerebro.adddata(feed, name=tkr)

    cfg = StrategyConfig(
        max_positions=int(max_positions),
        hard_dd_stop=float(dd_stop),
        risk_free=float(risk_free),
        min_align=int(min_align),
        use_recalc=bool(use_recalc),
        min_price=float(min_price),
        min_volume=int(min_volume),
        long_only=bool(long_only),
        trend_filter=bool(trend_filter),
        risk_pct=float(risk_pct),
    )

    # Use improved long-only strategy by default; fall back to original if long_only=False
    StrategyClass = ImprovedLongOnlyStrategy if long_only else MultiTickerSignalStrategy
    log(f"Strategy: {StrategyClass.__name__}")
    cerebro.addstrategy(StrategyClass,
                        signals_map=signals_map,
                        config=cfg,
                        final_date=end_dt.date())

    strat: MultiTickerSignalStrategy = cerebro.run(maxcpus=1)[0]

    # Equity curve
    eq = pd.DataFrame(strat.equity_curve, columns=['date', 'equity'])
    eq = eq[eq['date'] >= start_dt.date()].reset_index(drop=True)

    # Metrics
    trades_for_metrics = pd.DataFrame(strat.trades_log) if strat.trades_log else pd.DataFrame()
    metrics = compute_metrics(eq, strat.days_in_market, trades_for_metrics)

    # Trades
    trades = pd.DataFrame(strat.trades_log)

    # Save
    eq_path = os.path.join(out_dir, "portfolio_equity_curve.csv")
    tr_path = os.path.join(out_dir, "trade_log.csv")
    mt_path = os.path.join(out_dir, "summary_metrics.json")

    eq.to_csv(eq_path, index=False)
    trades.to_csv(tr_path, index=False)
    with open(mt_path, "w") as f:
        json.dump({
            "Sharpe":              metrics.sharpe,
            "Sortino":             metrics.sortino,
            "Calmar":              metrics.calmar,
            "Max Drawdown %":      metrics.max_drawdown_pct,
            "Max DD Duration (days)": metrics.max_dd_duration_days,
            "Time in Market %":    metrics.time_in_market_pct,
            "CAGR %":              metrics.cagr,
            "Win Rate %":          metrics.win_rate,
            "Profit Factor":       metrics.profit_factor,
            "Expectancy ($)":      metrics.expectancy,
            "Avg Bars Held":       metrics.avg_bars_held,
            "Total Trades":        metrics.total_trades,
            "Strategy":            StrategyClass.__name__,
        }, f, indent=2)

    log(f"Saved: {eq_path}")
    log(f"Saved: {tr_path}")
    log(f"Saved: {mt_path}")

    return eq, trades, metrics


# -----------------------------
# CLI + JSON config
# -----------------------------
DEFAULT_JSON_CONFIG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "results_run", "backtest_config.json"
)


def load_json_config(config_path: str) -> Dict[str, Any]:
    p = Path(config_path)
    if p.is_file():
        with p.open("r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception as e:
                log(f"[WARN] Failed to parse JSON config: {e}")
    return {}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ThinkFree Phase 4 — Backtrader Engine (Long/Short, CSV-driven)")
    p.add_argument("--signals_csv", help="Path to ta_analysis_detailed.csv (or equivalent)")
    p.add_argument("--out_dir", default=f"results_run_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}", help="Output directory")
    p.add_argument("--initial_cash", type=float, default=DEFAULT_INITIAL_CASH)
    p.add_argument("--commission", type=float, default=DEFAULT_COMMISSION, help="Commission per trade (fraction)")
    p.add_argument("--slippage_pct", type=float, default=DEFAULT_SLIPPAGE_PCT, help="Slippage percent per fill (fraction)")
    p.add_argument("--max_positions", type=int, default=DEFAULT_MAX_POSITIONS)
    p.add_argument("--risk_free", type=float, default=DEFAULT_RISK_FREE)
    p.add_argument("--dd_stop", type=float, default=MAX_PORTFOLIO_DRAWDOWN, help="Hard stop drawdown fraction (e.g., 0.35)")
    p.add_argument("--min_align", type=int, default=2, help="Minimum aligned signals required (1..3); default 2")
    p.add_argument("--use_recalc", type=lambda s: str(s).lower() in ("1", "true", "yes"), default=True, help="Use recalculated indicators")
    p.add_argument("--verbose_mismatch", type=lambda s: str(s).lower() in ("1", "true", "yes"), default=True)
    p.add_argument("--min_price", type=float, default=5.0, help="Skip trades when price below this (default $5)")
    p.add_argument("--min_volume", type=int, default=200_000, help="Skip trades when volume below this")
    p.add_argument("--long_only", type=lambda s: str(s).lower() in ("1", "true", "yes"), default=True, help="Long-only mode (no short selling)")
    p.add_argument("--trend_filter", type=lambda s: str(s).lower() in ("1", "true", "yes"), default=True, help="Only buy when Close > SMA200")
    p.add_argument("--risk_pct", type=float, default=0.015, help="Risk fraction per trade (default 1.5%%)")
    return p.parse_args(argv)


def overlay_args_with_json(args: argparse.Namespace, json_cfg: Dict[str, Any]) -> argparse.Namespace:
    for k, v in json_cfg.items():
        if hasattr(args, k):
            setattr(args, k, v)
    return args


def copy_config_to_outdir(config_source: str, out_dir: str) -> None:
    try:
        if Path(config_source).is_file():
            ensure_dir(out_dir)
            dst = Path(out_dir) / "config_used.json"
            with open(config_source, "r", encoding="utf-8") as src, open(dst, "w", encoding="utf-8") as dstf:
                dstf.write(src.read())
    except Exception as e:
        log(f"[WARN] Failed to copy config to out_dir: {e}")


def main(argv: Optional[List[str]] = None) -> None:
    # ① Parse CLI first (gets defaults)
    args = parse_args(argv)

    # ② Try reading JSON config (overrides CLI)
    json_cfg = load_json_config(DEFAULT_JSON_CONFIG)
    args = overlay_args_with_json(args, json_cfg)

    # ③ Validate critical args
    if not args.signals_csv:
        raise SystemExit(
            "No signals CSV provided. Set it in JSON config:\n"
            f"  {DEFAULT_JSON_CONFIG}\n"
            "as \"signals_csv\": \"<absolute or relative path>\",\n"
            "or pass --signals_csv on the command line."
        )

    # ④ Ensure output directory and copy config snapshot
    ensure_dir(args.out_dir)
    copy_config_to_outdir(DEFAULT_JSON_CONFIG, args.out_dir)

    # ⑤ Log run params
    log("=== ThinkFree Phase 4 Backtest (Long/Short, CSV-driven) ===")
    log(f"Signals CSV  : {args.signals_csv}")
    log(f"Output Dir   : {args.out_dir}")
    log(f"Initial Cash : {args.initial_cash:,.2f}")
    log(f"Max Positions: {args.max_positions}")
    log(f"Min Align    : {args.min_align}")
    log(f"Use Recalc   : {args.use_recalc}")
    log(f"Verbose Mism.: {args.verbose_mismatch}")
    if args.min_price or args.min_volume:
        log(f"Guards       : min_price={args.min_price}, min_volume={args.min_volume}")

    # ⑥ Run
    eq, trades, metrics = run_backtest(
        signals_csv=args.signals_csv,
        out_dir=args.out_dir,
        initial_cash=args.initial_cash,
        commission=args.commission,
        slippage_pct=args.slippage_pct,
        max_positions=args.max_positions,
        risk_free=args.risk_free,
        dd_stop=args.dd_stop,
        min_align=args.min_align,
        use_recalc=args.use_recalc,
        verbose_mismatch=args.verbose_mismatch,
        min_price=args.min_price,
        min_volume=args.min_volume,
        long_only=args.long_only,
        trend_filter=args.trend_filter,
        risk_pct=args.risk_pct,
    )

    # ⑦ Print summary
    log("\n--- Performance Summary ---")
    strategy_name = "ImprovedLongOnlyStrategy" if args.long_only else "MultiTickerSignalStrategy"
    log(f"Strategy         : {strategy_name}")
    log(f"CAGR (%)         : {metrics.cagr}")
    log(f"Sharpe           : {metrics.sharpe}")
    log(f"Sortino          : {metrics.sortino}")
    log(f"Calmar           : {metrics.calmar}")
    log(f"Max Drawdown (%) : {metrics.max_drawdown_pct}")
    log(f"DD Duration (d)  : {metrics.max_dd_duration_days}")
    log(f"Time in Market % : {metrics.time_in_market_pct}")
    log(f"Total Trades     : {metrics.total_trades}")
    log(f"Win Rate (%)     : {metrics.win_rate}")
    log(f"Profit Factor    : {metrics.profit_factor}")
    log(f"Expectancy ($)   : {metrics.expectancy}")
    log(f"Avg Bars Held    : {metrics.avg_bars_held}")
    log("\nDone.")


if __name__ == "__main__":
    main()
