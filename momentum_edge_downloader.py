"""
Momentum Edge Strategy — NSE Stock Data Downloader
Downloads full OHLCV data for all symbols in momentum_edge_symbols.csv.

Run first: python momentum_edge_downloader.py
Then run:  python momentum_edge_backtest.py
Then run:  streamlit run momentum_edge_dashboard.py
"""

import os
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

warnings.filterwarnings('ignore')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

DATA_FOLDER      = 'momentum_edge_data'
SYMBOLS_FILE     = 'momentum_edge_symbols.csv'
LOOKBACK_DAYS    = 1200          # ~4.8 years — needed for 220 EMA warmup + full backtest
MIN_TRADING_DAYS = 220           # skip stocks with fewer rows than this
BENCHMARK        = 'NIFTYBEES.NS'

# ═══════════════════════════════════════════════════════════════════════════════

W = 80

def sep(ch='─'):
    return ch * W


def load_symbols(symbols_file: str) -> dict[str, str]:
    """Read ticker → company name from CSV. Returns empty dict on missing file."""
    path = Path(symbols_file)
    if not path.exists():
        print(f'  WARN  {symbols_file} not found — using empty universe')
        return {}
    df = pd.read_csv(path)
    if 'Ticker' not in df.columns or 'Company' not in df.columns:
        raise ValueError(f'{symbols_file} must have Ticker and Company columns')
    return dict(zip(df['Ticker'].str.strip(), df['Company'].str.strip()))


def download_ohlcv(ticker: str, start, end) -> pd.DataFrame | None:
    """Download full OHLCV for a single NSE ticker. Returns None on failure."""
    try:
        raw = yf.download(
            ticker,
            start=str(start),
            end=str(end + timedelta(days=1)),
            progress=False,
            auto_adjust=True,
        )
        if raw is None or raw.empty:
            return None

        # Flatten MultiIndex produced by yfinance >= 0.2 on single tickers
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.droplevel(1)

        needed = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in raw.columns]
        if len(needed) < 5:
            return None

        df = raw[needed].copy()
        df = df.dropna(subset=['Close'])
        df.index = pd.to_datetime(df.index)
        df.index.name = 'Date'
        df.sort_index(inplace=True)
        return df

    except Exception:
        return None


def validate(ticker: str, df: pd.DataFrame) -> tuple[bool, str]:
    """Returns (passed, reason). Rejects stocks with insufficient history."""
    if len(df) < MIN_TRADING_DAYS:
        return False, f'only {len(df)} trading days  (min: {MIN_TRADING_DAYS})'
    if df['Close'].iloc[-1] <= 0:
        return False, 'latest close is zero or negative'
    if df['Volume'].replace(0, pd.NA).dropna().mean() < 10_000:
        return False, 'avg volume < 10,000 shares (illiquid)'
    return True, 'OK'


def main():
    today = datetime.now().date()
    start = today - timedelta(days=LOOKBACK_DAYS)

    universe = load_symbols(SYMBOLS_FILE)
    if not universe:
        print('No symbols loaded. Exiting.')
        return

    Path(DATA_FOLDER).mkdir(exist_ok=True)

    print('\n' + sep('═'))
    print('  MOMENTUM EDGE  —  NSE Stock Data Downloader')
    print(sep('═'))
    print(f'  Symbols file    : {SYMBOLS_FILE}  ({len(universe)} tickers)')
    print(f'  Date range      : {start}  to  {today}')
    print(f'  Min trading days: {MIN_TRADING_DAYS}')
    print(f'  Output folder   : {DATA_FOLDER}/')
    print(sep() + '\n')

    counts = {'ok': 0, 'skipped': 0, 'failed': 0}
    summary_rows = []

    for ticker, company in universe.items():
        df = download_ohlcv(ticker, start, today)

        if df is None or df.empty:
            print(f'  FAIL   {ticker:<22} {company[:40]:<40}  no data from Yahoo Finance')
            counts['failed'] += 1
            continue

        passed, reason = validate(ticker, df)
        if not passed:
            print(f'  SKIP   {ticker:<22} {company[:40]:<40}  {reason}')
            counts['skipped'] += 1
            continue

        out_path = os.path.join(DATA_FOLDER, f'{ticker}.csv')
        df.to_csv(out_path)

        latest   = round(float(df['Close'].iloc[-1]), 2)
        avg_vol  = float(df['Volume'].replace(0, pd.NA).dropna().mean())
        trading_days = len(df)

        print(
            f'  OK     {ticker:<22} {company[:40]:<40}  '
            f'{trading_days}d  Rs{latest:,.2f}'
        )

        summary_rows.append({
            'Ticker':        ticker,
            'Company':       company,
            'Trading_Days':  trading_days,
            'Start_Date':    df.index[0].date(),
            'End_Date':      df.index[-1].date(),
            'Latest_Close':  latest,
            'Avg_Vol_000s':  round(avg_vol / 1_000, 1),
        })
        counts['ok'] += 1

    # ── Benchmark ─────────────────────────────────────────────────────────────
    print()
    bench_df = download_ohlcv(BENCHMARK, start, today)
    if bench_df is not None and not bench_df.empty:
        bench_df.to_csv(os.path.join(DATA_FOLDER, f'{BENCHMARK}.csv'))
        print(f'  OK     {BENCHMARK:<22} NiftyBees ETF  (benchmark saved)')
    else:
        print(f'  FAIL   {BENCHMARK}  —  could not download benchmark')

    # ── Save summary ──────────────────────────────────────────────────────────
    if summary_rows:
        pd.DataFrame(summary_rows).to_csv(
            os.path.join(DATA_FOLDER, 'me_summary.csv'), index=False
        )

    print('\n' + sep())
    print(f'  Saved   : {counts["ok"]} stocks  →  {DATA_FOLDER}/')
    print(f'  Skipped : {counts["skipped"]}  (insufficient history or liquidity)')
    print(f'  Failed  : {counts["failed"]}  (no data on Yahoo Finance)')
    if counts['failed'] > 0:
        print('  Tip     : Verify ticker symbols at https://finance.yahoo.com (search NSE:<symbol>)')
    print(sep('═') + '\n')


if __name__ == '__main__':
    main()
