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
