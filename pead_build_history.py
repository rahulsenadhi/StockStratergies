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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from core.nse_announce import (
    fetch_announcements,
    parse_announcements,
)
from core.yf_cache import get_snapshot
from pead_event_builder import build_event
from pead_cohort import compute_cohort_deciles, mark_qualifies
from pead_sector_pb import attach_sector_median

DEFAULT_WORKERS = 12


def fetch_announcements_range(start: date, end: date, period: str) -> list[dict]:
    """NSE API doesn't support historical paging cleanly — best-effort current data only.

    Returns whatever it can. Backfill leans on yfinance fallback.
    """
    try:
        return fetch_announcements(period=period)
    except Exception:
        return []


def _yf_earnings_dates(ticker: str) -> pd.DataFrame | None:
    """Cached earnings_dates lookup via core.yf_cache."""
    try:
        snap = get_snapshot(ticker)
        return snap.get("earnings_dates")
    except Exception:
        return None


def _prefetch_universe(universe: list[str], workers: int = DEFAULT_WORKERS) -> None:
    """Warm the cache for every ticker in parallel. Subsequent build_event calls hit disk."""
    print(f"  Pre-fetching yfinance snapshots for {len(universe)} tickers "
          f"(workers={workers})...")
    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(get_snapshot, t): t for t in universe}
        for fut in as_completed(futures):
            completed += 1
            if completed % 25 == 0 or completed == len(universe):
                print(f"    {completed}/{len(universe)} cached")
            try:
                fut.result()
            except Exception:
                pass


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


def _build_ticker_events(ticker: str, start: date, end: date,
                          nse_hits: dict[date, str]) -> list[dict]:
    """Build all events for one ticker. NSE-confirmed dates use NSE period_type;
    remaining yfinance-only dates default to quarterly."""
    out: list[dict] = []
    df = _yf_earnings_dates(ticker)
    if df is None or df.empty:
        return out
    df = df[df["Reported EPS"].notna()]
    seen_dates: set[date] = set()
    for ts, row in df.iterrows():
        rd = ts.date() if hasattr(ts, "date") else ts
        if rd < start or rd > end:
            continue
        period_type = nse_hits.get(rd, "Q")
        ev = build_event(
            ticker=ticker, result_date=rd,
            period_type=period_type,
            eps_actual=float(row["Reported EPS"]),
        )
        out.append(ev)
        seen_dates.add(rd)
    return out


def build_history(
    universe: list[str],
    start: date,
    end: date,
    output_path: Path,
    workers: int = DEFAULT_WORKERS,
) -> int:
    _prefetch_universe(universe, workers=workers)

    # NSE corp-announce — only flips period_type from default Q to A where matched.
    nse_period_by_ticker: dict[str, dict[date, str]] = {}
    nse_raw: list[dict] = []
    for period in ("Quarterly", "Annual"):
        nse_raw.extend(fetch_announcements_range(start, end, period))
    for a in parse_announcements(nse_raw):
        nse_period_by_ticker.setdefault(a["yf_ticker"], {})[a["result_date"]] = a["period_type"]

    print(f"  Building events for {len(universe)} tickers (workers={workers})...")
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {
            ex.submit(_build_ticker_events, t, start, end,
                      nse_period_by_ticker.get(t, {})): t
            for t in universe
        }
        for fut in as_completed(futures):
            try:
                rows.extend(fut.result())
            except Exception as e:
                print(f"    WARN {futures[fut]}: {e}")

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
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    args = ap.parse_args()
    u = pd.read_csv(args.universe_csv)["yf_ticker"].dropna().tolist()
    n = build_history(u, args.start, args.end, Path(args.out), workers=args.workers)
    print(f"Wrote {n} events to {args.out}")
