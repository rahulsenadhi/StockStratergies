# precompute_insights.py
"""Precompute trade-analytics "Insights" — win rate / avg PnL by setup bucket.

Faithful to the Streamlit Insights tab's bucket tables (core.analytics.win_rate_by
+ win_rate_by_score_bucket + hold_day_curve), which answer "what predicts winners?".
These tables need only the trades CSV (PnL_Pct + the group column) — no OHLCV /
MAE-MFE load — so this stays light and deterministic.

Run:  python precompute_insights.py
Output (project root):  insights.json
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from core import analytics

BASE_DIR = Path(__file__).resolve().parent
OUT = BASE_DIR / "insights.json"


def _num(v):
    if v is None:
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v.item() if hasattr(v, "item") else v


def bucket_records(df: pd.DataFrame, group_col: str) -> list[dict]:
    """win_rate_by(df, group_col) -> JSON-safe camelCased records."""
    table = analytics.win_rate_by(df, group_col)
    if table is None or table.empty:
        return []
    out = []
    for _, r in table.iterrows():
        out.append(
            {
                "group": str(r[group_col]),
                "count": int(r["Count"]),
                "winRate": _num(r.get("Win_Rate")),
                "avgPnl": _num(r.get("Avg_PnL")),
                "medianPnl": _num(r.get("Median_PnL")),
            }
        )
    return out


def score_bucket_records(df: pd.DataFrame) -> list[dict]:
    table = analytics.win_rate_by_score_bucket(df)
    if table is None or table.empty:
        return []
    col = table.columns[0]
    out = []
    for _, r in table.iterrows():
        out.append(
            {
                "group": str(r[col]),
                "count": int(r["Count"]),
                "winRate": _num(r.get("Win_Rate")),
                "avgPnl": _num(r.get("Avg_PnL")),
                "medianPnl": _num(r.get("Median_PnL")),
            }
        )
    return out


def overall(df: pd.DataFrame) -> dict:
    if "PnL_Pct" not in df.columns or df.empty:
        return {"n": 0, "winRate": None, "avgPnl": None, "medianPnl": None}
    pnl = pd.to_numeric(df["PnL_Pct"], errors="coerce").dropna()
    return {
        "n": int(len(pnl)),
        "winRate": _num(round(analytics._safe_win_rate(pnl), 1)) if len(pnl) else None,
        "avgPnl": _num(round(pnl.mean(), 2)) if len(pnl) else None,
        "medianPnl": _num(round(pnl.median(), 2)) if len(pnl) else None,
    }


def _read(name: str) -> pd.DataFrame | None:
    p = BASE_DIR / name
    if not p.exists():
        return None
    try:
        return pd.read_csv(p)
    except Exception:
        return None


def build_strategy(df: pd.DataFrame | None, group_specs: list[tuple[str, str]]) -> dict:
    """group_specs = [(json_key, csv_col)]. Includes score-bucket if Score present."""
    if df is None or df.empty:
        return {}
    out: dict = {"overall": overall(df)}
    for key, col in group_specs:
        recs = bucket_records(df, col)
        if recs:
            out[key] = recs
    sb = score_bucket_records(df)
    if sb:
        out["byScoreBucket"] = sb
    return out


def build_all() -> dict:
    return {
        "momentum_edge": build_strategy(
            _read("momentum_edge_trades.csv"),
            [
                ("byEntryType", "Entry_Type"),
                ("byRecoverySpeed", "Recovery_Speed"),
                ("byExitReason", "Exit_Reason"),
            ],
        ),
        "ipo_edge": build_strategy(
            _read("ipo_edge_trades.csv"),
            [
                ("bySetupType", "Setup_Type"),
                ("byExitReason", "Exit_Reason"),
                ("byEntryStage", "Entry_Stage"),
            ],
        ),
    }


def main() -> None:
    result = build_all()
    OUT.write_text(json.dumps(result, indent=2))
    for strat, rep in result.items():
        ov = rep.get("overall", {})
        groups = [k for k in rep if k != "overall"]
        print(f"  {strat}: n={ov.get('n', 0)} winRate={ov.get('winRate')} | {', '.join(groups) or '(no buckets)'}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
