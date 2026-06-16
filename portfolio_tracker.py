#!/usr/bin/env python3
"""
ThinkFree Finance — Phase 10: Portfolio Tracker
Mock trading engine that simulates position tracking based on signal outputs.
Tracks entry/exit, P&L, exposure, and generates a portfolio snapshot.

NOT a live brokerage connection. Educational simulation only.
Output: portfolio_snapshot.json
"""

from __future__ import annotations

import json
from datetime import datetime, date
from pathlib import Path
from typing import Any

BASE_DIR      = Path(__file__).parent
OUTPUT_PATH   = BASE_DIR / "portfolio_snapshot.json"
PORTFOLIO_LOG = BASE_DIR / "portfolio_log.json"

STARTING_CASH = 100_000.0
MAX_POSITIONS = 10
RISK_PCT      = 0.02      # 2% of portfolio per trade
MIN_SCORE     = 6.5       # Minimum opportunity score to open a position
STOP_LOSS_PCT = 0.08      # 8% stop loss
TAKE_PROFIT   = 0.15      # 15% take profit target


def load_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def load_existing_portfolio() -> dict:
    snapshot = load_json(OUTPUT_PATH, None)
    if snapshot:
        return snapshot
    return {
        "cash": STARTING_CASH,
        "positions": {},
        "closed_trades": [],
        "inception_date": date.today().isoformat(),
    }


def fetch_current_price(ticker: str, quantlib_metrics: list[dict]) -> float | None:
    """Get cached price from QuantLib metrics (avoids extra yfinance calls)."""
    for m in quantlib_metrics:
        if m.get("ticker", "").upper() == ticker.upper():
            p = m.get("current_price", 0)
            return float(p) if p and p > 0 else None
    return None


def compute_position_size(portfolio_value: float, price: float) -> int:
    """Risk-based position sizing: risk 2% of portfolio on the trade."""
    if price <= 0:
        return 0
    dollar_risk     = portfolio_value * RISK_PCT
    stop_loss_price = price * (1 - STOP_LOSS_PCT)
    risk_per_share  = price - stop_loss_price
    if risk_per_share <= 0:
        return 0
    shares = int(dollar_risk / risk_per_share)
    # Also cap by max 10% of portfolio per position
    max_by_value = int((portfolio_value * 0.10) / price)
    return min(shares, max_by_value)


def open_position(portfolio: dict, ticker: str, price: float, opportunity_score: float, signal_reasoning: str) -> bool:
    """Open a new long position."""
    if ticker in portfolio["positions"]:
        return False  # Already have a position
    if len(portfolio["positions"]) >= MAX_POSITIONS:
        return False  # Portfolio full

    portfolio_value = portfolio["cash"] + sum(
        pos["shares"] * pos.get("last_price", pos["entry_price"])
        for pos in portfolio["positions"].values()
    )
    shares = compute_position_size(portfolio_value, price)
    if shares <= 0:
        return False

    cost = shares * price
    if cost > portfolio["cash"]:
        shares = int(portfolio["cash"] * 0.10 / price)
        cost = shares * price

    if shares <= 0:
        return False

    portfolio["cash"] -= cost
    portfolio["positions"][ticker] = {
        "ticker":            ticker,
        "shares":            shares,
        "entry_price":       round(price, 2),
        "last_price":        round(price, 2),
        "entry_date":        date.today().isoformat(),
        "cost_basis":        round(cost, 2),
        "opportunity_score": opportunity_score,
        "stop_loss":         round(price * (1 - STOP_LOSS_PCT), 2),
        "take_profit_target": round(price * (1 + TAKE_PROFIT), 2),
        "unrealized_pnl":    0.0,
        "unrealized_pnl_pct": 0.0,
        "signal_reasoning":  signal_reasoning[:200],
        "status":            "OPEN",
    }
    return True


