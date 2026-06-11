"""Unit tests for dryrun.py — DSL dry-run preview (S4 slice).

Real signatures (read dryrun.py before writing):
  extract_unknown_features(formula: str, known: set[str]) -> list[str]
  compute_preview(feat: pd.DataFrame, formula: str, history_days: int = 90) -> dict
  run_dryrun(formula: str, universe: str) -> dict
"""
import pandas as pd
import pytest

import dryrun as D


def test_extract_unknown_flags_typos():
    unknown = D.extract_unknown_features("rsi_14 > 70 AND xyz_bad > 1", D.KNOWN_FEATURES)
    assert unknown == ["xyz_bad"]


def test_extract_unknown_ignores_logical_keywords_and_numbers():
    # AND/OR/NOT (any case) and numeric literals are never "features"
    unknown = D.extract_unknown_features("rsi_14 > 70 and close > 0 OR not volume_z > 2", D.KNOWN_FEATURES)
    assert unknown == []


def test_extract_unknown_dedupes_preserving_order():
    unknown = D.extract_unknown_features("foo > 1 AND bar > 2 AND foo > 3", D.KNOWN_FEATURES)
    assert unknown == ["foo", "bar"]


def _panel():
    """3 trading days, 2 tickers. rsi>70 fires: AAA day1+day3, BBB day2."""
    dates = pd.to_datetime(["2026-06-01", "2026-06-02", "2026-06-03"])
    aaa = pd.DataFrame({"ticker": "AAA", "rsi_14": [80, 50, 90],
                        "close": [10, 11, 12], "sma_200": [5, 5, 5]}, index=dates)
    bbb = pd.DataFrame({"ticker": "BBB", "rsi_14": [40, 75, 30],
                        "close": [10, 11, 12], "sma_200": [5, 5, 5]}, index=dates)
    return pd.concat([aaa, bbb]).sort_index()


def test_compute_preview_today_matches():
    p = D.compute_preview(_panel(), "rsi_14 > 70")
    assert p["today"]["date"] == "2026-06-03"
    assert p["today"]["count"] == 1          # only AAA fires on the last day
    assert p["today"]["tickers"] == ["AAA"]


def test_compute_preview_history_counts():
    p = D.compute_preview(_panel(), "rsi_14 > 70")
    assert p["history"]["trading_days"] == 3  # fewer than 90 -> all available
    assert p["history"]["signal_rows"] == 3   # AAA d1, BBB d2, AAA d3
    assert p["history"]["distinct_tickers"] == 2


def test_compute_preview_dead_formula_zeroes():
    p = D.compute_preview(_panel(), "rsi_14 > 200")
    assert p["today"]["count"] == 0
    assert p["history"]["signal_rows"] == 0
    assert p["today"]["tickers"] == []


def test_compute_preview_caps_ticker_list_at_25():
    dates = pd.to_datetime(["2026-06-01"])
    frames = [pd.DataFrame({"ticker": f"T{i:02d}", "rsi_14": [99]}, index=dates) for i in range(30)]
    p = D.compute_preview(pd.concat(frames).sort_index(), "rsi_14 > 70")
    assert p["today"]["count"] == 30           # full count reported
    assert len(p["today"]["tickers"]) == 25     # list truncated
