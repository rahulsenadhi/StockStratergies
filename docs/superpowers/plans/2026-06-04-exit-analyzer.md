# Hold-Period & Exit-Ladder Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a data-driven recommendation — best holding duration plus a 3-tier scale-out ladder and stop — next to each strategy's live entry signals, computed from historical post-entry price paths.

**Architecture:** A pure analysis module (`core/exit_analyzer.py`) computes per-strategy recommendations from historical entries + OHLCV. A precompute script writes one `exit_recommendations.json`. The dashboard reads that JSON and renders a compact badge per signal row plus an "Exit Playbook" card per page. Backtests are untouched — this is an advisory overlay.

**Tech Stack:** Python 3, pandas, numpy, pytest, Streamlit, Plotly. Reuses `core/data_io.load_ohlcv`, `core/rotation_trades.build` / `build_pseudo_ohlcv`.

**Spec:** `docs/superpowers/specs/2026-06-04-exit-analyzer-design.md`

---

## File Structure

- Create: `core/exit_analyzer.py` — pure analysis functions + `Recommendation`/`Target` dataclasses.
- Create: `tests/test_exit_analyzer.py` — pure-function unit tests.
- Create: `precompute_exit_recommendations.py` — pipeline step → `exit_recommendations.json`.
- Modify: `run_all.py` — add the precompute step after backtests.
- Modify: `refresh_data.bat` — add the precompute step after backtests.
- Modify: `master_dashboard.py` — `load_exit_recs()`, `_exit_badge()`, `_exit_playbook_card()`, wired into `render_monthly`/`render_ipo`/`render_momentum`.
- Modify: `pead_dashboard.py` — render the card + badge on the PEAD page.

**Data contract — `entries` DataFrame:** columns `ticker` (str), `entry_date` (pd.Timestamp), `entry_price` (float), and optional `bucket` (str). All analyzer functions consume this shape.

---

## Task 1: Module skeleton — constants & dataclasses

**Files:**
- Create: `core/exit_analyzer.py`
- Test: `tests/test_exit_analyzer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_exit_analyzer.py
import pandas as pd
import numpy as np
import pytest

from core import exit_analyzer as ea


def test_constants_and_dataclasses_exist():
    assert ea.MAX_HORIZON_DAYS == 90
    assert ea.TARGET_PERCENTILES == (40, 65, 85)
    assert ea.BOOK_FRACTIONS == (40, 35, 25)
    assert ea.STOP_PERCENTILE == 75
    assert ea.MIN_SAMPLE == 20
    assert ea.MAE_FLOOR == 0.5

    t = ea.Target(pct=6.0, book_pct=40, hit_rate=0.78)
    assert t.pct == 6.0 and t.book_pct == 40

    rec = ea.Recommendation(
        strategy="x", bucket="ALL", hold_days=10, hold_median_return=1.0,
        hold_win_rate=0.5, targets=[t], stop_pct=-8.0, sample_size=30,
        data_quality="ohlcv", curve=[{"day": 1, "median": 0.1}],
    )
    d = rec.to_dict()
    assert d["strategy"] == "x"
    assert d["targets"][0]["pct"] == 6.0
    assert d["sample_size"] == 30
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_exit_analyzer.py::test_constants_and_dataclasses_exist -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.exit_analyzer'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/exit_analyzer.py
"""Hold-period & exit-ladder analyzer.

Pure functions (no Streamlit, no network). Given a strategy's historical entries
and an OHLCV price panel, computes:
  - the risk-adjusted best holding duration,
  - a 3-tier scale-out ladder (profit targets + booking %),
  - a stop level,
from the historical post-entry return / MFE / MAE distributions.

All inputs use the standard `entries` DataFrame contract:
    columns: ticker (str), entry_date (Timestamp), entry_price (float),
             optional bucket (str)
The price panel is a dict ticker -> OHLCV DataFrame (Date index, columns
Open/High/Low/Close/Volume), as produced by core.data_io.load_ohlcv or
core.rotation_trades.build_pseudo_ohlcv (close-only -> High==Low==Close).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

MAX_HORIZON_DAYS = 90          # trading days of post-entry path to study
TARGET_PERCENTILES = (40, 65, 85)   # MFE percentiles -> profit targets
BOOK_FRACTIONS = (40, 35, 25)       # % of position booked at each target
STOP_PERCENTILE = 75           # % of trades that should stay above the stop
MIN_SAMPLE = 20                # min entries for a recommendation / bucket
MAE_FLOOR = 0.5                # % floor on denominator of risk-adjusted score


@dataclass
class Target:
    pct: float
    book_pct: int
    hit_rate: float


@dataclass
class Recommendation:
    strategy: str
    bucket: str
    hold_days: int
    hold_median_return: float
    hold_win_rate: float
    targets: list          # list[Target]
    stop_pct: float
    sample_size: int
    data_quality: str      # 'ohlcv' | 'close'
    curve: list            # list[dict]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["targets"] = [asdict(t) if isinstance(t, Target) else t for t in self.targets]
        return d
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_exit_analyzer.py::test_constants_and_dataclasses_exist -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/exit_analyzer.py tests/test_exit_analyzer.py
git commit -m "feat(exit-analyzer): module skeleton with constants and dataclasses"
```

---

## Task 2: Per-entry post-entry path (`build_entry_path`)

**Files:**
- Modify: `core/exit_analyzer.py`
- Test: `tests/test_exit_analyzer.py`

