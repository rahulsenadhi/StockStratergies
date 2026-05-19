# NSE Strategy Hub — User Guide

**A simple, rules-based system for picking Indian stocks.** Three different strategies in one dashboard. No guessing, no emotions — just numbers and rules.

This guide is written for people who know stocks but are **not** programmers or quants. If a word looks technical, it is explained in the Glossary at the bottom.

---

## What this is

The NSE Strategy Hub is a small app that runs on your own computer. It does three things:

1. **Downloads daily price data** for Indian stocks from Yahoo Finance (free).
2. **Backtests three strategies** — meaning, it pretends to trade with historical data so you can see what *would have* happened.
3. **Shows you a dashboard** in your web browser with results, current signals, and easy-to-read charts.

### The three strategies

| Strategy | What it does | When it works best |
|----------|--------------|--------------------|
| 🔄 **Monthly Rotation** | Every month, buys the 5 strongest Nifty 50 stocks. Sells whichever fall out of the top 5. | Steady markets. Lowest effort — one decision per month. |
| 🚀 **IPO Edge** | Waits for new IPOs to settle for ~40 days, then buys when they break out on strong volume. | Bullish markets, when investors are excited about new listings. |
| 📈 **Momentum Edge** | Buys large-cap stocks that dipped below their long-term trend, recovered, then made a new all-time high. | Trending bull markets. Sits in cash during downturns automatically. |

You can run all three side-by-side and compare.

---

## Quick start (first time setup)

You will only do this once.

### Step 1 — Install Python

The dashboard needs **Python 3.10 or newer**.

