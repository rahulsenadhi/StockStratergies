"""Evaluate every open holding against the Momentum Edge exit rules.

Runs whenever data is updated (last step of every update path) or on demand.  Holdings
are evaluated even when they no longer pass the entry scanner.  Outputs:
  portfolio/evaluations.jsonl  - append-only audit history, one line per holding per run
  portfolio/alerts.json        - alerts raised on action changes (deduped) + acknowledgements
  ui_portfolio.json            - what the Next.js /portfolio page reads

Exit code: 0 normally (per-holding problems are listed in monitor.errors), 1 when the
ledger/settings/alerts file is corrupt, 2 for --validate-only with a rejected transaction.
  python portfolio_monitor.py [--dir D] [--ledger F] [--out F] [--validate-only CANDIDATE]
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from datetime import datetime
from pathlib import Path

from core.exit_monitor import IST, Evaluation, _as_ist, completed_cutoff, evaluate_holding
from core.portfolio import (DEFAULT_SETTINGS, LedgerCorrupt, _atomic_write,
                            estimated_exit_costs, load_ledger, load_settings, positions,
                            universe_index, validate_transaction)
from core.portfolio_alerts import load_alerts, update_alerts, with_ack_status

ROOT = Path(__file__).resolve().parent
PORTFOLIO_DIR = ROOT / "portfolio"
UI_OUT = ROOT / "ui_portfolio.json"
DATA_FOLDERS = ("data/nse_bse", "momentum_edge_data", "data")   # same order as the scanner
NIFTY_FILE = "^NSEI.csv"
UI_VERSION = 1


def _stub_streamlit() -> None:
    from precompute_momentum_signals import _install_streamlit_stub
    _install_streamlit_stub()


_md = None


def _dashboard():
    """master_dashboard with a Streamlit stub (same trick as precompute_momentum_signals)."""
    global _md
    if _md is None:
        import importlib.util
        _stub_streamlit()
        spec = importlib.util.spec_from_file_location("master_dashboard", str(ROOT / "master_dashboard.py"))
        _md = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_md)
    return _md


def find_csv(symbol: str) -> Path | None:
    for folder in DATA_FOLDERS:
        p = ROOT / folder / f"{symbol}.csv"
        if p.exists():
            return p
    return None


def load_bars(symbol: str):
    """Bars + ema220 from the dashboard's own indicator code (no filters), or None."""
    p = find_csv(symbol)
    return None if p is None else _dashboard()._compute_full_indicators(str(p))


def nifty_session_date(now: datetime):
    """Last completed session = last date in ^NSEI.csv (bar dated today only after 15:45 IST)."""
    import pandas as pd
    p = ROOT / "data" / "nse_bse" / NIFTY_FILE
    if not p.exists():
        return None
    try:
        idx = pd.to_datetime(pd.read_csv(p, usecols=[0]).iloc[:, 0], errors="coerce").dropna()
    except (OSError, ValueError):
        return None
    cutoff = completed_cutoff(now)
    done = [d.date() for d in idx if d.date() <= cutoff]
    return max(done) if done else None


def ensure_settings(path: Path) -> dict:
    if not path.exists():
        _atomic_write(path, DEFAULT_SETTINGS)
    return load_settings(path)


def _strategies(ledger: list[dict]) -> dict[str, str]:
    """momentum_edge unless every active BUY of the symbol is strategy 'other'."""
    voided = {t.get("voids") for t in ledger if t.get("type") == "VOID"}
    seen: dict[str, set] = {}
    for t in ledger:
        if t.get("type") == "BUY" and t.get("id") not in voided:
            seen.setdefault(t["symbol"], set()).add(t.get("strategy", "momentum_edge"))
    return {s: ("other" if v == {"other"} else "momentum_edge") for s, v in seen.items()}


def _unrealised(pos, ev: Evaluation) -> dict:
    if ev.last_close is None or not pos.open_qty:
        return {"unrealised_pnl": None, "unrealised_pnl_pct": None, "unrealised_pnl_net": None}
    cost = pos.avg_price * pos.open_qty
    gross = ev.last_close * pos.open_qty - cost
    net = None if pos.allocated_charges is None else round(gross - pos.allocated_charges, 2)
    return {"unrealised_pnl": round(gross, 2),
            "unrealised_pnl_pct": round(gross / cost * 100, 2) if cost else None,
            "unrealised_pnl_net": net}


def _position_row(pos, ev: Evaluation, universe: dict, settings: dict) -> dict:
    row = pos.to_dict()
    row["name"] = universe.get(pos.symbol, {}).get("name")
    row["evaluation"] = ev.to_dict()
    row.update(_unrealised(pos, ev))
    row["estimated_exit_costs"] = None
    if ev.last_close is not None:
        try:
            row["estimated_exit_costs"] = estimated_exit_costs(
                pos.symbol, pos.exchange, pos.open_qty, ev.last_close, settings)
        except (KeyError, ValueError):
            pass
    return row


def _evaluate_all(open_pos: dict, strategies: dict, nifty, now, settings, loader):
    evals: list[Evaluation] = []
    errors: list[str] = []
    for sym, pos in open_pos.items():
        pos = dataclasses.replace(pos, extra={**pos.extra, "strategy": strategies.get(sym, "momentum_edge")})
        try:
            ev = evaluate_holding(pos, loader(sym), nifty, now, settings)
        except Exception as exc:  # one bad holding must not stop the rest
            errors.append(f"{sym}: {type(exc).__name__}: {exc}")
            ev = Evaluation(symbol=sym, action="DATA UNAVAILABLE", rule=None,
                            explanation=f"Evaluation failed: {exc}", data_status="DATA UNAVAILABLE",
                            evaluated_at=_as_ist(now).isoformat(timespec="seconds"))
        evals.append((pos, ev))
    return evals, errors


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _settings_summary(settings: dict) -> dict:
    c = settings["charges"]
    return {"charges_as_of": c.get("as_of"), "charges_note": c.get("note"),
            "bands": settings["bands"],
            "experimental_reduce": bool(settings.get("monitor", {}).get("experimental_reduce"))}


