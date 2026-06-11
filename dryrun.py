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

import pandas as pd

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


TICKER_LIST_CAP = 25
HISTORY_DAYS = 90


def compute_preview(feat: pd.DataFrame, formula: str, history_days: int = HISTORY_DAYS) -> dict:
    """Evaluate a (pre-validated) formula on the feature panel and return today's
    matches + recent firing stats. `feat` is indexed by trading date and has a
    'ticker' column plus feature columns."""
    mask = _evaluate_signals(feat, formula)
    f = feat.assign(_m=mask)
    dates = f.index.unique().sort_values()
    last_day = dates[-1]
    win_start = dates[-history_days] if len(dates) >= history_days else dates[0]

    today_rows = f[(f.index == last_day) & f["_m"]]
    win_rows = f[(f.index >= win_start) & f["_m"]]
    tickers = sorted(today_rows["ticker"].tolist())
    day_str = last_day.date().isoformat() if hasattr(last_day, "date") else str(last_day)

    return {
        "today": {
            "date": day_str,
            "count": int(len(today_rows)),
            "tickers": tickers[:TICKER_LIST_CAP],
        },
        "history": {
            "trading_days": int(min(len(dates), history_days)),
            "signal_rows": int(len(win_rows)),
            "distinct_tickers": int(win_rows["ticker"].nunique()),
        },
    }


def run_dryrun(formula: str, universe: str) -> dict:
    """Orchestrate a DSL dry-run: validate, load, compute, preview.

    Returns a JSON-serialisable dict with ``"ok": True`` on success or
    ``"ok": False`` plus an ``"error"`` string on any failure.
    """
    formula = (formula or "").strip()
    if not formula:
        return {"ok": False, "error": "empty formula"}

    unknown = extract_unknown_features(formula, KNOWN_FEATURES)
    if unknown:
        return {
            "ok": False,
            "error": f"unknown feature(s): {', '.join(unknown)}",
            "unknown_features": unknown,
        }

    try:
        ohlcv = _load_universe({"universe": universe})
        if not ohlcv:
            return {"ok": False, "error": f"no data for universe {universe}"}
        feat = _compute_features(ohlcv).sort_index()
        if feat.empty:
            return {"ok": False, "error": "no features computable (too little history)"}
        preview = compute_preview(feat, formula)
        return {"ok": True, "universe": universe, **preview}
    except Exception as e:  # noqa: BLE001 — surface any engine error to the UI
        return {"ok": False, "error": str(e)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--formula", required=True)
    ap.add_argument("--universe", default="Nifty 50")
    args = ap.parse_args()
    print(json.dumps(run_dryrun(args.formula, args.universe)))


if __name__ == "__main__":
    main()
