# S0b — Local Incremental Catch-Up Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the PC is turned on and run, each strategy's price data catches up to the latest trading day by fetching only the missing bars (fast), surfaced via a per-strategy staleness banner + Update button.

**Architecture:** New `core/incremental.py` (gap-aware fetch engine: plan → fetch → atomic merge) generalizes the incremental logic currently trapped in `nse_bse_downloader.py`. `core/staleness.py` reports trading-days-behind for the banner. `core/refresh.py` orchestrates per-strategy refresh (fetch → Parquet sync → precompute). `core/refresh_ui.py` renders the Streamlit banner/button. The three full-download downloaders and `nse_bse` are refactored to call the shared engine. No cloud, no new infra.

**Tech Stack:** Python 3.13, pandas, numpy, yfinance, DuckDB (S0a), Streamlit, pytest. Spec: `docs/superpowers/specs/2026-06-04-s0b-incremental-catchup-design.md`.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `core/incremental.py` | `FetchPlan`, `last_stored_date`, `trading_days_between`, `plan_fetch`, `standardize`, `merge_save`, `refresh_tickers`, `yf_fetch` | Create |
| `core/staleness.py` | `dataset_staleness(folder)` → `{latest_date, days_behind}` | Create |
| `core/refresh.py` | `STRATEGY_CFG`, `refresh_strategy(name, st_status=None)` | Create |
| `core/refresh_ui.py` | `render_staleness_banner(...)` Streamlit helper | Create |
| `tests/test_incremental.py` | unit tests for the fetch engine | Create |
| `tests/test_staleness.py` | unit tests for staleness | Create |
| `step1_download_data.py` | Nifty-50 downloader | Refactor to call `refresh_tickers` |
| `momentum_edge_downloader.py` | Momentum Edge downloader | Refactor to call `refresh_tickers` |
| `ipo_edge_downloader.py` | IPO Edge downloader | Refactor to call `refresh_tickers` |
| `nse_bse_downloader.py` | Wide-universe downloader | Migrate incremental logic to `core.incremental`; call `merge_save`/`plan_fetch` |
| `momentum_edge_dashboard.py`, `dashboard_visual.py`, `ipo_edge_dashboard.py`, `master_dashboard.py` | dashboards | Add banner + Update button |

**Convention reminders (from existing code):**
- Tests: pytest, `tmp_path` + `monkeypatch`, no network (inject a fake `fetch_fn`). Run with `python -m pytest`.
- CSV schema: `Date,Open,High,Low,Close,Volume`, `Date` as `YYYY-MM-DD`.
- yfinance `end` is **exclusive** (existing downloaders pass `end + 1 day`).
- Commit message types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.

---

## Task 1: `last_stored_date` + `trading_days_between`

**Files:**
- Create: `core/incremental.py`
- Test: `tests/test_incremental.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_incremental.py
import datetime as dt
import pandas as pd
import pytest
from core import incremental as inc


def _write_csv(path, dates):
    pd.DataFrame({
        "Date": dates, "Open": 1.0, "High": 1.0, "Low": 1.0,
        "Close": 1.0, "Volume": 10,
    }).to_csv(path, index=False)


def test_last_stored_date_missing(tmp_path):
    assert inc.last_stored_date(tmp_path / "nope.csv") is None


def test_last_stored_date_empty(tmp_path):
    p = tmp_path / "e.csv"
    p.write_text("")
    assert inc.last_stored_date(p) is None


def test_last_stored_date_returns_max(tmp_path):
    p = tmp_path / "t.csv"
    _write_csv(p, ["2024-01-01", "2024-01-03", "2024-01-02"])
    assert inc.last_stored_date(p) == dt.date(2024, 1, 3)


def test_trading_days_between_same_day_zero():
    assert inc.trading_days_between(dt.date(2024, 1, 8), dt.date(2024, 1, 8)) == 0


def test_trading_days_between_weekend_zero():
    # Fri 2024-01-05 stored, today Sat 2024-01-06 -> 0 trading days behind
    assert inc.trading_days_between(dt.date(2024, 1, 5), dt.date(2024, 1, 6)) == 0


def test_trading_days_between_counts_business_days():
    # Mon stored, Thu today -> Tue, Wed, Thu = 3
    assert inc.trading_days_between(dt.date(2024, 1, 8), dt.date(2024, 1, 11)) == 3
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python -m pytest tests/test_incremental.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'core.incremental'`)

- [ ] **Step 3: Implement minimal `core/incremental.py`**

```python
# core/incremental.py
"""Gap-aware incremental OHLCV fetch engine (S0b).

Single source of truth for "fetch only the missing trading days" — generalizes
the incremental logic that previously lived inside nse_bse_downloader.py.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

OHLCV = ["Open", "High", "Low", "Close", "Volume"]
MIN_ROWS = 100                 # discard brand-new tickers with fewer rows than this
FULL_LOOKBACK_DAYS = 365 * 10  # initial backfill window for a never-seen ticker


def last_stored_date(path) -> dt.date | None:
    """Return max(Date) in a ticker CSV, or None if missing/empty/unreadable."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p, usecols=["Date"])
    except (ValueError, pd.errors.EmptyDataError, OSError):
        return None
    if df.empty:
        return None
    return pd.to_datetime(df["Date"]).dt.date.max()


def trading_days_between(last: dt.date, today: dt.date) -> int:
    """Business days strictly after `last` up to and including `today` (>=0).

    Weekend-aware via numpy busday_count (which treats Sat/Sun as non-business).
    Holidays are not modeled here; an empty fetch on a holiday is a harmless no-op.
    """
    if today <= last:
        return 0
    return int(np.busday_count(last + dt.timedelta(days=1), today + dt.timedelta(days=1)))
```

