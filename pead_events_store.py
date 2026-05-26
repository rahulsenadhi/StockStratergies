"""Append-only events.parquet store with dedup-update semantics.

Dedup key: (ticker, result_date, period_type). Re-appending overwrites the
existing row (last write wins).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

_KEY_COLS = ["ticker", "result_date", "period_type"]


def load_events(path: Path) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def append_events(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    new_df = pd.DataFrame(rows)
    path = Path(path)
    if path.exists():
        old = pd.read_parquet(path)
        # drop dups in 'old' that are about to be replaced
        merged = pd.concat([old, new_df], ignore_index=True)
        merged = merged.drop_duplicates(subset=_KEY_COLS, keep="last")
    else:
        merged = new_df.drop_duplicates(subset=_KEY_COLS, keep="last")
        path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(path, index=False)
