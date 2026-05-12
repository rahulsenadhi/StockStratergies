"""
IPO Edge Strategy — NSE IPO Data Downloader
Dynamically fetches all stocks listed on NSE within the last LISTING_AGE_MAX days
using the official NSE equity list (no manual ticker maintenance needed).

Run first: python ipo_edge_downloader.py
Then run:  python ipo_edge_backtest.py
Then run:  streamlit run ipo_edge_dashboard.py
"""

import os
import sys
import warnings
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

warnings.filterwarnings('ignore')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

DATA_FOLDER            = 'ipo_data'
LOOKBACK_DAYS          = 730                # 2 years of price history
LISTING_AGE_MAX        = 730                # include IPOs listed within last 2 years
MIN_AVG_VOLUME         = 50_000            # minimum average daily volume (shares)
MIN_AVG_VALUE_INR      = 1_000_000         # minimum average daily traded value (₹)
BENCHMARK              = 'NIFTYBEES.NS'

FETCH_DYNAMIC_UNIVERSE = True              # True = auto-fetch from NSE; False = use manual list
INCLUDE_BSE_IPOS       = False             # BSE-only IPOs (adds .BO tickers not already on NSE)

NSE_EQUITY_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
BSE_API_URL    = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"

# ── Fallback manual list (used when FETCH_DYNAMIC_UNIVERSE = False) ───────────
NSE_IPO_UNIVERSE_MANUAL = {
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
    'HEXAWARE.NS':    'Hexaware Technologies',
    'STALLION.NS':    'Stallion India Fluorochemicals',
    'SEPC.NS':        'SEPC Limited',
    'INDIASHE.NS':    'India Shelter Finance',
}

# ═══════════════════════════════════════════════════════════════════════════════

W = 80

def sep(ch='─'):
    return ch * W


# ── Symbol cleaning (inline, same logic as build_universe.py) ─────────────────
_NSE_EXCEPTIONS = {
    'M&M':       'M%26M',
    'M&MFIN':    'M%26MFIN',
    'BAJAJ-AUTO': 'BAJAJ-AUTO',
}

def _to_yf_nse(sym: str) -> str:
    s = sym.strip()
    return _NSE_EXCEPTIONS.get(s, s) + '.NS'


def _to_yf_bse(code: str) -> str:
    return str(code).strip() + '.BO'


# ── Dynamic universe fetchers ──────────────────────────────────────────────────

