# Holdings Alerts (Telegram + Email) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every weekday at 16:15 the laptop refreshes Nifty and holding prices, runs the holdings check, and sends new EXIT/REVIEW alerts, a failure notice, and a daily summary by Telegram and email.

**Architecture:** `core/notify.py` builds message texts and delivers them through pluggable senders, recording each attempt in `portfolio/notifications.jsonl` so nothing is sent twice and failures retry. `holdings_check.py` is the scheduled entry point: Nifty refresh, then the existing `portfolio_monitor.main`, then messages. A PowerShell script registers the Windows task.

**Tech Stack:** Python 3.13 standard library only (`urllib.request`, `smtplib`, `email.message`), pytest, Windows Task Scheduler (`Register-ScheduledTask`).

**Spec:** `docs/superpowers/specs/2026-11-14-holdings-alerts-design.md`

## Global Constraints

- No new dependencies. Standard library only for HTTP and SMTP.
- Secrets only in project-root `.env` (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SMTP_USER`, `SMTP_APP_PASSWORD`, `ALERT_EMAIL_TO`). Never in git, logs, `notifications.jsonl`, or message text.
- Root `portfolio/` stays git-ignored. `.env` and `holdings_check.log` are added to `.gitignore`.
- Message text never contains "guarantee", "no loss" or "100%" (same rule as `tests/test_exit_monitor.py::test_never_uses_forbidden_words`). Every alert body ends with: `Past rules, not a promise. Nothing is sold automatically; you decide.`
- Python is the only writer of `portfolio/` files. Tests use `tmp_path` only, never the real `portfolio/`, and never the network.
- Run Python tests with the project interpreter: `.venv/Scripts/python.exe -m pytest <file> -q -p no:cacheprovider`.
- Times are IST (`core.exit_monitor.IST`); dates in keys are `YYYY-MM-DD`.

## Review Focus

1. **First run after install:** alerts.json already holds older alerts (some superseded, e.g. REVIEW later became EXIT). Expect only alerts that match the symbol's current `state` and are not acknowledged to be sent, each once. Test in Task 1.
2. **Secret inside an error:** `urllib` errors can include the request URL, which contains the bot token. Expect the token and app password replaced by `***` in problems and in `notifications.jsonl`. Test in Task 2.
3. **Task runs twice in one day** (catch-up run plus a manual run): expect no second summary and no repeated alerts. Test in Task 3.
4. **Monitor crashed or `ui_portfolio.json` missing/unreadable:** expect a failure message, never a traceback that ends the run before sending. Test in Task 3.
5. **Hand-edited `.env`:** quotes, spaces around `=`, `#` comments, blank lines, a UTF-8 BOM. Expect values parsed correctly; an incomplete channel is skipped with a note. Test in Task 1.

---

### Task 1: Message building, `.env` config and delivery log (`core/notify.py`)

**Files:**
- Create: `core/notify.py`
- Modify: `core/portfolio.py:41-56` (add `"notifications": {"daily_summary": True}` to `DEFAULT_SETTINGS`)
- Modify: `.gitignore` (add `.env` and `holdings_check.log`)
- Test: `tests/test_notify.py`

**Interfaces:**
- Produces:
  - `Sender = Callable[[str, str], None]`: `(subject, body)`; raises on failure.
  - `load_config(env_path: Path, environ: Mapping[str, str] | None = None) -> tuple[dict[str, dict[str, str]], list[str]]`: returns `({"telegram": {"token", "chat_id"}, "email": {"user", "password", "to"}}` with only complete channels, `notes)`. `environ` values override the file; `None` means `os.environ`.
  - `alert_message(alert: dict, position: dict | None) -> dict`: `{"key": alert["id"], "subject", "body"}`.
  - `summary_message(ui: dict, session_date: str | None, today: str) -> dict`: key `summary:<today>`.
  - `failure_message(reason: str, today: str) -> dict`: key `failure:<today>:<sha1(reason)[:8]>`.
  - `alerts_to_send(alerts_doc: dict) -> list[dict]`: alerts whose `(action, rule)` equals `alerts_doc["state"][symbol]`, action in `("EXIT", "REVIEW", "REDUCE")`, not acknowledged.
  - `deliver(messages: list[dict], senders: dict[str, Sender], log_path: Path, now: datetime, secrets: Sequence[str] = ()) -> list[str]`: returns problems; skips `(key, channel)` pairs already logged `ok: true`; appends one JSON row per attempt: `{"key", "channel", "sent_at", "ok", "error"}`.

- [ ] **Step 1: Write the failing tests** in `tests/test_notify.py`:

```python
def test_env_parsing_handles_quotes_comments_bom(tmp_path):
    p = tmp_path / ".env"
    p.write_bytes('﻿# keys\nTELEGRAM_BOT_TOKEN = "123:abc"\nTELEGRAM_CHAT_ID=42\n\nSMTP_USER=me@x.com\n'.encode("utf-8"))
    cfg, notes = notify.load_config(p, environ={})
    assert cfg == {"telegram": {"token": "123:abc", "chat_id": "42"}}
    assert any("email" in n for n in notes)            # incomplete channel reported, not raised

def test_missing_env_file_gives_no_channels(tmp_path):
    assert notify.load_config(tmp_path / ".env", environ={})[0] == {}

def test_only_current_unacknowledged_alerts_are_sent():
    doc = {"state": {"A.NS": {"action": "EXIT", "rule": "ema"}, "B.NS": {"action": "HOLD", "rule": None}},
           "alerts": [{"id": "1", "symbol": "A.NS", "action": "REVIEW", "rule": "ema"},
                      {"id": "2", "symbol": "A.NS", "action": "EXIT", "rule": "ema"},
                      {"id": "3", "symbol": "B.NS", "action": "EXIT", "rule": "stop"},
                      {"id": "4", "symbol": "C.NS", "action": "EXIT", "rule": "stop"}],
           "acknowledgements": []}
    assert [a["id"] for a in notify.alerts_to_send(doc)] == ["2"]
    doc["acknowledgements"] = [{"alert_id": "2"}]
    assert notify.alerts_to_send(doc) == []

def test_alert_message_has_close_pnl_and_honesty_line():
    alert = {"id": "x1", "symbol": "BHARATGEAR.NS", "action": "EXIT", "rule": "Close below 220-day EMA",
             "trigger_bar_date": "2026-11-13", "message": "Close 98.54 is below the 220-day EMA 106.53."}
    pos = {"symbol": "BHARATGEAR.NS", "name": "Bharat Gears", "open_qty": 1051,
           "unrealised_pnl": -2399.0, "unrealised_pnl_pct": -2.3, "evaluation": {"last_close": 98.54}}
    m = notify.alert_message(alert, pos)
    assert m["key"] == "x1" and m["subject"] == "EXIT: BHARATGEAR.NS - Close below 220-day EMA"
    for part in ("Bharat Gears", "1051 shares", "-2.3%", "98.54", "2026-11-13",
                 "Past rules, not a promise. Nothing is sold automatically; you decide."):
        assert part in m["body"]

def test_summary_counts_and_holiday_wording():
    ui = {"positions": [{"symbol": s, "evaluation": {"action": a}, "unrealised_pnl_pct": 1.0}
                        for s, a in (("A.NS", "EXIT"), ("B.NS", "REVIEW"), ("C.NS", "HOLD"))]}
    m = notify.summary_message(ui, "2026-11-14", "2026-11-14")
    assert m["key"] == "summary:2026-11-14"
    assert m["subject"] == "Holdings check 2026-11-14: 1 EXIT, 1 REVIEW, 1 HOLD"
    holiday = notify.summary_message(ui, "2026-11-13", "2026-11-14")
    assert "No new trading session today" in holiday["body"]

def test_texts_never_use_forbidden_words():
    ...  # build alert, summary and failure messages; assert "guarantee", "no loss", "100%" absent (lowercased)

def test_deliver_sends_once_and_retries_failed_channel(tmp_path):
    log, calls = tmp_path / "n.jsonl", []
    ok = lambda s, b: calls.append(("tg", s))
    def down(s, b): raise OSError("smtp down")
    msgs = [notify.failure_message("prices old", "2026-11-14")]
    problems = notify.deliver(msgs, {"telegram": ok, "email": down}, log, NOW)
    assert calls == [("tg", msgs[0]["subject"])] and problems == [f"email: {msgs[0]['key']}: OSError: smtp down"]
    notify.deliver(msgs, {"telegram": ok, "email": lambda s, b: calls.append(("em", s))}, log, NOW)
    assert [c[0] for c in calls] == ["tg", "em"]      # telegram not repeated, email retried
    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
    assert [(r["channel"], r["ok"]) for r in rows] == [("telegram", True), ("email", False), ("email", True)]
```

`NOW = datetime(2026, 11, 14, 16, 20, tzinfo=IST)`. Fill in the forbidden-words test body exactly as its comment says.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_notify.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError` / `AttributeError` for `core.notify`.

- [ ] **Step 3: Implement `core/notify.py`** with the Interfaces above.
  - `.env` parse: read with `utf-8-sig`, skip blank and `#` lines, split on the first `=`, strip spaces and one pair of matching quotes.
  - Alert body lines, in order: `"{symbol} ({name})"`, the alert `message`, `"Last close {trigger_bar_date}: ₹{last_close:,.2f}"`, `"Your holding: {open_qty} shares, {pnl_pct:+.1f}% (₹{pnl:+,.0f})"` (skip any line whose value is missing), the honesty line.
  - Summary body: one line per holding `"{symbol}: {action} ({pnl_pct:+.1f}%)"`; when `session_date != today` the first line is `"No new trading session today (market holiday, or prices did not download). Latest session: {session_date}."`.
  - Failure subject: `"Holdings check problem {today}"`; body: the reason, then `"Open the app and press Check holdings now, or check holdings_check.log."`.
  - `deliver`: problem text `f"{channel}: {key}: {type(exc).__name__}: {exc}"`, with every string in `secrets` replaced by `***` before it is logged or returned.
  - Add `notifications` default to `DEFAULT_SETTINGS`; add `.env` and `holdings_check.log` to `.gitignore`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_notify.py tests/test_portfolio_ledger.py tests/test_portfolio_monitor.py -q -p no:cacheprovider`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add core/notify.py core/portfolio.py .gitignore tests/test_notify.py
git commit -m "feat(alerts): message texts, .env config and send-once delivery log"
```

### Task 2: Real Telegram and email senders

**Files:**
- Modify: `core/notify.py`
- Test: `tests/test_notify.py`

**Interfaces:**
- Consumes: `load_config` output from Task 1.
- Produces: `make_senders(config: dict[str, dict[str, str]]) -> dict[str, Sender]`, `secrets_of(config) -> list[str]` (token and password).

- [ ] **Step 1: Write the failing tests**

```python
def test_telegram_sender_posts_send_message(monkeypatch):
    seen = {}
    class Resp:
        status = 200
        def read(self): return b'{"ok": true}'
        def __enter__(self): return self
        def __exit__(self, *a): return False
    def fake_urlopen(req, timeout):
        seen["url"], seen["data"], seen["timeout"] = req.full_url, json.loads(req.data), timeout
        return Resp()
    monkeypatch.setattr(notify.urllib.request, "urlopen", fake_urlopen)
    notify.make_senders({"telegram": {"token": "123:abc", "chat_id": "42"}})["telegram"]("Subj", "Body")
    assert seen["url"] == "https://api.telegram.org/bot123:abc/sendMessage"
    assert seen["data"] == {"chat_id": "42", "text": "Subj\n\nBody"} and seen["timeout"] == 20

def test_telegram_ok_false_raises(monkeypatch): ...   # response {"ok": false, "description": "chat not found"} -> RuntimeError containing "chat not found"

def test_email_sender_uses_gmail_ssl(monkeypatch): ...
    # fake smtplib.SMTP_SSL records host "smtp.gmail.com", port 465, login(user, password), send_message(msg)
    # assert msg["Subject"] == "Subj", msg["To"] == "me@x.com", msg["From"] == "bot@x.com", body == "Body"

def test_secret_in_error_is_redacted(tmp_path, monkeypatch):
    cfg = {"telegram": {"token": "123:abc", "chat_id": "42"}}
    def boom(req, timeout): raise urllib.error.URLError(f"failed {req.full_url}")
    monkeypatch.setattr(notify.urllib.request, "urlopen", boom)
    log = tmp_path / "n.jsonl"
    problems = notify.deliver([notify.failure_message("x", "2026-11-14")], notify.make_senders(cfg), log, NOW,
                              secrets=notify.secrets_of(cfg))
    assert "123:abc" not in problems[0] and "***" in problems[0]
    assert "123:abc" not in log.read_text(encoding="utf-8")
```

Fill in the two `...` tests exactly as their comments say.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_notify.py -q -p no:cacheprovider`
Expected: FAIL with `AttributeError: module 'core.notify' has no attribute 'make_senders'`.

- [ ] **Step 3: Implement `make_senders` and `secrets_of`**
  - Telegram: POST JSON to `https://api.telegram.org/bot{token}/sendMessage`, body `{"chat_id", "text": subject + "\n\n" + body}`, `Content-Type: application/json`, `timeout=20`; raise `RuntimeError(description)` when the reply has `"ok": false`.
  - Email: `email.message.EmailMessage` with Subject/From (`user`)/To (`to`), `smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20)`, `login(user, password)`, `send_message`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_notify.py -q -p no:cacheprovider`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add core/notify.py tests/test_notify.py
git commit -m "feat(alerts): Telegram and Gmail senders with secret redaction"
```

### Task 3: Scheduled entry point `holdings_check.py`

**Files:**
- Create: `holdings_check.py`
- Test: `tests/test_holdings_check.py`

**Interfaces:**
- Consumes: everything from Tasks 1–2; `portfolio_monitor.main(argv) -> int`, `portfolio_monitor.nifty_session_date(now)`, `core.incremental.refresh_tickers(syms, folder, today, fetch, max_workers)`, `core.incremental.yf_fetch`, `core.exit_monitor.completed_cutoff(now)`, `core.portfolio.load_settings(path)`.
- Produces: `main(argv: list[str] | None = None, *, now: datetime | None = None, root: Path = ROOT, fetch=None, monitor=None, senders: dict | None = None) -> int`. Flag: `--test-message`. Returns 0 when every message was delivered on every configured channel, 1 otherwise (so the task history shows trouble).

Flow of `main`: load config (`root/.env`); if no channels and no injected `senders`, print the notes and return 1. Refresh `^NSEI` into `root/data/nse_bse` with `refresh_tickers(["^NSEI"], …, completed_cutoff(now), fetch or yf_fetch, max_workers=1)`; a refresh exception becomes a failure reason, not a crash. Run `monitor(["--dir", root/"portfolio", "--out", root/"ui_portfolio.json"])` (default `portfolio_monitor.main`), catching any exception into a failure reason. Read `ui_portfolio.json` and `portfolio/alerts.json`; unreadable ⇒ failure reason. Failure reasons: monitor rc ≠ 0, `monitor.ok` false (include its `errors`), any position with `evaluation.data_status` ≠ `"OK"` (name the symbols). Session date for the summary: latest `evaluation.last_bar_date` across positions. The `today` passed to `summary_message` and `failure_message` is `completed_cutoff(now).isoformat()`, not the calendar date, so a catch-up run the next morning (before 15:45) reports on the previous session instead of calling it a holiday. Add a test: `now = 2026-11-15 09:00 IST`, positions' last bar `2026-11-14` → summary key `summary:2026-11-14`, no "No new trading session" line. Messages: one per `alerts_to_send`, one `failure_message` per reason, one `summary_message` when `settings["notifications"]["daily_summary"]`. `deliver` to `root/portfolio/notifications.jsonl` with `secrets_of(config)`.

- [ ] **Step 1: Write the failing tests** (`root` = `tmp_path` laid out like the project; fake `fetch`; fake `monitor` that writes a given `ui_portfolio.json` / `alerts.json` and returns an rc; fake senders recording `(channel, subject)`):

```python
def test_sends_alerts_and_summary_once_per_day(tmp_path): ...
    # monitor writes 1 current EXIT alert + 2 positions (OK data); run main twice with the same now
    # first run: each channel gets the EXIT subject and the summary subject; rc 0
    # second run: no new sends; rc 0

def test_monitor_crash_sends_failure_message(tmp_path): ...
    # monitor raises RuntimeError("boom"); each channel gets subject "Holdings check problem 2026-11-14"; rc 0

def test_unreadable_ui_file_sends_failure_message(tmp_path): ...
    # monitor returns 0 but writes "{broken" to ui_portfolio.json; failure message sent, no traceback

def test_stale_position_is_a_failure(tmp_path): ...
    # one position with data_status "STALE"; failure message body names the symbol

def test_daily_summary_can_be_switched_off(tmp_path): ...
    # portfolio/settings.json {"notifications": {"daily_summary": false}}; no summary subject sent

def test_no_channels_configured_returns_1(tmp_path, capsys): ...
    # no .env, senders=None; rc 1; output mentions TELEGRAM_BOT_TOKEN

def test_test_message_flag_sends_one_message_per_channel(tmp_path): ...
    # --test-message: each channel gets subject "Test message from NSE Strategy Hub"; monitor not called
```

Write each test body exactly as its comments say, with `now = datetime(2026, 11, 14, 16, 20, tzinfo=IST)`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_holdings_check.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'holdings_check'`.

- [ ] **Step 3: Implement `holdings_check.py`** with the signature and flow above, plus `if __name__ == "__main__": sys.exit(main())`. Print one line per step and the final problem list (secrets already redacted).

- [ ] **Step 4: Run the new tests and the portfolio suites**

Run: `.venv/Scripts/python.exe -m pytest tests/test_holdings_check.py tests/test_notify.py tests/test_portfolio_monitor.py -q -p no:cacheprovider`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add holdings_check.py tests/test_holdings_check.py
git commit -m "feat(alerts): daily holdings check entry point with failure and summary messages"
```

### Task 4: Windows task, setup guide, full checks, handoff

**Files:**
- Create: `scripts/register_holdings_task.ps1`
- Create: `docs/holdings-alerts-setup.md`
- Modify: `docs/HANDOFF.md`, `MEMORY.md` (top section)

- [ ] **Step 1: Write `scripts/register_holdings_task.ps1`**: registers (or replaces) task `NSE Strategy Hub Holdings Check`. Action `cmd.exe /c ""<proj>\.venv\Scripts\python.exe" holdings_check.py >> holdings_check.log 2>&1"` with working directory = project root. Trigger weekly Mon–Fri 16:15. Settings: `-StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)`. Runs as the current user, only when logged on (no stored password). The project path comes from `$PSScriptRoot\..`, not a hard-coded string.

- [ ] **Step 2: Write `docs/holdings-alerts-setup.md`** for the user, in plain steps: make the bot with @BotFather; send it any message; get the chat id from `https://api.telegram.org/bot<TOKEN>/getUpdates`; make a Gmail app password (2-Step Verification required); create `.env` with the five keys; run `.venv\Scripts\python.exe holdings_check.py --test-message`; run the register script; how to switch off the daily summary.

- [ ] **Step 3: Full checks**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --ignore=tests/test_store.py`
Expected: all pass (baseline 425 + the new tests).
Run: `.venv/Scripts/python.exe verify_protected.py`
Expected: `OK` (no protected file touched).
Run: `git status --short --ignored | grep -E "\.env$|holdings_check.log"` then `git check-ignore .env holdings_check.log portfolio/notifications.jsonl`
Expected: all three paths printed by `git check-ignore` (ignored).

- [ ] **Step 4: Update `docs/HANDOFF.md` and `MEMORY.md`** with the commits, checks run, and what waits on the user (bot key, app password, test message, task registration).

- [ ] **Step 5: Commit**

```bash
git add scripts/register_holdings_task.ps1 docs/holdings-alerts-setup.md
git commit -m "feat(alerts): scheduled task script and setup guide"
```

(`docs/HANDOFF.md` and `MEMORY.md` are untracked/ignored; they are updated on disk, not committed.)

- [ ] **Step 6: With the user (not automated):** user fills `.env`; run `--test-message`; user confirms both messages arrived; with the user's go-ahead run `powershell -ExecutionPolicy Bypass -File scripts/register_holdings_task.ps1`; run the task once with `Start-ScheduledTask` and read `holdings_check.log`.
