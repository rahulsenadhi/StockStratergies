import math
from datetime import date
from unittest.mock import patch

from pead_event_builder import build_event


def _stub_fundamentals(ticker, as_of):
    return {"sector": "IT", "price": 1500.0, "book_value": 300.0, "pb": 5.0}


def _stub_qhist(ticker, as_of, n=4):
    return [22.0, 21.0, 23.0, 22.5]  # mean ~22.125, std ~0.78


def _stub_ahist(ticker, as_of, n=4):
    return [85.0, 80.0, 90.0, 88.0]


def _stub_piotroski_inputs(ticker, as_of):
    return None  # downstream handles None as nan score


@patch("pead_event_builder.get_price_and_book_value", _stub_fundamentals)
@patch("pead_event_builder.get_quarterly_eps_history", _stub_qhist)
@patch("pead_event_builder.get_annual_eps_history", _stub_ahist)
@patch("pead_event_builder.get_piotroski_inputs", _stub_piotroski_inputs)
def test_build_event_quarterly():
    ev = build_event(
        ticker="INFY.NS",
        result_date=date(2026, 4, 20),
        period_type="Q",
        eps_actual=25.0,
    )
    assert ev["ticker"] == "INFY.NS"
    assert ev["period_type"] == "Q"
    assert ev["result_date"] == date(2026, 4, 20)
    assert ev["sector"] == "IT"
    assert ev["eps_actual"] == 25.0
    assert ev["eps_history"] == [22.0, 21.0, 23.0, 22.5]
    assert math.isclose(ev["eps_expected"], 22.125)
    assert ev["sue"] > 0
    assert math.isnan(ev["piotroski"])
    assert ev["pb"] == 5.0


@patch("pead_event_builder.get_price_and_book_value", _stub_fundamentals)
@patch("pead_event_builder.get_quarterly_eps_history", _stub_qhist)
@patch("pead_event_builder.get_annual_eps_history", _stub_ahist)
@patch("pead_event_builder.get_piotroski_inputs", _stub_piotroski_inputs)
def test_build_event_annual():
    ev = build_event(
        ticker="INFY.NS",
        result_date=date(2026, 5, 10),
        period_type="A",
        eps_actual=95.0,
    )
    assert ev["period_type"] == "A"
    assert ev["eps_history"] == [85.0, 80.0, 90.0, 88.0]
    assert ev["sue"] > 0
