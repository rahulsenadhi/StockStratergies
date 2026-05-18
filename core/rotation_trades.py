"""Reconstruct per-trade rows for the Nifty Rotation strategy.

The Rotation engine only logs monthly portfolio snapshots (`rebalance_log.csv`)
plus an equity curve (`backtest_results.csv`). It does not write a trade-level
file. This module synthesizes one by walking the rebalance log: for each ticker
in Stocks_Bought on date T, scan forward to the next rebalance where it appears
in Stocks_Sold; that pair becomes one round-trip trade.

Output schema matches what core.analytics expects:
    Ticker, Entry_Date, Entry_Price, Exit_Date, Exit_Price,
    PnL_Pct, Holding_Days, Result, Exit_Reason

Price data folder = `data/` (each <ticker>.csv has Date index + single Close column).
"""

from pathlib import Path

import numpy as np
import pandas as pd


def _split_list(cell) -> list[str]:
    """Comma-separated tickers cell → list. NaN / empty → []."""
    if pd.isna(cell) or not str(cell).strip():
        return []
    return [t.strip() for t in str(cell).split(',') if t.strip()]


def _load_close_series(folder: Path, ticker: str) -> pd.Series | None:
    p = folder / f'{ticker}.csv'
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        df = df.sort_index()
        # data/*.csv has a single column named after the ticker
        return df.iloc[:, 0].dropna()
    except Exception:
        return None


def _price_at(series: pd.Series, dt: pd.Timestamp) -> float | None:
    """Last available Close on or before dt."""
    if series is None or series.empty:
        return None
    try:
        sub = series.loc[:dt]
        return float(sub.iloc[-1]) if not sub.empty else None
    except Exception:
        return None


def build(
    rebalance_log_csv: str = 'rebalance_log.csv',
    data_folder: str = 'data',
) -> pd.DataFrame:
    """Synthesize per-trade DataFrame from rebalance log + price files."""
    log_path = Path(rebalance_log_csv)
    if not log_path.exists():
        return pd.DataFrame()
    log = pd.read_csv(log_path, parse_dates=['Date']).sort_values('Date').reset_index(drop=True)
    if log.empty:
        return pd.DataFrame()

    folder = Path(data_folder)
    price_cache: dict[str, pd.Series | None] = {}

    def prices_for(ticker: str) -> pd.Series | None:
        if ticker not in price_cache:
            price_cache[ticker] = _load_close_series(folder, ticker)
        return price_cache[ticker]

    # ── Walk forward, opening positions on Stocks_Bought, closing on Stocks_Sold ─
    open_pos: dict[str, pd.Timestamp] = {}  # ticker → entry date
    trades: list[dict] = []
    last_date = log['Date'].iloc[-1]

    for _, row in log.iterrows():
        date = row['Date']

        # Close anything in Stocks_Sold first
        for ticker in _split_list(row.get('Stocks_Sold')):
            entry_dt = open_pos.pop(ticker, None)
            if entry_dt is None:
                continue
            series = prices_for(ticker)
            entry_px = _price_at(series, entry_dt)
            exit_px = _price_at(series, date)
            if entry_px is None or exit_px is None or entry_px <= 0:
                continue
            pnl = (exit_px / entry_px - 1) * 100
            trades.append({
                'Ticker':       ticker,
                'Entry_Date':   entry_dt,
                'Entry_Price':  round(entry_px, 2),
                'Exit_Date':    date,
                'Exit_Price':   round(exit_px, 2),
                'PnL_Pct':      round(pnl, 2),
                'Holding_Days': int((date - entry_dt).days),
                'Result':       'Win' if pnl > 0 else 'Loss',
                'Exit_Reason':  'Rebalance Rotation',
            })

        # Open new positions
        for ticker in _split_list(row.get('Stocks_Bought')):
            if ticker not in open_pos:
                open_pos[ticker] = date

    # Mark any still-open positions at the end as "Open" (PnL vs last known price)
    for ticker, entry_dt in open_pos.items():
        series = prices_for(ticker)
        entry_px = _price_at(series, entry_dt)
        exit_px = _price_at(series, last_date)
        if entry_px is None or exit_px is None or entry_px <= 0:
            continue
        pnl = (exit_px / entry_px - 1) * 100
        trades.append({
            'Ticker':       ticker,
            'Entry_Date':   entry_dt,
            'Entry_Price':  round(entry_px, 2),
            'Exit_Date':    last_date,
            'Exit_Price':   round(exit_px, 2),
            'PnL_Pct':      round(pnl, 2),
            'Holding_Days': int((last_date - entry_dt).days),
            'Result':       'Open',
            'Exit_Reason':  'Still Held',
        })

    return pd.DataFrame(trades)


def build_pseudo_ohlcv(data_folder: str = 'data') -> dict[str, pd.DataFrame]:
    """Wrap each ticker's Close series as a 5-col OHLCV frame so core.analytics
    helpers (which expect High/Low) accept it. Close is used for all OHLC slots
    — MAE/MFE on a Close-only series collapses to drawdown vs peak from entry.
    """
    folder = Path(data_folder)
    out: dict[str, pd.DataFrame] = {}
    for p in folder.glob('*.csv'):
        try:
            df = pd.read_csv(p, index_col=0, parse_dates=True).sort_index()
            close = df.iloc[:, 0].dropna()
            if close.empty:
                continue
            ohlc = pd.DataFrame({
                'Open':   close,
                'High':   close,
                'Low':    close,
                'Close':  close,
                'Volume': 0,
            })
            out[p.stem] = ohlc
        except Exception:
            continue
    return out
