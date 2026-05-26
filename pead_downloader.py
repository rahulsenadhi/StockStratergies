"""PEAD daily incremental refresh.

Flow (matches spec §10):
  1. Filter universe.
  2. Fetch today's NSE corp-announce (Quarterly + Annual).
  3. For each declaring ticker in universe: build event row.
  4. Attach sector P/B median.
  5. Compute decile cohort + qualifies flags.
  6. Append to events.parquet (dedup).
  7. Write live_signals.csv (today's qualifies_long).
  8. Write last_run_status.json.
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from core.nse_announce import (
    fetch_announcements,
    parse_announcements,
    cache_raw,
)
from pead_event_builder import build_event
from pead_universe import filter_universe
from pead_cohort import compute_cohort_deciles, mark_qualifies
from pead_sector_pb import attach_sector_median
from pead_events_store import append_events


def get_actual_eps(ticker: str, result_date: date, period_type: str) -> float:
    """Pull the just-declared EPS from yfinance.

    For quarterly, latest quarterly_earnings row whose index >= result_date - 95d.
    For annual, latest annual earnings row whose index year == result_date.year - 1
    (Indian fiscal year ends Mar — adjust if needed).
    """
    import yfinance as yf
    t = yf.Ticker(ticker)
    if period_type == "Q":
        df = t.quarterly_earnings
        if df is None or df.empty:
            return math.nan
        df = df.sort_index(ascending=False)
        for idx, val in df["Earnings"].items():
            if idx.date() <= result_date:
                return float(val)
        return math.nan
    else:
        df = getattr(t, "earnings", None)
        if df is None or df.empty:
            return math.nan
        df = df.sort_index(ascending=False)
        for idx, val in df["Earnings"].items():
            if idx.year <= result_date.year:
                return float(val)
        return math.nan


def _default_cfg() -> dict[str, Any]:
    base = Path("pead_data")
    return {
        "events_path": base / "events.parquet",
        "live_signals_path": base / "live_signals.csv",
        "raw_dir": base / "nse_announce_raw",
        "status_path": base / "last_run_status.json",
        "universe": None,                              # caller supplies
        "today": date.today(),
    }


def run_incremental(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = {**_default_cfg(), **(cfg or {})}
    today: date = cfg["today"]
    universe: list[str] | None = cfg["universe"]
    if universe is None:
        raise ValueError("cfg['universe'] required (load from build_universe output)")

    universe = filter_universe(universe)

    all_raw: list[dict] = []
    for period in ("Quarterly", "Annual"):
        try:
            raw = fetch_announcements(period=period)
        except RuntimeError as e:
            _write_status(cfg["status_path"], today, error=str(e))
            raise
        cache_raw(raw, cfg["raw_dir"], today)
        all_raw.extend(raw)

    announcements = parse_announcements(all_raw)
    universe_set = set(universe)
    in_universe = [a for a in announcements if a["yf_ticker"] in universe_set]

    rows: list[dict] = []
    for a in in_universe:
        eps_actual = get_actual_eps(a["yf_ticker"], a["result_date"], a["period_type"])
        if math.isnan(eps_actual):
            continue
        ev = build_event(
            ticker=a["yf_ticker"],
            result_date=a["result_date"],
            period_type=a["period_type"],
            eps_actual=eps_actual,
        )
        rows.append(ev)

    if rows:
        df = pd.DataFrame(rows)
        df = attach_sector_median(df)
        df = compute_cohort_deciles(df, window_td=5)
        df = mark_qualifies(df)
        append_events(cfg["events_path"], df.to_dict("records"))

        live = df[df["qualifies_long"]].copy()
        Path(cfg["live_signals_path"]).parent.mkdir(parents=True, exist_ok=True)
        live.to_csv(cfg["live_signals_path"], index=False)
    else:
        Path(cfg["live_signals_path"]).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(cfg["live_signals_path"], index=False)

    summary = {
        "run_date": today.isoformat(),
        "declared_count": len(in_universe),
        "rows_written": len(rows),
        "qualified_long": int(sum(r.get("qualifies_long", False) for r in rows)),
        "qualified_short": int(sum(r.get("qualifies_short", False) for r in rows)),
        "universe_size": len(universe),
        "error": None,
    }
    _write_status(cfg["status_path"], today, summary=summary)
    return summary


def _write_status(path: Path, today: date, summary: dict | None = None,
                  error: str | None = None) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    payload = summary or {
        "run_date": today.isoformat(),
        "error": error,
    }
    Path(path).write_text(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    import sys
    from pathlib import Path as _P
    universe_csv = _P("data/universe/universe.csv")
    if universe_csv.exists():
        u = pd.read_csv(universe_csv)["yf_ticker"].dropna().tolist()
    else:
        print("ERROR: data/universe/universe.csv missing — run build_universe.py first")
        sys.exit(1)
    summary = run_incremental({"universe": u})
    print(json.dumps(summary, indent=2, default=str))
