# Stock Strategy Hub — Easy Guide

A plain-English manual for running and understanding your 4 stock trading strategies.

---

## What is this?

You have **4 different ways of picking Indian stocks**, each based on a different idea about what makes a stock go up. The computer does the hard math; you read the answer.

| # | Strategy | One-line idea | Best for |
|---|---|---|---|
| 1 | **Monthly Rotation** | Buy the 5 strongest Nifty 50 stocks each month, sell the weak ones | Beginners — most reliable, biggest profits historically |
| 2 | **IPO Edge** | Buy brand new stocks (IPOs) when they show strength | Adventurous — small-cap focus |
| 3 | **Momentum Edge** | Buy any stock that's recovering and breaking to new highs | Long-term holds (~6 months) |
| 4 | **PEAD** | Buy stocks that just reported surprise good earnings | Earnings season players |

---

## One-button daily run

If you only remember one command, remember this. Double-click in File Explorer or run from terminal:

```
refresh_data.bat
```

This file does everything:
- Downloads today's stock prices
- Re-runs all 4 strategies with fresh data
- Updates the dashboards

**Time:** 5–15 minutes (depending on internet speed).
**When to run:** Once a day, after Indian market closes (after 4 PM IST).

---

## Opening the dashboards

After `refresh_data.bat` finishes, run this once to launch the dashboards:

```
python run_all.py --dash-only
```

Your browser opens automatically to the **Master Hub** at http://localhost:8500. From the left sidebar, click any of these:

- 🏠 **Home** — Quick snapshot of all 4 strategies
- 🔄 **Monthly Rotation** — Today's top 5 picks for the month
- 🚀 **IPO Edge** — Recent IPOs that are breaking out
- 📈 **Momentum Edge** — Stocks recovering and hitting new highs
- ⚡ **PEAD** — Earnings-surprise plays
- 🎯 **Suggestions** — Computer's top picks across all 4 strategies
- 🔬 **Insights** — How the strategies behave together
- 📊 **History & Proof** — Backtests, charts, win rates

**Light or dark mode:** sidebar has a Theme toggle (🌙 Dark / ☀️ Light / 🖥️ Auto).

---

## Strategy 1: Monthly Rotation 🏆 (recommended starting point)

**The idea:** Out of 50 big Indian companies (Nifty 50), 5 always outperform in any given month. Buy those 5, hold for a month, then on the last Friday of the month sell whatever's no longer in the top 5 and replace with the new top 5.

**What it has done:**
- **+22.65% per year** (4 years tracked)
- Nifty index did only +9.96% — so this is **+12.68% per year better than just buying the index**
- Worst dip was only -11% (mild)

**How to use it:**
1. Open Master Hub → 🔄 Monthly Rotation
2. Look at the table of 10 stocks ranked 1–10
3. The top 5 (highlighted) = today's portfolio
4. **Next rebalance date** is shown on the page — that's the day to actually buy/sell
5. The signal column tells you what to do:
   - 🟢 Strong BUY — stock outperforming
   - 🟡 Mild BUY — modest gain
   - 🟠 Weak — borderline
   - 🔴 AVOID/SELL — underperforming

**Today's top 5 (example):** ADANIENT, ADANIGREEN, GRASIM, ADANIPORTS, ASIANPAINT

**Manual re-run if needed:**
```
python step1_download_data.py
python step2_backtest_momentum.py
python step3_dashboard.py
```

---

## Strategy 2: IPO Edge 🚀

**The idea:** Brand new IPOs (within 1 year of listing) often have a quiet base-building phase, then a breakout. Buy the breakout, ride it for 1–4 weeks.

**What it has done:**
- **+10.19% per year**
- Very low drawdown (-5.68%) — safer than the others
- 64 closed trades, **56% win rate**

**How to use it:**
1. Open Master Hub → 🚀 IPO Edge
2. Look at "Currently Open" positions — these are trades the strategy is in right now
3. Check the table for setup type:
   - **Stage 1** — building base (cleanest entry)
   - **Stage 3** — already breaking out (riskier, missed early)
4. Exit reason shown when the trade closes:
   - **Hard Stop** = -10% loss limit hit, cut losses
   - **SMA10 Trail** = price broke its trailing stop, take profit
   - **SL→Breakeven** = stop moved to entry, locked in safety

**Manual re-run:**
```
python ipo_edge_downloader.py
python ipo_edge_backtest.py
```

---

## Strategy 3: Momentum Edge 📈

**The idea:** A stock that fell below its 220-day average (was beaten down), then recovers and breaks to a new high — that's a sign of a long-term turnaround. Hold for ~6 months.

**What it has done:**
- **+14.68% per year over 10 years** vs Nifty +12.17%
- Final value: ₹10,000 → ₹3,63,935 over the period (~36×)
- 130 trades, holds average **191 days each**
- **Big wins, sometimes big losses** — avg gain +85%, avg loss -13%

**How to use it:**
1. Open Master Hub → 📈 Momentum Edge
2. **Market Regime** at top tells you to participate or not:
   - 🟢 BULL — go ahead, take new positions
   - 🔴 BEAR — skip new entries, hold existing
3. Today's signals table shows stocks meeting all 6 filters
4. If you see "0 signals" — market doesn't have qualifying setups right now (this is normal)

**Manual re-run:**
```
python nse_bse_downloader.py     # SLOW — 15–30 min, only needed weekly
python momentum_edge_backtest.py
```

---

## Strategy 4: PEAD ⚡ (newest, experimental)

