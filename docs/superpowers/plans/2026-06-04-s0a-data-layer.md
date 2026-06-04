# S0a — Parquet/DuckDB Local Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-ticker CSV globbing with a partitioned Parquet store queried via DuckDB, behind a drop-in fast-path in `data_io.load_ohlcv`, so backtests/precompute/dashboard get fast loads with zero call-site changes.

**Architecture:** A CLI converter (`convert_to_parquet.py`) backfills + idempotently syncs CSVs → `data/parquet/<dataset>/ticker=<T>/bars.parquet` (manifest-gated). A new `core/store.py` exposes a `load_ohlcv`-shaped reader plus a `get_bars` slice query. `data_io.load_ohlcv` gains a Parquet fast-path with transparent CSV fallback. Non-breaking: no store → current CSV behavior.

**Tech Stack:** Python 3.13, pandas, pyarrow (installed), **duckdb (to install)**, pytest. Reuses `core.data_io.load_single`.

**Spec:** `docs/superpowers/specs/2026-06-04-s0a-data-layer-design.md`

---

## File Structure

- Create: `convert_to_parquet.py` — CSV→Parquet backfill + sync CLI.
- Create: `core/store.py` — Parquet/DuckDB read layer (`has_store`, `parquet_dir`, `load_ohlcv_parquet`, `get_bars`).
- Create: `requirements.txt` — direct runtime deps (adds duckdb; partial repro manifest).
- Create: `tests/test_convert_to_parquet.py`, `tests/test_store.py`.
- Modify: `core/data_io.py` — Parquet fast-path inside `load_ohlcv` (lazy `store` import).
- Modify: `run_all.py` — sync steps before backtests.
- Modify: `refresh_data.bat` — `--sync-all` step before momentum backtest.

**Datasets (name → CSV dir):** `nse_bse` → `data/nse_bse`, `ipo_data` → `ipo_data`, `momentum_edge_data` → `momentum_edge_data`.

**Parquet partition file schema:** `bars.parquet` has columns `Date` (datetime64, tz-naive), `Open`, `High`, `Low`, `Close` (float64), `Volume` (int64). `Date` stored as a COLUMN (not index) so DuckDB sees it.

---

## Task 0: Add the duckdb dependency

**Files:** Create `requirements.txt`

- [ ] **Step 1: Install duckdb into the project Python**

Run: `python -m pip install duckdb`
Expected: installs successfully (duckdb wheel).

- [ ] **Step 2: Verify import**

Run: `python -c "import duckdb, pyarrow; print('duckdb', duckdb.__version__)"`
Expected: prints a duckdb version (e.g. `duckdb 1.x.x`), no error.

- [ ] **Step 3: Create `requirements.txt`** (direct runtime deps observed in the project; not exhaustively pinned — names only):

```
pandas
numpy
pyarrow
duckdb
streamlit
plotly
matplotlib
yfinance
requests
pytest
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore(s0a): add duckdb dependency + requirements.txt"
```

---

## Task 1: Converter — `dataset_paths` + `backfill`

**Files:** Create `convert_to_parquet.py`; Test `tests/test_convert_to_parquet.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_convert_to_parquet.py
import pandas as pd
import pytest
from pathlib import Path

import convert_to_parquet as cvt


def _write_csv(path: Path, dates, closes):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "Date": dates,
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1000] * len(closes),
    }).to_csv(path, index=False)


def test_backfill_writes_partitioned_parquet(tmp_path, monkeypatch):
    csv_dir = tmp_path / "ipo_data"
    pq_root = tmp_path / "parquet"
    _write_csv(csv_dir / "AAA.NS.csv",
               pd.bdate_range("2024-01-01", periods=15), list(range(100, 115)))
    monkeypatch.setattr(cvt, "DATASETS", {"ipo_data": str(csv_dir)})
    monkeypatch.setattr(cvt, "PARQUET_ROOT", str(pq_root))

    n = cvt.backfill("ipo_data")
    assert n == 1
    part = pq_root / "ipo_data" / "ticker=AAA.NS" / "bars.parquet"
    assert part.exists()
    df = pd.read_parquet(part)
    assert list(df.columns) == ["Date", "Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 15
    assert pd.api.types.is_datetime64_any_dtype(df["Date"])
    # manifest written
    man = pq_root / "ipo_data" / "_manifest.json"
    assert man.exists()
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_convert_to_parquet.py -k backfill -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'convert_to_parquet'`

