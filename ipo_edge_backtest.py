"""
IPO Edge Strategy — Backtester
Simulates the IPO base-breakout strategy on downloaded NSE IPO data.

Run after: python ipo_edge_downloader.py
Run:       python ipo_edge_backtest.py
"""

import sys
import warnings
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

CFG = {
    # ── Capital & position sizing ─────────────────────────────────────────────
    'initial_capital':       5_00_000,     # Rs 5 lakh starting capital
    'max_alloc_pct':         0.10,         # 10% of capital per position
    'max_positions':         10,           # max simultaneous open positions

    # ── Base detection ────────────────────────────────────────────────────────
    'skip_initial_days':     3,            # ignore first N days after listing (volatile)
    'base_window':           40,           # days 4..43 form the IPO base
    'min_days_needed':       43,           # skip stock if fewer than this many rows

    # ── Entry filters ─────────────────────────────────────────────────────────
    'vol_multiplier':        1.5,          # breakout volume must be > N × base avg volume
    'ema_period':            10,           # EMA used for entry filter and trailing stop
    'use_ema_filter':        True,         # close must be above EMA10 at breakout

    # ── IPO quality filters ───────────────────────────────────────────────────
    'min_ipo_day_value_cr':  10,           # IPO listing day traded value min ₹10 Crore
    'promoter_quality_file': 'ipo_promoter_quality.csv',  # informational only

    # ── Exit rules ────────────────────────────────────────────────────────────
    'hard_stop_pct':         0.08,         # 8% hard stop below entry price
    'max_hold_days':         90,           # force-exit after this many trading days
    'cooldown_days':         15,           # min trading days before re-entering after exit
    'partial_booking':       True,         # book 1/3 position at partial_target_pct gain
    'partial_target_pct':    0.15,         # 15% gain triggers partial booking → move SL to cost

    # ── IPO age filter ────────────────────────────────────────────────────────
    'max_ipo_age_days':       252,            # skip stock if >252 trading days since listing

    # ── Paths ─────────────────────────────────────────────────────────────────
    'data_folder':           'ipo_data',
    'trades_out':            'ipo_edge_trades.csv',
    'equity_out':            'ipo_edge_equity.csv',
    'chart_out':             'ipo_edge_chart.png',
    'benchmark':             'NIFTYBEES.NS',

    # ── Debug ─────────────────────────────────────────────────────────────────
    'diagnostic_mode':        True,           # print per-filter stock counts
}

