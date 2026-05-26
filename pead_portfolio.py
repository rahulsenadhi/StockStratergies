"""Equal-weight portfolio bookkeeping for the PEAD backtest.

YAGNI: no transaction costs / slippage in v1. Spec calls them out as deferrable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd


@dataclass
class Position:
    ticker: str
    entry_date: date
    entry_px: float
    shares: int
    exit_due: date
    sue: float
    period_type: str


@dataclass
class Portfolio:
    cash: float
    open: dict[str, Position] = field(default_factory=dict)
    trades: list[dict] = field(default_factory=list)
    equity_curve: list[tuple[date, float]] = field(default_factory=list)

    def buy(self, ticker: str, entry_date: date, entry_px: float, shares: int,
            exit_due: date, sue: float, period_type: str) -> None:
        cost = shares * entry_px
        if cost > self.cash + 1e-6:
            return
        self.cash -= cost
        self.open[ticker] = Position(
            ticker=ticker, entry_date=entry_date, entry_px=entry_px,
            shares=shares, exit_due=exit_due, sue=sue, period_type=period_type,
        )

    def close(self, ticker: str, exit_date: date, exit_px: float, reason: str) -> dict:
        pos = self.open.pop(ticker)
        proceeds = pos.shares * exit_px
        self.cash += proceeds
        ret_pct = (exit_px - pos.entry_px) / pos.entry_px * 100.0
        trade = {
            "ticker": ticker,
            "entry_date": pos.entry_date,
            "entry_price": pos.entry_px,
            "shares": pos.shares,
            "exit_date": exit_date,
            "exit_price": exit_px,
            "return_pct": ret_pct,
            "hold_days": (exit_date - pos.entry_date).days,
            "exit_reason": reason,
            "period_type": pos.period_type,
            "sue": pos.sue,
        }
        self.trades.append(trade)
        return trade


def lookup_next_result(events: pd.DataFrame, ticker: str, after: date) -> date | None:
    rows = events[(events["ticker"] == ticker) & (events["result_date"] > after)]
    if rows.empty:
        return None
    return rows["result_date"].min()
