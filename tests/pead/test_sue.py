import math

import pytest

from core.sue import quarterly_sue


def test_quarterly_sue_textbook():
    # actual=12, prior=[10,11,9,10] -> mean=10, std=0.8165 (ddof=1)
    sue = quarterly_sue(actual=12.0, prior=[10.0, 11.0, 9.0, 10.0])
    assert math.isclose(sue, (12 - 10) / 0.8164965809277261, rel_tol=1e-6)


def test_quarterly_sue_negative_actual():
    sue = quarterly_sue(actual=-2.0, prior=[5.0, 6.0, 4.0, 5.0])
    assert sue < 0


def test_quarterly_sue_zero_std_returns_nan():
    sue = quarterly_sue(actual=15.0, prior=[10.0, 10.0, 10.0, 10.0])
    assert math.isnan(sue)


def test_quarterly_sue_fewer_than_4_returns_nan():
    sue = quarterly_sue(actual=12.0, prior=[10.0, 11.0, 9.0])
    assert math.isnan(sue)


def test_quarterly_sue_nan_in_prior_returns_nan():
    sue = quarterly_sue(actual=12.0, prior=[10.0, float("nan"), 9.0, 10.0])
    assert math.isnan(sue)


def test_quarterly_sue_nan_actual_returns_nan():
    sue = quarterly_sue(actual=float("nan"), prior=[10.0, 11.0, 9.0, 10.0])
    assert math.isnan(sue)


def test_annual_sue_same_as_quarterly():
    from core.sue import annual_sue
    a = annual_sue(20.0, [15.0, 16.0, 14.0, 15.0])
    q = quarterly_sue(20.0, [15.0, 16.0, 14.0, 15.0])
    assert a == q


def test_assign_deciles_basic():
    from core.sue import assign_deciles
    # 30 values, 1..30; decile 10 should be top 3 values.
    sues = list(range(1, 31))
    deciles = assign_deciles(sues)
    assert deciles[29] == 10
    assert deciles[28] == 10
    assert deciles[27] == 10
    assert deciles[0] == 1


def test_assign_deciles_with_nan():
    from core.sue import assign_deciles
    sues = [float("nan"), 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    deciles = assign_deciles(sues)
    assert math.isnan(deciles[0])  # nan stays nan
    assert deciles[10] == 10        # max → top decile


def test_assign_deciles_fewer_than_10_unique():
    from core.sue import assign_deciles
    # Only 3 unique values — qcut may collapse; expect ranks 1..3 mapped sensibly.
    sues = [1.0, 1.0, 2.0, 2.0, 3.0, 3.0]
    deciles = assign_deciles(sues)
    # Lowest values get decile 1; highest get max decile present.
    assert deciles[0] <= deciles[-1]
