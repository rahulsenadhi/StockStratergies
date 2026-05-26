from datetime import date

import pandas as pd
import pytest

from pead_lookahead_audit import audit_trades, LookaheadViolation


def test_audit_trades_passes_when_entry_after_result():
    trades = pd.DataFrame([
        {"ticker": "INFY.NS", "entry_date": date(2026, 4, 21),
         "result_date": date(2026, 4, 20)},
    ])
    audit_trades(trades)  # no exception


def test_audit_trades_raises_on_same_day_entry():
    trades = pd.DataFrame([
        {"ticker": "INFY.NS", "entry_date": date(2026, 4, 20),
         "result_date": date(2026, 4, 20)},
    ])
    with pytest.raises(LookaheadViolation):
        audit_trades(trades)


def test_audit_trades_raises_on_entry_before_result():
    trades = pd.DataFrame([
        {"ticker": "INFY.NS", "entry_date": date(2026, 4, 19),
         "result_date": date(2026, 4, 20)},
    ])
    with pytest.raises(LookaheadViolation):
        audit_trades(trades)
