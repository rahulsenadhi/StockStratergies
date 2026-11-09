"""Alerts for portfolio monitoring (Decision 6).

An alert is created only when a holding's (action, rule) changes; HOLD records state
but raises nothing.  Acknowledging records ``{alert_id, acknowledged_at}`` and never
touches the ledger or positions.  ``alerts.json`` shape:
  {version:1, state:{symbol:{action,rule}}, alerts:[...], acknowledgements:[...]}
"""
from __future__ import annotations

import hashlib
import errno
import json
import math
import os
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from core.portfolio import LedgerCorrupt, _atomic_write

ALERTS_VERSION = 1
MAX_ALERTS = 200
TRANSIENT_ACTIONS = ("STALE", "DATA UNAVAILABLE")
LOCK_TIMEOUT_SECONDS = 10.0


class AlertsLockTimeout(TimeoutError):
    """Another process did not finish writing alerts within the allotted time."""


@contextmanager
def alerts_lock(path: str | Path, timeout: float = LOCK_TIMEOUT_SECONDS):
    """Serialize alert writers across processes; the OS releases locks on exit.

    Lock a permanent sidecar, not alerts.json itself: atomic replacement changes
    that file's identity. Never unlink the sidecar, which would split the lock
    between processes already holding it and processes opening a new file.
    """
    if not math.isfinite(timeout) or timeout < 0:
        raise ValueError("alerts lock timeout must be finite and non-negative")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lock_path = p.with_name(p.name + ".lock")
    with open(lock_path, "a+b") as handle:
        if os.name == "nt":
            import msvcrt

            def acquire():
                handle.seek(0)
                # Windows permits locking bytes beyond EOF, even in an empty file.
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

            def release():
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            def acquire():
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            def release():
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

        deadline = time.monotonic() + timeout
        while True:
            try:
                acquire()
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AlertsLockTimeout(
                        f"Timed out waiting to write alerts at {p}; another process is busy. Retry shortly."
                    ) from exc
                time.sleep(min(0.05, remaining))
        try:
            yield
        finally:
            release()


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
        transient = action in TRANSIENT_ACTIONS     # data problems never replace the stored state
        if not transient:
            state[sym] = {"action": action, "rule": rule}
        if action == "HOLD" or (not transient and prev == state[sym]):
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
    with alerts_lock(path):
        data = load_alerts(path)
        if not any(a["id"] == alert_id_ for a in data["alerts"]):
            return False
        if not any(a.get("alert_id") == alert_id_ for a in data["acknowledgements"]):
            data["acknowledgements"].append(
                {"alert_id": alert_id_,
                 "acknowledged_at": (now or datetime.now()).isoformat(timespec="seconds")})
            _atomic_write(Path(path), data)
        return True


def update_saved_alerts(path: str | Path, evaluations: list[dict],
                        open_symbols: set[str], now: datetime) -> dict:
    """Merge evaluations into the latest saved alerts, preserving concurrent acks."""
    with alerts_lock(path):
        data = load_alerts(path)
        data, _ = update_alerts(data, evaluations, open_symbols, now)
        _atomic_write(Path(path), data)
        return data


def with_ack_status(data: dict) -> list[dict]:
    acked = {a["alert_id"]: a["acknowledged_at"] for a in data.get("acknowledgements", [])}
    return [dict(a, acknowledged_at=acked.get(a["id"])) for a in data.get("alerts", [])]