- [ ] **Step 4: Run tests, verify pass**

Run: `python -m pytest tests/test_incremental.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add core/incremental.py tests/test_incremental.py
git commit -m "feat(s0b): last_stored_date + trading_days_between"
```

---

## Task 2: `FetchPlan` + `plan_fetch`

**Files:**
- Modify: `core/incremental.py`
- Test: `tests/test_incremental.py`

- [ ] **Step 1: Append failing tests**

```python
# tests/test_incremental.py  (append)
def test_plan_fetch_no_file_is_full(tmp_path):
    plan = inc.plan_fetch(tmp_path / "new.csv", dt.date(2024, 6, 4))
    assert plan.kind == "full"
    assert plan.end == dt.date(2024, 6, 5)          # today + 1 (exclusive)
    assert plan.start == dt.date(2024, 6, 4) - dt.timedelta(days=inc.FULL_LOOKBACK_DAYS)


def test_plan_fetch_current_is_skip(tmp_path):
    p = tmp_path / "t.csv"
    _write_csv(p, ["2024-06-04"])
    plan = inc.plan_fetch(p, dt.date(2024, 6, 4))
    assert plan.kind == "skip"


def test_plan_fetch_gap(tmp_path):
    p = tmp_path / "t.csv"
    _write_csv(p, ["2024-05-30"])                   # Thu
    plan = inc.plan_fetch(p, dt.date(2024, 6, 4))   # Tue (gap exists)
    assert plan.kind == "gap"
    assert plan.start == dt.date(2024, 5, 31)       # last + 1
    assert plan.end == dt.date(2024, 6, 5)          # today + 1


def test_plan_fetch_weekend_is_skip(tmp_path):
    p = tmp_path / "t.csv"
    _write_csv(p, ["2024-06-07"])                   # Fri
    plan = inc.plan_fetch(p, dt.date(2024, 6, 8))   # Sat -> 0 trading days -> skip
    assert plan.kind == "skip"
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m pytest tests/test_incremental.py -q -k plan_fetch`
Expected: FAIL (`AttributeError: module 'core.incremental' has no attribute 'plan_fetch'`)

- [ ] **Step 3: Implement (append to `core/incremental.py`)**

```python
# core/incremental.py  (append)
@dataclass(frozen=True)
class FetchPlan:
    kind: str                       # "full" | "gap" | "skip"
    start: dt.date | None = None
    end: dt.date | None = None      # exclusive (yfinance convention)


def plan_fetch(path, today: dt.date, full_lookback_days: int = FULL_LOOKBACK_DAYS) -> FetchPlan:
    """Decide what to fetch for one ticker.

    - No CSV yet            -> FULL (initial backfill).
    - Already current       -> SKIP.
    - Otherwise             -> GAP (always gap, any size; never auto-full an existing ticker).
    """
    last = last_stored_date(path)
    if last is None:
        start = today - dt.timedelta(days=full_lookback_days)
        return FetchPlan("full", start, today + dt.timedelta(days=1))
    if trading_days_between(last, today) <= 0:
        return FetchPlan("skip")
    return FetchPlan("gap", last + dt.timedelta(days=1), today + dt.timedelta(days=1))
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m pytest tests/test_incremental.py -q`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add core/incremental.py tests/test_incremental.py
git commit -m "feat(s0b): plan_fetch (full/gap/skip decision)"
```

---

## Task 3: `standardize` + atomic `merge_save`

**Files:**
- Modify: `core/incremental.py`
- Test: `tests/test_incremental.py`

- [ ] **Step 1: Append failing tests**

```python
# tests/test_incremental.py  (append)
def _raw(dates, close=100.0):
    return pd.DataFrame({
        "Date": dates, "Open": close, "High": close, "Low": close,
        "Close": close, "Volume": 5,
    })


def test_standardize_drops_nan_close_and_dupes():
    df = _raw(["2024-01-01", "2024-01-01", "2024-01-02"])
    df.loc[2, "Close"] = float("nan")
    out = inc.standardize(df)
    assert list(out["Date"]) == [dt.date(2024, 1, 1)]


def test_standardize_missing_cols_returns_none():
    assert inc.standardize(pd.DataFrame({"Date": ["2024-01-01"], "Close": [1.0]})) is None


def test_merge_save_new_file(tmp_path):
    p = tmp_path / "t.csv"
    added = inc.merge_save(_raw(["2024-01-01", "2024-01-02"]), p)
    assert added == 2
    assert inc.last_stored_date(p) == dt.date(2024, 1, 2)


