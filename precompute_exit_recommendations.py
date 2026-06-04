# precompute_exit_recommendations.py
"""Precompute hold-period & exit-ladder recommendations for all strategies.

Runs once in the data pipeline (after the backtests). For each strategy it loads
historical entries + an OHLCV panel, calls core.exit_analyzer, and writes one
exit_recommendations.json keyed by strategy. The dashboard reads that file.

Run:  python precompute_exit_recommendations.py
Output (project root):  exit_recommendations.json
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from core import exit_analyzer as ea
from core import rotation_trades
from core.data_io import load_ohlcv

BASE_DIR = Path(__file__).resolve().parent
OUT = BASE_DIR / "exit_recommendations.json"


def load_entries_generic(
    csv_path: str,
    ticker_col: str,
    date_col: str,
    price_col: str,
    bucket_col: str | None = None,
) -> pd.DataFrame:
    """Read a trades CSV and normalize to the entries contract.

    Returns columns ticker, entry_date, entry_price [, bucket]. Empty DataFrame
    if the file is missing or unreadable.
    """
    p = Path(csv_path)
    if not p.exists():
        return pd.DataFrame(columns=["ticker", "entry_date", "entry_price"])
    try:
        df = pd.read_csv(p)
    except Exception:
        return pd.DataFrame(columns=["ticker", "entry_date", "entry_price"])

    out = pd.DataFrame({
        "ticker": df[ticker_col].astype(str),
        "entry_date": pd.to_datetime(df[date_col], errors="coerce"),
        "entry_price": pd.to_numeric(df[price_col], errors="coerce"),
    })
    if bucket_col and bucket_col in df.columns:
        out["bucket"] = df[bucket_col].astype(str)
    out = out.dropna(subset=["entry_date", "entry_price"])
    out = out[out["entry_price"] > 0].reset_index(drop=True)
    return out


def _sue_decile_bucket(df: pd.DataFrame) -> pd.DataFrame:
    """Add a 'bucket' column = SUE decile label, when a 'sue' column is present."""
    if "sue" not in df.columns or df["sue"].notna().sum() < 10:
        return df
    deciles = pd.qcut(df["sue"].rank(method="first"), 10, labels=False) + 1
    df = df.copy()
    df["bucket"] = "decile_" + deciles.astype(int).astype(str)
    return df


def build_all() -> dict:
    """Compute recommendations for every strategy. Returns the JSON-ready dict."""
    result: dict = {}

    # 1. Momentum Edge — OHLCV in momentum_edge_data/, bucket by Entry_Type
    me_ohlcv, _ = load_ohlcv(BASE_DIR / "momentum_edge_data")
    me_entries = load_entries_generic(
        str(BASE_DIR / "momentum_edge_trades.csv"),
        "Ticker", "Entry_Date", "Entry_Price", bucket_col="Entry_Type",
    )
    result["momentum_edge"] = {
        k: r.to_dict() for k, r in ea.analyze_with_buckets(
            me_entries, me_ohlcv, "momentum_edge", "ohlcv", bucket_col="bucket"
        ).items()
    }

    # 2. IPO Edge — OHLCV in ipo_data/, bucket by Setup_Type
    ipo_ohlcv, _ = load_ohlcv(BASE_DIR / "ipo_data")
    ipo_entries = load_entries_generic(
        str(BASE_DIR / "ipo_edge_trades.csv"),
        "Ticker", "Entry_Date", "Entry_Price", bucket_col="Setup_Type",
    )
    result["ipo_edge"] = {
        k: r.to_dict() for k, r in ea.analyze_with_buckets(
            ipo_entries, ipo_ohlcv, "ipo_edge", "ohlcv", bucket_col="bucket"
        ).items()
    }

    # 3. PEAD — prices from momentum_edge_data/, bucket by SUE decile
    pead_entries = load_entries_generic(
        str(BASE_DIR / "pead_trades.csv"),
        "ticker", "entry_date", "entry_price",
    )
    if not pead_entries.empty:
        raw = pd.read_csv(BASE_DIR / "pead_trades.csv")
        if "sue" in raw.columns and len(raw) == len(pead_entries):
            pead_entries["sue"] = pd.to_numeric(raw["sue"], errors="coerce").values
            pead_entries = _sue_decile_bucket(pead_entries)
    result["pead"] = {
        k: r.to_dict() for k, r in ea.analyze_with_buckets(
            pead_entries, me_ohlcv, "pead", "ohlcv", bucket_col="bucket"
        ).items()
    }

    # 4. Monthly Rotation — synthesized entries + close-only pseudo-OHLCV
    rot_trades = rotation_trades.build(
        str(BASE_DIR / "rebalance_log.csv"), str(BASE_DIR / "data")
    )
    rot_entries = pd.DataFrame(columns=["ticker", "entry_date", "entry_price"])
    if not rot_trades.empty:
        rot_entries = pd.DataFrame({
            "ticker": rot_trades["Ticker"].astype(str),
            "entry_date": pd.to_datetime(rot_trades["Entry_Date"]),
            "entry_price": pd.to_numeric(rot_trades["Entry_Price"], errors="coerce"),
        }).dropna(subset=["entry_price"])
    rot_ohlcv = rotation_trades.build_pseudo_ohlcv(str(BASE_DIR / "data"))
    result["monthly_rotation"] = {
        k: r.to_dict() for k, r in ea.analyze_with_buckets(
            rot_entries, rot_ohlcv, "monthly_rotation", "close"
        ).items()
    }

    return result


def main() -> None:
    result = build_all()
    OUT.write_text(json.dumps(result, indent=2))
    for strat, recs in result.items():
        buckets = ", ".join(recs.keys()) if recs else "(insufficient history)"
        print(f"  {strat}: {buckets}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
