"""Holdings alert messages and their delivery by Telegram and email.

Message texts are built here; ``deliver`` sends each message on each channel once,
recording every attempt in ``portfolio/notifications.jsonl`` so a failed channel is
retried at the next run and a sent message is never repeated.  Keys come from a local
``.env`` (never committed); they are redacted from every logged or returned error.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Callable, Mapping, Sequence

from core.exit_monitor import _as_ist

Sender = Callable[[str, str], None]

HONESTY_LINE = "Past rules, not a promise. Nothing is sold automatically; you decide."
SELL_ACTIONS = ("EXIT", "REVIEW", "REDUCE")
CHANNEL_KEYS = {
    "telegram": {"token": "TELEGRAM_BOT_TOKEN", "chat_id": "TELEGRAM_CHAT_ID"},
    "email": {"user": "SMTP_USER", "password": "SMTP_APP_PASSWORD", "to": "ALERT_EMAIL_TO"},
}


# ---------------------------------------------------------------- config

def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def load_config(env_path: Path, environ: Mapping[str, str] | None = None
                ) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Complete channels only, plus notes naming the keys a channel is missing."""
    values = _read_env_file(Path(env_path))
    values.update({k: v for k, v in (os.environ if environ is None else environ).items() if v})
    config: dict[str, dict[str, str]] = {}
    notes: list[str] = []
    for channel, fields in CHANNEL_KEYS.items():
        got = {field: values.get(env_key, "") for field, env_key in fields.items()}
        missing = [fields[f] for f, v in got.items() if not v]
        if not missing:
            config[channel] = got
        else:
            notes.append(f"{channel} not set up: missing {', '.join(missing)} in .env")
    return config, notes


# ---------------------------------------------------------------- messages

def alerts_to_send(alerts_doc: dict) -> list[dict]:
    """Alerts still matching the holding's current state, sell-side, not acknowledged."""
    state = alerts_doc.get("state", {})
    acked = {a.get("alert_id") for a in alerts_doc.get("acknowledgements", [])}
    out = []
    for a in alerts_doc.get("alerts", []):
        current = state.get(a.get("symbol"))
        if (a.get("action") in SELL_ACTIONS and a.get("id") not in acked and current is not None
                and (current.get("action"), current.get("rule")) == (a.get("action"), a.get("rule"))):
            out.append(a)
    return out


def _pnl_line(position: dict) -> str | None:
    qty, pct, pnl = position.get("open_qty"), position.get("unrealised_pnl_pct"), position.get("unrealised_pnl")
    if qty is None or pct is None or pnl is None:
        return None
    return f"Your holding: {qty} shares, {pct:+.1f}% (₹{pnl:+,.0f})"


def alert_message(alert: dict, position: dict | None) -> dict:
    sym = alert["symbol"]
    pos = position or {}
    close = (pos.get("evaluation") or {}).get("last_close")
    lines = [f"{sym} ({pos['name']})" if pos.get("name") else sym, alert.get("message")]
    if close is not None and alert.get("trigger_bar_date"):
        lines.append(f"Last close {alert['trigger_bar_date']}: ₹{close:,.2f}")
    lines.append(_pnl_line(pos) if pos else None)
    lines.append(HONESTY_LINE)
    rule = f" - {alert['rule']}" if alert.get("rule") else ""
    return {"key": alert["id"], "subject": f"{alert['action']}: {sym}{rule}",
            "body": "\n".join(line for line in lines if line)}


def summary_message(ui: dict, session_date: str | None, today: str) -> dict:
    positions = ui.get("positions") or []
    counts: dict[str, int] = {}
    lines = []
    if session_date != today:
        lines.append("No new trading session today (market holiday, or prices did not download). "
                     f"Latest session: {session_date or 'unknown'}.")
    for p in positions:
        action = (p.get("evaluation") or {}).get("action", "UNKNOWN")
        counts[action] = counts.get(action, 0) + 1
        pct = p.get("unrealised_pnl_pct")
        lines.append(f"{p.get('symbol')}: {action}" + (f" ({pct:+.1f}%)" if pct is not None else ""))
    order = ["EXIT", "REDUCE", "REVIEW", "HOLD"]
    parts = [f"{counts[a]} {a}" for a in order if a in counts]
    parts += [f"{n} {a}" for a, n in counts.items() if a not in order]
    head = ", ".join(parts) if parts else "no open holdings"
    return {"key": f"summary:{today}", "subject": f"Holdings check {today}: {head}",
            "body": "\n".join(lines) if lines else "No open holdings recorded."}


def failure_message(reason: str, today: str) -> dict:
    digest = hashlib.sha1(reason.encode("utf-8")).hexdigest()[:8]
    return {"key": f"failure:{today}:{digest}", "subject": f"Holdings check problem {today}",
            "body": f"{reason}\nOpen the app and press Check holdings now, or check holdings_check.log."}


# ---------------------------------------------------------------- delivery

def _redact(text: str, secrets: Sequence[str]) -> str:
    for s in secrets:
        if s:
            text = text.replace(s, "***")
    return text


def _sent_pairs(log_path: Path) -> set[tuple[str, str]]:
    if not log_path.exists():
        return set()
    done = set()
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("ok"):
            done.add((row.get("key"), row.get("channel")))
    return done


def deliver(messages: list[dict], senders: dict[str, Sender], log_path: Path, now: datetime,
            secrets: Sequence[str] = ()) -> list[str]:
    """Send each (message, channel) pair not yet sent; return redacted problems."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    done = _sent_pairs(log_path)
    stamp = _as_ist(now).isoformat(timespec="seconds")
    problems: list[str] = []
    with open(log_path, "a", encoding="utf-8") as fh:
        for msg in messages:
            for channel, send in senders.items():
                if (msg["key"], channel) in done:
                    continue
                error = None
                try:
                    send(msg["subject"], msg["body"])
                except Exception as exc:  # one channel failing must not stop the other
                    error = _redact(f"{type(exc).__name__}: {exc}", secrets)
                    problems.append(f"{channel}: {msg['key']}: {error}")
                fh.write(json.dumps({"key": msg["key"], "channel": channel, "sent_at": stamp,
                                     "ok": error is None, "error": error}, ensure_ascii=False) + "\n")
                fh.flush()
    return problems
