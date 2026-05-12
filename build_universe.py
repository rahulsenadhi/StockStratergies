"""
build_universe.py
-----------------
One-time setup script that builds a combined NSE + BSE stock universe.
Downloads symbol lists, deduplicates by ISIN, validates symbols via yfinance,
and saves results to DATA_FOLDER.
"""

import os
import time
import requests
import pandas as pd
import yfinance as yf
from pathlib import Path
from io import StringIO
from tqdm import tqdm

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
NSE_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
BSE_API_URL = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
MIN_DAILY_VALUE_CR = 1
BATCH_SIZE = 50
BATCH_DELAY_SECONDS = 3
VALIDATE_SYMBOLS = False   # skipped — nse_bse_downloader.py handles bad symbols during batch download
DATA_FOLDER = "./data/universe/"


# ─────────────────────────────────────────────
# HELPER: clean_symbol
# ─────────────────────────────────────────────
def clean_symbol(symbol: str, exchange: str) -> str:
    nse_exceptions = {
        'M&M': 'M%26M',
        'M&MFIN': 'M%26MFIN',
        'L&T': 'LT',
        'L&TFH': 'LTF',
        'MOTHERSUMI': 'MOTHERSON',
        'BAJAJ-AUTO': 'BAJAJ-AUTO',
    }
    if exchange == 'NSE':
        sym = nse_exceptions.get(symbol.strip(), symbol.strip())
        return sym + '.NS'
    else:
        return str(symbol).strip() + '.BO'


