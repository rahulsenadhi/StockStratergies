"""
IPO Edge Strategy — NSE IPO Data Downloader
Downloads OHLCV data for recently listed NSE stocks from Yahoo Finance.

Run first: python ipo_edge_downloader.py
Then run:  python ipo_edge_backtest.py
Then run:  streamlit run ipo_edge_dashboard.py
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
#  CONFIG  —  edit these values to tune the screener
# ═══════════════════════════════════════════════════════════════════════════════

DATA_FOLDER        = 'ipo_data'          # folder where OHLCV files are saved
LOOKBACK_DAYS      = 730                 # 2 years of history (backtest needs full IPO lifecycle)
LISTING_AGE_MAX    = 730                 # downloader saves ALL IPOs ≤ 2 years old;
                                         # the live dashboard applies a 365-day filter separately
MIN_AVG_VOLUME     = 50_000             # minimum average daily volume (shares)
MIN_AVG_VALUE_INR  = 1_000_000          # minimum average daily traded value (₹)
BENCHMARK          = 'NIFTYBEES.NS'

# ── NSE IPO Universe ──────────────────────────────────────────────────────────
# Add tickers here as new IPOs list on NSE.
# Listing date is automatically inferred from the first row of downloaded data.
# Tickers that fail to download or fail filters are skipped gracefully.

NSE_IPO_UNIVERSE = {
    # ─── FY 2024-25 IPOs (Aug–Dec 2024) ──────────────────────────────────────
    'PREMIERENE.NS':  'Premier Energies',
    'KROSS.NS':       'Kross Limited',
    'BAJAJHFL.NS':    'Bajaj Housing Finance',
    'MANBA.NS':       'Manba Finance',
    'GARUDA.NS':      'Garuda Construction',
    'WAAREEENER.NS':  'Waaree Energies',
    'HYUNDAI.NS':     'Hyundai Motor India',
    'SWIGGY.NS':      'Swiggy',
    'SAGILITY.NS':    'Sagility India',
    'NTPCGREEN.NS':   'NTPC Green Energy',
    'AFCONS.NS':      'Afcons Infrastructure',
    'MOBIKWIK.NS':    'MobiKwik',
    'VISHALMART.NS':  'Vishal Mega Mart',
    'DOMS.NS':        'DOMS Industries',
    'DEEPAKBUI.NS':   'Deepak Builders & Engineers',
    # ─── FY 2025-26 IPOs (Jan 2025 onward) ───────────────────────────────────
    'HEXAWARE.NS':    'Hexaware Technologies',
    'STALLION.NS':    'Stallion India Fluorochemicals',
    'SEPC.NS':        'SEPC Limited',
    'INDIASHE.NS':    'India Shelter Finance',
    # ─── Add new IPOs below ───────────────────────────────────────────────────
}

# ═══════════════════════════════════════════════════════════════════════════════

W = 80

def sep(ch='─'):
    return ch * W


def download_ohlcv(ticker: str, start, end) -> pd.DataFrame | None:
    """Download OHLCV for a single NSE ticker. Returns None on failure."""
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

        # Flatten MultiIndex if present (yfinance >= 0.2 with single ticker)
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


def apply_filters(ticker: str, df: pd.DataFrame, today) -> tuple[bool, str]:
    """
    Returns (passed, reason).
    Run in order — short-circuits on first failure.
    """
    listing_date = df.index[0].date()
    listing_age  = (today - listing_date).days

    if listing_age > LISTING_AGE_MAX:
        return False, f'listed {listing_age}d ago  (max: {LISTING_AGE_MAX}d)'

    # Exclude zero-volume days before averaging (circuit limits on listing day)
    vol_series = df['Volume'].replace(0, pd.NA).dropna()
    avg_vol    = float(vol_series.mean()) if len(vol_series) > 0 else 0
    if avg_vol < MIN_AVG_VOLUME:
        return False, f'avg volume {avg_vol:,.0f}  (min: {MIN_AVG_VOLUME:,})'

    avg_value = float((df['Close'] * df['Volume'].replace(0, pd.NA)).dropna().mean())
    if avg_value < MIN_AVG_VALUE_INR:
        return False, f'avg value Rs{avg_value / 1e6:.1f}M  (min: Rs{MIN_AVG_VALUE_INR / 1e6:.1f}M)'

    return True, 'OK'


def main():
    today = datetime.now().date()
    start = today - timedelta(days=LOOKBACK_DAYS)

    Path(DATA_FOLDER).mkdir(exist_ok=True)

    print('\n' + sep('═'))
    print('  IPO EDGE  —  NSE IPO Data Downloader')
    print(sep('═'))
    print(f'  Date range      : {start}  to  {today}')
    print(f'  Universe size   : {len(NSE_IPO_UNIVERSE)} tickers')
    print(f'  Listing filter  : <= {LISTING_AGE_MAX} days old (dashboard uses 365d for live screen)')
    print(f'  Volume filter   : avg >= {MIN_AVG_VOLUME:,} shares/day')
    print(f'  Value filter    : avg >= Rs{MIN_AVG_VALUE_INR / 1e6:.1f}M/day')
    print(sep() + '\n')

    summary_rows = []
    counts = {'passed': 0, 'skipped': 0, 'failed': 0}

    for ticker, company in NSE_IPO_UNIVERSE.items():
        df = download_ohlcv(ticker, start, today)

        if df is None or len(df) < 3:
            print(f'  FAIL   {ticker:<22} {company}  —  no data from Yahoo Finance')
            counts['failed'] += 1
            continue

        passed, reason = apply_filters(ticker, df, today)
        listing_date = df.index[0].date()
        listing_age  = (today - listing_date).days

        if not passed:
            print(f'  SKIP   {ticker:<22} {company[:38]:<38}  {reason}')
            counts['skipped'] += 1
            continue

        # Save full OHLCV
        out_path = os.path.join(DATA_FOLDER, f'{ticker}.csv')
        df.to_csv(out_path)

        avg_vol   = float(df['Volume'].replace(0, pd.NA).dropna().mean())
        avg_value = float((df['Close'] * df['Volume'].replace(0, pd.NA)).dropna().mean())
        ipo_hi    = round(float(df['High'].iloc[0]), 2)
        latest    = round(float(df['Close'].iloc[-1]), 2)

        print(
            f'  OK     {ticker:<22} {company[:38]:<38}  '
            f'listed {listing_date}  ({listing_age}d)  Rs{latest:,.2f}'
        )

        summary_rows.append({
            'Ticker':           ticker,
            'Company':          company,
            'Listing_Date':     listing_date,
            'Listing_Age_Days': listing_age,
            'Trading_Days':     len(df),
            'IPO_Day_High':     ipo_hi,
            'Latest_Close':     latest,
            'Avg_Vol_000s':     round(avg_vol / 1_000, 1),
            'Avg_Value_Cr':     round(avg_value / 1e7, 2),
        })
        counts['passed'] += 1

    # ── Benchmark ─────────────────────────────────────────────────────────────
    print()
    bench_df = download_ohlcv(BENCHMARK, start, today)
    if bench_df is not None:
        bench_df.to_csv(os.path.join(DATA_FOLDER, f'{BENCHMARK}.csv'))
        print(f'  OK     {BENCHMARK:<22} NiftyBees ETF  (benchmark saved)')
    else:
        print(f'  FAIL   {BENCHMARK}  —  could not download benchmark')

    # ── Save summary CSV ──────────────────────────────────────────────────────
    if summary_rows:
        summary_path = os.path.join(DATA_FOLDER, 'ipo_summary.csv')
        pd.DataFrame(summary_rows).to_csv(summary_path, index=False)

    print('\n' + sep())
    print(f'  Saved   : {counts["passed"]} stocks  →  {DATA_FOLDER}/')
    print(f'  Skipped : {counts["skipped"]}  (age or liquidity filter)')
    print(f'  Failed  : {counts["failed"]}  (no data on Yahoo Finance — check ticker spelling)')
    if counts['failed'] > 0:
        print(f'  Tip     : Verify ticker symbols at https://finance.yahoo.com (search NSE:<symbol>)')
    print(sep('═') + '\n')


if __name__ == '__main__':
    main()
