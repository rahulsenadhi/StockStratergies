import pandas as pd
import pytest
from pathlib import Path

import convert_to_parquet as cvt


def _write_csv(path: Path, dates, closes):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "Date": dates,
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1000] * len(closes),
    }).to_csv(path, index=False)


def test_backfill_writes_partitioned_parquet(tmp_path, monkeypatch):
    csv_dir = tmp_path / "ipo_data"
    pq_root = tmp_path / "parquet"
    _write_csv(csv_dir / "AAA.NS.csv",
               pd.bdate_range("2024-01-01", periods=15), list(range(100, 115)))
    monkeypatch.setattr(cvt, "DATASETS", {"ipo_data": str(csv_dir)})
    monkeypatch.setattr(cvt, "PARQUET_ROOT", str(pq_root))

    n = cvt.backfill("ipo_data")
    assert n == 1
    part = pq_root / "ipo_data" / "ticker=AAA.NS" / "bars.parquet"
    assert part.exists()
    df = pd.read_parquet(part)
    assert list(df.columns) == ["Date", "Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 15
    assert pd.api.types.is_datetime64_any_dtype(df["Date"])
    man = pq_root / "ipo_data" / "_manifest.json"
    assert man.exists()
