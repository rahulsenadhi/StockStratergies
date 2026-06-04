# core/store.py
"""Parquet/DuckDB read layer for price datasets.

Drop-in for core.data_io.load_ohlcv (load_ohlcv_parquet) plus a tidy slice query
(get_bars, added later). Reads the partitioned store written by convert_to_parquet.py:
    data/parquet/<dataset>/ticker=<TICKER>/bars.parquet

load_ohlcv_parquet uses pandas/pyarrow for full per-ticker reads (simplest, matches
the CSV loader's dict shape).
"""
from __future__ import annotations

from pathlib import Path

import duckdb
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
