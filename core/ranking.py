# core/ranking.py
"""Composite leaderboard rank — weighted z-score blend across the cohort (S1)."""
from __future__ import annotations

import numpy as np

DEFAULT_WEIGHTS = {"sharpe": 0.30, "cagr": 0.25, "max_dd": 0.20, "alpha": 0.15, "win_rate": 0.10}
MIN_COHORT = 3


def _dir(metric: str, value):
    if value is None:
        return None
    return value if metric == "max_dd" else value     # max_dd: less negative = higher = better (no flip needed)


def _fallback(kpis, ids):
    order = sorted(
        range(len(kpis)),
        key=lambda i: (-(kpis[i].get("sharpe") or float("-inf")),
                       -(kpis[i].get("cagr") or float("-inf"))),
    )
    out = [None] * len(kpis)
    for rank, i in enumerate(order, start=1):
        out[i] = {"id": ids[i], "score": 0.0, "rank": rank,
                  "components": {}, "fallback": True}
    return out


def rank_strategies(kpi_dicts, weights=None, min_cohort=MIN_COHORT):
    weights = weights or DEFAULT_WEIGHTS
    n = len(kpi_dicts)
    if n == 0:
        return []
    ids = [k.get("id") for k in kpi_dicts]
    if n < min_cohort:
        return _fallback(kpi_dicts, ids)

    metrics = list(weights)
    cols = {m: [_dir(m, kpi_dicts[i].get(m)) for i in range(n)] for m in metrics}
    stats = {}
    for m in metrics:
        present = [v for v in cols[m] if v is not None]
        stats[m] = (float(np.mean(present)), float(np.std(present))) if present else (0.0, 0.0)

    results = []
    for i in range(n):
        num = den = 0.0
        comps = {}
        for m in metrics:
            v = cols[m][i]
            mean, std = stats[m]
            if v is None:
                comps[m] = {"value": kpi_dicts[i].get(m), "z": 0.0, "imputed": True}
                continue
            z = 0.0 if std == 0 else (v - mean) / std
            comps[m] = {"value": kpi_dicts[i].get(m), "z": z, "imputed": False}
            num += weights[m] * z
            den += weights[m]
        score = num / den if den > 0 else 0.0
        results.append({"id": ids[i], "score": float(score), "components": comps,
                        "_sharpe": kpi_dicts[i].get("sharpe") or float("-inf"),
                        "_cagr": kpi_dicts[i].get("cagr") or float("-inf")})

    results.sort(key=lambda r: (-r["score"], -r["_sharpe"], -r["_cagr"]))
    for rank, r in enumerate(results, start=1):
        r["rank"] = rank
        r.pop("_sharpe", None)
        r.pop("_cagr", None)
    return results
