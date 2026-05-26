"""Look-ahead bias audit step.

Spec §8 / §11 final step: assert entry_date > result_date for every trade.
Raises LookaheadViolation on any failure.
"""
from __future__ import annotations

import pandas as pd


class LookaheadViolation(Exception):
    pass


def audit_trades(trades: pd.DataFrame) -> None:
    if trades.empty:
        return
    if "entry_date" not in trades.columns or "result_date" not in trades.columns:
        return
    bad = trades[trades["entry_date"] <= trades["result_date"]]
    if not bad.empty:
        first = bad.iloc[0]
        raise LookaheadViolation(
            f"LOOKAHEAD_VIOLATION: {first['ticker']} entry_date={first['entry_date']} "
            f"<= result_date={first['result_date']}"
        )
