"""Lookup-table scorer: turn analytics aggregates into per-signal predictions.

Given a feature dict (e.g. {Entry_Type: 'ATH', Recovery_Speed: 'Fast'}), look up
the matching cohort in an analytics report and return historical win rate +
avg PnL + sample size. Used to overlay live screener rows with what trades that
look like this signal historically did.

API:
    bucket_lookup(report, group_col, value)
        → dict {win_rate, avg_pnl, count} or None

    predict_quality(report, features)
        → dict {win_rate, avg_pnl, count, source}
        Combines bucket lookups: tries the most-specific feature (Score quintile)
        first, then falls back to Entry_Type, then Recovery_Speed, then Regime.

    enrich_signals(signals_df, report, feature_map)
        → DataFrame with added 'Hist Win%' and 'Hist Avg%' columns.
"""

from typing import Any

import pandas as pd


def bucket_lookup(report: dict, group_col: str, value: Any) -> dict | None:
    """Lookup one bucket row from a 'by_*' aggregate table.

    Returns None if the table is missing, the column is missing, or the value
    has no matching row.
    """
    df_key_map = {
        'Entry_Type':       'by_entry_type',
        'Recovery_Speed':   'by_recovery_speed',
        'Exit_Reason':      'by_exit_reason',
        'Regime_At_Entry':  'by_regime',
    }
    key = df_key_map.get(group_col)
    if key is None:
        return None
    df = report.get(key)
    if df is None or df.empty or group_col not in df.columns:
        return None
    hit = df[df[group_col] == value]
    if hit.empty:
        return None
    row = hit.iloc[0]
    return {
        'win_rate': float(row.get('Win_Rate', 0)),
        'avg_pnl':  float(row.get('Avg_PnL', 0)),
        'count':    int(row.get('Count', 0)),
    }


def predict_quality(report: dict, features: dict) -> dict:
    """Pick the most-specific bucket that has signal and return its stats.

    Tries in order: Entry_Type, Recovery_Speed, Regime_At_Entry.
    Returns dict with win_rate / avg_pnl / count / source (which key matched).
    Falls back to overall stats if no bucket matches.
    """
    for col in ('Entry_Type', 'Recovery_Speed', 'Regime_At_Entry'):
        val = features.get(col)
        if val is None:
            continue
        hit = bucket_lookup(report, col, val)
        if hit and hit['count'] >= 3:  # require minimum sample
            return {**hit, 'source': col}

    # Fallback to overall
    return {
        'win_rate': report.get('overall_win_rate', 0.0),
        'avg_pnl':  report.get('overall_avg_pnl', 0.0),
        'count':    len(report.get('trades', pd.DataFrame())),
        'source':   'overall',
    }


def enrich_signals(
    signals_df: pd.DataFrame,
    report: dict,
    feature_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Append 'Hist Win%', 'Hist Avg%', 'Hist N' columns to a live signals frame.

    Args:
        signals_df:  DataFrame of live signals (one row per ticker)
        report:      Output of core.analytics.full_report*
        feature_map: Maps signal-row column names → analytics-table column names.
                     e.g. {'Entry Type': 'Entry_Type', 'Recovery': 'Recovery_Speed'}

    Returns a new DataFrame; signals_df is not mutated.
    """
    if signals_df is None or signals_df.empty:
        return signals_df
    feature_map = feature_map or {
        'Entry Type': 'Entry_Type',
        'Recovery':   'Recovery_Speed',
    }

    out = signals_df.copy()
    win_rates, avg_pnls, ns = [], [], []
    for _, row in out.iterrows():
        features: dict = {}
        for src_col, analytics_col in feature_map.items():
            if src_col in row.index:
                val = row[src_col]
                # Strip emoji suffix like "Fast 🟢" → "Fast"
                if isinstance(val, str):
                    val = val.split(' ', 1)[0]
                features[analytics_col] = val
        pred = predict_quality(report, features)
        win_rates.append(round(pred['win_rate'], 1))
        avg_pnls.append(round(pred['avg_pnl'], 2))
        ns.append(pred['count'])

    out['Hist Win%'] = win_rates
    out['Hist Avg%'] = avg_pnls
    out['Hist N']    = ns
    return out
