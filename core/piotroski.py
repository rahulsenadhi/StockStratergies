"""Piotroski F-Score — 9 binary components, computed on annual financials."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class PiotroskiInputs:
    net_income: float
    net_income_prev: float
    total_assets: float
    total_assets_prev: float
    ocf: float                         # operating cash flow
    ocf_prev: float
    long_term_debt: float
    long_term_debt_prev: float
    current_assets: float
    current_liab: float
    current_assets_prev: float
    current_liab_prev: float
    shares_outstanding: float
    shares_outstanding_prev: float
    gross_profit: float
    revenue: float
    gross_profit_prev: float
    revenue_prev: float


def _has_nan(inp: PiotroskiInputs) -> bool:
    for v in inp.__dict__.values():
        if v is None:
            return True
        try:
            if math.isnan(float(v)):
                return True
        except (TypeError, ValueError):
            return True
    return False


def piotroski_score(inp: PiotroskiInputs) -> float:
    """Return integer score 0..9. Returns nan if any input is nan/missing."""
    if _has_nan(inp):
        return math.nan
    if (inp.total_assets == 0 or inp.total_assets_prev == 0
            or inp.current_liab == 0 or inp.current_liab_prev == 0
            or inp.revenue == 0 or inp.revenue_prev == 0):
        return math.nan

    roa = inp.net_income / inp.total_assets
    roa_prev = inp.net_income_prev / inp.total_assets_prev
    lev = inp.long_term_debt / inp.total_assets
    lev_prev = inp.long_term_debt_prev / inp.total_assets_prev
    cr = inp.current_assets / inp.current_liab
    cr_prev = inp.current_assets_prev / inp.current_liab_prev
    gm = inp.gross_profit / inp.revenue
    gm_prev = inp.gross_profit_prev / inp.revenue_prev
    at = inp.revenue / inp.total_assets
    at_prev = inp.revenue_prev / inp.total_assets_prev

    score = 0
    score += int(roa > 0)                                 # 1. ROA positive
    score += int(inp.ocf > 0)                             # 2. OCF positive
    score += int(roa > roa_prev)                          # 3. ΔROA positive
    score += int(inp.ocf > inp.net_income)                # 4. OCF > NI (accrual)
    score += int(lev < lev_prev)                          # 5. Δ leverage negative
    score += int(cr > cr_prev)                            # 6. Δ current ratio positive
    score += int(inp.shares_outstanding <= inp.shares_outstanding_prev)  # 7. No new shares
    score += int(gm > gm_prev)                            # 8. Δ gross margin positive
    score += int(at > at_prev)                            # 9. Δ asset turnover positive
    return float(score)