# ── Company names (kept in sync with downloader for trade reports) ────────────
COMPANY_NAMES = {
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
#  DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def load_ohlcv(folder: str) -> dict[str, pd.DataFrame]:
    """Load all IPO OHLCV CSVs from ipo_data/. Skips benchmark file."""
    ohlcv = {}
    data_path = Path(folder)
    if not data_path.exists():
        raise FileNotFoundError(f"'{folder}/' not found. Run ipo_edge_downloader.py first.")

    for csv_file in sorted(data_path.glob('*.csv')):
        if csv_file.stem in ('NIFTYBEES.NS', 'ipo_summary'):
            continue
        try:
            df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
            df.index = pd.to_datetime(df.index)
            df.sort_index(inplace=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            needed = ['Open', 'High', 'Low', 'Close', 'Volume']
            if not all(c in df.columns for c in needed):
                continue
            df = df[needed].dropna(subset=['Close'])
            if len(df) >= 5:
                ohlcv[csv_file.stem] = df
        except Exception:
            continue
    return ohlcv


def load_benchmark(folder: str, ticker: str) -> pd.Series:
    """Load NiftyBees Close as benchmark series."""
    path = Path(folder) / f'{ticker}.csv'
    if not path.exists():
        return pd.Series(dtype=float)
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    return df['Close'].sort_index()


def _load_promoter_quality(filepath: str) -> dict[str, dict]:
    """
    Load ipo_promoter_quality.csv → {Symbol: {PromoterBacked, Notes}}.
    Returns empty dict if file missing (informational only — does not fail).
    """
    path = Path(filepath)
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path)
        result = {}
        for _, row in df.iterrows():
            sym = str(row.get('Symbol', '')).strip().upper()
            if sym:
                result[sym] = {
                    'PromoterBacked': str(row.get('PromoterBacked', 'Unknown')).strip().upper(),
                    'Notes':          str(row.get('Notes', '')).strip(),
                }
        return result
    except Exception:
        return {}


# ═══════════════════════════════════════════════════════════════════════════════
#  BASE DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def compute_base(df: pd.DataFrame, cfg: dict) -> dict | None:
    """
    Detect the IPO base window and return base metrics including liquidity check.
    Returns None if there is insufficient data.
    """
    if len(df) < cfg['min_days_needed']:
        return None

    skip   = cfg['skip_initial_days']
    window = cfg['base_window']

    ipo_day_high  = float(df['High'].iloc[0])
    ipo_day_close = float(df['Close'].iloc[0])
    ipo_day_vol   = float(df['Volume'].iloc[0])

    # IPO Day Liquidity: total traded value in Crore (1 Cr = 10,000,000)
    ipo_day_value_cr  = ipo_day_close * ipo_day_vol / 1e7
    min_val_cr        = cfg.get('min_ipo_day_value_cr', 10)
    liquidity_ok      = ipo_day_value_cr >= min_val_cr
    liquidity_status  = 'Liquid' if liquidity_ok else 'Low Liquidity'

    base_slice    = df.iloc[skip: skip + window]
    vol_clean     = base_slice['Volume'].replace(0, np.nan).dropna()
    base_vol_avg  = float(vol_clean.mean()) if len(vol_clean) > 0 else 1.0

    base_high = float(base_slice['High'].max())
    base_low  = float(base_slice['Low'].min())

    breakout_level = max(base_high, ipo_day_high)

    return {
        'ipo_day_high':     ipo_day_high,
        'ipo_day_close':    ipo_day_close,
        'ipo_day_vol':      ipo_day_vol,
        'ipo_day_value_cr': round(ipo_day_value_cr, 2),
        'liquidity_ok':     liquidity_ok,
        'liquidity_status': liquidity_status,
        'base_high':        base_high,
        'base_low':         base_low,
        'base_vol_avg':     base_vol_avg,
        'breakout_level':   breakout_level,
        'base_end_idx':     skip + window,
        'base_start_date':  df.index[skip],
        'base_end_date':    df.index[skip + window - 1],
    }


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def detect_ipo_stage_bt(df_slice: pd.DataFrame, ipo_day_high: float,
                         breakout_level: float, base_low: float,
                         base_vol_avg: float, cfg: dict) -> str:
    """
    Classify a stock into its current IPO pattern stage using data up to df_slice.
    Used in the backtest to log which stage triggered each trade entry.

    Stage 3 — Breakout  : price > breakout_level + volume confirmed
    Stage 2 — Reclaiming: price > EMA10, still below breakout level
    Stage 1 — Base      : price below IPO day high, volume contracting
    Failed              : price >10% below base low
    """
    if len(df_slice) < 5:
        return 'Too Early'

    close   = df_slice['Close']
    volume  = df_slice['Volume']
    ema10   = compute_ema(close, cfg['ema_period'])

    latest_close = float(close.iloc[-1])
    latest_vol   = float(volume.iloc[-1])
    latest_ema   = float(ema10.iloc[-1])

    r5 = float(volume.iloc[-5:].replace(0, np.nan).mean())
    lw = float(volume.iloc[:5].replace(0, np.nan).mean())
    if np.isnan(lw) or lw == 0:
        lw = r5 if not np.isnan(r5) else 1.0
    vol_contracting = (not np.isnan(r5)) and r5 < lw

    # Use base_vol_avg for Stage 3 check — same reference as entry trigger for consistency
    vol_confirmed = (base_vol_avg > 0 and latest_vol >= cfg['vol_multiplier'] * base_vol_avg)

    if latest_close < base_low * 0.90:
        return 'Failed'
    if latest_close > breakout_level and vol_confirmed:
        return 'Stage 3 — Breakout'
    if latest_close > latest_ema and latest_close < breakout_level:
        return 'Stage 2 — Reclaiming'
    if latest_close <= ipo_day_high and vol_contracting:
        return 'Stage 1 — Building Base'
    return 'Stage 1 — Building Base'


# ═══════════════════════════════════════════════════════════════════════════════
#  SETUP TYPE DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def detect_flag_setup(df_slice: pd.DataFrame, base: dict) -> bool:
    """
    FLAG: tight consolidation during base period.
    Criteria: (base_high - base_low) / base_high < 15%  AND  volume declining.
    """
    bh = base['base_high']
    bl = base['base_low']
    if bh <= 0:
        return False
    range_pct = (bh - bl) / bh
    if range_pct >= 0.15:
        return False
    vols = df_slice['Volume'].replace(0, np.nan).dropna()
    if len(vols) < 10:
        return False
    first_half = vols.iloc[:len(vols)//2].mean()
    second_half = vols.iloc[len(vols)//2:].mean()
    return second_half < first_half


def detect_uturn_setup(df_slice: pd.DataFrame, base: dict) -> bool:
    """
    U-TURN: initial decline in base, then higher lows in second half.
    """
    closes = df_slice['Close']
    if len(closes) < 10:
        return False
    mid = len(closes) // 2
    first_low  = closes.iloc[:mid].min()
    second_low = closes.iloc[mid:].min()
    first_half_trend  = closes.iloc[:mid].iloc[-1] < closes.iloc[:mid].iloc[0]
    second_half_trend = second_low > first_low
    return first_half_trend and second_half_trend


def detect_earlyboom_setup(df_slice: pd.DataFrame, base: dict, sma10: pd.Series) -> bool:
    """
    EARLY BOOM: strong close in first week above IPO day high, then holds SMA10.
    """
    if len(df_slice) < 10:
        return False
    first_week_high = df_slice['Close'].iloc[:5].max()
    ipo_high = base['ipo_day_high']
    if first_week_high <= ipo_high:
        return False
    sma10_slice = sma10.reindex(df_slice.index)
    recent_closes = df_slice['Close'].iloc[-5:]
    recent_sma    = sma10_slice.iloc[-5:]
    holds_sma = (recent_closes >= recent_sma).mean() >= 0.6
    return holds_sma


def detect_ipo_setup_type(df_slice: pd.DataFrame, base: dict, sma10: pd.Series) -> str:
    """
    Return the primary setup type: FLAG, U-TURN, EARLY BOOM, or STANDARD.
    Checks in order of priority.
    """
    if detect_earlyboom_setup(df_slice, base, sma10):
        return 'EARLY BOOM'
    if detect_flag_setup(df_slice, base):
        return 'FLAG'
    if detect_uturn_setup(df_slice, base):
        return 'U-TURN'
    return 'STANDARD'


# ═══════════════════════════════════════════════════════════════════════════════
#  TRADE SIMULATION (per stock)
# ═══════════════════════════════════════════════════════════════════════════════

def simulate_stock_trades(ticker: str, df: pd.DataFrame, base: dict,
                          cfg: dict, promoter_quality: dict | None = None) -> list[dict]:
    """
    Detect breakout signals and simulate entries/exits for one IPO stock.

    Pipeline:
      Step 2 : IPO Day Liquidity filter (hard exclusion)
      Step 3 : Promoter quality (informational metadata)
      Step 5 : Entry at Stage 3 — close > breakout_level + volume ≥ 1.5× avg + above EMA10
      Step 6 : Enter at next-day open, 10% allocation
      Step 7 : Partial booking — sell 1/3 at 15% gain, move SL to entry (breakeven)
      Step 8 : Trail remaining 2/3 with EMA10 (exit on close < EMA10 once above it)
      Step 9 : Full exit on EMA10 break OR hard stop (8% below entry)
    """
    # Step 2: Liquidity filter (hard exclusion)
    if not base.get('liquidity_ok', True):
        return []

    # Step 3: Promoter quality (informational)
    symbol       = ticker.replace('.NS', '').upper()
    pq_info      = (promoter_quality or {}).get(symbol, {})
    promoter_val = pq_info.get('PromoterBacked', 'Unknown')
    if promoter_val not in ('YES', 'NO'):
        promoter_val = 'Unknown'

    trades    = []
    # EMA10 for entry filter only (FIX 4: use ewm)
    ema       = compute_ema(df['Close'], cfg['ema_period'])
    # SMA10 for trailing stop exit (FIX 4: must use rolling(), not ewm())
    sma10     = df['Close'].rolling(cfg['ema_period']).mean()
    # Rolling 20-day volume avg for volume confirmation (FIX 3)
    vol_20    = df['Volume'].rolling(20).mean()

    alloc     = CFG['initial_capital'] * cfg['max_alloc_pct']
    company   = COMPANY_NAMES.get(ticker, ticker)

    scan_start          = base['base_end_idx']
    in_trade            = False
    entry_price         = 0.0
    entry_idx           = 0
    stop_price          = 0.0
    sma_was_above       = False
    partial_done        = False
    partial_price       = 0.0
    partial_pct         = 0.0
    last_exit_idx       = -cfg['cooldown_days'] - 1
    pending_entry_stage = 'Stage 3 — Breakout'
    setup_type          = 'STANDARD'

    for i in range(scan_start, len(df)):
        close_i  = float(df['Close'].iloc[i])
        vol_i    = float(df['Volume'].iloc[i])
        ema_i    = float(ema.iloc[i])
        sma10_i  = float(sma10.iloc[i]) if not pd.isna(sma10.iloc[i]) else ema_i
        vol20_i  = float(vol_20.iloc[i]) if not pd.isna(vol_20.iloc[i]) else 1.0
        date_i   = df.index[i]

        # ── Manage open trade ─────────────────────────────────────────────────
        if in_trade:
            hold_days = i - entry_idx

            if close_i > sma10_i:
                sma_was_above = True

            # Step 7: Partial booking — 1/3 at first target, move SL to cost
            if cfg.get('partial_booking', False) and not partial_done:
                unrealized_pct = (close_i - entry_price) / entry_price * 100
                if unrealized_pct >= cfg.get('partial_target_pct', 0.15) * 100:
                    partial_done  = True
                    partial_price = close_i
                    partial_pct   = unrealized_pct
                    stop_price    = entry_price   # Step 7: SL moved to breakeven

            exit_reason = None
            exit_price  = close_i

            if close_i <= stop_price:
                exit_reason = 'SL→Breakeven' if partial_done else 'Hard Stop'
            elif sma_was_above and close_i < sma10_i:
                exit_reason = 'SMA10 Trail'   # FIX 4: use SMA10, not EMA10
            elif hold_days >= cfg['max_hold_days']:
                exit_reason = 'Max Hold Days'

            if exit_reason:
                if i + 1 < len(df):
                    exit_price = float(df['Open'].iloc[i + 1])

                shares = alloc / entry_price
                if partial_done:
                    # Blended PnL: 1/3 booked at partial_price, 2/3 at exit_price
                    pnl_pct = (
                        (1 / 3) * partial_pct +
                        (2 / 3) * (exit_price - entry_price) / entry_price * 100
                    )
                else:
                    pnl_pct = (exit_price - entry_price) / entry_price * 100

                exit_date = df.index[i + 1].date() if i + 1 < len(df) else date_i.date()
                trades.append({
                    'Ticker':            ticker,
                    'Company':           company,
                    'Entry_Date':        df.index[entry_idx].date(),
                    'Entry_Price':       round(entry_price, 2),
                    'Exit_Date':         exit_date,
                    'Exit_Price':        round(exit_price, 2),
                    'Shares':            round(shares, 4),
                    'Capital_Deployed':  round(alloc, 2),
                    'PnL':               round(shares * (exit_price - entry_price), 2),
                    'PnL_Pct':           round(pnl_pct, 2),
                    'Holding_Days':      hold_days,
                    'Exit_Reason':       exit_reason,
                    'Status':            'Closed',
                    'Result':            'Win' if pnl_pct > 0 else 'Loss',
                    'Partial_Booked':    partial_done,
                    'Partial_Price':     round(partial_price, 2) if partial_done else None,
                    'Partial_Pct':       round(partial_pct, 2) if partial_done else None,
                    'IPO_Day_Value_Cr':  base['ipo_day_value_cr'],
                    'Liquidity_Status':  base['liquidity_status'],
                    'Promoter_Backed':   promoter_val,
                    'Entry_Stage':       pending_entry_stage,
                    'Setup_Type':        setup_type,
                })
                in_trade      = False
                sma_was_above = False
                partial_done  = False
                partial_price = 0.0
                partial_pct   = 0.0
                last_exit_idx = i

        # ── Check entry signal (Step 5: Stage 3 trigger) ─────────────────────
        elif i + 1 < len(df) and (i - last_exit_idx) >= cfg['cooldown_days']:
            price_ok = close_i > base['breakout_level']
            # FIX 3: use rolling 20-day volume avg, not static base_vol_avg
            vol_ok   = vol20_i > 0 and vol_i > vol20_i * cfg['vol_multiplier']
            ema_ok   = close_i > ema_i if cfg['use_ema_filter'] else True

            if price_ok and vol_ok and ema_ok:
                pending_stage = detect_ipo_stage_bt(
                    df.iloc[:i + 1],
                    base['ipo_day_high'],
                    base['breakout_level'],
                    base['base_low'],
                    base['base_vol_avg'],
                    cfg,
                )
                # Detect setup type using base window data
                setup_type = detect_ipo_setup_type(
                    df.iloc[base['base_end_idx'] - base['base_end_idx'] + 1: i + 1]
                    if base['base_end_idx'] > 0 else df.iloc[:i + 1],
                    base,
                    sma10,
                )
                entry_price = float(df['Open'].iloc[i + 1])  # Step 6: next-day open
                if entry_price <= 0:
                    entry_price = close_i
                entry_idx  = i + 1
                stop_price = max(
                    base['base_low'],
                    entry_price * (1 - cfg['hard_stop_pct']),
                )
                in_trade            = True
                sma_was_above       = False
                partial_done        = False
                partial_price       = 0.0
                partial_pct         = 0.0
                pending_entry_stage = pending_stage

    # ── Close any still-open trade at last available price ────────────────────
    if in_trade:
        last_price = float(df['Close'].iloc[-1])
        shares     = alloc / entry_price
        if partial_done:
            pnl_pct = (
                (1 / 3) * partial_pct +
                (2 / 3) * (last_price - entry_price) / entry_price * 100
            )
        else:
            pnl_pct = (last_price - entry_price) / entry_price * 100

        trades.append({
            'Ticker':            ticker,
            'Company':           company,
            'Entry_Date':        df.index[entry_idx].date(),
            'Entry_Price':       round(entry_price, 2),
            'Exit_Date':         df.index[-1].date(),
            'Exit_Price':        round(last_price, 2),
            'Shares':            round(shares, 4),
            'Capital_Deployed':  round(alloc, 2),
            'PnL':               round(shares * (last_price - entry_price), 2),
            'PnL_Pct':           round(pnl_pct, 2),
            'Holding_Days':      len(df) - 1 - entry_idx,
            'Exit_Reason':       'Open',
            'Status':            'Open',
            'Result':            'Open',
            'Partial_Booked':    partial_done,
            'Partial_Price':     round(partial_price, 2) if partial_done else None,
            'Partial_Pct':       round(partial_pct, 2) if partial_done else None,
            'IPO_Day_Value_Cr':  base['ipo_day_value_cr'],
            'Liquidity_Status':  base['liquidity_status'],
            'Promoter_Backed':   promoter_val,
            'Entry_Stage':       pending_entry_stage,
            'Setup_Type':        setup_type,
        })

    return trades


# ═══════════════════════════════════════════════════════════════════════════════
#  PORTFOLIO SIMULATION (day-by-day equity curve)
# ═══════════════════════════════════════════════════════════════════════════════

def build_equity_curve(all_trades: list[dict], ohlcv: dict, cfg: dict) -> pd.DataFrame:
    """
    Build a daily equity curve by tracking cash + mark-to-market open positions.
    Returns DataFrame with columns: Date, Portfolio_Value.
    """
    if not all_trades:
        return pd.DataFrame(columns=['Date', 'Portfolio_Value'])

    all_dates = set()
    for df in ohlcv.values():
        all_dates.update(df.index)
    date_spine = sorted(all_dates)

    entry_map: dict = {}
    exit_map:  dict = {}
    for t in all_trades:
        ed = pd.Timestamp(t['Entry_Date'])
        xd = pd.Timestamp(t['Exit_Date'])
        entry_map.setdefault(ed, []).append(t)
        if t['Status'] == 'Closed':
            exit_map.setdefault(xd, []).append(t)

    cash             = float(cfg['initial_capital'])
    open_pos: dict   = {}
    equity_records   = []
    position_alloc   = cfg['initial_capital'] * cfg['max_alloc_pct']

    for date in date_spine:
        ts = pd.Timestamp(date)

        for t in exit_map.get(ts, []):
            tk = t['Ticker']
            if tk in open_pos:
                proceeds = open_pos[tk]['shares'] * t['Exit_Price']
                cash    += proceeds
                del open_pos[tk]

        for t in entry_map.get(ts, []):
            tk = t['Ticker']
            if tk in open_pos:
                continue
            if len(open_pos) >= cfg['max_positions']:
                continue
            if cash < position_alloc * 0.5:
                continue
            shares    = position_alloc / t['Entry_Price']
            cost      = shares * t['Entry_Price']
            cash     -= cost
            open_pos[tk] = {'shares': shares, 'ticker': tk}

        mkt_value = cash
        for tk, pos in open_pos.items():
            df = ohlcv.get(tk)
            if df is not None and ts in df.index:
                price = float(df.loc[ts, 'Close'])
            elif df is not None and not df.empty:
                prior = df[df.index <= ts]
                price = float(prior['Close'].iloc[-1]) if not prior.empty else 0.0
            else:
                price = 0.0
            mkt_value += pos['shares'] * price

        equity_records.append({'Date': ts, 'Portfolio_Value': mkt_value})

    return pd.DataFrame(equity_records)


# ═══════════════════════════════════════════════════════════════════════════════
#  METRICS
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_metrics(trades: list[dict], equity_df: pd.DataFrame, cfg: dict) -> dict:
    """Calculate strategy performance metrics."""
    closed  = [t for t in trades if t['Status'] == 'Closed']
    initial = cfg['initial_capital']

    if equity_df.empty or len(equity_df) < 2:
        return {'error': 'Not enough equity data to calculate metrics'}

    final_value = float(equity_df['Portfolio_Value'].iloc[-1])
    start_date  = equity_df['Date'].iloc[0]
    end_date    = equity_df['Date'].iloc[-1]
    years       = max((end_date - start_date).days / 365.25, 0.01)

    total_ret = (final_value - initial) / initial * 100
    cagr      = ((final_value / initial) ** (1 / years) - 1) * 100

    daily_ret = equity_df['Portfolio_Value'].pct_change().dropna()
    sharpe    = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else 0

    cummax    = equity_df['Portfolio_Value'].cummax()
    drawdowns = (equity_df['Portfolio_Value'] - cummax) / cummax * 100
    max_dd    = float(drawdowns.min())

    winners   = [t for t in closed if t['PnL'] > 0]
    losers    = [t for t in closed if t['PnL'] <= 0]
    win_rate  = len(winners) / len(closed) * 100 if closed else 0
    avg_gain  = np.mean([t['PnL_Pct'] for t in winners]) if winners else 0
    avg_loss  = np.mean([t['PnL_Pct'] for t in losers])  if losers  else 0

    return {
        'Final_Portfolio_Value': round(final_value, 2),
        'Total_Return_Pct':      round(total_ret, 2),
        'CAGR_Pct':              round(cagr, 2),
        'Sharpe_Ratio':          round(float(sharpe), 2),
        'Max_Drawdown_Pct':      round(max_dd, 2),
        'Total_Trades':          len(closed),
        'Open_Trades':           len(trades) - len(closed),
        'Win_Rate_Pct':          round(win_rate, 2),
        'Avg_Gain_Pct':          round(avg_gain, 2),
        'Avg_Loss_Pct':          round(avg_loss, 2),
        'Start_Date':            str(start_date.date()),
        'End_Date':              str(end_date.date()),
        'Years':                 round(years, 2),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  OUTPUT  —  CSV + CHART
# ═══════════════════════════════════════════════════════════════════════════════

def save_outputs(trades: list[dict], equity_df: pd.DataFrame,
                 benchmark: pd.Series, cfg: dict):
    """Save trades CSV, equity CSV, and comparison chart."""

    trades_df = pd.DataFrame(trades)
    if not trades_df.empty:
        trades_df = trades_df.sort_values('Entry_Date')
    trades_df.to_csv(cfg['trades_out'], index=False)
    print(f'  Saved: {cfg["trades_out"]}')

    if not equity_df.empty and not benchmark.empty:
        first_date   = equity_df['Date'].iloc[0]
        bench_start  = benchmark.asof(first_date)
        bench_norm   = (benchmark / bench_start * 100).rename('Benchmark_Value')
        bench_norm   = bench_norm.reindex(equity_df['Date']).ffill()

        out_equity = equity_df.copy()
        out_equity['Benchmark_Value'] = bench_norm.values
        out_equity.to_csv(cfg['equity_out'], index=False)
        print(f'  Saved: {cfg["equity_out"]}')

        strat_norm = equity_df['Portfolio_Value'] / float(equity_df['Portfolio_Value'].iloc[0]) * 100

        fig, ax = plt.subplots(figsize=(14, 6))
        fig.patch.set_facecolor('#0e1117')
        ax.set_facecolor('#0e1117')

        ax.plot(equity_df['Date'], strat_norm,
                color='#00c853', linewidth=2.5, label='IPO Edge Strategy', zorder=3)
        ax.plot(equity_df['Date'], bench_norm.values,
                color='#7c9cff', linewidth=2, linestyle='--',
                label='NiftyBees (Market)', zorder=2)
        ax.axhline(y=100, color='#3a4460', linewidth=1, linestyle=':')

        for t in [x for x in trades if x['Status'] == 'Closed']:
            try:
                ed  = pd.Timestamp(t['Entry_Date'])
                idx = equity_df[equity_df['Date'] >= ed].index
                if len(idx) > 0:
                    val = float(strat_norm.iloc[idx[0]])
                    ax.scatter(ed, val, color='#00c853', s=30, zorder=4, alpha=0.7)
            except Exception:
                pass

        ax.set_xlabel('Date', color='#8892a4', fontsize=11)
        ax.set_ylabel('Normalised Value (Start = 100)', color='#8892a4', fontsize=11)
        ax.set_title('IPO Edge Strategy vs NiftyBees Benchmark',
                     color='#dde4f0', fontsize=14, pad=14)
        ax.tick_params(colors='#8892a4')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha='right')
        for spine in ax.spines.values():
            spine.set_edgecolor('#242d47')
        ax.grid(color='#242d47', linewidth=0.5, alpha=0.7)
        ax.legend(fontsize=11, facecolor='#151927', labelcolor='#dde4f0',
                  edgecolor='#242d47')

        plt.tight_layout()
        plt.savefig(cfg['chart_out'], dpi=180, bbox_inches='tight',
                    facecolor=fig.get_facecolor())
        plt.close()
        print(f'  Saved: {cfg["chart_out"]}')


_DEFAULTS_IPO = {
    'initial_capital':      5_00_000,
    'max_alloc_pct':        0.10,
    'max_positions':        10,
    'vol_multiplier':       1.5,
    'hard_stop_pct':        0.08,
    'max_hold_days':        90,
    'cooldown_days':        15,
    'partial_booking':      True,
    'partial_target_pct':   0.15,
    'min_ipo_day_value_cr': 10,
    'skip_initial_days':    3,
    'base_window':          40,
    'use_ema_filter':       True,
}


def print_config_summary(cfg: dict, W: int = 70):
    """Print IPO Edge strategy rules and active config to terminal."""
    sep = lambda ch='─': ch * W

    print('\n' + sep('═'))
    print('  IPO EDGE — Strategy Configuration & Rules')
    print(sep('═'))

    rules = [
        ('Step 1', 'Listed within last 12 months  (live screener only)'),
        ('Step 2', f'IPO Day traded value ≥ ₹{cfg["min_ipo_day_value_cr"]} Cr  (hard exclusion)'),
        ('Step 3', f'Promoter Quality check  (informational only — no exclusion)'),
        ('Step 4', f'Stage detection  (1=Base, 2=Reclaim, 3=Breakout)'),
        ('Step 5', f'Entry: Close > breakout_level + Vol ≥ {cfg["vol_multiplier"]}× avg + EMA10 filter'),
        ('Step 6', f'Execute at next-day open  |  {cfg["max_alloc_pct"]*100:.0f}% allocation'),
        ('Step 7', f'Partial booking at +{cfg["partial_target_pct"]*100:.0f}%  → sell 1/3, move SL to cost  '
                   f'[active = {cfg["partial_booking"]}]'),
        ('Step 8', f'Trail remaining 2/3 with EMA{cfg["ema_period"]}'),
        ('Step 9', f'Full exit: Close < EMA{cfg["ema_period"]}  OR  >{cfg["hard_stop_pct"]*100:.0f}% hard stop'),
        ('Exit+ ', f'Max hold = {cfg["max_hold_days"]} days  |  Cooldown = {cfg["cooldown_days"]} days'),
    ]

    print(f'\n  Total rules active : {len(rules)}')
    print(f'  Capital            : ₹{cfg["initial_capital"]:,.0f}')
    print(f'  Position sizing    : {cfg["max_alloc_pct"]*100:.0f}% per stock  '
          f'| max {cfg["max_positions"]} concurrent')
    print()
    for step, desc in rules:
        print(f'    [{step}]  {desc}')

    non_def = [(k, cfg[k], _DEFAULTS_IPO[k]) for k in _DEFAULTS_IPO
               if k in cfg and cfg[k] != _DEFAULTS_IPO[k]]
    print()
    if non_def:
        print('  Non-default parameters:')
        for k, v, d in non_def:
            print(f'    {k} = {v}  (default: {d})')
    else:
        print('  All parameters at default values.')

    p = Path(cfg.get('trades_out', 'ipo_edge_trades.csv'))
    if p.exists():
        try:
            prev   = pd.read_csv(p)
            closed = prev[prev['Status'] == 'Closed']
            wins   = (closed['Result'] == 'Win').sum() if 'Result' in closed.columns else 0
            tot    = len(closed)
            wr     = wins / tot * 100 if tot else 0
            pb     = int(closed.get('Partial_Booked', pd.Series(False)).sum()) if 'Partial_Booked' in closed.columns else 0
            print(f'\n  Last saved results : {tot} closed trades  |  Win rate: {wr:.1f}%  '
                  f'|  Partial bookings: {pb}')
        except Exception:
            pass

    print(sep('─'))


def print_diagnostic_report_ipo(ohlcv: dict, cfg: dict, W: int = 70):
    """
    For each IPO entry filter, count how many stocks pass.
    Helps identify which filter eliminates all trades.
    Only runs when cfg['diagnostic_mode'] is True.
    """
    if not cfg.get('diagnostic_mode', False):
        return

    sep = '─' * W
    print('\n' + sep)
    print('  IPO DIAGNOSTIC REPORT — Per-filter pass counts')
    print(sep)

    f_total = f_min_bars = f_liquidity = f_ipo_age = f_base = f_signal = 0
    min_liq      = cfg.get('min_ipo_day_value_cr', 10)
    max_age      = cfg.get('max_ipo_age_days', 252)
    min_days     = cfg.get('min_days_needed', 43)

    for ticker, df in ohlcv.items():
        f_total += 1

        if len(df) < min_days:
            continue
        f_min_bars += 1

        base = compute_base(df, cfg)
        if base is None:
            continue

        if not base.get('liquidity_ok', True):
            continue
        f_liquidity += 1

        if len(df) > max_age:
            continue
        f_ipo_age += 1

        f_base += 1

        # Check if any breakout signal exists in scan window
        ema    = compute_ema(df['Close'], cfg['ema_period'])
        sma10  = df['Close'].rolling(cfg['ema_period']).mean()
        vol_20 = df['Volume'].rolling(20).mean()
        scan_start = base['base_end_idx']
        found_signal = False
        for i in range(scan_start, len(df) - 1):
            close_i = float(df['Close'].iloc[i])
            vol_i   = float(df['Volume'].iloc[i])
            ema_i   = float(ema.iloc[i])
            vol20_i = float(vol_20.iloc[i]) if not pd.isna(vol_20.iloc[i]) else 1.0
            price_ok = close_i > base['breakout_level']
            vol_ok   = vol20_i > 0 and vol_i > vol20_i * cfg['vol_multiplier']
            ema_ok   = close_i > ema_i if cfg['use_ema_filter'] else True
            if price_ok and vol_ok and ema_ok:
                found_signal = True
                break
        if found_signal:
            f_signal += 1

    print(f'  Total tickers loaded          : {f_total}')
    print(f'  F1 — Min bars ({min_days}d)         : {f_min_bars}')
    print(f'  F2 — Liquidity ≥₹{min_liq}Cr        : {f_liquidity}')
    print(f'  F3 — IPO age <{max_age} days      : {f_ipo_age}')
    print(f'  F4 — Base formed               : {f_base}')
    print(f'  F5 — At least 1 breakout signal: {f_signal}')
    print(sep)


def print_summary(metrics: dict, trades: list[dict]):
    W = 70
    print('\n' + '=' * W)
    print('  IPO EDGE — Backtest Summary')
    print('=' * W)
    if 'error' in metrics:
        print(f'\n  {metrics["error"]}')
        return

    print(f'\n  Period          : {metrics["Start_Date"]}  to  {metrics["End_Date"]}')
    print(f'  Duration        : {metrics["Years"]:.1f} years')
    print(f'\n  Strategy Return : {metrics["Total_Return_Pct"]:+.2f}%')
    print(f'  CAGR            : {metrics["CAGR_Pct"]:+.2f}%')
    print(f'  Sharpe Ratio    : {metrics["Sharpe_Ratio"]:.2f}')
    print(f'  Max Drawdown    : {metrics["Max_Drawdown_Pct"]:.2f}%')
    print(f'\n  Total Trades    : {metrics["Total_Trades"]}  closed  +  {metrics["Open_Trades"]}  open')
    print(f'  Win Rate        : {metrics["Win_Rate_Pct"]:.1f}%')
    print(f'  Avg Gain        : {metrics["Avg_Gain_Pct"]:+.2f}%')
    print(f'  Avg Loss        : {metrics["Avg_Loss_Pct"]:+.2f}%')

    if trades:
        print('\n  Recent Trades:')
        closed_sorted = sorted(
            [t for t in trades if t['Status'] == 'Closed'],
            key=lambda x: x['Exit_Date'], reverse=True
        )[:8]
        for t in closed_sorted:
            sign    = '+' if t['PnL_Pct'] >= 0 else ''
            prom    = t.get('Promoter_Backed', '?')
            liq     = t.get('IPO_Day_Value_Cr', 0)
            stage   = t.get('Entry_Stage', '?')
            partial = ' [P]' if t.get('Partial_Booked') else ''
            print(
                f'    {t["Ticker"]:<20} {sign}{t["PnL_Pct"]:6.2f}%{partial}  '
                f'{t["Holding_Days"]:3d}d  {t["Exit_Reason"]:<16}  '
                f'{stage:<22}  Liq:₹{liq:.1f}Cr  Promoter:{prom}'
            )
    print('\n' + '=' * W + '\n')


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print_config_summary(CFG)
    print('\n  IPO Edge — Loading data ...')
    ohlcv     = load_ohlcv(CFG['data_folder'])
    benchmark = load_benchmark(CFG['data_folder'], CFG['benchmark'])

    if not ohlcv:
        print('\n  No data found. Run ipo_edge_downloader.py first.\n')
        return

    print(f'  Loaded {len(ohlcv)} stocks from {CFG["data_folder"]}/\n')

    # Load promoter quality (informational)
    promoter_quality = _load_promoter_quality(CFG.get('promoter_quality_file', 'ipo_promoter_quality.csv'))
    if promoter_quality:
        print(f'  Promoter data   : {len(promoter_quality)} stocks loaded from {CFG["promoter_quality_file"]}')
    else:
        print(f'  Promoter data   : file not found — showing Unknown for all stocks')

    min_liq  = CFG.get('min_ipo_day_value_cr', 10)
    max_age  = CFG.get('max_ipo_age_days', 252)
    print(f'  Liquidity filter: IPO Day traded value ≥ ₹{min_liq} Cr')
    print(f'  IPO age filter  : ≤ {max_age} trading days since listing\n')

    print_diagnostic_report_ipo(ohlcv, CFG)

    all_trades = []
    skipped    = []
    liq_failed = []
    age_failed = []

    for ticker, df in sorted(ohlcv.items()):
        base = compute_base(df, CFG)
        if base is None:
            skipped.append(f'{ticker} ({len(df)} days < {CFG["min_days_needed"]} needed)')
            continue

        if not base['liquidity_ok']:
            liq_failed.append(
                f'{ticker}  IPO Day value ₹{base["ipo_day_value_cr"]:.1f}Cr < ₹{min_liq}Cr'
            )
            continue

        # IPO age filter: skip stocks with more than max_ipo_age_days trading days
        if len(df) > max_age:
            age_failed.append(f'{ticker}  ({len(df)} days > {max_age} max)')
            continue

        trades = simulate_stock_trades(ticker, df, base, CFG, promoter_quality)
        if trades:
            print(f'  {ticker:<22} {len(trades)} trade(s) detected  '
                  f'[Liq:₹{base["ipo_day_value_cr"]:.1f}Cr]')
        else:
            print(f'  {ticker:<22} no breakout signal  '
                  f'[Liq:₹{base["ipo_day_value_cr"]:.1f}Cr]')
        all_trades.extend(trades)

    if age_failed:
        print(f'\n  Excluded (IPO too old — >{max_age} days):')
        for s in age_failed:
            print(f'    {s}')
    if liq_failed:
        print(f'\n  Excluded (Low Liquidity):')
        for s in liq_failed:
            print(f'    {s}')
    if skipped:
        print(f'\n  Skipped (base not yet formed):')
        for s in skipped:
            print(f'    {s}')

    print(f'\n  Total trades: {len(all_trades)}')

    equity_df = build_equity_curve(all_trades, ohlcv, CFG)
    metrics   = calculate_metrics(all_trades, equity_df, CFG)

    print_summary(metrics, all_trades)

    print('  Saving outputs ...')
    save_outputs(all_trades, equity_df, benchmark, CFG)
    print('\n  Backtest complete.\n')


if __name__ == '__main__':
    main()
