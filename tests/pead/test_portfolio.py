from datetime import date

import pandas as pd
import pytest

from pead_portfolio import Position, Portfolio, lookup_next_result


def test_portfolio_buy_sell_pnl():
    p = Portfolio(cash=1_000_000)
    p.buy("INFY.NS", entry_date=date(2026, 4, 21), entry_px=1500.0,
          shares=100, exit_due=date(2026, 7, 14), sue=2.5, period_type="Q")
    assert len(p.open) == 1
    assert p.cash == 1_000_000 - 100 * 1500.0
    trade = p.close("INFY.NS", exit_date=date(2026, 7, 14), exit_px=1650.0,
                    reason="60D")
    assert trade["return_pct"] == pytest.approx(10.0, rel=1e-3)
    assert trade["exit_reason"] == "60D"
    assert "INFY.NS" not in p.open


def test_lookup_next_result_returns_first_after():
    events = pd.DataFrame([
        {"ticker": "INFY.NS", "result_date": date(2026, 1, 20), "period_type": "Q"},
        {"ticker": "INFY.NS", "result_date": date(2026, 4, 20), "period_type": "Q"},
        {"ticker": "INFY.NS", "result_date": date(2026, 7, 20), "period_type": "Q"},
    ])
    nxt = lookup_next_result(events, "INFY.NS", after=date(2026, 4, 25))
    assert nxt == date(2026, 7, 20)


def test_lookup_next_result_none_if_no_future():
    events = pd.DataFrame([
        {"ticker": "INFY.NS", "result_date": date(2026, 1, 20), "period_type": "Q"},
    ])
    nxt = lookup_next_result(events, "INFY.NS", after=date(2026, 6, 1))
    assert nxt is None
