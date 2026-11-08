"""Monthly rotation backtest: an unfinished calendar month.

pandas ``resample('ME')`` labels each month with its calendar month-end, so a
data refresh on 7 Nov produced a row dated 30 Nov and a rebalance chosen from
four trading days of November. The approved behaviour (2026-11-07, option A):
keep the unfinished month's mark-to-market value, date it with the real last
trading day, and do not rebalance on it. Finished months are unchanged.
"""
from __future__ import annotations

import pandas as pd
import pytest

from step2_backtest_momentum import MomentumRotationBacktest

TICKERS = ['AAA.NS', 'BBB.NS', 'CCC.NS', 'DDD.NS', 'EEE.NS', 'FFF.NS', 'GGG.NS']


def _series(start: str, end: str, daily_growth: float, base: float = 100.0) -> pd.Series:
    idx = pd.bdate_range(start, end)
    return pd.Series([base * (1 + daily_growth) ** i for i in range(len(idx))], index=idx)


def _backtest(end: str, cutoff: str) -> MomentumRotationBacktest:
    bt = MomentumRotationBacktest(initial_capital=50000, top_n=5)
    bt.benchmark = _series('2026-07-01', end, 0.0005)
    bt.prices = {t: _series('2026-07-01', end, 0.0002 * (i + 1)) for i, t in enumerate(TICKERS)}
    bt.cutoff_date = pd.Timestamp(cutoff)
    bt.prepare_monthly_data()
    bt.run_backtest()
    return bt


def test_unfinished_month_is_dated_with_last_trading_day():
    bt = _backtest(end='2026-11-06', cutoff='2026-11-07')
    assert bt.portfolio_dates[-1] == pd.Timestamp('2026-11-06')
    assert bt.benchmark_monthly.index[-1] == pd.Timestamp('2026-11-06')


def test_unfinished_month_does_not_rebalance():
    bt = _backtest(end='2026-11-06', cutoff='2026-11-07')
    log_dates = [pd.Timestamp(r['Date']) for r in bt.rebalance_log]
    assert log_dates[-1] == pd.Timestamp('2026-10-31')
    assert all(d.month != 11 for d in log_dates)


def test_unfinished_month_marks_october_holdings_at_latest_close():
    bt = _backtest(end='2026-11-06', cutoff='2026-11-07')
    expected = bt.cash + sum(shares * bt.prices[t].iloc[-1] for t, shares in bt.portfolio.items())
    assert bt.portfolio_value[-1] == pytest.approx(expected)


def test_finished_month_keeps_month_end_label_and_rebalance():
    bt = _backtest(end='2026-11-30', cutoff='2026-12-01')
    assert bt.portfolio_dates[-1] == pd.Timestamp('2026-11-30')
    assert pd.Timestamp(bt.rebalance_log[-1]['Date']) == pd.Timestamp('2026-11-30')


def test_stale_data_for_a_finished_month_is_unchanged():
    # Data stops on Friday 30 Oct; run on 7 Nov. October is over, so it is a
    # normal month-end row with its rebalance.
    bt = _backtest(end='2026-10-30', cutoff='2026-11-07')
    assert bt.portfolio_dates[-1] == pd.Timestamp('2026-10-31')
    assert pd.Timestamp(bt.rebalance_log[-1]['Date']) == pd.Timestamp('2026-10-31')