- [ ] **Step 1: Write the failing test**

```python
def _ohlcv(dates, highs, lows, closes):
    idx = pd.to_datetime(dates)
    return pd.DataFrame(
        {"Open": closes, "High": highs, "Low": lows, "Close": closes, "Volume": 0},
        index=idx,
    )


def test_build_entry_path_mfe_mae_running():
    # entry on day 0 at 100. Forward 3 days.
    df = _ohlcv(
        ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        highs=[100, 110, 105, 108],
        lows=[100, 98, 90, 102],
        closes=[100, 108, 95, 106],
    )
    path = ea.build_entry_path(df, pd.Timestamp("2024-01-01"), 100.0, max_horizon=3)
    # day offsets 1..3 (strictly after entry_date)
    assert list(path["day"]) == [1, 2, 3]
    # ret = close/entry - 1, in %
    assert path["ret"].tolist() == pytest.approx([8.0, -5.0, 6.0])
    # running MFE uses High: max(110,105,108)/100 -1 -> 10 at d1(110), stays 10
    assert path["mfe"].tolist() == pytest.approx([10.0, 10.0, 10.0])
    # running MAE uses Low: min so far: -2 (98), then -10 (90), then -10
    assert path["mae"].tolist() == pytest.approx([-2.0, -10.0, -10.0])


def test_build_entry_path_short_history():
    df = _ohlcv(["2024-01-01", "2024-01-02"], [100, 101], [100, 99], [100, 100.5])
    path = ea.build_entry_path(df, pd.Timestamp("2024-01-01"), 100.0, max_horizon=90)
    assert list(path["day"]) == [1]   # only one day available after entry
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_exit_analyzer.py -k build_entry_path -v`
Expected: FAIL — `AttributeError: module 'core.exit_analyzer' has no attribute 'build_entry_path'`

- [ ] **Step 3: Write minimal implementation**

Append to `core/exit_analyzer.py`:

```python
def build_entry_path(
    ohlcv: pd.DataFrame,
    entry_date: pd.Timestamp,
    entry_price: float,
    max_horizon: int = MAX_HORIZON_DAYS,
) -> pd.DataFrame:
    """Return a DataFrame of the post-entry path with running MFE/MAE.

    Columns: day (1-based offset), ret, mfe, mae — all in percent vs entry_price.
    Rows are the trading days strictly after entry_date, up to max_horizon.
    Returns an empty DataFrame if no forward data or entry_price is invalid.
    """
    cols = ["day", "ret", "mfe", "mae"]
    if ohlcv is None or ohlcv.empty or not entry_price or entry_price <= 0:
        return pd.DataFrame(columns=cols)

    fwd = ohlcv[ohlcv.index > pd.Timestamp(entry_date)].head(max_horizon)
    if fwd.empty:
        return pd.DataFrame(columns=cols)

    close = fwd["Close"].to_numpy(dtype=float)
    high = fwd["High"].to_numpy(dtype=float)
    low = fwd["Low"].to_numpy(dtype=float)

    ret = (close / entry_price - 1.0) * 100.0
    fav = (high / entry_price - 1.0) * 100.0
    adv = (low / entry_price - 1.0) * 100.0
    mfe = np.maximum.accumulate(fav)
    mae = np.minimum.accumulate(adv)

    return pd.DataFrame(
        {"day": np.arange(1, len(fwd) + 1), "ret": ret, "mfe": mfe, "mae": mae}
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_exit_analyzer.py -k build_entry_path -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add core/exit_analyzer.py tests/test_exit_analyzer.py
git commit -m "feat(exit-analyzer): per-entry post-entry path with running MFE/MAE"
```

---

## Task 3: Build matrix across entries (`build_matrix`)

**Files:**
- Modify: `core/exit_analyzer.py`
- Test: `tests/test_exit_analyzer.py`

- [ ] **Step 1: Write the failing test**

```python
def test_build_matrix_collects_paths_and_excursions():
    df_a = _ohlcv(
        ["2024-01-01", "2024-01-02", "2024-01-03"],
        highs=[100, 112, 108], lows=[100, 99, 95], closes=[100, 110, 104],
    )
    df_b = _ohlcv(
        ["2024-01-01", "2024-01-02", "2024-01-03"],
        highs=[50, 51, 60], lows=[50, 45, 48], closes=[50, 48, 58],
    )
    ohlcv = {"A": df_a, "B": df_b}
    entries = pd.DataFrame({
        "ticker": ["A", "B", "MISSING"],
        "entry_date": pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-01"]),
        "entry_price": [100.0, 50.0, 10.0],
    })

    paths, mfe_arr, mae_arr, skipped = ea.build_matrix(entries, ohlcv, max_horizon=2)

    assert len(paths) == 2          # MISSING has no price data
    assert skipped == 1
    # per-entry overall MFE: A -> 12 (112), B -> 20 (60 not reached in 2 days -> 51 => 2)
    assert sorted(np.round(mfe_arr, 2).tolist()) == [2.0, 12.0]
    # per-entry overall MAE: A -> -1 (99), B -> -10 (45)
    assert sorted(np.round(mae_arr, 2).tolist()) == [-10.0, -1.0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_exit_analyzer.py -k build_matrix -v`
Expected: FAIL — no attribute `build_matrix`

- [ ] **Step 3: Write minimal implementation**

Append:

