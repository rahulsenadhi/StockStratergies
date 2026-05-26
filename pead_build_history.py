"""One-time historical events backfill.

Strategy:
  1. Pull NSE corp-announce paged by month for [start..end].
  2. For gaps (tickers with no NSE hits in the range), fall back to
     yfinance ticker.earnings_dates which gives ~4yr of historical
     announcement timestamps.
  3. For each (ticker, result_date, period_type) build_event() it.
  4. Attach sector medians, compute deciles, mark qualifies, persist.

CLI:
  python pead_build_history.py --start 2022-01-01 --end 2026-05-25
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from core.nse_announce import (
    fetch_announcements,
    parse_announcements,
)
from pead_event_builder import build_event
from pead_cohort import compute_cohort_deciles, mark_qualifies
from pead_sector_pb import attach_sector_median


def fetch_announcements_range(start: date, end: date, period: str) -> list[dict]:
    """NSE API doesn't support historical paging cleanly — best-effort current data only.

    Returns whatever it can. Backfill leans on yfinance fallback.
    """
    try:
        return fetch_announcements(period=period)
    except Exception:
        return []


def _yf_earnings_dates(ticker: str) -> pd.DataFrame | None:
    try:
        t = yf.Ticker(ticker)
        return t.earnings_dates
    except Exception:
        return None


def _yf_fallback_events(ticker: str, start: date, end: date) -> list[dict]:
    """Yield (result_date, period_type, eps_actual) tuples from yfinance earnings_dates."""
    df = _yf_earnings_dates(ticker)
    if df is None or df.empty:
        return []
    df = df[df["Reported EPS"].notna()]
    out: list[dict] = []
    for ts, row in df.iterrows():
        rd = ts.date() if hasattr(ts, "date") else ts
        if rd < start or rd > end:
            continue
        out.append(
            {
                "yf_ticker": ticker,
                "result_date": rd,
                "period_type": "Q",   # earnings_dates is quarterly
                "eps_actual": float(row["Reported EPS"]),
            }
        )
    return out


def build_history(
    universe: list[str],
    start: date,
    end: date,
    output_path: Path,
) -> int:
    rows: list[dict] = []

    nse_raw: list[dict] = []
    for period in ("Quarterly", "Annual"):
        nse_raw.extend(fetch_announcements_range(start, end, period))
    nse_events = parse_announcements(nse_raw)
    nse_seen: set[tuple[str, date, str]] = set()
    for a in nse_events:
        if a["yf_ticker"] not in universe:
            continue
        if a["result_date"] < start or a["result_date"] > end:
            continue
        # Need actual EPS — pull from yfinance earnings_dates
        df = _yf_earnings_dates(a["yf_ticker"])
        if df is None or df.empty:
            continue
        match = df[df.index.date == a["result_date"]]
        if match.empty or pd.isna(match["Reported EPS"].iloc[0]):
            continue
        ev = build_event(
            ticker=a["yf_ticker"],
            result_date=a["result_date"],
            period_type=a["period_type"],
            eps_actual=float(match["Reported EPS"].iloc[0]),
        )
        rows.append(ev)
        nse_seen.add((a["yf_ticker"], a["result_date"], a["period_type"]))

    for ticker in universe:
        for fb in _yf_fallback_events(ticker, start, end):
            key = (fb["yf_ticker"], fb["result_date"], fb["period_type"])
            if key in nse_seen:
                continue
            ev = build_event(
                ticker=fb["yf_ticker"],
                result_date=fb["result_date"],
                period_type=fb["period_type"],
                eps_actual=fb["eps_actual"],
            )
            rows.append(ev)
            nse_seen.add(key)

    if not rows:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_parquet(output_path, index=False)
        return 0

    df = pd.DataFrame(rows)
    df = attach_sector_median(df)
    df = compute_cohort_deciles(df, window_td=5)
    df = mark_qualifies(df)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    return len(df)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, type=lambda s: date.fromisoformat(s))
    ap.add_argument("--end", required=True, type=lambda s: date.fromisoformat(s))
    ap.add_argument("--universe-csv", default="data/universe/universe.csv")
    ap.add_argument("--out", default="pead_data/historical_events.parquet")
    args = ap.parse_args()
    u = pd.read_csv(args.universe_csv)["yf_ticker"].dropna().tolist()
    n = build_history(u, args.start, args.end, Path(args.out))
    print(f"Wrote {n} events to {args.out}")
