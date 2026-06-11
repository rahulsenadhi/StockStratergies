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