```python
def build_matrix(
    entries: pd.DataFrame,
    ohlcv: dict,
    max_horizon: int = MAX_HORIZON_DAYS,
) -> tuple[list, np.ndarray, np.ndarray, int]:
    """Build per-entry paths and overall excursion arrays.

    Returns (paths, mfe_arr, mae_arr, skipped):
      paths   - list of per-entry path DataFrames (from build_entry_path)
      mfe_arr - np.array of each entry's overall max-favorable-excursion %
      mae_arr - np.array of each entry's overall max-adverse-excursion %
      skipped - count of entries with no usable forward price data
    """
    paths: list = []
    mfes: list = []
    maes: list = []
    skipped = 0

    for row in entries.itertuples(index=False):
        df = ohlcv.get(row.ticker)
        path = build_entry_path(df, row.entry_date, row.entry_price, max_horizon)
        if path.empty:
            skipped += 1
            continue
        paths.append(path)
        mfes.append(float(path["mfe"].iloc[-1]))
        maes.append(float(path["mae"].iloc[-1]))

    return paths, np.array(mfes), np.array(maes), skipped
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_exit_analyzer.py -k build_matrix -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/exit_analyzer.py tests/test_exit_analyzer.py
git commit -m "feat(exit-analyzer): build cross-entry matrix and excursion arrays"
```

---

## Task 4: Return-by-day curve + best hold day

**Files:**
- Modify: `core/exit_analyzer.py`
- Test: `tests/test_exit_analyzer.py`

- [ ] **Step 1: Write the failing test**

```python
def test_aggregate_curve_handles_ragged_paths():
    p1 = pd.DataFrame({"day": [1, 2, 3], "ret": [2.0, 4.0, 6.0],
                       "mfe": [2, 4, 6], "mae": [-1.0, -1.0, -2.0]})
    p2 = pd.DataFrame({"day": [1, 2], "ret": [0.0, 8.0],
                       "mfe": [0, 8], "mae": [-3.0, -3.0]})
    curve = ea.aggregate_curve([p1, p2], max_horizon=3)
    # day 1: ret median of [2,0] = 1.0 ; n=2
    row1 = curve[curve["day"] == 1].iloc[0]
    assert row1["median"] == pytest.approx(1.0)
    assert row1["n"] == 2
    assert row1["mae"] == pytest.approx(-2.0)   # avg of [-1,-3]
    # day 3: only p1 contributes
    row3 = curve[curve["day"] == 3].iloc[0]
    assert row3["median"] == pytest.approx(6.0)
    assert row3["n"] == 1


def test_best_hold_day_is_risk_adjusted():
    # day 5 has higher raw return but huge MAE; day 3 wins on risk-adjusted score
    curve = pd.DataFrame({
        "day": [3, 5],
        "median": [6.0, 9.0],
        "mae": [-2.0, -9.0],
        "win_rate": [0.7, 0.55],
        "n": [40, 40],
    })
    day, med, win = ea.best_hold_day(curve)
    assert day == 3            # 6/2=3.0  vs  9/9=1.0
    assert med == pytest.approx(6.0)
    assert win == pytest.approx(0.7)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_exit_analyzer.py -k "aggregate_curve or best_hold_day" -v`
Expected: FAIL — no attribute `aggregate_curve`

- [ ] **Step 3: Write minimal implementation**

Append:

```python
def aggregate_curve(paths: list, max_horizon: int = MAX_HORIZON_DAYS) -> pd.DataFrame:
    """Aggregate per-entry paths into a return-by-day curve.

    Columns: day, median, mean, p25, p75, mae (avg adverse), win_rate, n.
    Each day aggregates only the entries that have data for that offset.
    """
    rows = []
    for d in range(1, max_horizon + 1):
        rets = [p.loc[p["day"] == d, "ret"].iloc[0]
                for p in paths if (p["day"] == d).any()]
        maes = [p.loc[p["day"] == d, "mae"].iloc[0]
                for p in paths if (p["day"] == d).any()]
        if not rets:
            continue
        arr = np.array(rets, dtype=float)
        rows.append({
            "day": d,
            "median": float(np.median(arr)),
            "mean": float(np.mean(arr)),
            "p25": float(np.percentile(arr, 25)),
            "p75": float(np.percentile(arr, 75)),
            "mae": float(np.mean(maes)),
            "win_rate": float(np.mean(arr > 0)),
            "n": int(len(arr)),
        })
    return pd.DataFrame(rows)


def best_hold_day(curve: pd.DataFrame) -> tuple[int, float, float]:
    """Pick the day maximizing median_return / max(|avg_MAE|, MAE_FLOOR).

    Returns (day, median_return, win_rate). Returns (0, 0.0, 0.0) on empty curve.
    """
    if curve is None or curve.empty:
        return 0, 0.0, 0.0
    denom = np.maximum(np.abs(curve["mae"].to_numpy()), MAE_FLOOR)
    score = curve["median"].to_numpy() / denom
    idx = int(np.argmax(score))
    row = curve.iloc[idx]
    return int(row["day"]), float(row["median"]), float(row["win_rate"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_exit_analyzer.py -k "aggregate_curve or best_hold_day" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/exit_analyzer.py tests/test_exit_analyzer.py
git commit -m "feat(exit-analyzer): return-by-day curve and risk-adjusted best hold day"
```

---

## Task 5: Exit ladder + stop (`exit_ladder`)

**Files:**
- Modify: `core/exit_analyzer.py`
- Test: `tests/test_exit_analyzer.py`

- [ ] **Step 1: Write the failing test**