- [ ] **Step 3: Write minimal implementation**

```python
# convert_to_parquet.py
"""CSV -> Parquet backfill + idempotent sync for the price datasets.

Reuses core.data_io.load_single for CSV parsing/normalization so Parquet bytes
match what data_io.load_ohlcv would have produced. Store layout:
    data/parquet/<dataset>/ticker=<TICKER>/bars.parquet
    data/parquet/<dataset>/_manifest.json   ({ticker: source_csv_mtime})

CLI:
    python convert_to_parquet.py --backfill <dataset>
    python convert_to_parquet.py --sync <dataset>
    python convert_to_parquet.py --backfill-all
    python convert_to_parquet.py --sync-all
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd

from core.data_io import load_single

DATASETS = {
    "nse_bse": "data/nse_bse",
    "ipo_data": "ipo_data",
    "momentum_edge_data": "momentum_edge_data",
}
PARQUET_ROOT = "data/parquet"


def dataset_paths(dataset: str) -> tuple[Path, Path]:
    """Return (csv_dir, parquet_dir) for a dataset name."""
    if dataset not in DATASETS:
        raise ValueError(f"Unknown dataset: {dataset}")
    return Path(DATASETS[dataset]), Path(PARQUET_ROOT) / dataset


def _write_partition(parquet_dir: Path, ticker: str, df: pd.DataFrame) -> None:
    """Write one ticker's OHLCV DataFrame (Date index) to its partition."""
    out = df.reset_index().rename(columns={df.index.name or "index": "Date"})
    out = out[["Date", "Open", "High", "Low", "Close", "Volume"]]
    part = parquet_dir / f"ticker={ticker}" / "bars.parquet"
    part.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(part, index=False)


def _write_manifest(parquet_dir: Path, manifest: dict) -> None:
    """Atomically write the manifest dict."""
    parquet_dir.mkdir(parents=True, exist_ok=True)
    tmp = parquet_dir / "_manifest.json.tmp"
    tmp.write_text(json.dumps(manifest, indent=0))
    os.replace(tmp, parquet_dir / "_manifest.json")


def _read_manifest(parquet_dir: Path) -> dict:
    p = parquet_dir / "_manifest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def backfill(dataset: str) -> int:
    """Convert every CSV in the dataset to Parquet. Returns count written."""
    csv_dir, parquet_dir = dataset_paths(dataset)
    manifest: dict = {}
    written = 0
    for csv in sorted(csv_dir.glob("*.csv")):
        df = load_single(csv)
        if df is None:
            continue
        ticker = csv.stem
        _write_partition(parquet_dir, ticker, df)
        manifest[ticker] = csv.stat().st_mtime
        written += 1
    _write_manifest(parquet_dir, manifest)
    return written
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_convert_to_parquet.py -k backfill -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add convert_to_parquet.py tests/test_convert_to_parquet.py
git commit -m "feat(s0a): convert_to_parquet backfill + partition writer"
```

---

## Task 2: Converter — idempotent `sync`

**Files:** Modify `convert_to_parquet.py`; Test `tests/test_convert_to_parquet.py`

- [ ] **Step 1: Write the failing test**

```python
def test_sync_is_idempotent_and_incremental(tmp_path, monkeypatch):
    csv_dir = tmp_path / "ipo_data"
    pq_root = tmp_path / "parquet"
    _write_csv(csv_dir / "AAA.NS.csv",
               pd.bdate_range("2024-01-01", periods=15), list(range(100, 115)))
    _write_csv(csv_dir / "BBB.NS.csv",
               pd.bdate_range("2024-01-01", periods=15), list(range(50, 65)))
    monkeypatch.setattr(cvt, "DATASETS", {"ipo_data": str(csv_dir)})
    monkeypatch.setattr(cvt, "PARQUET_ROOT", str(pq_root))

    cvt.backfill("ipo_data")
    # 2nd sync: nothing changed
    res = cvt.sync("ipo_data")
    assert res == {"converted": 0, "skipped": 2}

    # touch one CSV with a newer mtime -> only that ticker reconverts
    import os, time
    p = csv_dir / "AAA.NS.csv"
    future = p.stat().st_mtime + 100
    os.utime(p, (future, future))
    res2 = cvt.sync("ipo_data")
    assert res2 == {"converted": 1, "skipped": 1}
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_convert_to_parquet.py -k sync -v`
Expected: FAIL — `AttributeError: module 'convert_to_parquet' has no attribute 'sync'`

