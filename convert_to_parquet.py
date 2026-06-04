# convert_to_parquet.py
"""CSV -> Parquet backfill + idempotent sync for the price datasets.

Reuses core.data_io.load_single for CSV parsing/normalization so Parquet bytes
match what data_io.load_ohlcv would have produced. Store layout:
    data/parquet/<dataset>/ticker=<TICKER>/bars.parquet
    data/parquet/<dataset>/_manifest.json   ({ticker: source_csv_mtime})

CLI:
    python convert_to_parquet.py --backfill <dataset>
    python convert_to_parquet.py --sync <dataset>
    python convert_to_parquet.py --backfill-all
    python convert_to_parquet.py --sync-all
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

import pandas as pd

from core.data_io import load_single

DATASETS = {
    "nse_bse": "data/nse_bse",
    "ipo_data": "ipo_data",
    "momentum_edge_data": "momentum_edge_data",
}
PARQUET_ROOT = "data/parquet"


def dataset_paths(dataset: str) -> tuple[Path, Path]:
    """Return (csv_dir, parquet_dir) for a dataset name."""
    if dataset not in DATASETS:
        raise ValueError(f"Unknown dataset: {dataset}")
    return Path(DATASETS[dataset]), Path(PARQUET_ROOT) / dataset


def _write_partition(parquet_dir: Path, ticker: str, df: pd.DataFrame) -> None:
    """Write one ticker's OHLCV DataFrame (Date index) to its partition."""
    out = df.reset_index().rename(columns={df.index.name or "index": "Date"})
    out = out[["Date", "Open", "High", "Low", "Close", "Volume"]]
    out["Volume"] = pd.to_numeric(out["Volume"], errors="coerce").astype("float64")
    part = parquet_dir / f"ticker={ticker}" / "bars.parquet"
    part.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(part, index=False)


def _write_manifest(parquet_dir: Path, manifest: dict) -> None:
    """Atomically write the manifest dict."""
    parquet_dir.mkdir(parents=True, exist_ok=True)
    tmp = parquet_dir / "_manifest.json.tmp"
    tmp.write_text(json.dumps(manifest, indent=0))
    os.replace(tmp, parquet_dir / "_manifest.json")


def _read_manifest(parquet_dir: Path) -> dict:
    p = parquet_dir / "_manifest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def backfill(dataset: str) -> int:
    """Convert every CSV in the dataset to Parquet. Returns count written."""
    csv_dir, parquet_dir = dataset_paths(dataset)
    manifest: dict = {}
    written = 0
    for csv in sorted(csv_dir.glob("*.csv")):
        df = load_single(csv)
        if df is None:
            logging.warning("convert_to_parquet: skipping unreadable CSV %s", csv)
            continue
        ticker = csv.stem
        _write_partition(parquet_dir, ticker, df)
        manifest[ticker] = csv.stat().st_mtime
        written += 1
    _write_manifest(parquet_dir, manifest)
    return written


def sync(dataset: str) -> dict:
    """Convert only CSVs whose mtime changed since the last manifest entry.

    Returns {'converted': int, 'skipped': int}.
    """
    csv_dir, parquet_dir = dataset_paths(dataset)
    manifest = _read_manifest(parquet_dir)
    converted = skipped = 0
    for csv in sorted(csv_dir.glob("*.csv")):
        ticker = csv.stem
        mtime = csv.stat().st_mtime
        if manifest.get(ticker) == mtime:
            skipped += 1
            continue
        df = load_single(csv)
        if df is None:
            logging.warning("convert_to_parquet: skipping unreadable CSV %s", csv)
            skipped += 1
            continue
        _write_partition(parquet_dir, ticker, df)
        manifest[ticker] = mtime
        converted += 1
    _write_manifest(parquet_dir, manifest)
    return {"converted": converted, "skipped": skipped}


def main() -> None:
    ap = argparse.ArgumentParser(description="CSV -> Parquet converter")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--backfill", metavar="DATASET")
    g.add_argument("--sync", metavar="DATASET")
    g.add_argument("--backfill-all", action="store_true")
    g.add_argument("--sync-all", action="store_true")
    args = ap.parse_args()

    if args.backfill:
        print(f"  {args.backfill}: backfilled {backfill(args.backfill)} tickers")
    elif args.sync:
        print(f"  {args.sync}: {sync(args.sync)}")
    elif args.backfill_all:
        for ds in DATASETS:
            print(f"  {ds}: backfilled {backfill(ds)} tickers")
    elif args.sync_all:
        for ds in DATASETS:
            print(f"  {ds}: {sync(ds)}")


if __name__ == "__main__":
    main()
