# precompute_pead_screener.py
"""Export the PEAD earnings-events universe for the Next.js screener.

The Streamlit PEAD screener (pead_dashboard.py:_tab_screener) reads
pead_data/events.parquet and filters by SUE / Piotroski / P-B / sector. The
Next.js app can't read parquet, so this exports the screener columns to a
camelCased JSON the web loader reads.

Run:  python precompute_pead_screener.py
Output (project root):  pead_screener.json
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
EVENTS = BASE_DIR / "pead_data" / "events.parquet"
OUT = BASE_DIR / "pead_screener.json"

# parquet column -> JSON (camelCase) key
COLS = {
    "ticker": "ticker",
    "sector": "sector",
    "result_date": "resultDate",
    "period_type": "periodType",
    "sue": "sue",
    "sue_decile": "sueDecile",
    "eps_actual": "epsActual",
    "eps_expected": "epsExpected",
    "piotroski": "piotroski",
    "pb": "pb",
    "pb_sector_median": "pbSectorMedian",
    "qualifies_long": "qualifiesLong",
}


def _clean(v):
    """JSON-safe scalar: NaN/NaT -> None, numpy types -> python, dates -> str."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, (pd.Timestamp,)):
        return None if pd.isna(v) else str(v.date())
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, "item"):  # numpy scalar
        return v.item()
    return v


def to_records(df: pd.DataFrame) -> list[dict]:
    """Map the events frame to camelCased, JSON-safe screener rows."""
    present = {src: dst for src, dst in COLS.items() if src in df.columns}
    out: list[dict] = []
    for _, row in df.iterrows():
        rec = {dst: _clean(row[src]) for src, dst in present.items()}
        if "resultDate" in rec and isinstance(row.get("result_date"), str):
            rec["resultDate"] = row["result_date"][:10]
        out.append(rec)
    return out


def build() -> list[dict]:
    if not EVENTS.exists():
        return []
    df = pd.read_parquet(EVENTS)
    # normalise result_date to a YYYY-MM-DD string
    if "result_date" in df.columns:
        df = df.copy()
        df["result_date"] = pd.to_datetime(df["result_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return to_records(df)


def main() -> None:
    rows = build()
    OUT.write_text(json.dumps(rows, indent=2))
    sectors = sorted({r.get("sector") for r in rows if r.get("sector")})
    print(f"  {len(rows)} events · {len(sectors)} sectors")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