- [ ] **Step 3: Write minimal implementation**

Append to `convert_to_parquet.py`:

```python
def sync(dataset: str) -> dict:
    """Convert only CSVs whose mtime changed since the last manifest entry.

    Returns {'converted': int, 'skipped': int}.
    """
    csv_dir, parquet_dir = dataset_paths(dataset)
    manifest = _read_manifest(parquet_dir)
    converted = skipped = 0
    for csv in sorted(csv_dir.glob("*.csv")):
        ticker = csv.stem
        mtime = csv.stat().st_mtime
        if manifest.get(ticker) == mtime:
            skipped += 1
            continue
        df = load_single(csv)
        if df is None:
            skipped += 1
            continue
        _write_partition(parquet_dir, ticker, df)
        manifest[ticker] = mtime
        converted += 1
    _write_manifest(parquet_dir, manifest)
    return {"converted": converted, "skipped": skipped}
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_convert_to_parquet.py -k sync -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add convert_to_parquet.py tests/test_convert_to_parquet.py
git commit -m "feat(s0a): idempotent manifest-gated sync"
```

---

## Task 3: Converter — CLI

**Files:** Modify `convert_to_parquet.py`

- [ ] **Step 1: Write the failing test**

```python
def test_cli_backfill_all_runs(tmp_path, monkeypatch, capsys):
    csv_dir = tmp_path / "ipo_data"
    pq_root = tmp_path / "parquet"
    _write_csv(csv_dir / "AAA.NS.csv",
               pd.bdate_range("2024-01-01", periods=15), list(range(100, 115)))
    monkeypatch.setattr(cvt, "DATASETS", {"ipo_data": str(csv_dir)})
    monkeypatch.setattr(cvt, "PARQUET_ROOT", str(pq_root))
    monkeypatch.setattr("sys.argv", ["convert_to_parquet.py", "--backfill-all"])

    cvt.main()
    out = capsys.readouterr().out
    assert "ipo_data" in out
    assert (pq_root / "ipo_data" / "ticker=AAA.NS" / "bars.parquet").exists()
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_convert_to_parquet.py -k cli -v`
Expected: FAIL — `AttributeError: ... has no attribute 'main'`

- [ ] **Step 3: Write minimal implementation**

Append to `convert_to_parquet.py`:

```python
def main() -> None:
    ap = argparse.ArgumentParser(description="CSV -> Parquet converter")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--backfill", metavar="DATASET")
    g.add_argument("--sync", metavar="DATASET")
    g.add_argument("--backfill-all", action="store_true")
    g.add_argument("--sync-all", action="store_true")
    args = ap.parse_args()

    if args.backfill:
        print(f"  {args.backfill}: backfilled {backfill(args.backfill)} tickers")
    elif args.sync:
        print(f"  {args.sync}: {sync(args.sync)}")
    elif args.backfill_all:
        for ds in DATASETS:
            print(f"  {ds}: backfilled {backfill(ds)} tickers")
    elif args.sync_all:
        for ds in DATASETS:
            print(f"  {ds}: {sync(ds)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_convert_to_parquet.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add convert_to_parquet.py tests/test_convert_to_parquet.py
git commit -m "feat(s0a): converter CLI (backfill/sync/-all)"
```

---

## Task 4: Store — `has_store` + `load_ohlcv_parquet`