def test_merge_save_appends_and_dedups(tmp_path):
    p = tmp_path / "t.csv"
    inc.merge_save(_raw(["2024-01-01", "2024-01-02"]), p)
    added = inc.merge_save(_raw(["2024-01-02", "2024-01-03"]), p)   # 02 overlaps
    assert added == 1
    df = pd.read_csv(p)
    assert list(pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")) == \
        ["2024-01-01", "2024-01-02", "2024-01-03"]


def test_merge_save_idempotent_no_rewrite(tmp_path):
    p = tmp_path / "t.csv"
    inc.merge_save(_raw(["2024-01-01", "2024-01-02"]), p)
    before = p.read_bytes()
    added = inc.merge_save(_raw(["2024-01-01", "2024-01-02"]), p)   # same data
    assert added == 0
    assert p.read_bytes() == before        # byte-identical, no write


def test_merge_save_empty_returns_negative(tmp_path):
    p = tmp_path / "t.csv"
    assert inc.merge_save(pd.DataFrame(), p) == -1
    assert not p.exists()
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m pytest tests/test_incremental.py -q -k "standardize or merge_save"`
Expected: FAIL (`AttributeError: ... 'standardize'`)

- [ ] **Step 3: Implement (append to `core/incremental.py`)**

```python
# core/incremental.py  (append)
import os


def standardize(df: pd.DataFrame | None) -> pd.DataFrame | None:
    """Normalize a raw yfinance frame to Date,O,H,L,C,V. None if empty/invalid.

    Note: no minimum-row gate here (gap fetches return few rows); MIN_ROWS is
    enforced only for brand-new tickers in refresh_tickers.
    """
    if df is None or getattr(df, "empty", True):
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [c[0] if c[0] else c[1] for c in df.columns]
    df = df.reset_index()
    for date_col in ("Date", "Datetime", "index"):
        if date_col in df.columns:
            df = df.rename(columns={date_col: "Date"})
            break
    if not {"Open", "High", "Low", "Close", "Volume"}.issubset(df.columns):
        return None
    keep = [c for c in ["Date"] + OHLCV if c in df.columns]
    df = df[keep].copy()
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    df = (df.dropna(subset=["Close"])
            .drop_duplicates(subset="Date")
            .sort_values("Date")
            .reset_index(drop=True))
    return df if len(df) else None


def merge_save(new_df: pd.DataFrame | None, path) -> int:
    """Standardize new_df, append into CSV at path (dedup by Date), atomic write.

    Returns count of NEW rows added (>=0), or -1 if new_df is empty/invalid.
    Idempotent: if nothing new, the file is left byte-identical (no rewrite).
    """
    std = standardize(new_df)
    if std is None:
        return -1
    p = Path(path)
    if p.exists():
        existing = pd.read_csv(p)
        existing["Date"] = pd.to_datetime(existing["Date"]).dt.date
        before = len(existing)
        merged = (pd.concat([existing, std], ignore_index=True)
                    .drop_duplicates(subset="Date")
                    .sort_values("Date")
                    .reset_index(drop=True))
        if len(merged) == before:
            return 0                          # nothing new -> don't touch the file
    else:
        before = 0
        merged = std
    tmp = p.with_suffix(".csv.tmp")
    merged.to_csv(tmp, index=False)
    os.replace(tmp, p)                        # atomic; crash before this keeps old CSV
    return len(merged) - before
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m pytest tests/test_incremental.py -q`
Expected: PASS (16 passed)

- [ ] **Step 5: Commit**

```bash
git add core/incremental.py tests/test_incremental.py
git commit -m "feat(s0b): standardize + atomic merge_save"
```

---

## Task 4: `refresh_tickers` orchestration + `yf_fetch`

**Files:**
- Modify: `core/incremental.py`
- Test: `tests/test_incremental.py`

- [ ] **Step 1: Append failing tests** (fake fetch_fn — no network)

```python
# tests/test_incremental.py  (append)
def test_refresh_tickers_skips_current_and_appends_gap(tmp_path):
    folder = tmp_path / "ds"
    folder.mkdir()
    _write_csv(folder / "CUR.csv", ["2024-06-04"])      # current -> skip
    _write_csv(folder / "OLD.csv", ["2024-05-30"])      # gap

    calls = []

    def fake_fetch(ticker, start, end):
        calls.append(ticker)
        return _raw(["2024-05-31", "2024-06-03", "2024-06-04"])

    status = inc.refresh_tickers(
        ["CUR", "OLD"], folder, dt.date(2024, 6, 4), fake_fetch, max_workers=1)

    assert status["CUR"] == "skipped"
    assert status["OLD"].startswith("gap_appended")
    assert calls == ["OLD"]                              # CUR never hit the network


def test_refresh_tickers_new_ticker_full(tmp_path):
    folder = tmp_path / "ds"
    folder.mkdir()
    dates = pd.bdate_range("2024-01-01", periods=120).strftime("%Y-%m-%d").tolist()

    status = inc.refresh_tickers(
        ["NEW"], folder, dt.date(2024, 6, 20),
        lambda t, s, e: _raw(dates), max_workers=1)

    assert status["NEW"].startswith("full")
    assert (folder / "NEW.csv").exists()


def test_refresh_tickers_new_ticker_below_min_rows_discarded(tmp_path):
    folder = tmp_path / "ds"
    folder.mkdir()
    status = inc.refresh_tickers(
        ["TINY"], folder, dt.date(2024, 6, 20),
        lambda t, s, e: _raw(["2024-06-18", "2024-06-19"]),  # 2 rows < MIN_ROWS
        max_workers=1, min_rows_new=100)
    assert status["TINY"] == "failed(min_rows)"
    assert not (folder / "TINY.csv").exists()


def test_refresh_tickers_one_failure_isolated(tmp_path):
    folder = tmp_path / "ds"
    folder.mkdir()
    _write_csv(folder / "A.csv", ["2024-05-30"])
    _write_csv(folder / "B.csv", ["2024-05-30"])

    def fake_fetch(ticker, start, end):
        if ticker == "A":
            raise RuntimeError("boom")
        return _raw(["2024-05-31", "2024-06-04"])

    status = inc.refresh_tickers(
        ["A", "B"], folder, dt.date(2024, 6, 4), fake_fetch, max_workers=1)
    assert status["A"].startswith("failed")
    assert status["B"].startswith("gap_appended")        # B unaffected


def test_refresh_tickers_empty_return_is_skip_noop(tmp_path):
    folder = tmp_path / "ds"
    folder.mkdir()
    _write_csv(folder / "A.csv", ["2024-05-30"])
    before = (folder / "A.csv").read_bytes()
    status = inc.refresh_tickers(
        ["A"], folder, dt.date(2024, 6, 4),
        lambda t, s, e: pd.DataFrame(), max_workers=1)     # empty fetch
    assert status["A"] == "failed(empty)"
    assert (folder / "A.csv").read_bytes() == before       # untouched
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m pytest tests/test_incremental.py -q -k refresh_tickers`
Expected: FAIL (`AttributeError: ... 'refresh_tickers'`)

- [ ] **Step 3: Implement (append to `core/incremental.py`)**

```python
# core/incremental.py  (append)
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

FetchFn = Callable[[str, dt.date, dt.date], pd.DataFrame]


def refresh_tickers(
    tickers,
    data_folder,
    today: dt.date,
    fetch_fn: FetchFn,
    *,
    max_workers: int = 8,
    min_rows_new: int = MIN_ROWS,
) -> dict[str, str]:
    """Plan -> fetch (only non-skip tickers) -> merge_save. Per-ticker isolated.

    fetch_fn(ticker, start, end) -> raw OHLCV DataFrame (end exclusive).
    Returns {ticker: "skipped" | "gap_appended(n)" | "full(n)" | "failed(reason)"}.
    """
    folder = Path(data_folder)
    folder.mkdir(parents=True, exist_ok=True)

    status: dict[str, str] = {}
    to_fetch: list[tuple[str, FetchPlan]] = []
    for t in tickers:
        plan = plan_fetch(folder / f"{t}.csv", today)
        if plan.kind == "skip":
            status[t] = "skipped"
        else:
            to_fetch.append((t, plan))

    def _one(item):
        ticker, plan = item
        path = folder / f"{ticker}.csv"
        existed = path.exists()
        try:
            raw = fetch_fn(ticker, plan.start, plan.end)
        except Exception as e:
            return ticker, f"failed({type(e).__name__})"
        added = merge_save(raw, path)
        if added < 0:
            return ticker, "failed(empty)"
        if not existed and plan.kind == "full":
            if len(pd.read_csv(path)) < min_rows_new:
                path.unlink(missing_ok=True)
                return ticker, "failed(min_rows)"
            return ticker, f"full({added})"
        return ticker, (f"gap_appended({added})" if plan.kind == "gap" else f"full({added})")

    if to_fetch:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            for ticker, st in ex.map(_one, to_fetch):
                status[ticker] = st
    return status


def yf_fetch(ticker: str, start: dt.date, end: dt.date) -> pd.DataFrame:
    """Real network fetch: single-ticker yfinance download for [start, end)."""
    import yfinance as yf
    return yf.download(
        ticker, start=str(start), end=str(end),
        progress=False, auto_adjust=False,
    )
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m pytest tests/test_incremental.py -q`
Expected: PASS (21 passed)

- [ ] **Step 5: Commit**

```bash
git add core/incremental.py tests/test_incremental.py
git commit -m "feat(s0b): refresh_tickers orchestration + yf_fetch"
```

---

## Task 5: `core/staleness.py`

**Files:**
- Create: `core/staleness.py`
- Test: `tests/test_staleness.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_staleness.py
import datetime as dt
import pandas as pd
from core import staleness


def _write(path, last):
    pd.DataFrame({
        "Date": [last], "Open": 1.0, "High": 1.0, "Low": 1.0,
        "Close": 1.0, "Volume": 1,
    }).to_csv(path, index=False)


def test_staleness_empty_folder(tmp_path):
    info = staleness.dataset_staleness(tmp_path, today=dt.date(2024, 6, 4))
    assert info == {"latest_date": None, "days_behind": None}


def test_staleness_up_to_date(tmp_path):
    _write(tmp_path / "A.csv", "2024-06-04")
    info = staleness.dataset_staleness(tmp_path, today=dt.date(2024, 6, 4))
    assert info["latest_date"] == dt.date(2024, 6, 4)
    assert info["days_behind"] == 0


def test_staleness_three_days_behind(tmp_path):
    _write(tmp_path / "A.csv", "2024-05-30")          # Thu
    info = staleness.dataset_staleness(tmp_path, today=dt.date(2024, 6, 4))  # Tue
    assert info["days_behind"] == 3                   # Fri, Mon, Tue


def test_staleness_uses_newest_across_files(tmp_path):
    _write(tmp_path / "A.csv", "2024-05-30")
    _write(tmp_path / "B.csv", "2024-06-04")
    info = staleness.dataset_staleness(tmp_path, today=dt.date(2024, 6, 4))
    assert info["latest_date"] == dt.date(2024, 6, 4)
    assert info["days_behind"] == 0


def test_staleness_ignores_benchmark_caret(tmp_path):
    _write(tmp_path / "^NSEI.csv", "2024-06-04")
    _write(tmp_path / "A.csv", "2024-05-30")
    info = staleness.dataset_staleness(tmp_path, today=dt.date(2024, 6, 4))
    assert info["latest_date"] == dt.date(2024, 5, 30)   # benchmark skipped
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m pytest tests/test_staleness.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'core.staleness'`)

- [ ] **Step 3: Implement `core/staleness.py`**

```python
# core/staleness.py
"""Report how many trading days behind a dataset's local CSVs are (S0b banner)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from core.incremental import last_stored_date, trading_days_between

# Tickers refresh together, so staleness is uniform; sampling a few files is
# accurate and avoids reading thousands of CSVs on every page load.
DEFAULT_SAMPLE = 25


def dataset_staleness(folder, today: dt.date | None = None, sample: int = DEFAULT_SAMPLE) -> dict:
    """Return {"latest_date": date|None, "days_behind": int|None}.

    Skips benchmark files (names starting with '^'). Reads up to `sample` files.
    """
    today = today or dt.date.today()
    folder = Path(folder)
    csvs = [p for p in sorted(folder.glob("*.csv")) if not p.name.startswith("^")]
    if sample:
        csvs = csvs[:sample]

    latest = None
    for p in csvs:
        d = last_stored_date(p)
        if d and (latest is None or d > latest):
            latest = d

    if latest is None:
        return {"latest_date": None, "days_behind": None}
    return {"latest_date": latest, "days_behind": trading_days_between(latest, today)}
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m pytest tests/test_staleness.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add core/staleness.py tests/test_staleness.py
git commit -m "feat(s0b): dataset_staleness (trading-days-behind)"
```

---

## Task 6: `core/refresh.py` — per-strategy orchestration

**Files:**
- Create: `core/refresh.py`
- Test: `tests/test_refresh.py`

**Note on `STRATEGY_CFG`:** maps strategy name → data folder, optional Parquet `dataset` (S0a), tickers source, and precompute scripts. Folders confirmed from code: Nifty-50 = `data`, Momentum = `momentum_edge_data`, IPO = `ipo_data`, wide = `data/nse_bse`. Precompute scripts confirmed present: `precompute_momentum_signals.py`, `precompute_exit_recommendations.py`.

- [ ] **Step 1: Write failing test** (subprocess + fetch mocked)

```python
# tests/test_refresh.py
import datetime as dt
import pandas as pd
import pytest
from core import refresh


def _seed(folder):
    folder.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "Date": ["2024-05-30"], "Open": 1.0, "High": 1.0, "Low": 1.0,
        "Close": 1.0, "Volume": 1,
    }).to_csv(folder / "AAA.csv", index=False)


def test_refresh_strategy_runs_fetch_sync_precompute(tmp_path, monkeypatch):
    folder = tmp_path / "ds"
    _seed(folder)

    monkeypatch.setitem(refresh.STRATEGY_CFG, "test", {
        "folder": str(folder),
        "dataset": "test_ds",
        "tickers_fn": lambda: ["AAA"],
        "precompute": ["fake_precompute.py"],
    })

    fetched = {}
    def fake_refresh_tickers(tickers, data_folder, today, fetch_fn, **kw):
        fetched["tickers"] = list(tickers)
        return {"AAA": "gap_appended(2)"}
    monkeypatch.setattr(refresh.incremental, "refresh_tickers", fake_refresh_tickers)

    ran = []
    def fake_run(cmd, **kw):
        ran.append(cmd)
        class R:  # minimal CompletedProcess stand-in
            returncode = 0
        return R()
    monkeypatch.setattr(refresh.subprocess, "run", fake_run)

    status = refresh.refresh_strategy("test")

    assert fetched["tickers"] == ["AAA"]
    assert status == {"AAA": "gap_appended(2)"}
    # one sync call + one precompute call
    assert any("convert_to_parquet.py" in " ".join(c) for c in ran)
    assert any("fake_precompute.py" in " ".join(c) for c in ran)


def test_refresh_strategy_unknown_name_raises():
    with pytest.raises(KeyError):
        refresh.refresh_strategy("does-not-exist")
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m pytest tests/test_refresh.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'core.refresh'`)

- [ ] **Step 3: Implement `core/refresh.py`**

```python
# core/refresh.py
"""Per-strategy incremental refresh orchestration (S0b).

refresh_strategy(name): fetch gaps -> sync Parquet store (S0a) -> run precompute.
Designed to be driven from a dashboard "Update now" button or the CLI.
"""
from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

from core import incremental

PY = sys.executable


def _universe_from_folder(folder: str):
    """All ticker CSVs in a folder, excluding benchmark (^) files."""
    return [p.stem for p in Path(folder).glob("*.csv") if not p.name.startswith("^")]


STRATEGY_CFG: dict[str, dict] = {
    "nifty50": {
        "folder": "data",
        "dataset": None,                         # Nifty-50 stays CSV (per S0a deferral)
        "tickers_fn": lambda: _universe_from_folder("data"),
        "precompute": [],
    },
    "momentum": {
        "folder": "momentum_edge_data",
        "dataset": "momentum_edge_data",
        "tickers_fn": lambda: _universe_from_folder("momentum_edge_data"),
        "precompute": ["precompute_momentum_signals.py", "precompute_exit_recommendations.py"],
    },
    "ipo": {
        "folder": "ipo_data",
        "dataset": "ipo_data",
        "tickers_fn": lambda: _universe_from_folder("ipo_data"),
        "precompute": [],
    },
    "nse_bse": {
        "folder": "data/nse_bse",
        "dataset": "nse_bse",
        "tickers_fn": lambda: _universe_from_folder("data/nse_bse"),
        "precompute": [],
    },
}


def refresh_strategy(name: str, st_status=None) -> dict[str, str]:
    """Run gap fetch + Parquet sync + precompute for one strategy. Returns status map.

    `st_status` (optional Streamlit st.status handle) receives progress lines.
    """
    cfg = STRATEGY_CFG[name]   # KeyError on unknown name is intentional

    def log(msg: str):
        if st_status is not None:
            st_status.write(msg)

    tickers = cfg["tickers_fn"]()
    log(f"Fetching gaps for {len(tickers)} tickers…")
    status = incremental.refresh_tickers(
        tickers, cfg["folder"], dt.date.today(), incremental.yf_fetch)

    updated = sum(1 for v in status.values() if v.startswith(("gap_appended", "full")))
    skipped = sum(1 for v in status.values() if v == "skipped")
    failed = sum(1 for v in status.values() if v.startswith("failed"))
    log(f"{updated} updated · {skipped} already current · {failed} failed.")

    if failed and updated == 0 and skipped == 0:
        raise RuntimeError(f"All {failed} tickers failed — likely network/Yahoo. Data unchanged.")

    if cfg.get("dataset"):
        log("Syncing Parquet store…")
        subprocess.run([PY, "convert_to_parquet.py", "--sync", cfg["dataset"]], check=True)

    for script in cfg.get("precompute", []):
        log(f"Precomputing ({script})…")
        subprocess.run([PY, script], check=True)

    return status
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m pytest tests/test_refresh.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add core/refresh.py tests/test_refresh.py
git commit -m "feat(s0b): refresh_strategy orchestration (fetch+sync+precompute)"
```

---

## Task 7: `core/refresh_ui.py` — Streamlit banner helper

**Files:**
- Create: `core/refresh_ui.py`

(No unit test — pure Streamlit glue, verified in the smoke run, Task 12. Logic it depends on is already tested in Tasks 5–6.)

- [ ] **Step 1: Implement `core/refresh_ui.py`**

```python
# core/refresh_ui.py
"""Streamlit staleness banner + Update button (S0b). Import lazily inside pages."""
from __future__ import annotations

import streamlit as st

from core.refresh import refresh_strategy
from core.staleness import dataset_staleness


def render_staleness_banner(strategy_name: str, dataset_folder: str) -> None:
    """Show a data-freshness banner; if behind, offer an Update button.

    strategy_name must be a key in core.refresh.STRATEGY_CFG.
    """
    info = dataset_staleness(dataset_folder)
    days_behind = info["days_behind"]
    latest = info["latest_date"]

    if days_behind is None:
        st.warning("No local data found for this strategy. Click **Update now** to download.")
    elif days_behind <= 0:
        st.success(f"✓ Data up to date ({latest})")
        return
    else:
        plural = "day" if days_behind == 1 else "days"
        st.warning(f"⚠ Data {days_behind} trading {plural} behind (latest: {latest}).")

    busy_key = f"_refreshing_{strategy_name}"
    busy = st.session_state.get(busy_key, False)

    if st.button("Update now", key=f"upd_{strategy_name}", disabled=busy):
        st.session_state[busy_key] = True
        try:
            with st.status(f"Updating {strategy_name}…", expanded=True) as status_box:
                refresh_strategy(strategy_name, st_status=status_box)
                status_box.update(label="Update complete", state="complete")
            st.cache_data.clear()
            st.rerun()
        except Exception as exc:                       # surface, keep data intact
            st.error(f"Update failed: {exc}")
        finally:
            st.session_state[busy_key] = False
```

- [ ] **Step 2: Import-smoke check**

Run: `python -c "import core.refresh_ui; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add core/refresh_ui.py
git commit -m "feat(s0b): refresh_ui staleness banner + Update button"
```

---

## Task 8: Refactor `step1_download_data.py` (Nifty-50) to use the engine

**Files:**
- Modify: `step1_download_data.py`

**Context:** currently loops tickers calling `yf.download(start, end)` then `data.to_csv(csv_path)` (full overwrite, ~line 96–120). Replace the per-ticker download+save with a single `refresh_tickers` call so it becomes gap-aware. Keep the existing ticker-list construction and the success/failure summary printing.

- [ ] **Step 1: Locate the download loop**

Run: `grep -n "yf.download\|to_csv\|for ticker\|csv_path\|start_date\|end_date" step1_download_data.py`
Expected: shows the loop (~line 90–125) and the data folder.

- [ ] **Step 2: Replace the loop with `refresh_tickers`**

Add near the imports:
```python
import datetime as dt
from core import incremental
```

Replace the per-ticker download/save loop body with a single call (keep the ticker list build + final summary). The data folder for Nifty-50 is `data`:
```python
    status = incremental.refresh_tickers(
        tickers, "data", dt.date.today(), incremental.yf_fetch)
    successful = [t for t, s in status.items() if not s.startswith("failed")]
    failed = [(t, s) for t, s in status.items() if s.startswith("failed")]
    print(f"  Updated/current: {len(successful)}   Failed: {len(failed)}")
    for t, s in failed:
        print(f"    {t}: {s}")
```
> `tickers` here is the existing list of `.NS` symbols the script already builds. Do not change how that list is produced.

- [ ] **Step 3: Smoke-run (network; small universe)**

Run: `python step1_download_data.py`
Expected: completes; second consecutive run reports most tickers current (few/zero downloads). Spot-check a CSV's last Date is recent.

- [ ] **Step 4: Commit**

```bash
git add step1_download_data.py
git commit -m "refactor(s0b): Nifty-50 downloader uses incremental engine"
```

---

## Task 9: Refactor `momentum_edge_downloader.py`

**Files:**
- Modify: `momentum_edge_downloader.py`

**Context:** `DATA_FOLDER = 'momentum_edge_data'`. Currently `yf.download(start, end)` then `df.to_csv(out_path)` per ticker (~line 56–134), plus a benchmark download and a `me_summary.csv`. Replace the per-ticker price download/save with `refresh_tickers`; **leave the benchmark download and summary code unchanged**.

- [ ] **Step 1: Locate loop + benchmark**

Run: `grep -n "yf.download\|to_csv\|DATA_FOLDER\|BENCHMARK\|for ticker\|summary" momentum_edge_downloader.py`

- [ ] **Step 2: Replace the per-ticker price loop**

Add imports:
```python
import datetime as dt
from core import incremental
```
Replace the price-download loop (not the benchmark/summary) with:
```python
    status = incremental.refresh_tickers(
        tickers, DATA_FOLDER, dt.date.today(), incremental.yf_fetch)
    counts = {
        "ok": sum(1 for s in status.values() if not s.startswith("failed")),
        "fail": sum(1 for s in status.values() if s.startswith("failed")),
    }
    print(f'  Saved/current : {counts["ok"]}  ·  Failed : {counts["fail"]}  →  {DATA_FOLDER}/')
```
> `tickers` = the existing momentum universe list the script already builds. Keep the benchmark (`^NSEI`) download and `me_summary.csv` write exactly as they are.

- [ ] **Step 3: Smoke-run**

Run: `python momentum_edge_downloader.py`
Expected: completes; re-run shows tickers current. Benchmark + summary still written.

- [ ] **Step 4: Commit**

```bash
git add momentum_edge_downloader.py
git commit -m "refactor(s0b): momentum downloader uses incremental engine"
```

---

## Task 10: Refactor `ipo_edge_downloader.py`

**Files:**
- Modify: `ipo_edge_downloader.py`

**Context:** `DATA_FOLDER = 'ipo_data'`. Same pattern: per-ticker `yf.download(start, end)` + `to_csv` (~line 225–324), plus benchmark + summary. IPO tickers are recently listed, so most will FULL-backfill on first run and gap-update after. Replace only the per-ticker price loop.

- [ ] **Step 1: Locate loop**

Run: `grep -n "yf.download\|to_csv\|DATA_FOLDER\|BENCHMARK\|summary\|for ticker" ipo_edge_downloader.py`

- [ ] **Step 2: Replace the per-ticker price loop**

Add imports:
```python
import datetime as dt
from core import incremental
```
Replace the price loop with:
```python
    status = incremental.refresh_tickers(
        tickers, DATA_FOLDER, dt.date.today(), incremental.yf_fetch)
    ok = sum(1 for s in status.values() if not s.startswith("failed"))
    fail = sum(1 for s in status.values() if s.startswith("failed"))
    print(f'  Saved/current : {ok}  ·  Failed : {fail}  →  {DATA_FOLDER}/')
```
> Keep the listing-age filter, benchmark download, and summary writer unchanged. `tickers` = the existing IPO universe list.

> **Note on short-history IPOs:** a freshly listed IPO with < `MIN_ROWS` (100) bars will be discarded by `refresh_tickers` (`failed(min_rows)`) — matching the prior `MIN_ROWS` discard behavior. If IPO Edge needs sub-100-bar names, pass `min_rows_new=<lower>` to `refresh_tickers`. Default keeps existing behavior.

- [ ] **Step 3: Smoke-run**

Run: `python ipo_edge_downloader.py`
Expected: completes; CSVs written for IPOs with ≥100 bars.

- [ ] **Step 4: Commit**

```bash
git add ipo_edge_downloader.py
git commit -m "refactor(s0b): IPO downloader uses incremental engine"
```

---

## Task 11: Migrate `nse_bse_downloader.py` onto the shared engine

**Files:**
- Modify: `nse_bse_downloader.py`

**Context:** this file already has `_is_fresh`, `_standardize`, `_merge_with_existing`, `_save`, and a batch downloader (`_parse_batch_result`, `_run_batches`) over ~2300 symbols. Goal: **remove the duplicated standardize/merge logic** and route saves through `core.incremental.merge_save`, and use `plan_fetch` to decide per-symbol start dates — while **keeping the efficient batch `yf.download(group_by='ticker')`** (per-ticker fetching 2300 symbols would be too slow).

- [ ] **Step 1: Delete the local duplicates, import the engine**

Add import:
```python
from core import incremental
```
Remove `_standardize`, `_merge_with_existing`, `_save` (now in `core.incremental` as `standardize`, `merge_save`). Keep `_is_fresh` as an optional mtime pre-filter (cheap skip before reading max-Date).

- [ ] **Step 2: Use `plan_fetch` for classification + `merge_save` for writes**

In the classification phase (~line 304–320), replace the mtime-only fresh/stale/full split with `plan_fetch` per symbol to get each symbol's fetch start; group symbols that need fetching into batches as before. After a batch returns, for each symbol's frame call:
```python
    incremental.merge_save(symbol_df, data_folder / f"{sym}.csv")
```
instead of `_save(_merge_with_existing(_standardize(df), path), path)`.

> Keep the batch sizing (`BATCH_SIZE`), `BATCH_SLEEP`, retry pass, benchmark, and status/failed CSV outputs. Only the standardize+merge+save and the staleness decision change.

- [ ] **Step 3: Run the store tests (ensure CSV shape unchanged)**

Run: `python -m pytest tests/test_store.py tests/test_convert_to_parquet.py -q`
Expected: PASS (CSV schema consumed by S0a is unchanged).

- [ ] **Step 4: Smoke-run a small slice**

Run: `python nse_bse_downloader.py` (or interrupt after a couple batches)
Expected: batches download; re-run skips fresh symbols quickly.

- [ ] **Step 5: Commit**

```bash
git add nse_bse_downloader.py
git commit -m "refactor(s0b): nse_bse downloader reuses core.incremental (dedup)"
```

---

## Task 12: Wire banner into dashboards + integration smoke + memory

**Files:**
- Modify: `momentum_edge_dashboard.py`, `dashboard_visual.py`, `ipo_edge_dashboard.py`, `master_dashboard.py`

- [ ] **Step 1: Add the banner to each dashboard (top of the main render, after page config)**

Momentum (`momentum_edge_dashboard.py`, folder `momentum_edge_data`):
```python
from core.refresh_ui import render_staleness_banner
render_staleness_banner("momentum", "momentum_edge_data")
```
Monthly Rotation (`dashboard_visual.py`, folder `data`):
```python
from core.refresh_ui import render_staleness_banner
render_staleness_banner("nifty50", "data")
```
IPO Edge (`ipo_edge_dashboard.py`, folder `ipo_data`):
```python
from core.refresh_ui import render_staleness_banner
render_staleness_banner("ipo", "ipo_data")
```
Master hub PEAD page (`master_dashboard.py`): PEAD has its own incremental downloader; show the wide-universe freshness instead:
```python
from core.refresh_ui import render_staleness_banner
render_staleness_banner("nse_bse", "data/nse_bse")
```
> Place the call where it renders once at the top of the page body. Match each file's existing import block style.

- [ ] **Step 2: Import-smoke every dashboard (no Streamlit server needed)**

Run:
```bash
python -c "import ast,sys; [ast.parse(open(f,encoding='utf-8').read()) for f in ['momentum_edge_dashboard.py','dashboard_visual.py','ipo_edge_dashboard.py','master_dashboard.py']]; print('syntax ok')"
```
Expected: `syntax ok`

- [ ] **Step 3: Full unit-test run + coverage**

Run: `python -m pytest tests/test_incremental.py tests/test_staleness.py tests/test_refresh.py --cov=core.incremental --cov=core.staleness --cov=core.refresh --cov-report=term-missing -q`
Expected: PASS; coverage ≥80% on `core/incremental.py` and `core/staleness.py`.

- [ ] **Step 4: Live banner smoke**

Run: `streamlit run momentum_edge_dashboard.py --server.port 8503`
Manually: confirm the banner shows freshness; if behind, click **Update now**, watch the status box step through fetch → sync → precompute, and the page reruns showing the new latest date. (Stop the server after.)

- [ ] **Step 5: Update roadmap memory + commit**

Edit `C:\Users\User\.claude\projects\C--Users-User-Documents-Stocks-Nifty-Momentum-Rotation-Stratergy\memory\platform_v2_roadmap.md`: note S0b shipped as **local incremental catch-up** (not cloud); cloud (R2/Actions/VM) deferred. Add a new memory file `s0b_incremental_catchup.md` + an index line in `MEMORY.md`.

```bash
git add momentum_edge_dashboard.py dashboard_visual.py ipo_edge_dashboard.py master_dashboard.py
git commit -m "feat(s0b): staleness banner + Update button on dashboards"
```

---

## Self-Review

**Spec coverage:**
- §4 architecture (4 new modules + refactors) → Tasks 1–12. ✓
- §5 fetch logic (plan_fetch always-gap, last-bar-date staleness, end+1, trading-day aware, batched, atomic merge, idempotent) → Tasks 2–4. ✓
- §6 UI (banner from staleness, Update→fetch+sync+precompute, st.status, cache clear+rerun, banner-only launch, concurrency guard via session_state) → Tasks 5–7, 12. ✓
- §7 error handling (per-ticker isolation, empty=no-op, atomic merge, network-wide failure message, UI catch, boundary validation) → Tasks 3,4,6,7. ✓
- §8 testing (all listed cases + integration + ≥80% coverage) → Tasks 1–6, 12. ✓
- §9 deviation-from-roadmap memory update → Task 12 Step 5. ✓
- §10 open questions: holiday calendar → weekday approximation documented (Task 1 docstring); `FULL_LOOKBACK` reuse → `FULL_LOOKBACK_DAYS` constant; mtime pre-filter → kept optional in nse_bse (Task 11 Step 1). ✓

**Placeholder scan:** no TBD/TODO; every code step shows complete code. ✓

**Type consistency:** `FetchPlan(kind,start,end)`, `plan_fetch`, `merge_save`→int, `refresh_tickers`→`dict[str,str]` with statuses `skipped|gap_appended(n)|full(n)|failed(reason)`, `dataset_staleness`→`{latest_date,days_behind}`, `refresh_strategy(name, st_status=None)`, `render_staleness_banner(strategy_name, dataset_folder)`. Names consistent across tasks and the spec. ✓
