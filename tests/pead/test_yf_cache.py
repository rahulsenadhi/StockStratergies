"""Tests for core.yf_cache."""
import time
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from core import yf_cache


@pytest.fixture(autouse=True)
def _tmp_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(yf_cache, "CACHE_DIR", tmp_path)
    yield tmp_path


def _fake_snap(label="A"):
    return {
        "earnings_dates": pd.DataFrame({"Reported EPS": [10.0]},
                                        index=pd.to_datetime(["2026-01-01"])),
        "income_stmt": pd.DataFrame({pd.Timestamp("2025-03-31"): [100]},
                                     index=["Net Income"]),
        "balance_sheet": pd.DataFrame(),
        "cashflow": pd.DataFrame(),
        "info": {"sector": "IT", "label": label},
    }


def test_get_snapshot_miss_triggers_fetch(_tmp_cache_dir):
    with patch.object(yf_cache, "_fetch_live") as mock_fetch:
        mock_fetch.return_value = _fake_snap("X")
        snap = yf_cache.get_snapshot("AAA.NS")
        assert snap["info"]["label"] == "X"
        assert mock_fetch.call_count == 1


def test_get_snapshot_hit_skips_fetch(_tmp_cache_dir):
    with patch.object(yf_cache, "_fetch_live") as mock_fetch:
        mock_fetch.return_value = _fake_snap("FIRST")
        yf_cache.get_snapshot("BBB.NS")
        assert mock_fetch.call_count == 1

    # Second call should NOT re-fetch
    with patch.object(yf_cache, "_fetch_live") as mock_fetch:
        mock_fetch.return_value = _fake_snap("SHOULD_NOT_SEE")
        snap = yf_cache.get_snapshot("BBB.NS")
        assert snap["info"]["label"] == "FIRST"
        assert mock_fetch.call_count == 0


def test_get_snapshot_stale_refetches(_tmp_cache_dir):
    with patch.object(yf_cache, "_fetch_live") as mock_fetch:
        mock_fetch.return_value = _fake_snap("OLD")
        yf_cache.get_snapshot("CCC.NS", max_age_days=7)

    # Backdate file mtime 8 days
    path = yf_cache._cache_path("CCC.NS")
    old = time.time() - (8 * 86400)
    import os
    os.utime(path, (old, old))

    with patch.object(yf_cache, "_fetch_live") as mock_fetch:
        mock_fetch.return_value = _fake_snap("NEW")
        snap = yf_cache.get_snapshot("CCC.NS", max_age_days=7)
        assert snap["info"]["label"] == "NEW"
        assert mock_fetch.call_count == 1


def test_get_snapshot_force_refetches(_tmp_cache_dir):
    with patch.object(yf_cache, "_fetch_live") as mock_fetch:
        mock_fetch.return_value = _fake_snap("V1")
        yf_cache.get_snapshot("DDD.NS")

    with patch.object(yf_cache, "_fetch_live") as mock_fetch:
        mock_fetch.return_value = _fake_snap("V2")
        snap = yf_cache.get_snapshot("DDD.NS", force=True)
        assert snap["info"]["label"] == "V2"
        assert mock_fetch.call_count == 1


def test_clear_single(_tmp_cache_dir):
    with patch.object(yf_cache, "_fetch_live") as mock_fetch:
        mock_fetch.return_value = _fake_snap()
        yf_cache.get_snapshot("EEE.NS")
        yf_cache.get_snapshot("FFF.NS")
    assert yf_cache.clear("EEE.NS") == 1
    assert yf_cache._cache_path("EEE.NS").exists() is False
    assert yf_cache._cache_path("FFF.NS").exists() is True


def test_clear_all(_tmp_cache_dir):
    with patch.object(yf_cache, "_fetch_live") as mock_fetch:
        mock_fetch.return_value = _fake_snap()
        yf_cache.get_snapshot("GGG.NS")
        yf_cache.get_snapshot("HHH.NS")
    assert yf_cache.clear() == 2