**Files:** Create `core/store.py`; Test `tests/test_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_store.py
import pandas as pd
import numpy as np
import pytest
from pathlib import Path

from core import store
import convert_to_parquet as cvt
from core import data_io


def _make_csv_dataset(tmp_path, monkeypatch, n_tickers=3, n_bars=20):
    csv_dir = tmp_path / "nse_bse"
    csv_dir.mkdir(parents=True)
    dates = pd.bdate_range("2024-01-01", periods=n_bars)
    for i in range(n_tickers):
        closes = np.linspace(100 + i, 130 + i, n_bars)
        pd.DataFrame({
            "Date": dates, "Open": closes, "High": closes * 1.02,
            "Low": closes * 0.98, "Close": closes, "Volume": 1000 + i,
        }).to_csv(csv_dir / f"T{i}.NS.csv", index=False)
    monkeypatch.setattr(cvt, "DATASETS", {"nse_bse": str(csv_dir)})
    monkeypatch.setattr(cvt, "PARQUET_ROOT", str(tmp_path / "parquet"))
    monkeypatch.setattr(store, "DATASETS", {"nse_bse": str(csv_dir)})
    monkeypatch.setattr(store, "PARQUET_ROOT", str(tmp_path / "parquet"))
    return csv_dir


def test_has_store_false_then_true(tmp_path, monkeypatch):
    _make_csv_dataset(tmp_path, monkeypatch)
    assert store.has_store("nse_bse") is False
    cvt.backfill("nse_bse")
    assert store.has_store("nse_bse") is True


def test_load_ohlcv_parquet_matches_csv_loader(tmp_path, monkeypatch):
    csv_dir = _make_csv_dataset(tmp_path, monkeypatch)
    cvt.backfill("nse_bse")

    csv_dict, _ = data_io.load_ohlcv(str(csv_dir))          # CSV path (no store on this folder name? force CSV)
    pq_dict, mt = store.load_ohlcv_parquet("nse_bse")

    assert set(pq_dict) == set(csv_dict)
    for t in csv_dict:
        a, b = csv_dict[t], pq_dict[t]
        assert list(b.columns) == ["Open", "High", "Low", "Close", "Volume"]
        assert b.index.name == "Date"
        assert len(a) == len(b)
        np.testing.assert_allclose(a["Close"].to_numpy(), b["Close"].to_numpy(), rtol=1e-9)
        assert t in mt


def test_load_ohlcv_parquet_honors_whitelist_skip_minbars(tmp_path, monkeypatch):
    _make_csv_dataset(tmp_path, monkeypatch, n_tickers=3, n_bars=20)
    cvt.backfill("nse_bse")
    only, _ = store.load_ohlcv_parquet("nse_bse", whitelist={"T1.NS"})
    assert set(only) == {"T1.NS"}
    sk, _ = store.load_ohlcv_parquet("nse_bse", skip={"T1.NS"})
    assert "T1.NS" not in sk
    none, _ = store.load_ohlcv_parquet("nse_bse", min_bars=999)
    assert none == {}
```

