# Holdings alerts by Telegram and email (short design)

Date: 2026-11-14. Status: approved by the user in conversation ("ok, then let's do the build part locally").

## Intent

The user holds 7 stocks, 3 of them already flagged EXIT by the holdings check. Today the check runs only
when the app runs an update or the user presses "Check holdings now", and nothing tells the user while
the app is closed. The user wants the app to keep watching holdings every market day and send a
Telegram message and an email when it is time to sell. Everything runs on this laptop for now; hosting
online comes later and must not need a rewrite of this work.

## Finding that shapes the design

A Windows task "NSE Strategy Hub Daily Refresh" already exists (Mon-Fri 16:00, runs `refresh_data.bat`,
whose last step is `portfolio_monitor.py`). It has never finished a run: there is no `refresh_log.txt`,
and its last result is 0x800710E0 (Windows refused to start it). Its settings skip the run when the laptop
is on battery and never catch up a missed run. The full 12-step refresh is also long, so an alert would
wait behind every backtest.

## Goals

- Every weekday after the close, the laptop refreshes Nifty and holding prices, runs the holdings check, and
  sends messages.
- Send a Telegram message and an email for each new EXIT or REVIEW alert, with the stock, rule, last close,
  rule level, and gain or loss on the holding.
- Send a failure message when the check could not run or ran on old prices, so silence never means safe.
- Send one short daily summary ("Checked 7 holdings: 3 EXIT, 2 REVIEW, 2 HOLD"). It can be switched off.
- Retry a message that failed to send at the next run. One channel failing must not stop the other.

## Non-goals

- No orders and no automatic selling. Messages inform; the user decides.
- No WhatsApp or SMS. No hosting. The sell-rule research and per-buy sell plans are separate projects.

## Anti-goals (failure even if it works)

- A check that silently does not run.
- The same alert sent again every day (the existing alert dedupe must hold).
- The bot key or app password in git, in logs, or in any message.

## Approaches considered

- **A. Separate light task + standard-library senders (chosen).** A new task at 16:15 runs only the steps
  alerts need: Nifty prices, holding prices, the check, messages. It takes minutes, does not depend on
  the backtests, and the sender code moves to a server unchanged.
- B. Add a messaging step to the end of the existing full refresh. Rejected: alerts would wait behind every
  backtest and fail whenever an earlier step hangs, and that task has never completed.
- C. A third-party relay (IFTTT, ntfy). Rejected: one more account and less control for no gain over the
  Telegram Bot API and Gmail.

## Design

- **Entry script** `holdings_check.py` (project root): refresh `^NSEI` in `data/nse_bse/` with completed bars
  only, run `portfolio_monitor` (which already re-fetches holdings behind Nifty), then send messages. It always
  exits after trying to send, and it reports its own crash through the failure message when possible.
- **Sender module** `core/notify.py`: Telegram via HTTPS `sendMessage` and email via Gmail SMTP over SSL, with
  standard library only (urllib, smtplib); no new dependencies. Keys come from a local `.env`: `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID`, `SMTP_USER`, `SMTP_APP_PASSWORD`, `ALERT_EMAIL_TO`. A missing channel is skipped and
  reported, never a crash.
- **What was sent** is recorded in `portfolio/notifications.jsonl`, one row per message per channel:
  `{alert_id, channel, sent_at (ISO-8601 IST), ok, error}`. An alert counts as sent per channel only after
  that channel succeeds.
- **Settings** go in `portfolio/settings.json` under `notifications` (daily summary on or off). Defaults are
  added without touching existing keys.
- **Test command**: `python holdings_check.py --test-message` sends one test message on each channel.
- **Scheduled task** "NSE Strategy Hub Holdings Check": Mon-Fri 16:15 using the project `.venv` Python, run as
  soon as possible after a missed start, allowed on battery, log to a git-ignored log file. Registered by a
  small PowerShell script in the repo, run once with the user's go-ahead.
- **Market holidays**: no new Nifty bar means no new session. The summary says so; that is not a failure.
- `.env` and the log file are added to `.gitignore`.

## Left to the builder

- Exact message wording (plain language, no "guaranteed" or "no loss" wording; existing forbidden-word tests apply).
- Whether the /portfolio page shows the last scheduled run (the UI file has a `scheduler` field that says "none").
- Fixing the existing full-refresh task's settings is offered to the user separately, not changed silently.

## Testing

Unit tests with fake senders and temp folders; no network in tests. Cases: new alert sent once on both channels;
one channel down, the other still sends and the failed one retries next run; no keys means skip and report;
failure message on a crashed or stale check; holiday summary; the key never appears in logs. One live test
with the user's own bot and email after setup.