```python
def test_exit_ladder_targets_and_stop():
    # 10 entries, MFE evenly spread 2..20, MAE spread -1..-10
    mfe = np.array([2, 4, 6, 8, 10, 12, 14, 16, 18, 20], dtype=float)
    mae = np.array([-1, -2, -3, -4, -5, -6, -7, -8, -9, -10], dtype=float)
    targets, stop = ea.exit_ladder(mfe, mae)

    assert [t.book_pct for t in targets] == [40, 35, 25]
    # percentiles 40/65/85 of mfe
    assert targets[0].pct == pytest.approx(np.percentile(mfe, 40), abs=0.5)
    assert targets[2].pct == pytest.approx(np.percentile(mfe, 85), abs=0.5)
    # hit_rate = fraction of entries whose MFE >= target pct
    assert 0.0 <= targets[0].hit_rate <= 1.0
    assert targets[0].hit_rate >= targets[2].hit_rate
    # stop = percentile of MAE leaving STOP_PERCENTILE(75)% of trades above it
    assert stop == pytest.approx(np.percentile(mae, 100 - ea.STOP_PERCENTILE), abs=0.5)
    assert stop < 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_exit_analyzer.py -k exit_ladder -v`
Expected: FAIL — no attribute `exit_ladder`

- [ ] **Step 3: Write minimal implementation**

Append:

```python
def exit_ladder(mfe_arr: np.ndarray, mae_arr: np.ndarray) -> tuple[list, float]:
    """Derive 3 profit targets (from MFE percentiles) + a stop (from MAE).

    Returns (targets, stop_pct):
      targets  - list[Target] at TARGET_PERCENTILES of the MFE distribution,
                 each booking BOOK_FRACTIONS of the position, with the historical
                 hit-rate (fraction of entries whose MFE reached the target).
      stop_pct - negative %; the (100 - STOP_PERCENTILE)th percentile of MAE,
                 i.e. the level STOP_PERCENTILE% of trades stayed above.
    """
    targets: list = []
    for pct_rank, book in zip(TARGET_PERCENTILES, BOOK_FRACTIONS):
        tgt = float(np.percentile(mfe_arr, pct_rank))
        hit = float(np.mean(mfe_arr >= tgt))
        targets.append(Target(pct=round(tgt, 1), book_pct=int(book),
                              hit_rate=round(hit, 2)))
    stop = float(np.percentile(mae_arr, 100 - STOP_PERCENTILE))
    return targets, round(stop, 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_exit_analyzer.py -k exit_ladder -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/exit_analyzer.py tests/test_exit_analyzer.py
git commit -m "feat(exit-analyzer): 3-tier exit ladder and MAE-based stop"
```

---

## Task 6: Orchestration — `analyze` + `analyze_with_buckets`

**Files:**
- Modify: `core/exit_analyzer.py`
- Test: `tests/test_exit_analyzer.py`

- [ ] **Step 1: Write the failing test**

```python
def _make_entries(n, ticker="A", price=100.0, bucket=None):
    data = {
        "ticker": [ticker] * n,
        "entry_date": pd.to_datetime(["2024-01-01"] * n),
        "entry_price": [price] * n,
    }
    if bucket is not None:
        data["bucket"] = bucket
    return pd.DataFrame(data)


def _rising_ohlcv():
    dates = pd.bdate_range("2024-01-01", periods=40)
    closes = np.linspace(100, 140, 40)
    return {"A": pd.DataFrame(
        {"Open": closes, "High": closes * 1.01, "Low": closes * 0.99,
         "Close": closes, "Volume": 0}, index=dates)}


def test_analyze_returns_none_below_min_sample():
    entries = _make_entries(5)
    rec = ea.analyze(entries, _rising_ohlcv(), strategy="t", data_quality="ohlcv")
    assert rec is None


def test_analyze_returns_recommendation():
    entries = _make_entries(25)
    rec = ea.analyze(entries, _rising_ohlcv(), strategy="t", data_quality="ohlcv")
    assert rec is not None
    assert rec.strategy == "t"
    assert rec.bucket == "ALL"
    assert rec.sample_size == 25
    assert rec.hold_days >= 1
    assert len(rec.targets) == 3
    assert rec.stop_pct <= 0
    assert rec.data_quality == "ohlcv"
    assert len(rec.curve) >= 1
    # serializable
    import json
    json.dumps(rec.to_dict())


def test_analyze_with_buckets_falls_back_below_min_sample():
    # 25 'BIG' (kept) + 5 'small' (dropped as a bucket, still in ALL)
    big = _make_entries(25, bucket=["BIG"] * 25)
    small = _make_entries(5, bucket=["small"] * 5)
    entries = pd.concat([big, small], ignore_index=True)
    recs = ea.analyze_with_buckets(
        entries, _rising_ohlcv(), strategy="t", data_quality="ohlcv",
        bucket_col="bucket",
    )
    assert "ALL" in recs
    assert recs["ALL"].sample_size == 30
    assert "BIG" in recs            # >= MIN_SAMPLE
    assert "small" not in recs      # below MIN_SAMPLE -> dropped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_exit_analyzer.py -k "analyze" -v`
Expected: FAIL — no attribute `analyze`

- [ ] **Step 3: Write minimal implementation**

Append:

```python
def analyze(
    entries: pd.DataFrame,
    ohlcv: dict,
    strategy: str,
    data_quality: str,
    bucket: str = "ALL",
    max_horizon: int = MAX_HORIZON_DAYS,
) -> Recommendation | None:
    """Compute a single Recommendation, or None if fewer than MIN_SAMPLE usable
    entries have price data."""
    paths, mfe_arr, mae_arr, _skipped = build_matrix(entries, ohlcv, max_horizon)
    if len(paths) < MIN_SAMPLE:
        return None

    curve = aggregate_curve(paths, max_horizon)
    hold_days, hold_med, hold_win = best_hold_day(curve)
    targets, stop = exit_ladder(mfe_arr, mae_arr)

    return Recommendation(
        strategy=strategy,
        bucket=bucket,
        hold_days=hold_days,
        hold_median_return=round(hold_med, 2),
        hold_win_rate=round(hold_win, 2),
        targets=targets,
        stop_pct=stop,
        sample_size=len(paths),
        data_quality=data_quality,
        curve=[{k: round(float(v), 3) for k, v in row.items()}
               for row in curve.to_dict("records")],
    )


def analyze_with_buckets(
    entries: pd.DataFrame,
    ohlcv: dict,
    strategy: str,
    data_quality: str,
    bucket_col: str | None = None,
    max_horizon: int = MAX_HORIZON_DAYS,
) -> dict:
    """Return {'ALL': Recommendation, <bucket>: Recommendation, ...}.

    The 'ALL' key is always attempted. If bucket_col is given, each bucket value
    with >= MIN_SAMPLE entries also gets its own recommendation; smaller buckets
    are skipped (callers fall back to 'ALL'). Buckets that fail the price-data
    threshold inside analyze() are also skipped.
    """
    out: dict = {}
    all_rec = analyze(entries, ohlcv, strategy, data_quality, "ALL", max_horizon)
    if all_rec is not None:
        out["ALL"] = all_rec

    if bucket_col and bucket_col in entries.columns:
        for val, grp in entries.groupby(bucket_col):
            if grp[bucket_col].isna().all() or len(grp) < MIN_SAMPLE:
                continue
            rec = analyze(grp, ohlcv, strategy, data_quality, str(val), max_horizon)
            if rec is not None:
                out[str(val)] = rec
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_exit_analyzer.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add core/exit_analyzer.py tests/test_exit_analyzer.py
git commit -m "feat(exit-analyzer): analyze orchestration with bucket fallback"
```

---

## Task 7: Precompute script — `precompute_exit_recommendations.py`

**Files:**
- Create: `precompute_exit_recommendations.py`
- Test: `tests/test_exit_analyzer.py` (entry-loader unit tests)

- [ ] **Step 1: Write the failing test**

```python
def test_load_entries_momentum_normalizes_columns(tmp_path):
    import precompute_exit_recommendations as pre
    csv = tmp_path / "trades.csv"
    pd.DataFrame({
        "Ticker": ["A.NS", "B.NS"],
        "Entry_Date": ["2024-01-01", "2024-02-01"],
        "Entry_Price": [100.0, 50.0],
        "Entry_Type": ["ATH", "ATH"],
    }).to_csv(csv, index=False)

    entries = pre.load_entries_generic(
        str(csv), ticker_col="Ticker", date_col="Entry_Date",
        price_col="Entry_Price", bucket_col="Entry_Type",
    )
    assert list(entries.columns) == ["ticker", "entry_date", "entry_price", "bucket"]
    assert entries["ticker"].tolist() == ["A.NS", "B.NS"]
    assert pd.api.types.is_datetime64_any_dtype(entries["entry_date"])
    assert entries["entry_price"].tolist() == [100.0, 50.0]


def test_load_entries_generic_missing_file_returns_empty(tmp_path):
    import precompute_exit_recommendations as pre
    entries = pre.load_entries_generic(
        str(tmp_path / "nope.csv"), ticker_col="Ticker",
        date_col="Entry_Date", price_col="Entry_Price",
    )
    assert entries.empty
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_exit_analyzer.py -k load_entries -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'precompute_exit_recommendations'`

- [ ] **Step 3: Write minimal implementation**