- **Windows:** open Microsoft Store, search "Python 3.12", install it. Or download from [python.org](https://www.python.org/downloads/).
- **Mac:** open Terminal and run `brew install python3` (install Homebrew first from [brew.sh](https://brew.sh) if needed).

To check it worked, open a terminal / PowerShell and type:

```
python --version
```

You should see something like `Python 3.12.5`. If you do, you're set.

### Step 2 — Install the project

1. **Download the project** to your computer. If you have the folder already, skip this.
2. **Open a terminal** inside the project folder. On Windows, you can right-click the folder and pick "Open in Terminal".
3. **Create a virtual environment** (a clean sandbox for the project — it stops it messing with other Python apps):

   ```
   python -m venv .venv
   ```

4. **Activate the sandbox.**
   - Windows PowerShell: `.\.venv\Scripts\Activate.ps1`
   - Mac / Linux: `source .venv/bin/activate`

   You should now see `(.venv)` at the start of your terminal prompt.

5. **Install the libraries** the app needs:

   ```
   pip install streamlit pandas numpy plotly yfinance pyarrow
   ```

   Takes 1–2 minutes. Tea time.

### Step 3 — Download fresh price data

The app comes with sample data, but you'll want today's prices. Run:

```
python step1_download_data.py
python nse_bse_downloader.py
```

The first one grabs Nifty 50 daily prices. The second downloads the wider NSE/BSE universe used by Momentum Edge.

This takes 2–5 minutes the first time. After that, each daily refresh is faster because only new bars get downloaded.

### Step 4 — Start the dashboard

```
streamlit run master_dashboard.py
```

After a few seconds, your browser opens at `http://localhost:8501` and you'll see the dashboard. **That's it.**

To stop the dashboard, press `Ctrl + C` in the terminal where it's running.

---

## Daily routine (after first-time setup)

Every morning (or whenever you check), do this:

1. Open the terminal in the project folder.
2. Activate the sandbox: `.\.venv\Scripts\Activate.ps1` (or `source .venv/bin/activate` on Mac).
3. Refresh data:
   ```
   python step1_download_data.py
   python nse_bse_downloader.py
   ```
4. Start the dashboard:
   ```
   streamlit run master_dashboard.py
   ```

If you want to re-run a backtest after data refresh (recommended weekly):

- **Monthly Rotation:** `python step2_backtest_momentum.py`
- **Momentum Edge:** `python momentum_edge_backtest.py`
- IPO Edge: backtest auto-runs from its dashboard page.

---

## What each page does

When the dashboard opens, the sidebar on the left lists the pages.

### 🏠 Home

A bird's-eye view. Shows all three strategies side-by-side: how much ₹1 lakh grew to, worst loss ever, win rate, and today's top picks.

### 🔄 Monthly Rotation

Shows the current top 5 stocks to hold this month, the full ranking of all 50 Nifty stocks, the equity curve (how the portfolio has grown over time), and the rebalance log (which stocks were swapped in/out each month).

### 🚀 IPO Edge

Live screener of new IPOs. Tells you which ones are in a base, which are breaking out, and which are still too young. Each signal has a Setup type (FLAG, U-TURN, EARLY BOOM, STANDARD) explained inline.

### 📈 Momentum Edge

The most complex strategy. Shows breakouts to all-time highs, near-breakouts to watch, and a filter funnel (how many stocks pass each filter step). Includes a drill-down chart for any stock — click and you see the price with the 220-day average, 52-week high/low, and past trade markers.

### 🔬 Insights

Post-trade analysis. For each closed trade, it asks:
- **Where should the stop-loss go?** (using MAE — see Glossary)
- **When to take profits?** (using fade rate at +10%, +15%, +20% levels)
- **How long should you hold?** (best return bucket vs. safest bucket)
- **Which entry setups predicted winners?**

### 📊 History & Proof

Year-by-year track record. Did the strategy actually make money? Did it beat Nifty? In how many years out of how many? Shown in plain language with verdict emojis.

---

## Glossary — what each term means

Every page also has a glossary expander at the bottom, but here's the full list in one place.

| Term | Plain English |
|------|---------------|
| **ATH** (All-Time High) | The highest price the stock has ever traded. Breaking above ATH = very bullish — no one is sitting at a loss, so no one is selling. |
| **Alpha** | Extra return above the market. If Nifty did 12% and your strategy did 20%, your alpha is +8%. |
| **Backtest** | Pretending to trade with historical data to see what *would have* happened. Not the same as live trading, but the closest we can get without risking real money. |
| **Base / IPO Base** | The sideways trading range after a stock first lists. Usually ~40 days of "settling" before the real move starts. |
| **Bear market** | A market that's falling or stuck. Our regime banner shows 🔴 when this is the case — new entries are paused. |
| **Bull market** | A rising market. Our banner shows 🟢. All three regime conditions are on. |
| **Breakout** | Price crosses a key resistance level (like a 52-week high or an ATH). With strong volume = real. Without volume = often a fake-out. |
| **CAGR** (Compounded Annual Growth Rate) | Your average yearly return. If ₹1 lakh grew to ₹1.5 lakh in 3 years, CAGR is about 14%/year. |
| **Choppiness Index** | A 0–100 score. Below 61.8 = the chart is trending (good to trade). Above 61.8 = sideways/noisy (avoid). |
| **Drawdown** | A drop from a peak. If your portfolio hit ₹1.5L then fell to ₹1.1L, that's a -27% drawdown. |
| **EMA** (Exponential Moving Average) | A trend line that averages recent prices, giving more weight to the latest days. 220 EMA = long-term trend. |
| **Equity curve** | The line showing how much money your portfolio has grown over time. Up and to the right = good. |
| **Fade Rate** | The % of times a gain gets given back. If +15% has a 30% fade rate, then 30% of trades that touched +15% closed below +15%. Low fade rate = book profits there. |
| **Hard Stop** | An automatic exit at a fixed loss. If you buy at ₹100 with a 15% hard stop, you sell at ₹85 no matter what. Protects you from disasters. |
| **Live Breakout** | The IPO Edge signal for a stock that *right now* is breaking above its base on strong volume. The buy signal. |
| **MAE** (Maximum Adverse Excursion) | The deepest dip a trade saw before it closed. Even winners dip — the question is how deep. Used to size your stop-loss. |
| **MFE** (Maximum Favourable Excursion) | The biggest gain a trade touched before it closed. Used to pick profit-taking levels. |
| **Max Drawdown** | The worst-ever drop. Smaller is safer. A good strategy keeps this below -25%. |
| **Momentum** | The tendency of strong stocks to keep being strong. Our strategies buy momentum, never bet against it. |
| **Near Breakout** | A stock 0–2% below its breakout level. Worth watching — it might break out tomorrow. |
| **p95** (95th percentile) | A worst-case bound that ignores rare outliers. "p95 MAE = -10%" means 95% of trades dipped no more than 10%. |
| **Partial Booking** | Selling part of your position once it hits a profit (e.g. sell 1/3 at +15%). Locks in profit while letting the rest run. |
| **Quintile** | Top 5 buckets, each holding 20% of the data. We use this to check if higher Score really predicts higher win rate (a "monotonic ladder"). |
| **Rebalance** | Adjusting the portfolio on a schedule. Monthly Rotation rebalances on the 1st of every month — sells losers, buys the new top 5. |
| **Regime** | The overall market state: Bull or Bear. We use 3 conditions on Nifty itself (above its 200 SMA, 50 SMA above 200 SMA, within 10% of 52-week high). All 3 on = Bull. |
| **Recovery Speed** | How fast a stock bounced back after dipping below its 220 EMA. Fast (≤30 days) is best. |
| **RS Score** (Relative Strength) | How much a stock outperformed the index over the last N months. Higher RS = stronger stock. We buy the top 5 RS in Monthly Rotation. |
| **Sharpe Ratio** | Return per unit of risk. Above 1.0 = good. Above 2.0 = excellent. |
| **Signal** | A trade idea for today: "Breakout Today" (buy), "Near Breakout" (watch), "Watch Zone" (monitor). |
| **SMA** (Simple Moving Average) | A trend line that averages prices equally. 50 SMA = average of last 50 closes. Used with 200 SMA to confirm trend direction. |
| **Stage 1 / 2 / 3** (IPO Edge) | Stage 1 = still building the base. Stage 2 = recovering above its 10-day average. Stage 3 = breaking out with volume — the buy. |
| **Stop-Loss** | A price below which you automatically sell to cap losses. Our backtests use a 15% hard stop on Momentum Edge. |
| **Vol Ratio** | Today's volume divided by the 20-day average volume. Above 1.5× = strong buying interest. Below 1.0× = quiet. |
| **Watch Zone** | A signal that's close but not ready. Don't buy yet — wait for it to upgrade to Live Breakout or Breakout Today. |
| **Win Rate** | % of trades that made a profit. 60% = 6 out of 10 winners. Even 45% can be great if the wins are much bigger than the losses. |
| **52W High / Low** | The highest / lowest price in the last 52 weeks (1 year). Distance from 52W high is a key strength measure. |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Dashboard shows "No backtest data" | You haven't run the backtest yet. See "Daily routine" → re-run backtest section. |
| Data feels stale | Re-run `python step1_download_data.py` and `python nse_bse_downloader.py`. The downloader will skip files already up-to-date. |
| `ModuleNotFoundError` when starting | Your virtual environment isn't activated. Run `.\.venv\Scripts\Activate.ps1` (Windows) or `source .venv/bin/activate` (Mac/Linux) first. |
| Browser doesn't open | Open it manually and go to `http://localhost:8501`. |
| Dashboard is slow on first load | Normal. Streamlit caches data for an hour after first load. Subsequent navigation is fast. |
| Charts look broken | Your browser may have cached an old version. Hard refresh: `Ctrl + Shift + R`. |

---

## Important disclaimers

- **This is not investment advice.** Backtests show what *would have* happened in the past. Past performance does not guarantee future results.
- **All trades shown are paper trades** — no real money is involved unless you choose to execute them yourself with a broker.
- **Always do your own research.** Use this dashboard as one input among many, not as a black box you blindly follow.
- **Brokerage, taxes, and slippage** are not modelled. Real trading costs will reduce your actual returns vs the backtest numbers.

---

## Where to go next

- Start on the **🏠 Home** page to see the big picture.
- Read the **📊 History** page to see how each strategy actually performed.
- Use **🔬 Insights** before you size your positions — it tells you where to put the stop-loss and when to book profits.
- Pick one strategy, follow it for a few months in paper-trading mode, and only commit real capital once you understand it.

Good hunting.
