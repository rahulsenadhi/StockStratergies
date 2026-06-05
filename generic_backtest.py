"""Generic backtest engine for user-defined strategies.

Reads a strategy spec JSON (saved from the Add Strategy wizard) and runs an
event-driven daily-EOD backtest:

  1. Load universe (Nifty 50 / Full / Custom CSV)
  2. Build a daily feature panel: rsi_14, atr_14, sma_50, sma_200, volume_z, mcap_cr
     (PEAD-style sue/piotroski/pb deferred to Phase G)
  3. Each trading day: evaluate the DSL formula → signal vector
  4. Apply exit rules: time-based, hard stop, trailing stop, next-earnings (placeholder)
  5. Equal-weight portfolio (capped or unlimited)
  6. Write trades.csv + equity.csv + kpis.csv
  7. Update strategies_index.json with KPIs + last_run

CLI:
    python generic_backtest.py --spec strategies/my_strategy.json

  Or from Streamlit wizard via subprocess.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from core.data_io import load_ohlcv
from core.kpis import compute_kpis as _core_kpis

DATA_FOLDER_NIFTY50 = 'data'
DATA_FOLDER_WIDE = 'data/nse_bse'
DATA_FOLDER_ME = 'momentum_edge_data'


# ─────────────────────────────────────────────────────────────────────────────
# Feature engineering — daily-EOD OHLCV-derived features
# ─────────────────────────────────────────────────────────────────────────────

def _compute_features(ohlcv: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Return a long DataFrame: index=date, columns=[ticker, close, rsi_14, atr_14,
    sma_50, sma_200, volume_z, mcap_cr]."""
    rows = []
    for tk, df in ohlcv.items():
        if df is None or len(df) < 200:
            continue
        c = df['Close']
        v = df['Volume']

        # RSI(14)
        delta = c.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = -delta.clip(upper=0).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        # ATR(14)
        tr = pd.concat([
            (df['High'] - df['Low']),
            (df['High'] - c.shift()).abs(),
            (df['Low']  - c.shift()).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()

        sma50  = c.rolling(50).mean()
        sma200 = c.rolling(200).mean()
        vol_mean = v.rolling(50).mean()
        vol_std  = v.rolling(50).std()
        vol_z = (v - vol_mean) / vol_std.replace(0, np.nan)

        feat = pd.DataFrame({
            'ticker':  tk,
            'close':   c,
            'volume':  v,
            'rsi_14':  rsi,
            'atr_14':  atr,
            'sma_50':  sma50,
            'sma_200': sma200,
            'volume_z': vol_z,
        }).dropna()
        rows.append(feat)
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# DSL evaluation
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_formula(formula: str) -> str:
    """Translate AND/OR/NOT (case-insensitive) to pandas.eval operators."""
    s = ' ' + formula.strip() + ' '
    for k, v in [
        (' AND ', ' & '), (' and ', ' & '),
        (' OR ',  ' | '), (' or ',  ' | '),
        (' NOT ', ' ~ '), (' not ', ' ~ '),
    ]:
        s = s.replace(k, v)
    return s.strip()


def _evaluate_signals(features: pd.DataFrame, formula: str) -> pd.Series:
    """Return boolean Series aligned to features.index where formula evaluates True."""
    if not formula.strip():
        return pd.Series(False, index=features.index)
    expr = _normalize_formula(formula)
    try:
        mask = features.eval(expr)
        if isinstance(mask, pd.Series) and mask.dtype == bool:
            return mask
        return mask.astype(bool)
    except Exception as e:
        print(f"WARN: formula eval failed: {e}")
        return pd.Series(False, index=features.index)


# ─────────────────────────────────────────────────────────────────────────────
# Universe loaders
# ─────────────────────────────────────────────────────────────────────────────

def _load_universe(spec: dict) -> dict[str, pd.DataFrame]:
    """Return ticker -> OHLCV DataFrame for the chosen universe."""
    uni = spec.get('universe', 'Nifty 200')
    if uni in ('Nifty 50', 'Nifty 100'):
        ohlcv, _ = load_ohlcv(DATA_FOLDER_ME)
        return ohlcv
    if uni in ('Nifty 200', 'Nifty 500', 'BSE 500', 'Full NSE+BSE'):
        ohlcv, _ = load_ohlcv(DATA_FOLDER_WIDE)
        return ohlcv
    if uni == 'Custom CSV':
        path = spec.get('custom_csv_path', '')
        try:
            tickers = pd.read_csv(path)
            col = next((c for c in ('yf_ticker', 'ticker', 'Symbol') if c in tickers.columns), None)
            wanted = set(tickers[col].dropna()) if col else set()
        except Exception:
            wanted = set()
        full, _ = load_ohlcv(DATA_FOLDER_WIDE)
        return {tk: df for tk, df in full.items() if tk in wanted}
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio simulation
# ─────────────────────────────────────────────────────────────────────────────

class _Pos:
    __slots__ = ('ticker', 'entry_date', 'entry_px', 'shares', 'peak')
    def __init__(self, ticker, entry_date, entry_px, shares):
        self.ticker = ticker
        self.entry_date = entry_date
        self.entry_px = entry_px
        self.shares = shares
        self.peak = entry_px


def run_backtest(spec: dict) -> dict[str, Any]:
    print(f"[1/5] Loading universe: {spec.get('universe')}")
    ohlcv = _load_universe(spec)
    if not ohlcv:
        raise RuntimeError(f"No data for universe {spec.get('universe')}")
    print(f"      Loaded {len(ohlcv)} tickers")

    print('[2/5] Computing features')
    feat = _compute_features(ohlcv)
    if feat.empty:
        raise RuntimeError("No features computable (too little history)")
    feat = feat.sort_index()
    print(f"      Feature panel: {len(feat):,} rows, {feat['ticker'].nunique()} tickers")

    print('[3/5] Evaluating entry signals')
    formula = spec.get('entry_formula', '')
    mask = _evaluate_signals(feat, formula)
    feat['_signal'] = mask
    n_signals = int(mask.sum())
    print(f"      {n_signals:,} signal-rows")

    # Build close panel for portfolio mark-to-market
    close_panel = feat.reset_index().pivot(index='Date', columns='ticker', values='close').sort_index()

    print('[4/5] Simulating portfolio')
    exits = spec.get('exits', {})
    sizing = spec.get('sizing', {})
    max_pos = sizing.get('max_positions', 10) if 'capped' in sizing.get('method', '') else 10_000
    cash = float(sizing.get('initial_cash', 1_000_000))
    hold_days = int(exits.get('time_days', 60)) if exits.get('time_enabled') else None
    hard_stop_pct = float(exits.get('hard_stop_pct', 0)) / 100 if exits.get('hard_stop_enabled') else None
    trail_pct = float(exits.get('trail_pct', 0)) / 100 if exits.get('trail_enabled') else None

    trading_days = close_panel.index
    open_pos: dict[str, _Pos] = {}
    trades: list[dict] = []
    equity_curve: list[tuple[date, float]] = []

    # Pre-compute signal sets per day
    sig_by_day: dict[date, list[str]] = {}
    sig_rows = feat[feat['_signal']]
    for ts, group in sig_rows.groupby(level=0):
        d = ts.date() if hasattr(ts, 'date') else ts
        sig_by_day[d] = group['ticker'].tolist()

    for ts in trading_days:
        today = ts.date()

        # 1. Update trailing peaks
        for tk, pos in open_pos.items():
            if tk in close_panel.columns:
                px = close_panel.loc[ts, tk]
                if pd.notna(px) and px > pos.peak:
                    pos.peak = float(px)

        # 2. Process exits
        to_close: list[tuple[str, float, str]] = []
        for tk, pos in open_pos.items():
            if tk not in close_panel.columns:
                continue
            px = close_panel.loc[ts, tk]
            if pd.isna(px):
                continue
            px = float(px)

            # Time exit
            if hold_days is not None:
                if (ts - pd.Timestamp(pos.entry_date)).days >= hold_days * 1.4:  # cal-days approx
                    to_close.append((tk, px, 'TIME')); continue
            # Hard stop
            if hard_stop_pct is not None:
                if px <= pos.entry_px * (1 - hard_stop_pct):
                    to_close.append((tk, px, 'HARD_STOP')); continue
            # Trailing stop
            if trail_pct is not None:
                if px <= pos.peak * (1 - trail_pct):
                    to_close.append((tk, px, 'TRAIL')); continue

        for tk, px, reason in to_close:
            pos = open_pos.pop(tk)
            proceeds = pos.shares * px
            cash += proceeds
            trades.append({
                'ticker': tk,
                'entry_date': pos.entry_date,
                'entry_price': pos.entry_px,
                'shares': pos.shares,
                'exit_date': today,
                'exit_price': px,
                'return_pct': (px - pos.entry_px) / pos.entry_px * 100,
                'hold_days': (today - pos.entry_date).days,
                'exit_reason': reason,
            })

        # 3. Process new entries
        new_signals = sig_by_day.get(today, [])
        new_signals = [tk for tk in new_signals if tk not in open_pos]
        slots = max_pos - len(open_pos)
        new_signals = new_signals[:slots]
        if new_signals:
            cash_per_new = cash / max(len(new_signals), 1)
            for tk in new_signals:
                if tk not in close_panel.columns:
                    continue
                px = close_panel.loc[ts, tk]
                if pd.isna(px) or px <= 0:
                    continue
                px = float(px)
                shares = int(cash_per_new // px)
                if shares == 0:
                    continue
                cost = shares * px
                if cost > cash:
                    continue
                cash -= cost
                open_pos[tk] = _Pos(tk, today, px, shares)

        # 4. Mark to market
        mtm = cash
        for tk, pos in open_pos.items():
            if tk in close_panel.columns:
                px = close_panel.loc[ts, tk]
                if pd.notna(px):
                    mtm += pos.shares * float(px)
        equity_curve.append((today, mtm))

    print('[5/5] Writing outputs')
    sid = spec.get('_strategy_id', 'unknown')
    out_dir = Path('strategies'); out_dir.mkdir(exist_ok=True)
    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_curve, columns=['date', 'equity'])
    trades_path = out_dir / f"{sid}_trades.csv"
    equity_path = out_dir / f"{sid}_equity.csv"
    trades_df.to_csv(trades_path, index=False)
    equity_df.to_csv(equity_path, index=False)

    # KPIs — delegate to canonical core.kpis (reads the written CSVs)
    kpis = _core_kpis(equity_path, trades_path)
    (out_dir / f"{sid}_kpis.csv").write_text(
        '\n'.join(f"{k},{v}" for k, v in kpis.items())
    )
    print(f"      Trades: {len(trades_df)} | Final equity: Rs {kpis['final_equity']:,.0f} | "
          f"CAGR: {kpis['cagr']*100:+.2f}%")

    return {
        'spec_id': sid,
        'trades_path': str(trades_path),
        'equity_path': str(equity_path),
        'kpis': kpis,
    }


def _compute_kpis(equity: pd.DataFrame, trades: pd.DataFrame) -> dict[str, float]:
    if equity.empty:
        return {'cagr': 0.0, 'sharpe': 0.0, 'max_dd': 0.0, 'final_equity': 0,
                'win_rate': 0.0, 'num_trades': 0}
    eq = equity['equity'].astype(float)
    days = (pd.to_datetime(equity['date'].iloc[-1]) - pd.to_datetime(equity['date'].iloc[0])).days
    years = max(days / 365.25, 1/365)
    initial = eq.iloc[0]
    final = eq.iloc[-1]
    cagr = (final / initial) ** (1 / years) - 1 if initial > 0 else 0
    rets = eq.pct_change().dropna()
    sharpe = (rets.mean() / rets.std()) * np.sqrt(252) if rets.std() > 0 else 0
    peak = eq.cummax()
    mdd = float(((eq - peak) / peak).min())
    if trades.empty:
        win_rate = 0.0
    else:
        win_rate = float((trades['return_pct'] > 0).mean())
    return {
        'cagr': float(cagr),
        'sharpe': float(sharpe),
        'max_dd': mdd,
        'final_equity': float(final),
        'win_rate': win_rate,
        'num_trades': int(len(trades)),
    }


def _update_strategies_index(sid: str, kpis: dict, trades_path: str, equity_path: str) -> None:
    idx_path = Path('strategies_index.json')
    if not idx_path.exists():
        return
    idx = json.loads(idx_path.read_text())
    for strat in idx['strategies']:
        if strat['id'] == sid:
            strat['kpis_inline'] = {
                'cagr': kpis.get('cagr'),
                'sharpe': kpis.get('sharpe'),
                'max_dd': kpis.get('max_dd'),
                'win_rate': kpis.get('win_rate'),   # may be None (JSON null) — do not coerce
                'num_trades': kpis.get('num_trades'),
            }
            strat['trades_csv'] = trades_path
            strat['equity_csv'] = equity_path
            strat['last_run'] = datetime.now().isoformat(timespec='seconds')
            break
    idx_path.write_text(json.dumps(idx, indent=2, default=str))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', required=True, help='Path to strategy spec JSON')
    args = ap.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"ERROR: spec not found: {spec_path}")
        sys.exit(1)
    spec = json.loads(spec_path.read_text())
    spec['_strategy_id'] = spec_path.stem

    result = run_backtest(spec)
    _update_strategies_index(spec['_strategy_id'], result['kpis'],
                              result['trades_path'], result['equity_path'])
    try:
        from core.leaderboard import refresh_all
        refresh_all()
    except Exception as e:
        print(f"WARN: leaderboard refresh failed: {e}")
    print('DONE')


if __name__ == '__main__':
    main()
