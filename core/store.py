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
    Reads all partitions in one DuckDB pass (far faster than per-file reads at
    thousands of tickers), then splits per ticker.
    """
    if not has_store(dataset):
        return {}, {}
    skip = skip or set()
    d = parquet_dir(dataset)
    glob = str(d / "ticker=*" / "bars.parquet").replace("\\", "/")
    con = _connection()
    sql = ("SELECT ticker, Date, Open, High, Low, Close, Volume "
           "FROM read_parquet(?, hive_partitioning=true) ORDER BY ticker, Date")
    df = con.execute(sql, [glob]).df()

    ohlcv: dict = {}
    mtimes: dict = {}
    for ticker, g in df.groupby("ticker", sort=False):
        if ticker in skip:
            continue
        if whitelist is not None and ticker not in whitelist:
            continue
        gg = g.set_index("Date")[_OHLCV].dropna(subset=["Close"])
        if len(gg) < min_bars:
            continue
        gg.index.name = "Date"
        ohlcv[ticker] = gg
        part = d / f"ticker={ticker}" / "bars.parquet"
        try:
            mtimes[ticker] = part.stat().st_mtime
        except OSError:
            mtimes[ticker] = 0.0
    return ohlcv, mtimes


_con = None


def _connection() -> "duckdb.DuckDBPyConnection":
    global _con
    if _con is None:
        _con = duckdb.connect(database=":memory:")
    return _con


def get_bars(
    dataset: str, tickers: list | None = None,
    start: str | None = None, end: str | None = None,
    cols: list | None = None,
) -> pd.DataFrame:
    """Tidy slice query via DuckDB. Columns: ticker, Date, + requested OHLCV
    (all OHLCV when cols is None). Returns an empty DataFrame if no store."""
    if cols is not None:
        invalid = set(cols) - set(_OHLCV)
        if invalid:
            raise ValueError(f"Invalid column names: {sorted(invalid)}")
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
    con = _connection()
    return con.execute(sql, [glob, *params]).df()
