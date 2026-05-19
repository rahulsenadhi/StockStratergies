"""Post-hoc trade analytics.

Reconstructs MAE / MFE per trade from the existing trades CSV + OHLCV files,
without touching the backtest engines. Aggregates win-rate and expectancy
buckets that answer:

    • Optimal entry  — which entry features predict winners?
    • Optimal sell   — at what gain bucket does forward expectancy peak?
    • Loss avoidance — what MAE level should the stop sit at?

All functions are pure: they take DataFrames / dicts in and return DataFrames
out. The dashboard layer formats them. The backtest engines are not modified.

Schema expected on the trades DataFrame (column names match what the three
strategies already write):
    Ticker, Entry_Date, Entry_Price, Exit_Date, Exit_Price, Exit_Reason,
    PnL_Pct, Holding_Days, Result, [Entry_Type], [Recovery_Speed], [Score]
"""

import numpy as np
import pandas as pd

from core import regime as core_regime


# ── Loaders ──────────────────────────────────────────────────────────────────

def load_trades(path: str) -> pd.DataFrame:
    """Read a trades CSV, coerce dates, drop unclosed rows."""
    df = pd.read_csv(path)
    for col in ('Entry_Date', 'Exit_Date'):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    if 'Exit_Date' in df.columns:
        df = df.dropna(subset=['Exit_Date'])
    return df.reset_index(drop=True)


# ── MAE / MFE reconstruction ─────────────────────────────────────────────────

