"""Alerts for portfolio monitoring (Decision 6).

An alert is created only when a holding's (action, rule) changes; HOLD records state
but raises nothing.  Acknowledging records ``{alert_id, acknowledged_at}`` and never
touches the ledger or positions.  ``alerts.json`` shape:
  {version:1, state:{symbol:{action,rule}}, alerts:[...], acknowledgements:[...]}
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from core.portfolio import LedgerCorrupt, _atomic_write

ALERTS_VERSION = 1
MAX_ALERTS = 200


def _empty() -> dict:
    return {"version": ALERTS_VERSION, "state": {}, "alerts": [], "acknowledgements": []}


def load_alerts(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return _empty()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if (not isinstance(raw, dict) or raw.get("version") != ALERTS_VERSION
                or not isinstance(raw.get("alerts"), list)):
            raise ValueError("unsupported alerts file")
    except (OSError, ValueError) as exc:
        raise LedgerCorrupt(f"{p}: {exc}") from exc
    out = _empty()
    out.update({k: raw[k] for k in ("state", "alerts", "acknowledgements") if k in raw})
    return out


def alert_id(symbol: str, action: str, rule: str | None, bar_date: str | None) -> str:
    key = "|".join([symbol, action, rule or "", bar_date or ""])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def update_alerts(data: dict, evaluations: list[dict], open_symbols: set[str],
                  now: datetime) -> tuple[dict, list[dict]]:
    """Return (new alerts doc, alerts created now).  Does not mutate ``data``."""
    state = {s: v for s, v in data.get("state", {}).items() if s in open_symbols}
    alerts = list(data.get("alerts", []))
    known_ids = {a["id"] for a in alerts}
    created: list[dict] = []
    for ev in evaluations:
        sym, action, rule = ev["symbol"], ev["action"], ev.get("rule")
        prev = state.get(sym)
        state[sym] = {"action": action, "rule": rule}
        if action == "HOLD" or (prev and prev == state[sym]):
            continue
        aid = alert_id(sym, action, rule, ev.get("last_bar_date"))
        if aid in known_ids:
            continue
        alert = {"id": aid, "symbol": sym, "action": action, "rule": rule,
                 "trigger_bar_date": ev.get("last_bar_date"), "message": ev.get("explanation"),
                 "created_at": now.isoformat(timespec="seconds")}
        alerts.append(alert)
        known_ids.add(aid)
        created.append(alert)
    doc = {"version": ALERTS_VERSION, "state": state, "alerts": alerts[-MAX_ALERTS:],
           "acknowledgements": list(data.get("acknowledgements", []))}
    return doc, created


def acknowledge(path: str | Path, alert_id_: str, now: datetime | None = None) -> bool:
    """Record an acknowledgement.  Returns False when the alert id is unknown."""
    data = load_alerts(path)
    if not any(a["id"] == alert_id_ for a in data["alerts"]):
        return False
    if not any(a.get("alert_id") == alert_id_ for a in data["acknowledgements"]):
        data["acknowledgements"].append(
            {"alert_id": alert_id_,
             "acknowledged_at": (now or datetime.now()).isoformat(timespec="seconds")})
        _atomic_write(Path(path), data)
    return True


def with_ack_status(data: dict) -> list[dict]:
    acked = {a["alert_id"]: a["acknowledged_at"] for a in data.get("acknowledgements", [])}
    return [dict(a, acknowledged_at=acked.get(a["id"])) for a in data.get("alerts", [])]
