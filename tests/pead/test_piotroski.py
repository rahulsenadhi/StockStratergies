import math

import pandas as pd
import pytest

from core.piotroski import piotroski_score, PiotroskiInputs


def _good_inputs() -> PiotroskiInputs:
    """All 9 conditions pass → score 9."""
    return PiotroskiInputs(
        net_income=100, net_income_prev=80,
        total_assets=1000, total_assets_prev=1000,
        ocf=120, ocf_prev=80,
        long_term_debt=200, long_term_debt_prev=250,
        current_assets=500, current_liab=200,
        current_assets_prev=400, current_liab_prev=200,
        shares_outstanding=100, shares_outstanding_prev=100,
        gross_profit=400, revenue=1000,
        gross_profit_prev=300, revenue_prev=950,
    )


def test_piotroski_all_pass_returns_9():
    score = piotroski_score(_good_inputs())
    assert score == 9


def test_piotroski_all_fail_returns_0():
    inp = PiotroskiInputs(
        net_income=-100, net_income_prev=80,
        total_assets=1000, total_assets_prev=900,
        ocf=-120, ocf_prev=80,
        long_term_debt=300, long_term_debt_prev=200,
        current_assets=300, current_liab=400,
        current_assets_prev=400, current_liab_prev=200,
        shares_outstanding=120, shares_outstanding_prev=100,
        gross_profit=200, revenue=1000,
        gross_profit_prev=300, revenue_prev=900,
    )
    assert piotroski_score(inp) == 0


def test_piotroski_roa_positive_alone():
    inp = _good_inputs()
    inp.net_income = -1
    assert piotroski_score(inp) == 7  # Both ROA and DROA fail


def test_piotroski_ocf_gt_ni_accrual():
    inp = _good_inputs()
    inp.ocf = 50  # less than net_income=100 -> accrual condition fails
    assert piotroski_score(inp) == 8


def test_piotroski_shares_issued_fails():
    inp = _good_inputs()
    inp.shares_outstanding = 110  # issued shares -> fails
    assert piotroski_score(inp) == 8


def test_piotroski_returns_nan_on_missing_input():
    inp = _good_inputs()
    inp.total_assets_prev = math.nan
    score = piotroski_score(inp)
    assert math.isnan(score)
