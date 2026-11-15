"""Daily holdings check with Telegram and email alerts (run by the Windows task at 16:15).

Steps: refresh Nifty prices (completed bars only) -> run portfolio_monitor (which also
re-fetches holdings behind Nifty) -> send new EXIT/REVIEW alerts, failure notices and a
daily summary.  Every send is recorded in portfolio/notifications.jsonl, so a message is
sent once per channel and a failed channel is retried at the next run.

  python holdings_check.py                 # the daily run
  python holdings_check.py --test-message  # one test message on each channel

Exit code 0 when every message was delivered on every configured channel, else 1.
Keys live in .env (see docs/holdings-alerts-setup.md); they never appear in output.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

from core import notify
from core.exit_monitor import IST, completed_cutoff
from core.portfolio import load_settings

ROOT = Path(__file__).resolve().parent
NIFTY = "^NSEI"
TEST_SUBJECT = "Test message from NSE Strategy Hub"


def _refresh_nifty(root: Path, now: datetime, fetch) -> list[str]:
    from core import incremental
    try:
        status = incremental.refresh_tickers([NIFTY], root / "data" / "nse_bse", completed_cutoff(now),
                                             fetch or incremental.yf_fetch, max_workers=1)
    except Exception as exc:  # a download problem must not stop the check
        return [f"Nifty price download failed: {type(exc).__name__}: {exc}"]
    st = status.get(NIFTY, "")
    # failed(empty) = Yahoo returned nothing (holiday or no data yet); the summary reports that case.
    if st.startswith("failed") and st != "failed(empty)":
        return [f"Nifty price download failed: {st}"]
    return []


def _run_monitor(root: Path, monitor) -> list[str]:
    if monitor is None:
        import portfolio_monitor
        monitor = portfolio_monitor.main
    try:
        rc = monitor(["--dir", str(root / "portfolio"), "--out", str(root / "ui_portfolio.json")])
    except (Exception, SystemExit) as exc:
        return [f"Holdings check crashed: {type(exc).__name__}: {exc}"]
    return [] if rc == 0 else [f"Holdings check ended with exit code {rc}."]


def _read_json(path: Path) -> dict | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _check_results(ui: dict | None) -> list[str]:
    if ui is None:
        return ["Holdings results file ui_portfolio.json is missing or unreadable."]
    reasons = []
    mon = ui.get("monitor") or {}
    if mon.get("ok") is False:
        reasons.append("Holdings check reported errors: " + "; ".join(mon.get("errors") or ["no detail"]))
    bad = [p.get("symbol") for p in ui.get("positions") or []
           if (p.get("evaluation") or {}).get("data_status", "OK") != "OK"]
    if bad:
        reasons.append("Prices are old or missing for: " + ", ".join(bad)
                       + ". Their sell signals could not be checked on today's prices.")
    return reasons


def _session(ui: dict | None, today: str) -> str:
    """Latest bar date across holdings; with no holdings there is nothing to call stale."""
    bars = [(p.get("evaluation") or {}).get("last_bar_date") for p in (ui or {}).get("positions") or []]
    bars = [b for b in bars if b]
    return max(bars) if bars else today


def _no_new_bar(ui: dict | None, today: str) -> list[str]:
    """A weekday with no bar for today: holiday, or the download failed (Yahoo can return empty)."""
    session = _session(ui, today)
    if ui is None or session >= today or date.fromisoformat(today).weekday() >= 5:
        return []
    return [f"No price bar for {today}: market holiday, or the price download failed. "
            f"Holdings were checked on {session} prices, so a sell signal from today could be missing."]


def _messages(root: Path, ui: dict | None, reasons: list[str], today: str, settings: dict) -> list[dict]:
    alerts_doc = _read_json(root / "portfolio" / "alerts.json") or {}
    by_symbol = {p.get("symbol"): p for p in (ui or {}).get("positions") or []}
    msgs = [notify.alert_message(a, by_symbol.get(a["symbol"])) for a in notify.alerts_to_send(alerts_doc)]
    msgs += [notify.failure_message(r, today) for r in reasons]
    if ui is not None and settings.get("notifications", {}).get("daily_summary", True):
        msgs.append(notify.summary_message(ui, _session(ui, today), today))
    return msgs


def _daily(root: Path, now: datetime, today: str, fetch, monitor, senders: dict, log: Path,
           secrets: list[str]) -> list[str]:
    print("holdings_check: refreshing Nifty prices")
    reasons = _refresh_nifty(root, now, fetch)
    print("holdings_check: checking holdings")
    reasons += _run_monitor(root, monitor)
    ui = _read_json(root / "ui_portfolio.json")
    reasons += _check_results(ui) + _no_new_bar(ui, today)
    msgs = _messages(root, ui, reasons, today, _settings(root))
    print(f"holdings_check: sending {len(msgs)} message(s)")
    return notify.deliver(msgs, senders, log, now, secrets)


def _settings(root: Path) -> dict:
    try:
        return load_settings(root / "portfolio" / "settings.json")
    except Exception:  # an unreadable settings file must not silence alerts
        return {"notifications": {"daily_summary": True}}


def main(argv: list[str] | None = None, *, now: datetime | None = None, root: Path = ROOT,
         fetch=None, monitor=None, senders: dict | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--test-message", action="store_true", help="send one test message on each channel")
    args = ap.parse_args(argv)
    now = now or datetime.now(IST)
    root = Path(root)
    config, notes = notify.load_config(root / ".env")
    for note in notes:
        print(f"holdings_check: {note}")
    if senders is None:
        senders = notify.make_senders(config)
    if not senders:
        print("holdings_check: no channel set up; add TELEGRAM_BOT_TOKEN and the other keys to .env "
              "(see docs/holdings-alerts-setup.md)")
        return 1
    secrets = notify.secrets_of(config)
    log = root / "portfolio" / "notifications.jsonl"
    stamp = now.astimezone(IST).isoformat(timespec="seconds")

    if args.test_message:
        msg = {"key": f"test:{stamp}", "subject": TEST_SUBJECT,
               "body": "If you can read this, holdings alerts can reach you on this channel."}
        problems = notify.deliver([msg], senders, log, now, secrets)
    else:
        today = completed_cutoff(now).isoformat()
        try:
            problems = _daily(root, now, today, fetch, monitor, senders, log, secrets)
        except BaseException as exc:  # report any crash through the failure message when possible
            reason = notify._redact(f"Holdings check crashed unexpectedly: {type(exc).__name__}: {exc}", secrets)
            print(f"holdings_check: {reason}")
            try:
                problems = notify.deliver([notify.failure_message(reason, today)], senders, log, now, secrets)
            except Exception as exc2:
                problems = [notify._redact(f"could not send the crash notice: {type(exc2).__name__}: {exc2}", secrets)]
            problems = problems or [reason]     # a crash always makes the run fail (exit 1)
    for p in problems:
        print(f"holdings_check: send failed: {p}")
    print(f"holdings_check: done at {stamp}, {len(problems)} send problem(s)")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
