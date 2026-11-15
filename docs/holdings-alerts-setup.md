# Holdings alerts: one-time setup

The daily holdings check runs on weekdays at 4:15 pm and sends a Telegram message and an email when a
holding is flagged EXIT or REVIEW, when the check fails, and once a day as a summary. It never sells
anything. Setup takes about 10 minutes.

Your keys go in a file named `.env` in the project folder. Git ignores this file, so it is never uploaded.
Never paste the keys into a chat or a message.

## 1. Telegram bot

1. In Telegram, open **@BotFather**, send `/newbot`, and follow the prompts (any name; the username must end in `bot`).
2. BotFather replies with a key that looks like `123456789:ABC...`. This is `TELEGRAM_BOT_TOKEN`.
3. Open your new bot in Telegram and send it any message, for example `hi`.
4. In a browser, open `https://api.telegram.org/bot<YOUR KEY>/getUpdates` (put your key in place of `<YOUR KEY>`).
   Find `"chat":{"id":` followed by a number. That number is `TELEGRAM_CHAT_ID`.

## 2. Gmail app password

1. Your Google account needs 2-Step Verification turned on (Google Account > Security).
2. Go to Google Account > Security > App passwords, create one named `Holdings alerts`.
3. Google shows a 16-letter password once. This is `SMTP_APP_PASSWORD`. Your normal Gmail password will not work.

## 3. Create `.env`

In the project folder (`Nifty Momentum Rotation Stratergy`), create a file named `.env` containing:

```
TELEGRAM_BOT_TOKEN=123456789:ABC...
TELEGRAM_CHAT_ID=987654321
SMTP_USER=your.address@gmail.com
SMTP_APP_PASSWORD=abcdabcdabcdabcd
ALERT_EMAIL_TO=your.address@gmail.com
```

You can set up only one channel; the other is skipped and named in the log.

## 4. Send a test message

From the project folder:

```
.venv\Scripts\python.exe holdings_check.py --test-message
```

You should get "Test message from NSE Strategy Hub" in Telegram and by email. If not, the command prints why
(keys are shown as `***`).

## 5. Turn on the daily check

```
powershell -ExecutionPolicy Bypass -File scripts\register_holdings_task.ps1
```

This creates the Windows task "NSE Strategy Hub Holdings Check": weekdays at 4:15 pm, catches up if the laptop
was asleep or off, and runs on battery. Output goes to `holdings_check.log`.

## Turning the daily summary off

Add this to `portfolio/settings.json` (keep the other settings in the file):

```json
"notifications": {"daily_summary": false}
```

Alerts and failure messages still arrive.

## What the messages mean

- **EXIT / REVIEW**: the holding met a sell rule of the strategy (for example a close below the 220-day line).
  Past rules, not a promise; you decide whether to sell.
- **Holdings check problem**: the check could not run or ran on old prices. Silence never means "safe".
- **Holdings check (summary)**: one line per holding. "No new trading session today" means a market holiday,
  or prices did not download.