def update_position(pos: dict, current_price: float) -> dict:
    """Update position with current price and compute unrealized P&L."""
    pos["last_price"]        = round(current_price, 2)
    pos["unrealized_pnl"]    = round((current_price - pos["entry_price"]) * pos["shares"], 2)
    pos["unrealized_pnl_pct"] = round(
        (current_price - pos["entry_price"]) / pos["entry_price"] * 100, 2
    )

    # Check stop loss and take profit
    if current_price <= pos["stop_loss"]:
        pos["exit_signal"] = "STOP_LOSS"
    elif current_price >= pos["take_profit_target"]:
        pos["exit_signal"] = "TAKE_PROFIT"
    else:
        pos["exit_signal"] = None

    return pos


def close_position(portfolio: dict, ticker: str, current_price: float, reason: str) -> dict | None:
    """Close an open position and log the trade."""
    if ticker not in portfolio["positions"]:
        return None

    pos    = portfolio["positions"].pop(ticker)
    shares = pos["shares"]
    entry  = pos["entry_price"]
    proceeds = shares * current_price
    pnl      = proceeds - pos["cost_basis"]
    pnl_pct  = (current_price - entry) / entry * 100

    portfolio["cash"] += proceeds

    closed = {
        **pos,
        "exit_price":   round(current_price, 2),
        "exit_date":    date.today().isoformat(),
        "exit_reason":  reason,
        "realized_pnl": round(pnl, 2),
        "realized_pnl_pct": round(pnl_pct, 2),
        "status":       "CLOSED",
    }
    portfolio["closed_trades"].append(closed)
    return closed


def compute_portfolio_metrics(portfolio: dict) -> dict:
    """Compute aggregate portfolio performance metrics."""
    positions = list(portfolio["positions"].values())
    closed    = portfolio["closed_trades"]
    cash      = portfolio["cash"]

    # Portfolio value
    open_value = sum(p["shares"] * p["last_price"] for p in positions)
    total_value = cash + open_value

    # Returns
    total_return = total_value - STARTING_CASH
    total_return_pct = (total_return / STARTING_CASH) * 100

    # Win/loss on closed trades
    wins   = [t for t in closed if t.get("realized_pnl", 0) > 0]
    losses = [t for t in closed if t.get("realized_pnl", 0) <= 0]
    win_rate = (len(wins) / len(closed) * 100) if closed else 0.0

    gross_profit = sum(t["realized_pnl"] for t in wins) if wins else 0
    gross_loss   = abs(sum(t["realized_pnl"] for t in losses)) if losses else 0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    # Exposure
    exposure_pct = (open_value / total_value * 100) if total_value > 0 else 0

    return {
        "total_portfolio_value": round(total_value, 2),
        "cash":                  round(cash, 2),
        "open_positions_value":  round(open_value, 2),
        "exposure_pct":          round(exposure_pct, 1),
        "total_return":          round(total_return, 2),
        "total_return_pct":      round(total_return_pct, 2),
        "open_positions_count":  len(positions),
        "closed_trades_count":   len(closed),
        "win_rate_pct":          round(win_rate, 1),
        "profit_factor":         round(profit_factor, 2) if profit_factor != float("inf") else "∞",
        "gross_profit":          round(gross_profit, 2),
        "gross_loss":            round(gross_loss, 2),
    }