def fetch_nse_recent_ipos(cutoff_date) -> dict:
    """
    Downloads the NSE equity list and returns tickers for stocks
    whose DATE OF LISTING is on or after cutoff_date.
    Returns {yf_ticker: company_name}.
    """
    print("  Fetching NSE equity list from nseindia.com ...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(NSE_EQUITY_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        df.columns = [c.strip() for c in df.columns]

        # Keep EQ series only
        df = df[df['SERIES'].str.strip() == 'EQ'].copy()

        # Parse listing date — column is "DATE OF LISTING"
        date_col = next((c for c in df.columns if 'DATE' in c.upper() and 'LIST' in c.upper()), None)
        if date_col is None:
            print(f"  WARNING: Could not find listing-date column. Columns: {list(df.columns)}")
            return {}

        df['listing_dt'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
        recent = df[df['listing_dt'] >= pd.Timestamp(cutoff_date)].copy()

        universe = {}
        for _, row in recent.iterrows():
            sym    = str(row['SYMBOL']).strip()
            name   = str(row['NAME OF COMPANY']).strip()
            ticker = _to_yf_nse(sym)
            universe[ticker] = name

        print(f"  NSE recent IPOs found : {len(universe)}")
        return universe

    except Exception as e:
        print(f"  WARNING: Could not fetch NSE list: {e}")
        return {}


def fetch_bse_recent_ipos(cutoff_date, nse_isins: set) -> dict:
    """
    Downloads BSE equity list and returns BSE-exclusive tickers
    (those whose ISIN is NOT already in the NSE list) listed after cutoff_date.
    Returns {yf_ticker: company_name}.
    """
    print("  Fetching BSE equity list from bseindia.com ...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer':    'https://www.bseindia.com/',
        }
        params = {
            'GroupName': '',
            'Scripcode': '',
            'industry':  '',
            'segment':   'Equity',
            'status':    'Active',
        }
        resp = requests.get(BSE_API_URL, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, dict):
            records = data.get('Table') or data[next(iter(data))]
        elif isinstance(data, list):
            records = data
        else:
            raise ValueError(f"Unexpected response type: {type(data)}")

        df = pd.DataFrame(records)
        if df.empty:
            return {}

        df.columns = [c.strip() for c in df.columns]

        # Filter groups A, B, T
        grp_col = next((c for c in df.columns if c.upper() == 'GROUP'), None)
        if grp_col:
            df = df[df[grp_col].isin({'A', 'B', 'T'})].copy()

        code_col = next((c for c in df.columns if 'SECURITY_CODE' in c or 'scripcode' in c.lower()), None)
        name_col = next((c for c in df.columns if 'SECURITY_NAME' in c or 'scripname' in c.lower()), None)
        isin_col = next((c for c in df.columns if 'ISIN' in c.upper()), None)
        date_col = next((c for c in df.columns if 'DATE' in c.upper() and 'LIST' in c.upper()), None)

        if code_col is None or name_col is None:
            print(f"  WARNING: Cannot identify BSE columns. Available: {list(df.columns)}")
            return {}

        if date_col:
            df['listing_dt'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
            df = df[df['listing_dt'] >= pd.Timestamp(cutoff_date)].copy()

        # Exclude ISINs already in NSE universe
        if isin_col and nse_isins:
            df = df[~df[isin_col].isin(nse_isins)].copy()

        universe = {}
        for _, row in df.iterrows():
            code   = str(row[code_col]).strip()
            name   = str(row[name_col]).strip()
            ticker = _to_yf_bse(code)
            universe[ticker] = name

        print(f"  BSE-exclusive recent IPOs: {len(universe)}")
        return universe

    except Exception as e:
        print(f"  WARNING: Could not fetch BSE list: {e}")
        return {}


def build_universe(cutoff_date) -> dict:
    """Returns combined {ticker: name} dict for all recent IPOs."""
    nse = fetch_nse_recent_ipos(cutoff_date)

    if INCLUDE_BSE_IPOS:
        # We don't have ISINs here, pass empty set — BSE will include all recent listings
        bse = fetch_bse_recent_ipos(cutoff_date, nse_isins=set())
        combined = {**nse, **bse}
    else:
        combined = nse

    return combined


# ── OHLCV download ─────────────────────────────────────────────────────────────

def download_ohlcv(ticker: str, start, end) -> pd.DataFrame | None:
    """Download OHLCV for a single ticker. Returns None on failure."""
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
    """Returns (passed, reason). Short-circuits on first failure."""
    listing_date = df.index[0].date()
    listing_age  = (today - listing_date).days

    if listing_age > LISTING_AGE_MAX:
        return False, f'listed {listing_age}d ago  (max: {LISTING_AGE_MAX}d)'

    vol_series = df['Volume'].replace(0, pd.NA).dropna()
    avg_vol    = float(vol_series.mean()) if len(vol_series) > 0 else 0
    if avg_vol < MIN_AVG_VOLUME:
        return False, f'avg volume {avg_vol:,.0f}  (min: {MIN_AVG_VOLUME:,})'

    avg_value = float((df['Close'] * df['Volume'].replace(0, pd.NA)).dropna().mean())
    if avg_value < MIN_AVG_VALUE_INR:
        return False, f'avg value Rs{avg_value / 1e6:.1f}M  (min: Rs{MIN_AVG_VALUE_INR / 1e6:.1f}M)'

    return True, 'OK'


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    today    = datetime.now().date()
    start    = today - timedelta(days=LOOKBACK_DAYS)
    cutoff   = today - timedelta(days=LISTING_AGE_MAX)

    Path(DATA_FOLDER).mkdir(exist_ok=True)

    print('\n' + sep('═'))
    print('  IPO EDGE  —  NSE IPO Data Downloader')
    print(sep('═'))
    print(f'  Date range      : {start}  to  {today}')
    print(f'  Listing filter  : listed on or after {cutoff}  (last {LISTING_AGE_MAX} days)')
    print(f'  Volume filter   : avg >= {MIN_AVG_VOLUME:,} shares/day')
    print(f'  Value filter    : avg >= Rs{MIN_AVG_VALUE_INR / 1e6:.1f}M/day')
    print(f'  Universe mode   : {"Dynamic (NSE API)" if FETCH_DYNAMIC_UNIVERSE else "Manual list"}')
    print(sep())

    # Build universe
    if FETCH_DYNAMIC_UNIVERSE:
        universe = build_universe(cutoff)
        if not universe:
            print('\n  WARNING: Dynamic fetch returned 0 tickers — falling back to manual list.')
            universe = NSE_IPO_UNIVERSE_MANUAL
    else:
        universe = NSE_IPO_UNIVERSE_MANUAL

    print(f'\n  Universe size   : {len(universe)} tickers\n' + sep() + '\n')

    summary_rows = []
    counts = {'passed': 0, 'skipped': 0, 'failed': 0}

    for ticker, company in universe.items():
        df = download_ohlcv(ticker, start, today)

        if df is None or len(df) < 3:
            print(f'  FAIL   {ticker:<22} {company[:40]}  —  no data')
            counts['failed'] += 1
            continue

        passed, reason = apply_filters(ticker, df, today)
        listing_date = df.index[0].date()
        listing_age  = (today - listing_date).days

        if not passed:
            print(f'  SKIP   {ticker:<22} {company[:38]:<38}  {reason}')
            counts['skipped'] += 1
            continue

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

    # Benchmark
    print()
    bench_df = download_ohlcv(BENCHMARK, start, today)
    if bench_df is not None:
        bench_df.to_csv(os.path.join(DATA_FOLDER, f'{BENCHMARK}.csv'))
        print(f'  OK     {BENCHMARK:<22} NiftyBees ETF  (benchmark saved)')
    else:
        print(f'  FAIL   {BENCHMARK}  —  could not download benchmark')

    # Summary CSV
    if summary_rows:
        summary_path = os.path.join(DATA_FOLDER, 'ipo_summary.csv')
        pd.DataFrame(summary_rows).to_csv(summary_path, index=False)

    print('\n' + sep())
    print(f'  Saved   : {counts["passed"]} stocks  →  {DATA_FOLDER}/')
    print(f'  Skipped : {counts["skipped"]}  (too old, or below liquidity threshold)')
    print(f'  Failed  : {counts["failed"]}  (no data on Yahoo Finance)')
    if counts['failed'] > 0:
        print(f'  Tip     : Some NSE tickers may use different codes on Yahoo Finance')
    print(sep('═') + '\n')


if __name__ == '__main__':
    main()