**The idea:** When a company reports earnings that beat what analysts expected, the stock often keeps drifting up for ~2 months. Buy after a positive surprise, hold ~60 days or until next earnings.

**What it has done so far:**
- Only 54 stocks tested (Nifty 50ish)
- 4 trades since 2024 — too few to be sure yet
- **All 4 trades won** (WIPRO twice, CIPLA, TATASTEEL)
- Best trade: WIPRO +10%, worst: WIPRO +2%

**Why so few trades?** PEAD needs strict filters (top 10% surprise + healthy balance sheet + reasonable price). Most quarters, only 1–2 stocks across the universe qualify.

**How to use it:**
1. Open Master Hub → ⚡ PEAD
2. Four tabs at top:
   - **Live + Open** — stocks qualifying today + currently held
   - **Backtest** — historical performance + charts
   - **Calendar + Heatmap** — upcoming earnings dates + which sectors are beating expectations
   - **Screener** — filter all events by SUE/Piotroski/PB
3. Glossary at top of page explains the jargon (SUE, Piotroski, P/B, etc.)

**Manual re-run:**
```
python pead_build_history.py --start 2024-01-01 --end 2026-05-27
python pead_backtest.py --start 2024-06-01 --end 2026-05-27 --flavor both
```

---

## Daily routine (5 minutes)

1. After market closes (4 PM IST), double-click `refresh_data.bat`
2. Wait for it to finish (background, you can do other things)
3. Open http://localhost:8500 in browser
4. Check the **Suggestions** page — that combines all 4 strategies into 1 picks list
5. Check the **Master Hub home page** for any "next rebalance" alerts

---

## Weekly routine (15 minutes, Saturday morning)

1. Run `python nse_bse_downloader.py` — refreshes the wide stock universe for Momentum Edge (slow, ~20 min)
2. Re-run Momentum Edge backtest: `python momentum_edge_backtest.py`
3. Review the **History & Proof** page — see if strategies are still beating benchmarks

---

## Monthly routine (last Friday)

1. **Monthly Rotation rebalance day.** Check the dashboard's "Next Rebalance Date" — when it's today:
   - Sell anything that fell out of the top 5
   - Buy anything that newly entered the top 5
2. Update your broker positions to match the new top 5

---

## What do these numbers mean?

| Term | Plain meaning |
|---|---|
| **CAGR** | Average yearly return. CAGR +20% means ₹1 lakh becomes ~₹1.2 lakh per year, compounding |
| **Max DD** | Biggest dip during the test. -15% means at one point you'd have been down 15% — can you stomach that? |
| **Sharpe** | How much profit per unit of stress. >1 = good, >2 = excellent |
| **Win rate** | % of trades that made money. 50%+ is fine if winners > losers |
| **Alpha** | Extra return above just buying the index. +10% alpha = 10% better than Nifty |
| **SUE** | (PEAD only) How big the earnings surprise was. >+2 = big beat |
| **Piotroski** | (PEAD only) Balance-sheet health 0–9. 7+ = strong company |
| **P/B** | (PEAD only) Price compared to book value. Lower vs sector = cheaper |
| **Rebalance** | Sell old picks, buy new picks. Monthly Rotation does this on last Friday |
| **220 EMA** | (Momentum Edge) Long-term price trend line — like a moving floor |

---

## If something breaks

| Problem | Try this |
|---|---|
| Dashboard shows old data | Run `refresh_data.bat` again |
| "No data available" | Run the strategy's downloader (e.g. `python step1_download_data.py`) |
| Dashboards won't open | Run `python run_all.py --dash-only` |
| Port already in use error | Existing dashboards already running — just open http://localhost:8500 |
| PEAD page shows "no data" | Run `python pead_build_history.py --start 2024-01-01 --end 2026-05-27` |
| Slow data downloads | Already cached after first run — second runs are much faster (PEAD: 5 min → 40 sec) |

---

## Where the result files live

| File | What it contains |
|---|---|
| `live_rankings.csv` | Today's Monthly Rotation top 10 |
| `backtest_results.csv` | Monthly Rotation historical performance |
| `ipo_edge_trades.csv` | All IPO Edge trades, open + closed |
| `momentum_edge_trades.csv` | All Momentum Edge trades |
| `pead_trades.csv` | All PEAD trades |
| `pead_data/live_signals.csv` | Today's PEAD qualifying entries |
| `pead_kpis.csv` | PEAD performance metrics |
| `*_equity.csv` | Daily portfolio value over time (for charts) |

Open any of these in Excel or Google Sheets to look at the raw numbers.

---

## Quick reference — every command

```
# Daily (5 min)
refresh_data.bat

# Open dashboards
python run_all.py --dash-only

# Individual strategies
python step1_download_data.py + step2_backtest_momentum.py + step3_dashboard.py
python ipo_edge_downloader.py + ipo_edge_backtest.py
python momentum_edge_downloader.py + momentum_edge_backtest.py
python pead_downloader.py
python pead_backtest.py --start 2024-06-01 --end 2026-05-27 --flavor both

# Weekly (slow — wide stock universe)
python nse_bse_downloader.py

# Universe rebuild (rarely — when new IPOs added)
python build_universe.py
```

---

## A reminder

These strategies have been tested on past data. **Past performance is not a guarantee of future returns.** Indian markets can move differently than the test period suggests. Always:

1. Start with a small amount you can afford to lose
2. Follow the rules — don't override the system based on news/feelings
3. Track results in a spreadsheet so you know if the strategy is still working
4. Re-evaluate quarterly — if a strategy stops working for 6+ months, pause it

Good luck. The hard work is in following the rules, not in picking the rules.