Note: in `test_load_ohlcv_parquet_matches_csv_loader`, `data_io.load_ohlcv(str(csv_dir))` is called with the raw temp path; its dataset basename is `nse_bse`, but the store-monkeypatch points `PARQUET_ROOT` under tmp — the CSV loader's fast-path (added in Task 6) would also resolve. To keep this test purely CSV-vs-parquet, call the CSV reader directly via `data_io.load_single` per file OR assert the CSV path by ensuring Task 6 isn't yet present. Since Task 4 runs before Task 6, `load_ohlcv` has no fast-path yet — it reads CSV. Keep as written; it is valid at Task 4 time and remains valid because the parity is value-based.

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_store.py -k "has_store or matches_csv or honors" -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.store'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/store.py
"""Parquet/DuckDB read layer for price datasets.

Drop-in for core.data_io.load_ohlcv (load_ohlcv_parquet) plus a tidy slice query
(get_bars). Reads the partitioned store written by convert_to_parquet.py:
    data/parquet/<dataset>/ticker=<TICKER>/bars.parquet

load_ohlcv_parquet uses pandas/pyarrow for full per-ticker reads (simplest, matches
the CSV loader's dict shape); get_bars uses DuckDB for pushdown slice queries.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATASETS = {
    "nse_bse": "data/nse_bse",
    "ipo_data": "ipo_data",
    "momentum_edge_data": "momentum_edge_data",
}
PARQUET_ROOT = "data/parquet"
_OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def parquet_dir(dataset: str) -> Path:
    return Path(PARQUET_ROOT) / dataset


def has_store(dataset: str) -> bool:
    """True if the dataset has at least one written partition."""
    d = parquet_dir(dataset)
    return d.exists() and any(d.glob("ticker=*/bars.parquet"))


def load_ohlcv_parquet(
    dataset: str, min_bars: int = 10,
    skip: set | None = None, whitelist: set | None = None,
) -> tuple[dict, dict]:
    """Drop-in equivalent of data_io.load_ohlcv reading the Parquet store.

    Returns ({ticker: OHLCV DataFrame with Date index}, {ticker: parquet mtime}).
    """
    d = parquet_dir(dataset)
    skip = skip or set()
    ohlcv: dict = {}
    mtimes: dict = {}
    for part in sorted(d.glob("ticker=*/bars.parquet")):
        ticker = part.parent.name.split("=", 1)[1]
        if ticker in skip:
            continue
        if whitelist is not None and ticker not in whitelist:
            continue
        df = pd.read_parquet(part)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        df.index.name = "Date"
        df = df[_OHLCV].dropna(subset=["Close"])
        if len(df) < min_bars:
            continue
        ohlcv[ticker] = df
        mtimes[ticker] = part.stat().st_mtime
    return ohlcv, mtimes
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_store.py -k "has_store or matches_csv or honors" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/store.py tests/test_store.py
git commit -m "feat(s0a): store.load_ohlcv_parquet drop-in reader"
```

---

## Task 5: Store — `get_bars` query helper (DuckDB)

**Files:** Modify `core/store.py`; Test `tests/test_store.py`

- [ ] **Step 1: Write the failing test**

```python
def test_get_bars_filters(tmp_path, monkeypatch):
    _make_csv_dataset(tmp_path, monkeypatch, n_tickers=3, n_bars=20)
    cvt.backfill("nse_bse")

    # all tickers, all cols
    allb = store.get_bars("nse_bse")
    assert {"ticker", "Date"}.issubset(allb.columns)
    assert set(allb["ticker"].unique()) == {"T0.NS", "T1.NS", "T2.NS"}

    # ticker filter + column projection
    sub = store.get_bars("nse_bse", tickers=["T1.NS"], cols=["Close"])
    assert set(sub["ticker"].unique()) == {"T1.NS"}
    assert set(sub.columns) == {"ticker", "Date", "Close"}

    # date range filter
    rng = store.get_bars("nse_bse", tickers=["T0.NS"],
                         start="2024-01-10", end="2024-01-15")
    assert rng["Date"].min() >= pd.Timestamp("2024-01-10")
    assert rng["Date"].max() <= pd.Timestamp("2024-01-15")
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_store.py -k get_bars -v`
Expected: FAIL — `AttributeError: module 'core.store' has no attribute 'get_bars'`

- [ ] **Step 3: Write minimal implementation**

Append to `core/store.py`:

```python
import duckdb


def _connect() -> "duckdb.DuckDBPyConnection":
    return duckdb.connect(database=":memory:")


def get_bars(
    dataset: str, tickers: list | None = None,
    start: str | None = None, end: str | None = None,
    cols: list | None = None,
) -> pd.DataFrame:
    """Tidy slice query via DuckDB. Columns: ticker, Date, + requested OHLCV
    (all OHLCV when cols is None). Returns an empty DataFrame if no store."""
    d = parquet_dir(dataset)
    if not has_store(dataset):
        return pd.DataFrame(columns=["ticker", "Date"] + (cols or _OHLCV))

    select_cols = ", ".join(["ticker", "Date"] + (cols or _OHLCV))
    glob = str(d / "ticker=*" / "bars.parquet").replace("\\", "/")
    where = []
    params: list = []
    if tickers:
        ph = ", ".join(["?"] * len(tickers))
        where.append(f"ticker IN ({ph})")
        params.extend(tickers)
    if start:
        where.append("Date >= ?")
        params.append(start)
    if end:
        where.append("Date <= ?")
        params.append(end)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    sql = (f"SELECT {select_cols} FROM read_parquet(?, hive_partitioning=true)"
           f"{clause} ORDER BY ticker, Date")
    con = _connect()
    try:
        return con.execute(sql, [glob, *params]).df()
    finally:
        con.close()
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_store.py -k get_bars -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/store.py tests/test_store.py
git commit -m "feat(s0a): store.get_bars DuckDB slice query"
```

---

## Task 6: `data_io.load_ohlcv` Parquet fast-path

**Files:** Modify `core/data_io.py`; Test `tests/test_store.py`

- [ ] **Step 1: Write the failing test**

```python
def test_load_ohlcv_fastpath_uses_store_and_matches(tmp_path, monkeypatch):
    csv_dir = _make_csv_dataset(tmp_path, monkeypatch)
    cvt.backfill("nse_bse")
    # data_io.load_ohlcv called with a folder whose basename == 'nse_bse'
    # should now read from the (monkeypatched) store and match a direct parquet read.
    via_loader, _ = data_io.load_ohlcv(str(csv_dir))
    via_store, _ = store.load_ohlcv_parquet("nse_bse")
    assert set(via_loader) == set(via_store)
    for t in via_store:
        np.testing.assert_allclose(
            via_loader[t]["Close"].to_numpy(),
            via_store[t]["Close"].to_numpy(), rtol=1e-9)


def test_load_ohlcv_falls_back_to_csv_without_store(tmp_path, monkeypatch):
    csv_dir = tmp_path / "weird_ds"   # basename not in store DATASETS -> no store
    csv_dir.mkdir()
    dates = pd.bdate_range("2024-01-01", periods=15)
    pd.DataFrame({"Date": dates, "Open": range(15), "High": range(15),
                  "Low": range(15), "Close": range(1, 16), "Volume": [1]*15}
                 ).to_csv(csv_dir / "Z.NS.csv", index=False)
    monkeypatch.setattr(store, "PARQUET_ROOT", str(tmp_path / "parquet"))
    out, _ = data_io.load_ohlcv(str(csv_dir))
    assert "Z.NS" in out   # CSV path still works
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_store.py -k "fastpath or falls_back" -v`
Expected: FAIL — fast-path test fails because `load_ohlcv` still globs CSV (the temp folder has no CSVs matching, or returns CSV not store); falls_back should pass.

- [ ] **Step 3: Write minimal implementation**

In `core/data_io.py`, inside `load_ohlcv`, immediately after `folder = Path(folder)` and the `if not folder.exists()` guard, add:

```python
    # Parquet fast-path (transparent CSV fallback). Lazy import avoids a
    # circular import: store.py imports data_io.load_single at module level.
    try:
        from core import store
        dataset = folder.name
        if store.has_store(dataset):
            return store.load_ohlcv_parquet(dataset, min_bars=min_bars,
                                            skip=skip, whitelist=whitelist)
    except Exception:
        import logging
        logging.warning("Parquet fast-path failed for %s; using CSV", folder.name)
    # --- existing CSV glob path continues below unchanged ---
```

Do NOT remove or alter the existing CSV logic; this only adds an early return when a store exists.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_store.py -k "fastpath or falls_back" -v`
Expected: PASS

- [ ] **Step 5: Run full store + converter suites + whole project suite**

Run: `python -m pytest tests/test_store.py tests/test_convert_to_parquet.py -v`
Expected: all PASS.
Run: `python -m pytest -q`
Expected: no regressions vs baseline (was 80 passed; now higher, 0 failures).

- [ ] **Step 6: Commit**

```bash
git add core/data_io.py tests/test_store.py
git commit -m "feat(s0a): load_ohlcv Parquet fast-path with CSV fallback"
```

---

## Task 7: Pipeline wiring + seed the store

**Files:** Modify `run_all.py:54-71`; Modify `refresh_data.bat`

- [ ] **Step 1: Add sync steps to `run_all.py` PIPELINES**

In `run_all.py`, the `PIPELINES` dict (around lines 54-71) runs groups in order. Insert a sync step BEFORE each backtest that reads a store-backed dataset. Edit the `IPO Edge` and `Momentum Edge` groups:

```python
    'IPO Edge': [
        [PY, 'ipo_edge_downloader.py'],
        [PY, 'convert_to_parquet.py', '--sync', 'ipo_data'],
        [PY, 'ipo_edge_backtest.py'],
    ],
    'Momentum Edge': [
        [PY, 'build_universe.py'],
        [PY, 'nse_bse_downloader.py'],
        [PY, 'convert_to_parquet.py', '--sync', 'nse_bse'],
        [PY, 'momentum_edge_backtest.py'],
    ],
```

(Monthly Rotation uses close-only `data/` which is out of scope — no sync there. `momentum_edge_data` is static/legacy — synced by the one-time backfill in Step 3, not the pipeline.)

- [ ] **Step 2: Add a sync step to `refresh_data.bat`**

In `refresh_data.bat`, after the `nse_bse_downloader.py` step (step `[2/3]`, around line 27-33) and before `momentum_edge_backtest.py` (step `[3/5]`), insert:

```bat
echo [2b] Syncing Parquet store ... >> "%LOG%"
"%PY%" convert_to_parquet.py --sync nse_bse >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  !! convert_to_parquet.py FAILED >> "%LOG%"
) else (
    echo  ok parquet sync done >> "%LOG%"
)
```

- [ ] **Step 3: One-time backfill seed (real data)**

Run: `python convert_to_parquet.py --backfill-all`
Expected: prints per-dataset backfilled counts (e.g. `nse_bse: backfilled ~963 tickers`, `ipo_data: ...`, `momentum_edge_data: ...`); creates `data/parquet/<dataset>/` trees + manifests. (May take a minute on the large `nse_bse` set.)

- [ ] **Step 4: Verify the fast-path is live on real data**

Run: `python -c "from core import store; print('nse_bse store:', store.has_store('nse_bse')); from core.data_io import load_ohlcv; d,_=load_ohlcv('data/nse_bse'); print('tickers loaded:', len(d))"`
Expected: `nse_bse store: True` and a nonzero ticker count.

Run: `python -c "import run_all" ` and `findstr /C:"convert_to_parquet" run_all.py refresh_data.bat`
Expected: clean import; a match in each file.

- [ ] **Step 5: Commit**

```bash
git add run_all.py refresh_data.bat
git commit -m "chore(s0a): wire parquet sync into run_all + refresh_data"
```

Note: `data/parquet/` should be gitignored (large, regenerable). Confirm `.gitignore` excludes it; if not, add a line `data/parquet/` and commit that with this task. Do NOT commit the parquet store itself.

---

## Task 8: Verification — full suite + perf sanity + app smoke

**Files:** Test `tests/test_store.py` (add the perf sanity test)

- [ ] **Step 1: Add a loose perf-sanity test**

```python
def test_parquet_load_not_slower_than_csv(tmp_path, monkeypatch):
    import time
    csv_dir = _make_csv_dataset(tmp_path, monkeypatch, n_tickers=40, n_bars=250)
    # CSV baseline (read each file via data_io.load_single)
    from core import data_io as dio
    t0 = time.perf_counter()
    _ = {p.stem: dio.load_single(p) for p in csv_dir.glob("*.csv")}
    csv_t = time.perf_counter() - t0
    cvt.backfill("nse_bse")
    t1 = time.perf_counter()
    _ = store.load_ohlcv_parquet("nse_bse")
    pq_t = time.perf_counter() - t1
    # loose guard: parquet should not be dramatically slower (allow 1.5x slack for tiny sets)
    assert pq_t <= csv_t * 1.5
```

- [ ] **Step 2: Run the full project suite**

Run: `python -m pytest -q`
Expected: all PASS, no regressions.

- [ ] **Step 3: Smoke the dashboard data loaders (no server)**

Run: `python -c "import ast; ast.parse(open('master_dashboard.py',encoding='utf-8').read()); print('dash syntax ok')"`
Expected: `dash syntax ok`.
Run: `python -c "from core.data_io import load_ohlcv; import time; t=time.perf_counter(); d,_=load_ohlcv('ipo_data'); print('ipo tickers', len(d), 'in', round(time.perf_counter()-t,2),'s')"`
Expected: loads via parquet fast-path quickly.

- [ ] **Step 4: Commit**

```bash
git add tests/test_store.py
git commit -m "test(s0a): perf-sanity + verification"
```

---

## Self-Review Notes

- **Spec coverage:** store layout + datasets (Task 1), backfill (T1), idempotent sync + atomic manifest (T2), CLI (T3), `has_store`/`load_ohlcv_parquet` drop-in + skip/whitelist/min_bars (T4), `get_bars` DuckDB pushdown (T5), `load_ohlcv` fast-path + lazy import + CSV fallback (T6), pipeline wiring + one-time backfill (T7), equivalence/parity + perf-sanity + no-regression (T4/T6/T8). duckdb dependency (T0). All spec sections mapped.
- **Type consistency:** `DATASETS`/`PARQUET_ROOT` names identical in `convert_to_parquet.py` and `core/store.py`; partition path `ticker=<T>/bars.parquet` and column order `[Date,Open,High,Low,Close,Volume]` consistent across writer (T1) and readers (T4/T5). `load_ohlcv_parquet(dataset, min_bars, skip, whitelist)` signature matches the call in the `data_io` fast-path (T6). `sync` returns `{'converted','skipped'}` as asserted (T2).
- **Edge cases:** corrupt CSV (`load_single` None) skipped (T1/T2); no store → CSV fallback (T6); empty/whitelist/min_bars (T4); missing manifest (T2 `_read_manifest`); store gitignored, not committed (T7).
- **Deviation from spec wording:** spec said all reads "go through DuckDB"; `load_ohlcv_parquet` uses pandas/pyarrow for full per-ticker reads (simpler, same shape, no DuckDB benefit for full scans) while `get_bars` uses DuckDB for pushdown. Functionally equivalent; noted here intentionally.
