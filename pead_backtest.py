"""PEAD historical backtest engine.

Reads events.parquet + price CSVs. Equal-weight, unlimited concurrent positions.
Exits at min(entry+60td, day_before_next_result). Long-only.
"""
from __future__ import annotations

import argparse
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from core.data_io import load_ohlcv
from pead_portfolio import Portfolio, lookup_next_result

HOLD_DAYS = 60   # trading days


def _next_trading_day(idx: pd.DatetimeIndex, d: date) -> date | None:
    after = idx[pd.Series(idx.date) > d]
    return after[0].date() if len(after) else None


def _td_offset(idx: pd.DatetimeIndex, d: date, n: int) -> date | None:
    """Return the trading day n positions after d (in idx)."""
    pos = idx.searchsorted(pd.Timestamp(d))
    if pos + n >= len(idx):
        return None
    return idx[pos + n].date()


def _prev_trading_day(idx: pd.DatetimeIndex, d: date) -> date | None:
    before = idx[pd.Series(idx.date) < d]
    return before[-1].date() if len(before) else None


def run_backtest(
    events: pd.DataFrame,
    closes: pd.DataFrame,
    opens: pd.DataFrame,
    start: date,
    end: date,
    initial_cash: float = 1_000_000,
) -> dict[str, Any]:
    """Run the PEAD long-only backtest. Returns {trades, equity_curve, portfolio}."""
    events = events.copy()
    events["result_date"] = pd.to_datetime(events["result_date"]).dt.date
    events = events.sort_values("result_date")
    idx = closes.index

    p = Portfolio(cash=initial_cash)

    trading_days = idx[(pd.Series(idx.date) >= start) & (pd.Series(idx.date) <= end)]

    for ts in trading_days:
        today = ts.date()

        # 1. Exits first
        for tk in list(p.open):
            pos = p.open[tk]
            nxt = lookup_next_result(events, tk, after=pos.entry_date)
            sixty_td = _td_offset(idx, pos.entry_date, HOLD_DAYS)
            candidates = [d for d in [sixty_td] if d is not None]
            if nxt is not None:
                day_before = _prev_trading_day(idx, nxt)
                if day_before is not None and day_before > pos.entry_date:
                    candidates.append(day_before)
            if not candidates:
                continue
            exit_due = min(candidates)
            if today >= exit_due:
                if tk not in closes.columns:
                    continue
                exit_px = closes.loc[ts, tk]
                if pd.isna(exit_px):
                    continue
                reason = "60D" if exit_due == sixty_td else "NEXT_EARNINGS"
                p.close(tk, exit_date=today, exit_px=float(exit_px), reason=reason)

        # 2. Entries — events with result_date == prev trading day
        prev_td = _prev_trading_day(idx, today)
        if prev_td is None:
            continue
        yest_events = events[
            (events["result_date"] == prev_td) & (events["qualifies_long"])
        ]
        if yest_events.empty:
            continue
        total_after = len(p.open) + len(yest_events)
        cash_per_new = p.cash / total_after if total_after > 0 else 0
        for _, ev in yest_events.iterrows():
            tk = ev["ticker"]
            if tk in p.open or tk not in opens.columns:
                continue
            px = opens.loc[ts, tk]
            if pd.isna(px) or px <= 0:
                continue
            shares = int(cash_per_new // float(px))
            if shares == 0:
                continue
            sixty_td = _td_offset(idx, today, HOLD_DAYS) or end
            p.buy(
                ticker=tk, entry_date=today, entry_px=float(px),
                shares=shares, exit_due=sixty_td,
                sue=float(ev["sue"]), period_type=str(ev["period_type"]),
            )

        # 3. Mark to market
        mtm = p.cash
        for tk, pos in p.open.items():
            if tk in closes.columns and not pd.isna(closes.loc[ts, tk]):
                mtm += pos.shares * float(closes.loc[ts, tk])
        p.equity_curve.append((today, mtm))

    return {
        "trades": pd.DataFrame(p.trades),
        "equity_curve": pd.DataFrame(p.equity_curve, columns=["date", "equity"]),
        "portfolio": p,
    }


def _load_price_panels(folder: str = "data") -> tuple[pd.DataFrame, pd.DataFrame]:
    ohlcv, _ = load_ohlcv(folder)
    closes = pd.DataFrame({tk: df["Close"] for tk, df in ohlcv.items()}).sort_index()
    opens = pd.DataFrame({tk: df["Open"] for tk, df in ohlcv.items()}).sort_index()
    return closes, opens


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default="pead_data/historical_events.parquet")
    ap.add_argument("--start", required=True, type=lambda s: date.fromisoformat(s))
    ap.add_argument("--end", required=True, type=lambda s: date.fromisoformat(s))
    ap.add_argument("--flavor", default="both", choices=["Q", "A", "both"])
    ap.add_argument("--cash", type=float, default=1_000_000)
    ap.add_argument("--trades-out", default="pead_trades.csv")
    ap.add_argument("--equity-out", default="pead_equity.csv")
    args = ap.parse_args()

    events = pd.read_parquet(args.events)
    if args.flavor != "both":
        events = events[events["period_type"] == args.flavor]

    closes, opens = _load_price_panels()
    result = run_backtest(
        events=events, closes=closes, opens=opens,
        start=args.start, end=args.end, initial_cash=args.cash,
    )

    # Attach result_date to each trade for the look-ahead audit:
    # per (ticker, entry_date), use the most recent events.result_date < entry_date.
    from pead_lookahead_audit import audit_trades

    if not result["trades"].empty:
        rd_per_ticker = {
            tk: events[events["ticker"] == tk].sort_values("result_date")
            for tk in result["trades"]["ticker"].unique()
        }
        result_dates = []
        for _, t in result["trades"].iterrows():
            tk_events = rd_per_ticker[t["ticker"]]
            prior = tk_events[tk_events["result_date"] < t["entry_date"]]
            result_dates.append(
                prior["result_date"].iloc[-1] if not prior.empty else t["entry_date"]
            )
        result["trades"]["result_date"] = result_dates

    audit_trades(result["trades"])

    result["trades"].to_csv(args.trades_out, index=False)
    result["equity_curve"].to_csv(args.equity_out, index=False)
    print(f"Wrote {len(result['trades'])} trades to {args.trades_out}")
    if not result["equity_curve"].empty:
        print(f"Final equity: {result['equity_curve']['equity'].iloc[-1]:,.0f}")
    else:
        print("Final equity: (no trading days in range)")

    from pead_diagnostics import compute_kpis, compute_decile_spread, attach_fwd_60d
    kpis = compute_kpis(result["equity_curve"], result["trades"])
    print("KPIs:", kpis)
    events_with_fwd = attach_fwd_60d(events, closes)
    spread = compute_decile_spread(events_with_fwd)
    spread.to_csv("pead_decile_spread.csv")
    pd.Series(kpis).to_csv("pead_kpis.csv")


if __name__ == "__main__":
    main()
