"""Alert persistence must serialize independent monitor/API Python processes."""
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime

import pytest

from core.portfolio import LedgerCorrupt
from core.portfolio_alerts import (
    acknowledge, alerts_lock, load_alerts, update_saved_alerts,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 9, 17)


def evaluation(symbol="A.NS", action="EXIT"):
    return {"symbol": symbol, "action": action, "rule": "hard stop",
            "last_bar_date": "2026-11-09", "explanation": "Exit triggered"}


def worker(tmp_path, name, body):
    """Spawn an independent interpreter; ready marker precedes its lock attempt."""
    ready = tmp_path / f"{name}.ready"
    code = (
        "from pathlib import Path\n"
        "from datetime import datetime\n"
        "from core.portfolio_alerts import *\n"
        "import sys\n"
        "p = Path(sys.argv[1])\n"
        "Path(sys.argv[2]).write_text('ready')\n" + body
    )
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(tmp_path / "alerts.json"), str(ready)],
        cwd=ROOT, env={**os.environ, "PYTHONUTF8": "1"},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return child, ready


def wait_ready(children):
    deadline = time.monotonic() + 15
    while not all(ready.exists() for _, ready in children):
        assert time.monotonic() < deadline, "worker failed to start"
        assert all(child.poll() is None for child, ready in children if not ready.exists())
        time.sleep(0.01)


def finish(children):
    for child, _ in children:
        stdout, stderr = child.communicate(timeout=15)
        assert child.returncode == 0, stdout + stderr


def cleanup(children):
    for child, _ in children:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=15)


def test_update_reloads_acknowledgement_saved_during_evaluation(tmp_path):
    path = tmp_path / "alerts.json"
    initial = update_saved_alerts(path, [evaluation()], {"A.NS"}, NOW)
    aid = initial["alerts"][0]["id"]
    assert acknowledge(path, aid, NOW)
    updated = update_saved_alerts(path, [evaluation(action="REVIEW")], {"A.NS"}, NOW)
    assert updated["acknowledgements"] == [{"alert_id": aid, "acknowledged_at": NOW.isoformat()}]
    assert len(updated["alerts"]) == 2
    assert load_alerts(path) == updated


def test_separate_process_ack_and_monitor_writes_preserve_all_changes(tmp_path):
    path = tmp_path / "alerts.json"
    seeded = update_saved_alerts(path, [evaluation("A.NS"), evaluation("B.NS")],
                                 {"A.NS", "B.NS"}, NOW)
    ids = [a["id"] for a in seeded["alerts"]]
    children = []
    try:
        with alerts_lock(path):
            for idx, aid in enumerate(ids):
                children.append(worker(tmp_path, f"ack-{idx}", f"assert acknowledge(p, {aid!r})\n"))
            children.append(worker(tmp_path, "monitor",
                f"update_saved_alerts(p, [{evaluation('C.NS')!r}], "
                "{'A.NS', 'B.NS', 'C.NS'}, datetime(2026, 11, 9, 17))\n"))
            wait_ready(children)
            # Every operation must wait for the same cross-process lock.
            for child, _ in children:
                with pytest.raises(subprocess.TimeoutExpired):
                    child.wait(timeout=0.15)
        finish(children)
        saved = load_alerts(path)
        assert {a["alert_id"] for a in saved["acknowledgements"]} == set(ids)
        assert {a["symbol"] for a in saved["alerts"]} == {"A.NS", "B.NS", "C.NS"}
    finally:
        cleanup(children)


def test_lock_timeout_is_bounded_and_clear_and_release_allows_retry(tmp_path):
    path = tmp_path / "alerts.json"
    children = []
    try:
        with alerts_lock(path):
            children.append(worker(tmp_path, "timeout",
                "try:\n"
                "    with alerts_lock(p, timeout=0.15):\n"
                "        raise AssertionError('unexpected lock acquisition')\n"
                "except AlertsLockTimeout as exc:\n"
                "    assert 'Retry shortly' in str(exc)\n"
                "    assert str(p) in str(exc)\n"))
            wait_ready(children)
            finish(children)
        assert update_saved_alerts(path, [evaluation()], {"A.NS"}, NOW)["alerts"]
    finally:
        cleanup(children)


def test_lock_released_after_process_is_killed(tmp_path):
    children = []
    path = tmp_path / "alerts.json"
    acquired = tmp_path / "acquired"
    try:
        children.append(worker(tmp_path, "holder",
            "import time\n"
            "with alerts_lock(p):\n"
            f"    Path({str(acquired)!r}).write_text('locked')\n"
            "    time.sleep(30)\n"))
        wait_ready([(children[0][0], acquired)])
        children[0][0].kill()
        children[0][0].communicate(timeout=15)
        with alerts_lock(path, timeout=0.5):
            pass
    finally:
        cleanup(children)


def test_corrupt_alerts_are_preserved_and_lock_released(tmp_path):
    path = tmp_path / "alerts.json"
    path.write_text("{broken", encoding="utf-8")
    for operation in (
        lambda: acknowledge(path, "missing"),
        lambda: update_saved_alerts(path, [evaluation()], {"A.NS"}, NOW),
    ):
        with pytest.raises(LedgerCorrupt):
            operation()
        assert path.read_text(encoding="utf-8") == "{broken"
        with alerts_lock(path, timeout=0):
            pass
