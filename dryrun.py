"""DSL dry-run: validate an entry formula and preview its signals without a full
backtest. Reuses the generic_backtest feature pipeline so counts are honest.

CLI:
    python dryrun.py --formula "rsi_14 > 70 AND close > sma_200" --universe "Nifty 50"

Prints one JSON blob to stdout (see run_dryrun for the contract).
"""
from __future__ import annotations

import argparse
import json
import re

from generic_backtest import _load_universe, _compute_features, _evaluate_signals

# Feature columns produced by generic_backtest._compute_features.
KNOWN_FEATURES = {"close", "volume", "rsi_14", "atr_14", "sma_50", "sma_200", "volume_z"}
_LOGICAL = {"and", "or", "not"}
_IDENT_RE = re.compile(r"[A-Za-z_]\w*")


def extract_unknown_features(formula: str, known: set[str]) -> list[str]:
    """Return identifiers in the formula that are neither a known feature nor a
    logical keyword (AND/OR/NOT). De-duplicated, first-seen order preserved.
    Numeric literals never match the identifier regex."""
    unknown: list[str] = []
    seen: set[str] = set()
    for tok in _IDENT_RE.findall(formula):
        if tok.lower() in _LOGICAL or tok in known or tok in seen:
            continue
        seen.add(tok)
        unknown.append(tok)
    return unknown
