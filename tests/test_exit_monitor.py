from datetime import datetime

import pandas as pd
import pytest

from core.exit_monitor import IST, evaluate_holding
from core.portfolio import DEFAULT_SETTINGS, Position

SETTINGS = DEFAULT_SETTINGS
END = "2026-11-06"          # a Friday
NOW = datetime(2026, 11, 9, 18, 0, tzinfo=IST)   # Monday evening: Friday's bar is current


def make_bars(closes, end=END):
    """Bars ending on ``end``; the EMA is computed with the same span as production."""
    idx = pd.bdate_range(end=end, periods=len(closes))
    s = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"Close": s, "Volume": 1000.0, "ema220": s.ewm(span=220, adjust=False).mean()})


def pos(avg=100.0, first_buy="2026-01-05", date_known=True, strategy=None, qty=10):
    p = Position(symbol="TEST.NS", exchange="NSE", open_qty=qty, lots=[], avg_price=avg,
                 avg_price_incl_charges=avg, realised_pnl=0.0, realised_charges=0.0,
                 charges_known=True, first_buy_date=first_buy if date_known else None,
                 date_known=date_known, closed=False)
    if strategy:
        p.extra["strategy"] = strategy
    return p


def uptrend(n=300, last=None):
    c = [100 + i * 0.1 for i in range(n)]
    if last is not None:
        c[-1] = last
    return c


def ev(closes, position=None, now=NOW, nifty=END, end=END):
    return evaluate_holding(position or pos(avg=100), make_bars(closes, end), nifty, now, SETTINGS)


def test_hard_stop_gives_exit():
    e = ev(uptrend(last=80), pos(avg=100))      # 80 < 85
    assert (e.action, e.rule) == ("EXIT", "hard stop")
    assert "not a guaranteed price" in e.explanation
    assert e.levels["hard_stop"] == 85.0


def test_ema_break_gives_exit():
    e = ev(uptrend(last=100), pos(avg=100))     # above stop 85, below EMA (~125)
    assert (e.action, e.rule) == ("EXIT", "EMA220 break")
    assert "next session's open" in e.explanation


def test_hard_stop_wins_when_both_fire():
    e = ev(uptrend(last=50), pos(avg=100))
    assert e.rule == "hard stop"


def test_near_ema_is_review():
    bars = make_bars(uptrend())
    ema = bars["ema220"].iloc[-2]
    closes = uptrend(last=ema * 1.02)
    e = ev(closes, pos(avg=100))
    assert e.action == "REVIEW" and "Advisory" in e.explanation


def test_near_stop_is_review():
    closes = [60.0] * 150 + [87.0] * 150          # EMA well below 87; stop is 85 (2.4% away)
    e = ev(closes, pos(avg=100))
    assert (e.action, e.rule) == ("REVIEW", "near hard stop")


def test_normal_is_hold():
    e = ev(uptrend(last=140), pos(avg=100))
    assert e.action == "HOLD" and e.rule is None
    assert e.data_status == "OK"


def test_stale_when_three_sessions_behind_nifty():
    e = ev(uptrend(last=140), nifty="2026-11-11")
    assert e.action == "STALE" and e.data_status == "STALE"


def test_no_bars_is_data_unavailable():
    e = evaluate_holding(pos(), None, END, NOW, SETTINGS)
    assert e.action == "DATA UNAVAILABLE" and e.data_status == "DATA UNAVAILABLE"


def test_short_history_is_data_unavailable():
    e = ev([100.0 + i for i in range(150)])
    assert e.action == "DATA UNAVAILABLE" and "Insufficient history" in e.explanation


def test_bar_dated_today_before_close_is_ignored():
    now = datetime(2026, 11, 6, 11, 0, tzinfo=IST)
    closes = uptrend(last=140)
    closes[-1], closes[-2] = 10.0, 140.0         # today's partial bar would be a hard stop
    e = ev(closes, pos(avg=100), now=now, nifty="2026-11-05")
    assert e.incomplete_bar_ignored is True
    assert e.last_bar_date == "2026-11-05" and e.action == "HOLD"


def test_bar_dated_today_after_close_is_used():
    now = datetime(2026, 11, 6, 16, 0, tzinfo=IST)
    e = ev(uptrend(last=140), now=now)
    assert e.incomplete_bar_ignored is False and e.last_bar_date == END


def test_reconstruction_ignores_bars_on_or_before_buy_date():
    closes = uptrend()
    closes[260], closes[270] = 50.0, 40.0         # two breaks; only those after buy count
    bars = make_bars(closes)
    d260, d270 = bars.index[260].strftime("%Y-%m-%d"), bars.index[270].strftime("%Y-%m-%d")
    e = evaluate_holding(pos(avg=100, first_buy=d260), bars, END, NOW, SETTINGS)
    assert e.reconstructed_first_exit["date"] == d270
    assert e.reconstructed_first_exit["rule"] == "hard stop"
    assert "Reconstructed" in e.reconstructed_first_exit["label"]


def test_opening_balance_skips_date_dependent_fields():
    e = ev(uptrend(last=80), pos(avg=100, date_known=False))
    assert e.action == "EXIT" and e.rule == "hard stop"
    assert e.held_days is None and e.drawdown_from_peak is None
    assert e.levels["highest_close_since_entry"] is None
    assert e.reconstructed_first_exit is None and e.reconstruction_note == "buy date unknown"


def test_peak_drawdown_and_held_days():
    e = ev(uptrend(last=125), pos(avg=100, first_buy="2026-10-01"))
    assert e.held_days == 39
    assert e.levels["highest_close_since_entry"] > 125
    assert e.drawdown_from_peak < 0


def test_ema_immature_is_labelled():
    e = ev(uptrend(n=300, last=140))
    assert e.levels["ema_immature"] is True and "immature" in e.explanation


def test_strategy_other_is_labelled_review():
    e = ev(uptrend(last=80), pos(strategy="other"))
    assert e.action == "REVIEW" and "No automated exit rules" in e.explanation


def test_never_uses_forbidden_words():
    for last in (80, 100, 140):
        text = ev(uptrend(last=last)).explanation.lower()
        assert "no loss" not in text and "100%" not in text
        assert text.count("guarantee") == text.count("not a guaranteed")