```python
# precompute_exit_recommendations.py
"""Precompute hold-period & exit-ladder recommendations for all strategies.

Runs once in the data pipeline (after the backtests). For each strategy it loads
historical entries + an OHLCV panel, calls core.exit_analyzer, and writes one
exit_recommendations.json keyed by strategy. The dashboard reads that file.

Run:  python precompute_exit_recommendations.py
Output (project root):  exit_recommendations.json
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from core import exit_analyzer as ea
from core import rotation_trades
from core.data_io import load_ohlcv

BASE_DIR = Path(__file__).resolve().parent
OUT = BASE_DIR / "exit_recommendations.json"


def load_entries_generic(
    csv_path: str,
    ticker_col: str,
    date_col: str,
    price_col: str,
    bucket_col: str | None = None,
) -> pd.DataFrame:
    """Read a trades CSV and normalize to the entries contract.

    Returns columns ticker, entry_date, entry_price [, bucket]. Empty DataFrame
    if the file is missing or unreadable.
    """
    p = Path(csv_path)
    if not p.exists():
        return pd.DataFrame(columns=["ticker", "entry_date", "entry_price"])
    try:
        df = pd.read_csv(p)
    except Exception:
        return pd.DataFrame(columns=["ticker", "entry_date", "entry_price"])

    out = pd.DataFrame({
        "ticker": df[ticker_col].astype(str),
        "entry_date": pd.to_datetime(df[date_col], errors="coerce"),
        "entry_price": pd.to_numeric(df[price_col], errors="coerce"),
    })
    if bucket_col and bucket_col in df.columns:
        out["bucket"] = df[bucket_col].astype(str)
    out = out.dropna(subset=["entry_date", "entry_price"])
    out = out[out["entry_price"] > 0].reset_index(drop=True)
    return out


def _sue_decile_bucket(df: pd.DataFrame) -> pd.DataFrame:
    """Add a 'bucket' column = SUE decile label, when a 'sue' column is present."""
    if "sue" not in df.columns or df["sue"].notna().sum() < 10:
        return df
    deciles = pd.qcut(df["sue"].rank(method="first"), 10, labels=False) + 1
    df = df.copy()
    df["bucket"] = "decile_" + deciles.astype(int).astype(str)
    return df


def build_all() -> dict:
    """Compute recommendations for every strategy. Returns the JSON-ready dict."""
    result: dict = {}

    # 1. Momentum Edge — OHLCV in momentum_edge_data/, bucket by Entry_Type
    me_ohlcv, _ = load_ohlcv(BASE_DIR / "momentum_edge_data")
    me_entries = load_entries_generic(
        str(BASE_DIR / "momentum_edge_trades.csv"),
        "Ticker", "Entry_Date", "Entry_Price", bucket_col="Entry_Type",
    )
    result["momentum_edge"] = {
        k: r.to_dict() for k, r in ea.analyze_with_buckets(
            me_entries, me_ohlcv, "momentum_edge", "ohlcv", bucket_col="bucket"
        ).items()
    }

    # 2. IPO Edge — OHLCV in ipo_data/, bucket by Setup_Type
    ipo_ohlcv, _ = load_ohlcv(BASE_DIR / "ipo_data")
    ipo_entries = load_entries_generic(
        str(BASE_DIR / "ipo_edge_trades.csv"),
        "Ticker", "Entry_Date", "Entry_Price", bucket_col="Setup_Type",
    )
    result["ipo_edge"] = {
        k: r.to_dict() for k, r in ea.analyze_with_buckets(
            ipo_entries, ipo_ohlcv, "ipo_edge", "ohlcv", bucket_col="bucket"
        ).items()
    }

    # 3. PEAD — prices from momentum_edge_data/, bucket by SUE decile
    pead_entries = load_entries_generic(
        str(BASE_DIR / "pead_trades.csv"),
        "ticker", "entry_date", "entry_price",
    )
    if not pead_entries.empty:
        raw = pd.read_csv(BASE_DIR / "pead_trades.csv")
        if "sue" in raw.columns and len(raw) == len(pead_entries):
            pead_entries["sue"] = pd.to_numeric(raw["sue"], errors="coerce").values
            pead_entries = _sue_decile_bucket(pead_entries)
    result["pead"] = {
        k: r.to_dict() for k, r in ea.analyze_with_buckets(
            pead_entries, me_ohlcv, "pead", "ohlcv", bucket_col="bucket"
        ).items()
    }

    # 4. Monthly Rotation — synthesized entries + close-only pseudo-OHLCV
    rot_trades = rotation_trades.build(
        str(BASE_DIR / "rebalance_log.csv"), str(BASE_DIR / "data")
    )
    rot_entries = pd.DataFrame(columns=["ticker", "entry_date", "entry_price"])
    if not rot_trades.empty:
        rot_entries = pd.DataFrame({
            "ticker": rot_trades["Ticker"].astype(str),
            "entry_date": pd.to_datetime(rot_trades["Entry_Date"]),
            "entry_price": pd.to_numeric(rot_trades["Entry_Price"], errors="coerce"),
        }).dropna(subset=["entry_price"])
    rot_ohlcv = rotation_trades.build_pseudo_ohlcv(str(BASE_DIR / "data"))
    result["monthly_rotation"] = {
        k: r.to_dict() for k, r in ea.analyze_with_buckets(
            rot_entries, rot_ohlcv, "monthly_rotation", "close"
        ).items()
    }

    return result


def main() -> None:
    result = build_all()
    OUT.write_text(json.dumps(result, indent=2))
    for strat, recs in result.items():
        buckets = ", ".join(recs.keys()) if recs else "(insufficient history)"
        print(f"  {strat}: {buckets}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_exit_analyzer.py -k load_entries -v`
Expected: PASS

- [ ] **Step 5: Smoke-run the precompute against real data**

Run: `python precompute_exit_recommendations.py`
Expected: prints a line per strategy and `Wrote .../exit_recommendations.json`; the file exists and is valid JSON. (Strategies with too few trades print `(insufficient history)` — acceptable.)

- [ ] **Step 6: Commit**

```bash
git add precompute_exit_recommendations.py tests/test_exit_analyzer.py exit_recommendations.json
git commit -m "feat(exit-analyzer): precompute script writing exit_recommendations.json"
```

---

## Task 8: Pipeline wiring — `run_all.py` + `refresh_data.bat`

**Files:**
- Modify: `run_all.py:54-71` (the per-strategy command lists)
- Modify: `refresh_data.bat`

- [ ] **Step 1: Add the precompute step to `run_all.py`**

In `run_all.py`, the pipeline command groups end around line 70 with the PEAD downloader. After the existing momentum precompute (search for `precompute_momentum_signals.py`; if absent, after `momentum_edge_backtest.py`), append the exit-recommendation precompute so it runs after all backtests. Add this command to the final pipeline group (the one that already contains `precompute_momentum_signals.py`):