# ─────────────────────────────────────────────
# STEP 1: Download NSE symbol list
# ─────────────────────────────────────────────
def download_nse_symbols() -> pd.DataFrame:
    print("\n[1/5] Downloading NSE equity list...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(NSE_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        # Normalise column names (strip spaces)
        df.columns = [c.strip() for c in df.columns]
        # Filter EQ series only
        df = df[df['SERIES'].str.strip() == 'EQ'].copy()
        # Extract required columns
        df['Symbol'] = df['SYMBOL'].apply(lambda s: clean_symbol(s, 'NSE'))
        df['Name'] = df['NAME OF COMPANY'].str.strip()
        df['ISIN'] = df['ISIN NUMBER'].str.strip()
        df['Exchange'] = 'NSE'
        result = df[['Symbol', 'Name', 'ISIN', 'Exchange']].drop_duplicates(subset='Symbol').reset_index(drop=True)
        print(f"    NSE symbols found: {len(result)}")
        return result
    except Exception as e:
        print(f"    ERROR downloading NSE list: {e}")
        return pd.DataFrame(columns=['Symbol', 'Name', 'ISIN', 'Exchange'])


# ─────────────────────────────────────────────
# STEP 2: Download BSE symbol list
# ─────────────────────────────────────────────
def download_bse_symbols() -> pd.DataFrame:
    print("\n[2/5] Downloading BSE equity list...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://www.bseindia.com/',
        }
        params = {
            'GroupName': '',
            'Scripcode': '',
            'industry': '',
            'segment': 'Equity',
            'status': 'Active',
        }
        resp = requests.get(BSE_API_URL, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # Try to parse: key "Table" or first key
        if isinstance(data, dict):
            if 'Table' in data:
                records = data['Table']
            else:
                first_key = next(iter(data))
                records = data[first_key]
        elif isinstance(data, list):
            records = data
        else:
            raise ValueError(f"Unexpected BSE API response type: {type(data)}")

        df = pd.DataFrame(records)
        if df.empty:
            raise ValueError("BSE API returned empty table")

        # Normalise column names
        df.columns = [c.strip() for c in df.columns]

        # Filter groups A, B, T
        if 'Group' in df.columns:
            df = df[df['Group'].isin({'A', 'B', 'T'})].copy()
        elif 'GROUP' in df.columns:
            df = df[df['GROUP'].isin({'A', 'B', 'T'})].copy()

        # Map columns — handle alternate naming
        code_col = next((c for c in df.columns if 'SECURITY_CODE' in c or 'ScripCode' in c or 'scripcode' in c.lower()), None)
        name_col = next((c for c in df.columns if 'SECURITY_NAME' in c or 'ScripName' in c or 'scripname' in c.lower()), None)
        isin_col = next((c for c in df.columns if 'ISIN' in c.upper()), None)

        if code_col is None or name_col is None:
            raise ValueError(f"Could not identify required BSE columns. Available: {list(df.columns)}")

        df['Symbol'] = df[code_col].apply(lambda s: clean_symbol(str(s), 'BSE'))
        df['Name'] = df[name_col].str.strip() if name_col else ''
        df['ISIN'] = df[isin_col].str.strip() if isin_col else ''
        df['Exchange'] = 'BSE'

        result = df[['Symbol', 'Name', 'ISIN', 'Exchange']].drop_duplicates(subset='Symbol').reset_index(drop=True)
        print(f"    BSE symbols found: {len(result)}")
        return result

    except Exception as e:
        print(f"    WARNING: Could not download BSE list: {e}")
        print("    Continuing with NSE only.")
        return pd.DataFrame(columns=['Symbol', 'Name', 'ISIN', 'Exchange'])


# ─────────────────────────────────────────────
# STEP 3: Deduplicate by ISIN
# ─────────────────────────────────────────────
def deduplicate_by_isin(nse_df: pd.DataFrame, bse_df: pd.DataFrame) -> pd.DataFrame:
    print("\n[3/5] Deduplicating by ISIN (NSE preferred)...")

    if nse_df.empty and bse_df.empty:
        print("    ERROR: Both NSE and BSE DataFrames are empty. Aborting.")
        return pd.DataFrame(columns=['Symbol', 'Name', 'ISIN', 'Exchange'])

    if nse_df.empty:
        print("    NSE list is empty — using BSE only.")
        return bse_df.copy()

    if bse_df.empty:
        print("    BSE list is empty — using NSE only.")
        return nse_df.copy()

    nse_isins = set(nse_df['ISIN'].dropna().unique())

    # BSE-exclusive: those with an ISIN not in NSE list (or no ISIN overlap)
    bse_exclusive = bse_df[~bse_df['ISIN'].isin(nse_isins)].copy()

    combined = pd.concat([nse_df, bse_exclusive], ignore_index=True)
    n_duplicates = len(bse_df) - len(bse_exclusive)
    print(f"    NSE symbols       : {len(nse_df)}")
    print(f"    BSE symbols       : {len(bse_df)}")
    print(f"    Duplicates removed: {n_duplicates}")
    print(f"    Combined universe : {len(combined)}")
    return combined


# ─────────────────────────────────────────────
# STEP 4: Validate symbols via yfinance
# ─────────────────────────────────────────────
def validate_symbols(df: pd.DataFrame, data_folder: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (valid_df, failed_df)."""
    print(f"\n[4/5] Validating {len(df)} symbols via yfinance (batches of {BATCH_SIZE})...")
    symbols = df['Symbol'].tolist()
    valid_symbols = []
    failed_symbols = []

    total = len(symbols)
    pbar = tqdm(total=total, desc="Validating", unit="sym")

    for batch_start in range(0, total, BATCH_SIZE):
        batch = symbols[batch_start: batch_start + BATCH_SIZE]
        for i, sym in enumerate(batch, start=1):
            global_idx = batch_start + i
            pbar.set_description(f"Validating {global_idx}/{total}: {sym}")
            try:
                hist = yf.download(sym, period='5d', progress=False, auto_adjust=True)
                if not hist.empty and 'Volume' in hist.columns and hist['Volume'].sum() > 0:
                    valid_symbols.append(sym)
                    pbar.set_postfix_str(f"{sym} OK")
                else:
                    failed_symbols.append(sym)
                    pbar.set_postfix_str(f"{sym} FAILED (empty/no volume)")
            except Exception as e:
                failed_symbols.append(sym)
                pbar.set_postfix_str(f"{sym} FAILED ({e})")
            pbar.update(1)

        # Pause between batches (not after the last one)
        if batch_start + BATCH_SIZE < total:
            pbar.set_description(f"Batch pause {BATCH_DELAY_SECONDS}s...")
            time.sleep(BATCH_DELAY_SECONDS)

    pbar.close()

    valid_df = df[df['Symbol'].isin(valid_symbols)].copy().reset_index(drop=True)
    failed_df = df[df['Symbol'].isin(failed_symbols)].copy().reset_index(drop=True)
    print(f"    Valid   : {len(valid_df)}")
    print(f"    Failed  : {len(failed_df)}")
    return valid_df, failed_df


# ─────────────────────────────────────────────
# STEP 5: Save output files
# ─────────────────────────────────────────────
def save_outputs(
    combined: pd.DataFrame,
    nse_df: pd.DataFrame,
    bse_df: pd.DataFrame,
    failed_df: pd.DataFrame,
    data_folder: Path,
    n_nse: int,
    n_bse: int,
    n_duplicates: int,
) -> None:
    print(f"\n[5/5] Saving output files to {data_folder} ...")
    data_folder.mkdir(parents=True, exist_ok=True)

    # combined universe (all valid)
    combined_path = data_folder / "combined_universe.csv"
    combined.to_csv(combined_path, index=False)
    print(f"    Saved: {combined_path}  ({len(combined)} rows)")

    # NSE-only
    nse_valid = combined[combined['Exchange'] == 'NSE']
    nse_path = data_folder / "nse_only_universe.csv"
    nse_valid.to_csv(nse_path, index=False)
    print(f"    Saved: {nse_path}  ({len(nse_valid)} rows)")

    # BSE-exclusive
    bse_valid = combined[combined['Exchange'] == 'BSE']
    bse_path = data_folder / "bse_only_universe.csv"
    bse_valid.to_csv(bse_path, index=False)
    print(f"    Saved: {bse_path}  ({len(bse_valid)} rows)")

    # Failed symbols
    failed_path = data_folder / "failed_symbols.csv"
    if not failed_df.empty:
        failed_df.to_csv(failed_path, index=False)
        print(f"    Saved: {failed_path}  ({len(failed_df)} rows)")
    else:
        print(f"    No failed symbols.")

    # Summary text
    summary_path = data_folder / "universe_summary.txt"
    summary_lines = [
        "NSE + BSE Universe Build Summary",
        "=" * 40,
        f"Build date              : {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"NSE symbols found       : {n_nse}",
        f"BSE symbols found       : {n_bse}",
        f"Duplicates removed      : {n_duplicates}",
        f"Failed validation       : {len(failed_df)}",
        f"FINAL UNIVERSE SIZE     : {len(combined)}",
        f"  - NSE symbols         : {len(nse_valid)}",
        f"  - BSE-exclusive       : {len(bse_valid)}",
    ]
    summary_text = "\n".join(summary_lines)
    summary_path.write_text(summary_text, encoding='utf-8')
    print(f"    Saved: {summary_path}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  NSE + BSE Universe Builder")
    print("=" * 55)

    data_folder = Path(DATA_FOLDER)
    data_folder.mkdir(parents=True, exist_ok=True)

    # 1. NSE
    nse_df = download_nse_symbols()
    n_nse = len(nse_df)

    # 2. BSE
    bse_df = download_bse_symbols()
    n_bse = len(bse_df)

    # 3. Deduplicate
    combined_raw = deduplicate_by_isin(nse_df, bse_df)
    n_duplicates = n_bse - len(combined_raw[combined_raw['Exchange'] == 'BSE']) if n_bse > 0 else 0

    # 4. Validate
    failed_df = pd.DataFrame(columns=['Symbol', 'Name', 'ISIN', 'Exchange'])
    if VALIDATE_SYMBOLS and not combined_raw.empty:
        combined_valid, failed_df = validate_symbols(combined_raw, data_folder)
    else:
        combined_valid = combined_raw.copy()
        if not VALIDATE_SYMBOLS:
            print("\n[4/5] Skipping validation (VALIDATE_SYMBOLS=False)")

    # 5. Save
    save_outputs(
        combined=combined_valid,
        nse_df=nse_df,
        bse_df=bse_df,
        failed_df=failed_df,
        data_folder=data_folder,
        n_nse=n_nse,
        n_bse=n_bse,
        n_duplicates=n_duplicates,
    )

    # Final summary
    print("\n" + "=" * 40)
    print(f"  NSE symbols found       : {n_nse}")
    print(f"  BSE symbols found       : {n_bse}")
    print(f"  Duplicates removed      : {n_duplicates}")
    print(f"  Failed validation       : {len(failed_df)}")
    print(f"  FINAL UNIVERSE SIZE     : {len(combined_valid)}")
    print("=" * 40)


if __name__ == '__main__':
    main()
