# precompute_suggestions.py
"""Precompute the "Buy These Now" / Suggestions feed for the Next.js app.

Faithful port of master_dashboard.py's Suggestions engine (_edge_buckets,
_build_{monthly,momentum,ipo}_suggestions, _regime_snapshot). Heavy compute
(regime build, edge buckets, per-strategy signal filtering) runs here once in
the data pipeline; the web side is a thin loader + RSC page that reads the JSON.

Mirrors precompute_exit_recommendations.py -> exit_recommendations.json.

Run:  python precompute_suggestions.py
Output (project root):  suggestions.json
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from core import regime as core_regime

BASE_DIR = Path(__file__).resolve().parent
OUT = BASE_DIR / "suggestions.json"

S_MONTHLY = "Monthly Rotation"
S_IPO = "IPO Edge"
S_MOMENTUM = "Momentum Edge"

STRATEGY_ID = {
    S_MONTHLY: "monthly_rotation",
    S_IPO: "ipo_edge",
    S_MOMENTUM: "momentum_edge",
}


# ── pure: edge buckets ──────────────────────────────────────────────────────
def edge_buckets(
    trades: pd.DataFrame | None, group_cols: list[str], min_n: int = 3
) -> pd.DataFrame:
    """Rank historical edge per (group_cols) bucket. Port of _edge_buckets.

    Returns DF with group cols + n, win_rate, avg_pnl, median_pnl,
    profit_factor, expectancy, edge_score. Sorted by edge_score desc.
    edge_score = expectancy * sqrt(n) (penalises small samples).
    """
    if trades is None or trades.empty:
        return pd.DataFrame()
    cols = [c for c in group_cols if c in trades.columns]
    if not cols or "Result" not in trades.columns or "PnL_Pct" not in trades.columns:
        return pd.DataFrame()

    rows = []
    for keys, g in trades.groupby(cols, dropna=False):
        wins = g.loc[g["Result"] == "Win", "PnL_Pct"]
        losses = g.loc[g["Result"] == "Loss", "PnL_Pct"]
        n = len(g)
        wr = (g["Result"] == "Win").mean() * 100
        avg = g["PnL_Pct"].mean()
        med = g["PnL_Pct"].median()
        gp = wins.sum() if not wins.empty else 0.0
        gl = abs(losses.sum()) if not losses.empty else 0.0
        pf = (gp / gl) if gl > 0 else (gp if gp > 0 else 0.0)
        exp_ = (wr / 100) * (wins.mean() if not wins.empty else 0.0) + (
            1 - wr / 100
        ) * (losses.mean() if not losses.empty else 0.0)
        key_tuple = keys if isinstance(keys, tuple) else (keys,)
        row = dict(zip(cols, key_tuple))
        row.update(
            {
                "n": n,
                "win_rate": wr,
                "avg_pnl": avg,
                "median_pnl": med,
                "profit_factor": pf,
                "expectancy": exp_,
            }
        )
        rows.append(row)

    g = pd.DataFrame(rows)
    g = g[g["n"] >= min_n].copy()
    if g.empty:
        return g
    g["edge_score"] = g["expectancy"] * g["n"].pow(0.5)
    g = g.sort_values("edge_score", ascending=False).reset_index(drop=True)
    return g


def _rr(close: float, stop: float, target: float) -> float:
    return abs((target - close) / (close - stop)) if (close - stop) > 0 else 0.0


# ── pure: per-strategy builders ─────────────────────────────────────────────
def build_monthly_suggestions(
    rankings: pd.DataFrame | None,
    equity: pd.DataFrame | None,
    is_bull: bool,
    max_picks: int = 5,
) -> list[dict]:
    """Monthly: top-RS Strong-BUY signals from live_rankings, gated by regime."""
    out: list[dict] = []
    if rankings is None or rankings.empty:
        return out
    rk = rankings.copy()
    hist_wr = 60.0  # Monthly Rotation has confirmed +21% CAGR
    hist_avg = 1.8  # avg monthly return
    if equity is not None and "Strategy_Value" in equity.columns:
        monthly_ret = equity["Strategy_Value"].pct_change().dropna() * 100
        if not monthly_ret.empty:
            hist_wr = float((monthly_ret > 0).mean() * 100)
            hist_avg = float(monthly_ret.mean())

    if "Signal" in rk.columns:
        rk = rk[
            rk["Signal"].astype(str).str.contains("Strong BUY", case=False, na=False)
        ]
    rk = rk.head(max_picks)

    n_eq = len(equity) if equity is not None else 0
    for _, r in rk.iterrows():
        close = float(r.get("Current_Price", 0) or 0)
        if close <= 0:
            continue
        stop = round(close * 0.92, 2)
        target = round(close * 1.10, 2)
        rs_score = float(r.get("RS_Score", 0) or 0)
        rationale = (
            f"Top-{int(r.get('Rank', 0) or 0)} RS pick. RS Score {rs_score:.1f} — "
            f"price beating Nifty by "
            f"{float(r.get('Return_%', 0) or 0) - float(r.get('Benchmark_Return_%', 0) or 0):+.1f}% this month. "
            f"Monthly Rotation backtest: ~21% CAGR, max DD -11%. "
            + (
                "Regime is Bull — entries allowed."
                if is_bull
                else "Regime is Bear — hold off or size half."
            )
        )
        out.append(
            {
                "ticker": str(r.get("Ticker", "")).replace(".NS", ""),
                "company": str(r.get("Company", "")),
                "strategy": S_MONTHLY,
                "strategyId": STRATEGY_ID[S_MONTHLY],
                "signal": str(r.get("Signal", "")),
                "close": close,
                "stop": stop,
                "target": target,
                "rr": round(_rr(close, stop, target), 2),
                "confidence": round(hist_wr, 1),
                "avgPnl": round(hist_avg, 2),
                "nHist": n_eq,
                "positionPct": 20.0 if is_bull else 10.0,
                "edgeScore": hist_wr + rs_score,
                "rationale": rationale,
            }
        )
    return out


_ENTRY_MAP = {"52W High": "52W_HIGH_FALLBACK", "ATH": "ATH"}


def build_momentum_suggestions(
    signals: pd.DataFrame | None,
    trades: pd.DataFrame | None,
    is_bull: bool,
    max_picks: int = 5,
) -> list[dict]:
    """Momentum: signals filtered by best (Entry_Type x Recovery_Speed) bucket."""
    out: list[dict] = []
    if signals is None or signals.empty:
        return out

    edge = (
        edge_buckets(trades, ["Entry_Type", "Recovery_Speed"], min_n=3)
        if trades is not None
        else pd.DataFrame()
    )
    best_pairs: set = set()
    edge_lookup: dict = {}
    if not edge.empty:
        good = edge[edge["expectancy"] > 0]
        for _, r in good.iterrows():
            key = (str(r["Entry_Type"]), str(r["Recovery_Speed"]))
            best_pairs.add(key)
            edge_lookup[key] = r

    sig = signals
    if "Signal" in sig.columns:
        sig = sig[
            sig["Signal"]
            .astype(str)
            .str.contains("Breakout|Near|Watch", case=False, regex=True, na=False)
        ]

    def _norm_entry(v) -> str:
        return _ENTRY_MAP.get(str(v).strip(), str(v).strip())

    def _norm_recov(v) -> str:
        return str(v).split()[0] if v else ""

    if best_pairs and {"Entry Type", "Recovery"}.issubset(sig.columns):
        sig = sig.copy()
        sig["_et_norm"] = sig["Entry Type"].map(_norm_entry)
        sig["_rs_norm"] = sig["Recovery"].map(_norm_recov)
        matched = sig[
            sig.apply(lambda r: (r["_et_norm"], r["_rs_norm"]) in best_pairs, axis=1)
        ]
        if not matched.empty:
            sig = matched

    if "Chart Qual" in sig.columns:
        clean = sig[sig["Chart Qual"].astype(str).str.contains("Clean", na=False)]
        if not clean.empty:
            sig = clean

    sig = sig.head(max_picks)

    for _, r in sig.iterrows():
        close = float(r.get("Close", 0) or 0)
        if close <= 0:
            continue
        ema220 = float(r.get("220 EMA", close * 0.85) or close * 0.85)
        stop = round(max(close * 0.85, ema220), 2)
        target = round(close * 1.25, 2)
        et = _norm_entry(r.get("Entry Type", ""))
        rs = _norm_recov(r.get("Recovery", ""))
        lk = edge_lookup.get((et, rs))
        wr = float(lk["win_rate"]) if lk is not None else 40.0
        avgp = float(lk["avg_pnl"]) if lk is not None else 0.0
        n = int(lk["n"]) if lk is not None else 0
        rationale = (
            f"Entry: {et} - Recovery: {rs}. "
            f"This bucket won {wr:.0f}% of {n} historical trades, avg {avgp:+.2f}%. "
            f"Stop placed at 220 EMA (Rs {ema220:,.2f}) or -15%, whichever is tighter. "
            + (
                "Bull regime - green light."
                if is_bull
                else "Bear regime - skip new ATH plays."
            )
        )
        out.append(
            {
                "ticker": str(r.get("Ticker", "")).replace(".NS", ""),
                "company": str(r.get("Company", "")),
                "strategy": S_MOMENTUM,
                "strategyId": STRATEGY_ID[S_MOMENTUM],
                "signal": str(r.get("Signal", "")),
                "close": close,
                "stop": stop,
                "target": target,
                "rr": round(_rr(close, stop, target), 2),
                "confidence": round(wr, 1),
                "avgPnl": round(avgp, 2),
                "nHist": n,
                "positionPct": 12.0 if is_bull else 6.0,
                "edgeScore": wr + float(r.get("Score", 0) or 0),
                "rationale": rationale,
            }
        )
    return out


def build_ipo_suggestions(
    signals: pd.DataFrame | None,
    trades: pd.DataFrame | None,
    is_bull: bool,
    max_picks: int = 5,
) -> list[dict]:
    """IPO Edge: live signals filtered by best historical Setup_Type. Bull-only."""
    out: list[dict] = []
    if signals is None or signals.empty:
        return out

    edge_setup = (
        edge_buckets(trades, ["Setup_Type"], min_n=2)
        if trades is not None
        else pd.DataFrame()
    )
    best_setups: set = set()
    setup_lookup: dict = {}
    if not edge_setup.empty:
        good = edge_setup[edge_setup["expectancy"] > 0]
        best_setups = set(good["Setup_Type"].dropna().astype(str))
        setup_lookup = {str(r["Setup_Type"]): r for _, r in edge_setup.iterrows()}

    sig = signals
    if "Signal" in sig.columns:
        sig = sig[
            sig["Signal"]
            .astype(str)
            .str.contains("Breakout|Near", case=False, regex=True, na=False)
        ]
    if "Setup" in sig.columns and best_setups:
        sig = sig[sig["Setup"].astype(str).isin(best_setups)]
    sig = sig.head(max_picks)

    for _, r in sig.iterrows():
        close = float(r.get("Close", 0) or 0)
        if close <= 0:
            continue
        stop = round(close * 0.92, 2)
        target = round(close * 1.20, 2)
        setup = str(r.get("Setup", ""))
        lk = setup_lookup.get(setup)
        wr = float(lk["win_rate"]) if lk is not None else 45.0
        avgp = float(lk["avg_pnl"]) if lk is not None else 0.0
        n = int(lk["n"]) if lk is not None else 0
        rationale = (
            f"Setup: {setup or 'STANDARD'} - Stage: {r.get('Stage', '-')}. "
            f"Historical {setup or 'this setup'} won {wr:.0f}% of {n} trades, avg {avgp:+.2f}%. "
            f"Liquidity: {r.get('Liquidity', '-')}. "
            + (
                "Bull regime - proceed."
                if is_bull
                else "Bear regime - wait or quarter-size."
            )
        )
        out.append(
            {
                "ticker": str(r.get("Ticker", "")).replace(".NS", ""),
                "company": str(r.get("Company", "")),
                "strategy": S_IPO,
                "strategyId": STRATEGY_ID[S_IPO],
                "signal": str(r.get("Signal", "")),
                "close": close,
                "stop": stop,
                "target": target,
                "rr": round(_rr(close, stop, target), 2),
                "confidence": round(wr, 1),
                "avgPnl": round(avgp, 2),
                "nHist": n,
                "positionPct": 8.0 if is_bull else 4.0,
                "edgeScore": wr + float(r.get("Score", 0) or 0),
                "rationale": rationale,
            }
        )
    return out


# ── pure: regime + assembly ─────────────────────────────────────────────────
def compute_regime(benchmark: pd.Series | None) -> dict:
    """Nifty 3-condition regime snapshot. Port of _regime_snapshot."""
    if benchmark is None or len(benchmark) < 200:
        return {"status": "Unknown", "barsSinceFlip": 0}
    series = core_regime.build_series(benchmark, {"use_regime_filter": True})
    if series is None or series.dropna().empty:
        return {"status": "Unknown", "barsSinceFlip": 0}
    state_now = bool(series.dropna().iloc[-1])
    high52 = float(benchmark.rolling(252).max().iloc[-1])
    close = float(benchmark.iloc[-1])
    return {
        "status": "Bull" if state_now else "Bear",
        "barsSinceFlip": core_regime.bars_since_flip(series),
        "close": round(close, 2),
        "sma50": round(float(benchmark.rolling(50).mean().iloc[-1]), 2),
        "sma200": round(float(benchmark.rolling(200).mean().iloc[-1]), 2),
        "high52": round(high52, 2),
        "pctFromHigh": round((close / high52 - 1) * 100, 2) if high52 > 0 else 0.0,
        "date": str(benchmark.index[-1].date()),
    }


def assemble(regime: dict, pools: list[list[dict]]) -> dict:
    """Merge per-strategy pools, sort by edgeScore desc, re-rank, compute summary."""
    picks = sorted(
        [p for pool in pools for p in pool],
        key=lambda x: x["edgeScore"],
        reverse=True,
    )
    for i, p in enumerate(picks, start=1):
        p["rank"] = i
    n = len(picks)
    avg_conf = round(sum(p["confidence"] for p in picks) / n, 1) if n else 0.0
    total_alloc = sum(p["positionPct"] for p in picks)
    summary = {
        "picks": n,
        "avgConfidence": avg_conf,
        "totalAllocation": round(min(total_alloc, 100), 1),
        "cashReserve": round(max(0.0, 100 - total_alloc), 1),
    }
    return {"regime": regime, "summary": summary, "picks": picks}


# ── I/O ─────────────────────────────────────────────────────────────────────
def _read_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def load_benchmark() -> pd.Series | None:
    """Load Nifty benchmark close series (data/nse_bse first, then data)."""
    for folder in ("data/nse_bse", "data"):
        p = BASE_DIR / folder / "NIFTYBEES.NS.csv"
        if not p.exists():
            continue
        try:
            df = pd.read_csv(p, index_col=0, parse_dates=True)
        except Exception:
            continue
        if df.empty:
            continue
        close_cols = [c for c in df.columns if str(c).lower() in ("close", "nifty bees", "niftybees.ns")]
        col = close_cols[0] if close_cols else df.columns[-1]
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if not s.empty:
            return s
    return None


def build_all() -> dict:
    """Read local CSVs, build regime + all pools, return JSON-ready dict."""
    regime = compute_regime(load_benchmark())
    is_bull = regime.get("status") == "Bull"

    monthly = build_monthly_suggestions(
        _read_csv(BASE_DIR / "live_rankings.csv"),
        _read_csv(BASE_DIR / "backtest_results.csv"),
        is_bull,
    )
    momentum = build_momentum_suggestions(
        _read_csv(BASE_DIR / "momentum_edge_signals.csv"),
        _read_csv(BASE_DIR / "momentum_edge_trades.csv"),
        is_bull,
    )
    # IPO is bull-only and currently has no live-signals CSV -> empty pool.
    ipo = (
        build_ipo_suggestions(
            _read_csv(BASE_DIR / "ipo_edge_signals.csv"),
            _read_csv(BASE_DIR / "ipo_edge_trades.csv"),
            is_bull,
        )
        if is_bull
        else []
    )
    return assemble(regime, [monthly, momentum, ipo])


def main() -> None:
    result = build_all()
    OUT.write_text(json.dumps(result, indent=2))
    reg = result["regime"]["status"]
    n = result["summary"]["picks"]
    print(f"  regime: {reg} | picks: {n}")
    for p in result["picks"]:
        print(f"    #{p['rank']:>2} {p['strategy']:<16} {p['ticker']:<14} "
              f"conf {p['confidence']:.0f}% edge {p['edgeScore']:.1f}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
