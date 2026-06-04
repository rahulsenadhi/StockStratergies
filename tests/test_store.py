import pandas as pd
import numpy as np
import pytest
from pathlib import Path

from core import store
import convert_to_parquet as cvt
from core import data_io


def _make_csv_dataset(tmp_path, monkeypatch, n_tickers=3, n_bars=20):
    csv_dir = tmp_path / "nse_bse"
    csv_dir.mkdir(parents=True)
    dates = pd.bdate_range("2024-01-01", periods=n_bars)
    for i in range(n_tickers):
        closes = np.linspace(100 + i, 130 + i, n_bars)
        pd.DataFrame({
            "Date": dates, "Open": closes, "High": closes * 1.02,
            "Low": closes * 0.98, "Close": closes, "Volume": 1000 + i,
        }).to_csv(csv_dir / f"T{i}.NS.csv", index=False)
    monkeypatch.setattr(cvt, "DATASETS", {"nse_bse": str(csv_dir)})
    monkeypatch.setattr(cvt, "PARQUET_ROOT", str(tmp_path / "parquet"))
    monkeypatch.setattr(store, "DATASETS", {"nse_bse": str(csv_dir)})
    monkeypatch.setattr(store, "PARQUET_ROOT", str(tmp_path / "parquet"))
    return csv_dir


def test_has_store_false_then_true(tmp_path, monkeypatch):
    _make_csv_dataset(tmp_path, monkeypatch)
    assert store.has_store("nse_bse") is False
    cvt.backfill("nse_bse")
    assert store.has_store("nse_bse") is True


def test_load_ohlcv_parquet_matches_csv_loader(tmp_path, monkeypatch):
    csv_dir = _make_csv_dataset(tmp_path, monkeypatch)
    cvt.backfill("nse_bse")

    csv_dict, _ = data_io.load_ohlcv(str(csv_dir))
    pq_dict, mt = store.load_ohlcv_parquet("nse_bse")

    assert set(pq_dict) == set(csv_dict)
    for t in csv_dict:
        a, b = csv_dict[t], pq_dict[t]
        assert list(b.columns) == ["Open", "High", "Low", "Close", "Volume"]
        assert b.index.name == "Date"
        assert len(a) == len(b)
        np.testing.assert_allclose(a["Close"].to_numpy(), b["Close"].to_numpy(), rtol=1e-9)
        assert t in mt


def test_load_ohlcv_parquet_honors_whitelist_skip_minbars(tmp_path, monkeypatch):
    _make_csv_dataset(tmp_path, monkeypatch, n_tickers=3, n_bars=20)
    cvt.backfill("nse_bse")
    only, _ = store.load_ohlcv_parquet("nse_bse", whitelist={"T1.NS"})
    assert set(only) == {"T1.NS"}
    sk, _ = store.load_ohlcv_parquet("nse_bse", skip={"T1.NS"})
    assert "T1.NS" not in sk
    none, _ = store.load_ohlcv_parquet("nse_bse", min_bars=999)
    assert none == {}


def test_get_bars_filters(tmp_path, monkeypatch):
    _make_csv_dataset(tmp_path, monkeypatch, n_tickers=3, n_bars=20)
    cvt.backfill("nse_bse")

    allb = store.get_bars("nse_bse")
    assert {"ticker", "Date"}.issubset(allb.columns)
    assert set(allb["ticker"].unique()) == {"T0.NS", "T1.NS", "T2.NS"}

    sub = store.get_bars("nse_bse", tickers=["T1.NS"], cols=["Close"])
    assert set(sub["ticker"].unique()) == {"T1.NS"}
    assert set(sub.columns) == {"ticker", "Date", "Close"}

    rng = store.get_bars("nse_bse", tickers=["T0.NS"],
                         start="2024-01-10", end="2024-01-15")
    assert rng["Date"].min() >= pd.Timestamp("2024-01-10")
    assert rng["Date"].max() <= pd.Timestamp("2024-01-15")