def _doc(now: datetime, ok: bool, errors: list[str], rows=(), closed=(), alerts=(),
         settings=None, last_good: str | None = None) -> dict:
    stamp = _as_ist(now).isoformat(timespec="seconds")
    return {"version": UI_VERSION, "generated_at": stamp,
            "monitor": {"last_run": stamp, "ok": ok, "errors": errors,
                        "last_good_check": stamp if ok else last_good},
            "positions": list(rows), "closed": list(closed), "alerts": list(alerts),
            "settings_summary": _settings_summary(settings or DEFAULT_SETTINGS),
            "scheduler": "none"}


def run(pdir: Path, ledger_path: Path, out: Path, now: datetime, loader, nifty) -> int:
    loaded = {}
    for kind, loader_fn, path in (("settings", ensure_settings, pdir / "settings.json"),
                                  ("ledger", load_ledger, ledger_path),
                                  ("alerts", load_alerts, pdir / "alerts.json")):
        try:
            loaded[kind] = loader_fn(path)
        except LedgerCorrupt as exc:
            _write_unreadable(out, now, f"{kind} file unreadable: {exc}")
            print(f"portfolio_monitor: {kind} file unreadable: {exc}", file=sys.stderr)
            return 1
    settings, ledger, alert_doc = loaded["settings"], loaded["ledger"], loaded["alerts"]
    allpos = positions(ledger)
    open_pos = {s: p for s, p in allpos.items() if p.open_qty > 0}
    universe = universe_index()
    nifty = nifty(now) if callable(nifty) else nifty
    if nifty is None and open_pos:
        errors_pre = ["Market calendar unavailable: data/nse_bse/^NSEI.csv missing or unreadable"]
    else:
        errors_pre = []
    pairs, errors = _evaluate_all(open_pos, _strategies(ledger), nifty, now, settings, loader)
    errors = errors_pre + errors
    evals = [ev.to_dict() for _, ev in pairs]
    _append_jsonl(pdir / "evaluations.jsonl", evals)
    alert_doc, _ = update_alerts(alert_doc, evals, set(open_pos), now)
    _atomic_write(pdir / "alerts.json", alert_doc)
    rows = [_position_row(p, ev, universe, settings) for p, ev in pairs]
    closed = [dict(p.to_dict(), name=universe.get(s, {}).get("name"))
              for s, p in allpos.items() if p.closed]
    _atomic_write(out, _doc(now, True, errors, rows, closed, with_ack_status(alert_doc), settings))
    print(f"portfolio_monitor: {len(rows)} open, {len(closed)} closed, {len(errors)} errors")
    return 0


def _write_unreadable(out: Path, now: datetime, message: str) -> None:
    """Keep the last good positions (marked STALE) instead of blanking the page."""
    prev = {}
    try:
        prev = json.loads(out.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    old_mon = prev.get("monitor") if isinstance(prev.get("monitor"), dict) else {}
    last_good = old_mon.get("last_good_check") or (old_mon.get("last_run") if old_mon.get("ok") else None)
    rows = []
    for row in prev.get("positions") or []:
        ev = dict(row.get("evaluation") or {})
        ev.update(action="STALE", rule=None, data_status="STALE",
                  explanation=f"Ledger unreadable; showing the last good check from {last_good or 'an unknown time'}")
        rows.append(dict(row, evaluation=ev))
    doc = _doc(now, False, [message], rows, prev.get("closed") or [], prev.get("alerts") or [],
               last_good=last_good)
    _atomic_write(out, doc)


def validate_only(candidate: Path) -> int:
    """Validate the LAST transaction of a candidate ledger against the others."""
    try:
        txs = json.loads(candidate.read_text(encoding="utf-8")).get("transactions")
        if not isinstance(txs, list) or not txs:
            raise ValueError("candidate ledger has no transactions")
        last = {k: v for k, v in txs[-1].items() if k not in ("id", "created_at")}
        errors = validate_transaction(last, txs[:-1], universe_index())
    except Exception as exc:  # malformed input must give ok:false, never a traceback
        errors = [f"cannot validate candidate ledger: {type(exc).__name__}: {exc}"]
    print(json.dumps({"ok": not errors, "errors": errors}))
    return 0 if not errors else 2


def main(argv: list[str] | None = None, *, now: datetime | None = None,
         bars_loader=None, nifty_last_date=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", type=Path, default=PORTFOLIO_DIR, help="portfolio data folder")
    ap.add_argument("--ledger", type=Path, help="ledger file (default: <dir>/ledger.json)")
    ap.add_argument("--out", type=Path, default=UI_OUT, help="ui_portfolio.json path")
    ap.add_argument("--validate-only", type=Path, metavar="CANDIDATE_LEDGER")
    args = ap.parse_args(argv)
    if args.validate_only:
        return validate_only(args.validate_only)
    return run(args.dir, args.ledger or args.dir / "ledger.json", args.out,
               now or datetime.now(IST), bars_loader or load_bars,
               nifty_last_date if nifty_last_date is not None else nifty_session_date)


if __name__ == "__main__":
    sys.exit(main())