def compute_mae_mfe(
    trades: pd.DataFrame,
    ohlcv: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Add MAE_Pct, MFE_Pct, Time_To_MAE, Time_To_MFE columns.

    MAE = max % drawdown vs entry seen during the trade.
    MFE = max % run-up vs entry seen during the trade.

    Both are signed % from entry: MAE ≤ 0, MFE ≥ 0.
    Time_* are trading-day offsets from entry to that extreme.
    """
    mae_pct, mfe_pct, t_mae, t_mfe = [], [], [], []

    for _, row in trades.iterrows():
        tkr = row['Ticker']
        df = ohlcv.get(tkr)
        if df is None or df.empty:
            mae_pct.append(np.nan); mfe_pct.append(np.nan)
            t_mae.append(np.nan);   t_mfe.append(np.nan)
            continue

        entry_dt = row['Entry_Date']
        exit_dt = row['Exit_Date']
        entry_px = float(row['Entry_Price'])

        path = df.loc[(df.index >= entry_dt) & (df.index <= exit_dt)]
        if path.empty or entry_px <= 0:
            mae_pct.append(np.nan); mfe_pct.append(np.nan)
            t_mae.append(np.nan);   t_mfe.append(np.nan)
            continue

        low_min = path['Low'].min() if 'Low' in path else path['Close'].min()
        high_max = path['High'].max() if 'High' in path else path['Close'].max()

        mae = (low_min - entry_px) / entry_px * 100
        mfe = (high_max - entry_px) / entry_px * 100

        mae_idx = path['Low'].idxmin() if 'Low' in path else path['Close'].idxmin()
        mfe_idx = path['High'].idxmax() if 'High' in path else path['Close'].idxmax()
        try:
            t_mae.append(int((mae_idx - entry_dt).days))
            t_mfe.append(int((mfe_idx - entry_dt).days))
        except Exception:
            t_mae.append(np.nan); t_mfe.append(np.nan)

        mae_pct.append(round(mae, 2))
        mfe_pct.append(round(mfe, 2))

    out = trades.copy()
    out['MAE_Pct'] = mae_pct
    out['MFE_Pct'] = mfe_pct
    out['Time_To_MAE'] = t_mae
    out['Time_To_MFE'] = t_mfe
    return out


# ── Regime tagging ───────────────────────────────────────────────────────────

def tag_regime_at_entry(
    trades: pd.DataFrame,
    benchmark: pd.Series | None,
    cfg: dict | None = None,
) -> pd.DataFrame:
    """Add Regime_At_Entry column ('Bull' / 'Bear' / 'Unknown').

    Reads benchmark Close series and the 3-condition gate from core.regime.
    Missing benchmark → all entries tagged 'Unknown'.
    """
    out = trades.copy()
    if benchmark is None or benchmark.empty:
        out['Regime_At_Entry'] = 'Unknown'
        return out

    series = core_regime.build_series(benchmark, cfg)
    if series is None or series.empty:
        out['Regime_At_Entry'] = 'Unknown'
        return out

    series = series.dropna()
    labels = []
    for entry_dt in out['Entry_Date']:
        try:
            # Use the regime value on the last bar at or before entry
            sub = series.loc[:entry_dt]
            if sub.empty:
                labels.append('Unknown')
            else:
                labels.append('Bull' if bool(sub.iloc[-1]) else 'Bear')
        except Exception:
            labels.append('Unknown')
    out['Regime_At_Entry'] = labels
    return out


# ── Aggregate metrics ────────────────────────────────────────────────────────

def _safe_win_rate(s: pd.Series) -> float:
    if len(s) == 0:
        return 0.0
    return (s > 0).sum() / len(s) * 100


def _expectancy(pnl: pd.Series) -> float:
    """Avg PnL per trade — combines win rate × payoff."""
    return pnl.mean() if len(pnl) else 0.0


def win_rate_by(trades: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Win rate + avg PnL + count, grouped by a column."""
    if group_col not in trades.columns:
        return pd.DataFrame()
    grp = trades.groupby(group_col, dropna=False)['PnL_Pct']
    return pd.DataFrame({
        'Count':      grp.count(),
        'Win_Rate':   grp.apply(_safe_win_rate).round(1),
        'Avg_PnL':    grp.mean().round(2),
        'Median_PnL': grp.median().round(2),
        'Expectancy': grp.mean().round(2),
    }).reset_index()


def win_rate_by_score_bucket(trades: pd.DataFrame, bins: int = 5) -> pd.DataFrame:
    """Bin Score column into deciles/quintiles and report win rate."""
    if 'Score' not in trades.columns or trades['Score'].isna().all():
        return pd.DataFrame()
    t = trades.copy()
    t['Score_Bucket'] = pd.qcut(t['Score'], bins, duplicates='drop')
    return win_rate_by(t, 'Score_Bucket')


def hold_day_curve(trades: pd.DataFrame, max_days: int = 130) -> pd.DataFrame:
    """Avg PnL grouped by 10-day holding bucket. Reveals optimal hold horizon."""
    if 'Holding_Days' not in trades.columns:
        return pd.DataFrame()
    t = trades.copy()
    t['Hold_Bucket'] = pd.cut(
        t['Holding_Days'].clip(upper=max_days),
        bins=[0, 10, 20, 30, 45, 60, 90, max_days],
        include_lowest=True,
    )
    return win_rate_by(t, 'Hold_Bucket')


# ── Optimal exit study ───────────────────────────────────────────────────────

def optimal_partial_levels(trades_with_mae: pd.DataFrame,
                           levels: list[float] | None = None) -> pd.DataFrame:
    """For each candidate partial-booking level, count how many trades would hit it
    (using MFE) and what % of those went on to finish positive vs faded.

    Helps answer: "Should partial be at +10%, +15%, +20%?"
    """
    if 'MFE_Pct' not in trades_with_mae.columns:
        return pd.DataFrame()
    levels = levels or [5, 10, 15, 20, 25, 30, 40, 50]
    rows = []
    for lvl in levels:
        hit = trades_with_mae[trades_with_mae['MFE_Pct'] >= lvl]
        if len(hit) == 0:
            continue
        # Of trades that touched lvl, how many finished above lvl vs faded?
        held_through = (hit['PnL_Pct'] >= lvl).sum()
        faded = len(hit) - held_through
        rows.append({
            'Level_Pct':    lvl,
            'Trades_Hit':   len(hit),
            'Pct_of_Total': round(len(hit) / len(trades_with_mae) * 100, 1),
            'Held_Through': held_through,
            'Faded':        faded,
            'Fade_Rate':    round(faded / len(hit) * 100, 1) if len(hit) else 0.0,
            'Avg_Final':    round(hit['PnL_Pct'].mean(), 2),
        })
    return pd.DataFrame(rows)


# ── Loss avoidance ───────────────────────────────────────────────────────────

def stop_loss_recommendation(trades_with_mae: pd.DataFrame,
                              percentiles: list[int] | None = None) -> dict:
    """Compare MAE distribution of winners vs losers.

    Recommended stop = N-th percentile of |MAE| among winners. Loose enough that
    most eventual winners survive, tight enough to cap losses.
    """
    if 'MAE_Pct' not in trades_with_mae.columns:
        return {}
    percentiles = percentiles or [80, 90, 95, 99]
    t = trades_with_mae.dropna(subset=['MAE_Pct'])
    winners = t[t['PnL_Pct'] > 0]['MAE_Pct'].abs()
    losers = t[t['PnL_Pct'] <= 0]['MAE_Pct'].abs()
    out = {
        'winner_count': int(len(winners)),
        'loser_count':  int(len(losers)),
        'winner_mae_mean': round(winners.mean(), 2) if len(winners) else None,
        'loser_mae_mean':  round(losers.mean(), 2)  if len(losers)  else None,
    }
    for p in percentiles:
        out[f'winner_mae_p{p}'] = round(np.percentile(winners, p), 2) if len(winners) else None
        out[f'loser_mae_p{p}']  = round(np.percentile(losers, p), 2)  if len(losers)  else None
    return out


def loss_clusters(trades: pd.DataFrame) -> dict:
    """Consecutive-loss runs, sorted chronologically by Exit_Date."""
    if 'Result' not in trades.columns and 'PnL_Pct' not in trades.columns:
        return {}
    t = trades.sort_values('Exit_Date').reset_index(drop=True)
    is_loss = (t['PnL_Pct'] <= 0).astype(int) if 'PnL_Pct' in t else (t['Result'] == 'Loss').astype(int)
    # Run-length encoding of consecutive 1s
    runs = []
    cur = 0
    for v in is_loss:
        if v == 1:
            cur += 1
        else:
            if cur > 0:
                runs.append(cur)
            cur = 0
    if cur > 0:
        runs.append(cur)
    return {
        'max_consecutive_losses': max(runs) if runs else 0,
        'avg_consecutive_losses': round(np.mean(runs), 2) if runs else 0.0,
        'num_loss_streaks':       len(runs),
        'total_losses':           int(is_loss.sum()),
    }


# ── Hold-period recommendations ──────────────────────────────────────────────

def optimal_hold_period(trades: pd.DataFrame) -> dict:
    """Recommend best holding-day buckets from historical trades.

    Returns dict with:
      best_return_bucket  — bucket with highest avg PnL (max expectancy)
      best_winrate_bucket — bucket with highest win rate (safest profit)
      curve               — full hold_day_curve DataFrame
    """
    curve = hold_day_curve(trades)
    if curve.empty:
        return {'curve': curve, 'best_return_bucket': None, 'best_winrate_bucket': None}

    # Need minimum 3 trades to consider a bucket reliable
    reliable = curve[curve['Count'] >= 3].copy()
    if reliable.empty:
        reliable = curve.copy()

    br = reliable.loc[reliable['Avg_PnL'].idxmax()]
    bw = reliable.loc[reliable['Win_Rate'].idxmax()]

    def _row_to_dict(row) -> dict:
        return {
            'bucket':    str(row.get('Hold_Bucket')),
            'count':     int(row['Count']),
            'win_rate':  float(row['Win_Rate']),
            'avg_pnl':   float(row['Avg_PnL']),
            'median_pnl': float(row.get('Median_PnL', 0)),
        }

    return {
        'curve':               curve,
        'best_return_bucket':  _row_to_dict(br),
        'best_winrate_bucket': _row_to_dict(bw),
    }


def safe_hold_period(trades: pd.DataFrame, stop_pct: float = 15.0) -> dict:
    """Find bucket where average loser-PnL stays better than -stop_pct.

    "Safe" = even if it's a loss, you won't lose more than the strategy's
    hard stop. Returns the longest such bucket (gives time for thesis to play out)
    and overall stats.

    Args:
        trades: trades DataFrame
        stop_pct: positive number — strategy's hard stop, e.g. 15 for ME's 15%

    Returns:
        dict with safe_bucket (best long safe hold), all_safe_buckets (list).
    """
    curve = hold_day_curve(trades)
    if curve.empty:
        return {'curve': curve, 'safe_bucket': None, 'all_safe_buckets': []}

    # For each bucket, compute avg loser PnL (only losing trades within bucket)
    if 'Holding_Days' not in trades.columns or 'PnL_Pct' not in trades.columns:
        return {'curve': curve, 'safe_bucket': None, 'all_safe_buckets': []}

    t = trades.copy()
    t['Hold_Bucket'] = pd.cut(
        t['Holding_Days'].clip(upper=130),
        bins=[0, 10, 20, 30, 45, 60, 90, 130],
        include_lowest=True,
    )

    safe_rows = []
    for bucket, grp in t.groupby('Hold_Bucket', dropna=False, observed=True):
        if grp.empty:
            continue
        losers = grp[grp['PnL_Pct'] < 0]
        avg_loser = float(losers['PnL_Pct'].mean()) if len(losers) else 0.0
        win_rate  = float((grp['PnL_Pct'] > 0).sum() / len(grp) * 100)
        avg_pnl   = float(grp['PnL_Pct'].mean())
        # Safe = average loser stays within stop budget (-stop_pct or better)
        is_safe = (len(losers) == 0) or (avg_loser >= -stop_pct)
        safe_rows.append({
            'bucket':     str(bucket),
            'count':      len(grp),
            'win_rate':   round(win_rate, 1),
            'avg_pnl':    round(avg_pnl, 2),
            'avg_loser':  round(avg_loser, 2),
            'is_safe':    is_safe,
        })

    all_safe = [r for r in safe_rows if r['is_safe'] and r['count'] >= 3]
    safe_bucket = all_safe[-1] if all_safe else None  # longest = last in time-ordered bins

    return {
        'curve':            curve,
        'safe_bucket':      safe_bucket,
        'all_safe_buckets': all_safe,
        'all_buckets':      safe_rows,
        'stop_pct':         stop_pct,
    }


# ── Per-ticker history ───────────────────────────────────────────────────────

def per_ticker_history(trades: pd.DataFrame, min_trades: int = 1) -> pd.DataFrame:
    """Aggregate every closed trade by ticker. Reveals recurring winners/losers."""
    if trades is None or trades.empty:
        return pd.DataFrame()
    if 'Ticker' not in trades.columns:
        return pd.DataFrame()

    g = trades.groupby('Ticker', dropna=False)
    out = pd.DataFrame({
        'Trades':        g.size(),
        'Wins':          g['PnL_Pct'].apply(lambda s: (s > 0).sum()),
        'Losses':        g['PnL_Pct'].apply(lambda s: (s <= 0).sum()),
        'Win_Rate':      g['PnL_Pct'].apply(_safe_win_rate).round(1),
        'Avg_PnL':       g['PnL_Pct'].mean().round(2),
        'Total_PnL':     g['PnL_Pct'].sum().round(2),
        'Best_Trade':    g['PnL_Pct'].max().round(2),
        'Worst_Trade':   g['PnL_Pct'].min().round(2),
    })
    if 'Holding_Days' in trades.columns:
        out['Avg_Hold']  = g['Holding_Days'].mean().round(0).astype(int)
    out = out[out['Trades'] >= min_trades].reset_index()
    out = out.sort_values('Total_PnL', ascending=False)
    return out


# ── Top-level summary ────────────────────────────────────────────────────────

def full_report(
    trades_csv: str,
    ohlcv: dict[str, pd.DataFrame],
    benchmark: pd.Series | None = None,
    regime_cfg: dict | None = None,
) -> dict:
    """One-shot driver from a CSV path."""
    trades = load_trades(trades_csv)
    return full_report_from_df(trades, ohlcv, benchmark, regime_cfg)


def full_report_from_df(
    trades: pd.DataFrame,
    ohlcv: dict[str, pd.DataFrame],
    benchmark: pd.Series | None = None,
    regime_cfg: dict | None = None,
) -> dict:
    """One-shot driver: returns every analytic bundle in a single dict.

    Optional `benchmark` (Close series) enables regime-at-entry tagging.
    Dashboard "Insights" tab can render each key as a section.
    """
    if trades is None or trades.empty:
        return {'trades': pd.DataFrame(), 'error': 'No trades'}

    # Coerce date columns if caller passed raw DataFrame
    trades = trades.copy()
    for col in ('Entry_Date', 'Exit_Date'):
        if col in trades.columns:
            trades[col] = pd.to_datetime(trades[col], errors='coerce')

    trades_x = compute_mae_mfe(trades, ohlcv)
    trades_x = tag_regime_at_entry(trades_x, benchmark, regime_cfg)

    # Hold-period analytics — best return + safe hold
    stop_default = 15.0  # ME default; IPO/Rotation can pass their own via regime_cfg later
    if regime_cfg and 'stop_loss_pct' in regime_cfg:
        stop_default = float(regime_cfg['stop_loss_pct']) * 100

    report = {
        'trades':            trades_x,
        'overall_win_rate':  round(_safe_win_rate(trades_x['PnL_Pct']), 1),
        'overall_avg_pnl':   round(trades_x['PnL_Pct'].mean(), 2),
        'overall_median':    round(trades_x['PnL_Pct'].median(), 2),
        'by_entry_type':     win_rate_by(trades_x, 'Entry_Type'),
        'by_recovery_speed': win_rate_by(trades_x, 'Recovery_Speed'),
        'by_exit_reason':    win_rate_by(trades_x, 'Exit_Reason'),
        'by_regime':         win_rate_by(trades_x, 'Regime_At_Entry'),
        'by_score_bucket':   win_rate_by_score_bucket(trades_x),
        'hold_curve':        hold_day_curve(trades_x),
        'optimal_hold':      optimal_hold_period(trades_x),
        'safe_hold':         safe_hold_period(trades_x, stop_pct=stop_default),
        'ticker_history':    per_ticker_history(trades_x),
        'partial_levels':    optimal_partial_levels(trades_x),
        'stop_recommendation': stop_loss_recommendation(trades_x),
        'loss_clusters':     loss_clusters(trades_x),
    }
    return report
