# core/leaderboard.py
"""Recompute canonical KPIs + composite rank for all strategies, persist to index (S1)."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from core.kpis import KpiError, compute_kpis
from core.ranking import rank_strategies

_CANONICAL = ["cagr", "total_return", "volatility", "sharpe", "max_dd",
              "calmar", "win_rate", "num_trades", "alpha", "final_equity"]


def refresh_all(index_path: str = "strategies_index.json", benchmark_loader=None) -> list[dict]:
    """Recompute KPIs for every strategy, rank the cohort, persist. Returns the strategies."""
    p = Path(index_path)
    idx = json.loads(p.read_text())
    strategies = idx["strategies"]

    for s in strategies:
        try:
            kp = compute_kpis(
                s["equity_csv"], s.get("trades_csv"),
                equity_col=s.get("equity_col"), benchmark_col=s.get("benchmark_col"),
                pnl_col=s.get("pnl_col"), benchmark_loader=benchmark_loader,
            )
            s["kpis_inline"] = {k: kp[k] for k in _CANONICAL}
            s["kpis_updated"] = datetime.now().isoformat(timespec="seconds")
            s.pop("kpis_error", None)
        except KpiError as e:
            s["kpis_error"] = str(e)

    cohort = [{"id": s["id"], **s["kpis_inline"]}
              for s in strategies if "kpis_error" not in s and "kpis_inline" in s]
    ranked = {r["id"]: r for r in rank_strategies(cohort)}
    for s in strategies:
        r = ranked.get(s["id"])
        if r:
            s["rank"] = r["rank"]
            s["rank_score"] = r["score"]

    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(idx, indent=2, default=str))
    os.replace(tmp, p)
    return strategies
