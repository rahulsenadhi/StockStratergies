"""Assembles a single PEAD event row from primitives.

Single function `build_event(ticker, result_date, period_type, eps_actual)`
returns a dict matching the spec data model. Decile + qualifies flags are
filled in later by the cohort step.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

from core.fundamentals import (
    get_annual_eps_history,
    get_piotroski_inputs,
    get_price_and_book_value,
    get_quarterly_eps_history,
)
from core.piotroski import piotroski_score
from core.sue import quarterly_sue, annual_sue


def build_event(
    ticker: str,
    result_date: date,
    period_type: str,
    eps_actual: float,
) -> dict[str, Any]:
    assert period_type in ("Q", "A")
    if period_type == "Q":
        hist = get_quarterly_eps_history(ticker, as_of=result_date, n=4)
        sue = quarterly_sue(eps_actual, hist) if len(hist) == 4 else math.nan
    else:
        hist = get_annual_eps_history(ticker, as_of=result_date, n=4)
        sue = annual_sue(eps_actual, hist) if len(hist) == 4 else math.nan

    pf_info = get_price_and_book_value(ticker, as_of=result_date)
    pf_inputs = get_piotroski_inputs(ticker, as_of=result_date)
    pio = piotroski_score(pf_inputs) if pf_inputs is not None else math.nan

    expected = float(sum(hist) / len(hist)) if len(hist) == 4 else math.nan

    return {
        "ticker": ticker,
        "sector": pf_info["sector"],
        "result_date": result_date,
        "period_type": period_type,
        "eps_actual": float(eps_actual),
        "eps_history": hist,
        "eps_expected": expected,
        "sue": sue,
        "piotroski": pio,
        "pb": pf_info["pb"],
        "price_at_result": pf_info["price"],
        "book_value": pf_info["book_value"],
        # Filled later:
        "pb_sector_median": math.nan,
        "sue_decile": math.nan,
        "qualifies_long": False,
        "qualifies_short": False,
    }