```python
        [PY, 'precompute_exit_recommendations.py'],
```

If no group contains `precompute_momentum_signals.py`, add a new trailing group:

```python
    run_pipeline('Exit Recommendations', [
        [PY, 'precompute_momentum_signals.py'],
        [PY, 'precompute_exit_recommendations.py'],
    ])
```

- [ ] **Step 2: Add the step to `refresh_data.bat`**

Open `refresh_data.bat`. After the line that runs `precompute_momentum_signals.py` (or after the last backtest if that line is absent), add:

```bat
python precompute_exit_recommendations.py
```

- [ ] **Step 3: Verify the pipeline references resolve**

Run: `python -c "import run_all"` 
Expected: no error (module imports cleanly).

Run: `findstr /C:"precompute_exit_recommendations" run_all.py refresh_data.bat`
Expected: a matching line in each file.

- [ ] **Step 4: Commit**

```bash
git add run_all.py refresh_data.bat
git commit -m "chore(exit-analyzer): wire precompute into run_all and refresh_data"
```

---

## Task 9: Dashboard display — loader + badge + card

**Files:**
- Modify: `master_dashboard.py` — add `load_exit_recs()`, `_exit_badge()`, `_exit_playbook_card()`; call them in `render_monthly` (~5854), `render_ipo` (~5972), `render_momentum` (~6166).
- Modify: `pead_dashboard.py` — render the card on the PEAD page.

- [ ] **Step 1: Add the loader and helpers to `master_dashboard.py`**

Add near the other `load_*` functions (after `load_momentum` ends, ~line 2390). `BASE_DIR` and `st`, `pd`, `json` are already imported at the top of the file.

```python
import json as _json_exit  # safe alias; module-level json may already be imported

@st.cache_data(ttl=300)
def load_exit_recs() -> dict:
    """Read exit_recommendations.json (per-strategy hold/exit recommendations).

    Returns {} if the file is missing or unreadable so callers degrade gracefully.
    """
    p = Path(BASE_DIR) / 'exit_recommendations.json'
    if not p.exists():
        return {}
    try:
        return _json_exit.loads(p.read_text())
    except Exception:
        return {}


def _pick_rec(strategy: str, bucket: str | None = None) -> dict | None:
    """Return the recommendation for a strategy, preferring a bucket-level one."""
    recs = load_exit_recs().get(strategy, {})
    if not recs:
        return None
    if bucket and bucket in recs:
        return recs[bucket]
    return recs.get('ALL')


def _exit_badge(rec: dict | None) -> str:
    """One-line scale-out summary, e.g. 'Hold ~32d · T1/T2/T3 +6/+12/+22% · Stop -8%'."""
    if not rec:
        return '—'
    tg = rec.get('targets', [])
    if len(tg) >= 3:
        tline = f"T1/T2/T3 +{tg[0]['pct']:.0f}/+{tg[1]['pct']:.0f}/+{tg[2]['pct']:.0f}%"
    else:
        tline = 'targets n/a'
    return f"Hold ~{rec['hold_days']}d · {tline} · Stop {rec['stop_pct']:.0f}%"


def _exit_playbook_card(rec: dict | None, *, title: str = 'Exit Playbook') -> None:
    """Render the detailed recommendation card + return-by-day curve."""
    if not rec:
        st.info('Exit Playbook: insufficient trade history to recommend a hold/exit plan yet.')
        return

    dq = 'intraday OHLCV' if rec.get('data_quality') == 'ohlcv' else 'close-only (approx.)'
    st.markdown(f"#### 🎯 {title}")
    c1, c2, c3 = st.columns(3)
    c1.metric('Recommended hold', f"{rec['hold_days']} days",
              help='Trading days that historically maximised median return per unit of drawdown.')
    c2.metric('Median return at hold', f"{rec['hold_median_return']:.1f}%")
    c3.metric('Win rate at hold', f"{rec['hold_win_rate']*100:.0f}%")

    tdf = pd.DataFrame([
        {'Tier': f'T{n+1}', 'Profit target': f"+{t['pct']:.1f}%",
         'Book': f"{t['book_pct']}%", 'Hit rate (hist.)': f"{t['hit_rate']*100:.0f}%"}
        for n, t in enumerate(rec.get('targets', []))
    ])
    if not tdf.empty:
        st.markdown(_modern_table(tdf), unsafe_allow_html=True)
    st.caption(f"Stop level: **{rec['stop_pct']:.1f}%**  ·  "
               f"sample: **{rec['sample_size']} trades**  ·  data: {dq}")

    curve = rec.get('curve', [])
    if curve:
        cdf = pd.DataFrame(curve)
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=cdf['day'], y=cdf['median'], name='Median return %',
                                 mode='lines'))
        fig.add_trace(go.Scatter(x=cdf['day'], y=cdf['p25'], name='p25', mode='lines',
                                 line=dict(dash='dot')))
        fig.add_trace(go.Scatter(x=cdf['day'], y=cdf['p75'], name='p75', mode='lines',
                                 line=dict(dash='dot')))
        fig.add_vline(x=rec['hold_days'], line=dict(color='#7c9cff', dash='dash'))
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10),
                          xaxis_title='Days held', yaxis_title='Return %',
                          template='plotly_dark')
        st.plotly_chart(fig, use_container_width=True)
```

- [ ] **Step 2: Call the card in each strategy page**

In `render_monthly(m)` (def at ~line 5854), near the top of the function body (after its heading, before the signal table), add:

```python
    _exit_playbook_card(_pick_rec('monthly_rotation'), title='Monthly Rotation — Exit Playbook')
```

In `render_ipo(i)` (~line 5972), add near the top:

```python
    _exit_playbook_card(_pick_rec('ipo_edge'), title='IPO Edge — Exit Playbook')
```

In `render_momentum(mo)` (~line 6166), add near the top:

```python
    _exit_playbook_card(_pick_rec('momentum_edge'), title='Momentum Edge — Exit Playbook')
```

- [ ] **Step 3: Add the per-signal badge column (Monthly Rotation example)**

`render_monthly` shows the live picks from `live_rankings` via `_modern_table` (~line 5950). Immediately before that `_modern_table(...)` call, inject a badge column onto the displayed DataFrame (the variable passed to `_modern_table`; adjust the name to match the local). Use the strategy-level rec for every row:

```python
    _rec_m = _pick_rec('monthly_rotation')
    disp['Exit Plan'] = _exit_badge(_rec_m)
```

Apply the same one-liner before the signal-table `_modern_table(...)` in `render_ipo` (use `_pick_rec('ipo_edge')`, and where the row has a `Setup_Type`, pass it: `_exit_badge(_pick_rec('ipo_edge', row_setup))` only if iterating rows — otherwise the strategy-level badge is fine) and in `render_momentum` (use `_pick_rec('momentum_edge')`). Match the actual local DataFrame variable name feeding each `_modern_table` call (grep the function for `_modern_table(`).

- [ ] **Step 4: Add the card to the PEAD page (`pead_dashboard.py`)**

Open `pead_dashboard.py`, find its `render()` function. Near the top of `render()` (after the page heading), add:

```python
    try:
        import json
        from pathlib import Path
        _p = Path(__file__).resolve().parent / 'exit_recommendations.json'
        _pead = json.loads(_p.read_text()).get('pead', {}).get('ALL') if _p.exists() else None
    except Exception:
        _pead = None
    if _pead:
        import streamlit as st
        st.markdown('#### 🎯 PEAD — Exit Playbook')
        st.write(f"Recommended hold **{_pead['hold_days']} days** · "
                 f"targets +{_pead['targets'][0]['pct']:.0f}/"
                 f"+{_pead['targets'][1]['pct']:.0f}/"
                 f"+{_pead['targets'][2]['pct']:.0f}% · "
                 f"stop {_pead['stop_pct']:.0f}% · "
                 f"sample {_pead['sample_size']} trades")
    else:
        import streamlit as st
        st.info('Exit Playbook: insufficient PEAD trade history yet.')
```

- [ ] **Step 5: Manual smoke test of the dashboard**

Run: `python -c "import ast; ast.parse(open('master_dashboard.py', encoding='utf-8').read()); ast.parse(open('pead_dashboard.py', encoding='utf-8').read()); print('syntax ok')"`
Expected: `syntax ok`

Then launch and eyeball each page:
Run: `streamlit run master_dashboard.py`
Expected: Monthly / IPO / Momentum / PEAD pages each show an "Exit Playbook" card (or a clear "insufficient history" note) and the live signal tables show an "Exit Plan" column. No exceptions in the terminal.

- [ ] **Step 6: Commit**

```bash
git add master_dashboard.py pead_dashboard.py
git commit -m "feat(exit-analyzer): exit playbook card and per-signal badge in dashboard"
```

---

## Task 10: Full test + coverage check

**Files:** none (verification only)

- [ ] **Step 1: Run the full analyzer test suite**

Run: `python -m pytest tests/test_exit_analyzer.py -v`
Expected: all tests PASS.

- [ ] **Step 2: Run the whole project test suite (no regressions)**

Run: `python -m pytest -q`
Expected: no new failures vs the pre-change baseline.

- [ ] **Step 3: Coverage of the analyzer module**

Run: `python -m pytest tests/test_exit_analyzer.py --cov=core.exit_analyzer --cov-report=term-missing`
Expected: `core/exit_analyzer.py` coverage >= 80%. If below, add tests for the uncovered lines (e.g. empty-curve guard in `best_hold_day`, missing-ticker path in `build_matrix`).

- [ ] **Step 4: Commit any added tests**

```bash
git add tests/test_exit_analyzer.py
git commit -m "test(exit-analyzer): raise coverage to >=80%"
```

---

## Self-Review Notes

- **Spec coverage:** per-strategy historical basis (Tasks 6-7), risk-adjusted hold (Task 4), 3-tier MFE ladder + MAE stop (Task 5), sub-bucketing with fallback (Task 6), precompute JSON pipeline (Tasks 7-8), badge + card display with graceful empty state (Task 9), close-only flag for Monthly Rotation (Task 7 `data_quality='close'`, surfaced in Task 9 card). All spec sections map to a task.
- **Type consistency:** `entries` contract (ticker/entry_date/entry_price/bucket) used identically across Tasks 2-7. `Recommendation.to_dict()` shape consumed verbatim by `_exit_badge`/`_exit_playbook_card` (Task 9). `analyze_with_buckets` returns `{bucket: Recommendation}` consumed by precompute via `.to_dict()` (Task 7) and read back as dicts by the dashboard (Task 9).
- **Edge cases:** short history (Task 2), missing ticker / skipped entries (Task 3), ragged-length aggregation (Task 4), below-MIN_SAMPLE returns None and falls back (Task 6), missing JSON degrades to empty state (Task 9).