def run_portfolio_tracker() -> dict:
    print("=== ThinkFree — Phase 10: Portfolio Tracker ===")

    # Load all inputs
    signals     = load_json(BASE_DIR / "Module_2_Technical_Analysis" / "signal_output_phase3.json", [])
    opportunity = load_json(BASE_DIR / "opportunity_scores.json", {})
    ql_metrics  = load_json(BASE_DIR / "quantlib_metrics.json", {})
    profile     = load_json(BASE_DIR / "user_profile.json", {})

    ql_ticker_metrics = ql_metrics.get("ticker_metrics", []) if ql_metrics else []
    ticker_opps = opportunity.get("ticker_opportunities", []) if opportunity else []

    # Build lookup: ticker → opportunity score
    opp_lookup: dict[str, float] = {
        t["ticker"].upper(): t.get("opportunity_score", 5.0)
        for t in ticker_opps
        if isinstance(t, dict) and t.get("ticker")
    }

    # Build lookup: ticker → signal reasoning
    sig_lookup: dict[str, dict] = {
        s["ticker"].upper(): s
        for s in signals
        if isinstance(s, dict) and s.get("ticker")
    }

    portfolio = load_existing_portfolio()

    # ── Update existing open positions with current prices ──────────────────
    tickers_to_close = []
    for ticker, pos in portfolio["positions"].items():
        price = fetch_current_price(ticker, ql_ticker_metrics)
        if price:
            update_position(pos, price)
            if pos.get("exit_signal"):
                tickers_to_close.append((ticker, price, pos["exit_signal"]))

    for ticker, price, reason in tickers_to_close:
        result = close_position(portfolio, ticker, price, reason)
        if result:
            pnl = result["realized_pnl"]
            print(f"  Closed {ticker} ({reason}): P&L ${pnl:+,.2f}")

    # ── Open new positions from high-scoring buy signals ────────────────────
    buy_signals = sorted(
        [s for s in signals if isinstance(s, dict) and s.get("final_signal") == "BUY"],
        key=lambda s: opp_lookup.get(s.get("ticker", "").upper(), 5.0),
        reverse=True,
    )

    risk_tolerance = profile.get("risk_tolerance", "moderate")
    min_score = MIN_SCORE
    if risk_tolerance == "low":
        min_score = 7.5    # conservative — only very strong signals
    elif risk_tolerance == "high":
        min_score = 5.5    # aggressive — more opportunities

    opened = 0
    for sig in buy_signals:
        ticker = sig.get("ticker", "").upper()
        opp_score = opp_lookup.get(ticker, 5.0)

        if opp_score < min_score:
            continue

        price = fetch_current_price(ticker, ql_ticker_metrics)
        if not price or price <= 0:
            continue

        reasoning = sig.get("reasoning", "")
        success = open_position(portfolio, ticker, price, opp_score, reasoning)
        if success:
            opened += 1
            print(f"  Opened {ticker} @ ${price:.2f}  score={opp_score}/10")

    # ── Compute metrics ──────────────────────────────────────────────────────
    metrics = compute_portfolio_metrics(portfolio)

    # ── Assemble snapshot ────────────────────────────────────────────────────
    snapshot = {
        **portfolio,
        "snapshot_timestamp": datetime.utcnow().isoformat() + "Z",
        "metrics": metrics,
        "settings": {
            "starting_cash":   STARTING_CASH,
            "max_positions":   MAX_POSITIONS,
            "risk_pct":        RISK_PCT,
            "stop_loss_pct":   STOP_LOSS_PCT,
            "take_profit_pct": TAKE_PROFIT,
            "min_opp_score":   min_score,
        },
        "user_risk_tolerance": risk_tolerance,
        "disclaimer": (
            "This is a simulated paper trading portfolio for educational purposes only. "
            "No real money is at risk. ThinkFree does not execute live trades or manage real funds. "
            "Past simulated performance does not predict future results."
        ),
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, default=str)

    print(f"\nPortfolio snapshot saved to {OUTPUT_PATH}")
    print(f"  Total value:    ${metrics['total_portfolio_value']:,.2f}")
    print(f"  Return:         {metrics['total_return_pct']:+.2f}%")
    print(f"  Open positions: {metrics['open_positions_count']}")
    print(f"  Cash:           ${metrics['cash']:,.2f}")
    print(f"  Positions opened this run: {opened}")

    return snapshot


def reset_portfolio():
    """Reset portfolio to starting state (for testing)."""
    fresh = {
        "cash": STARTING_CASH,
        "positions": {},
        "closed_trades": [],
        "inception_date": date.today().isoformat(),
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(fresh, f, indent=2)
    print(f"Portfolio reset. Starting cash: ${STARTING_CASH:,.0f}")


if __name__ == "__main__":
    import sys
    if "--reset" in sys.argv:
        reset_portfolio()
    else:
        run_portfolio_tracker()
