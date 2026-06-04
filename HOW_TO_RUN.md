# How to Run the 4 Strategies — Simple Manual

You have 4 strategies. Each one has 2 steps: **(1) Download fresh data**, then **(2) Run the backtest**. After both, you open the dashboard in your browser to see results.

Always open a terminal (PowerShell) inside the project folder first:

```
cd "c:\Users\User\Documents\Stocks\Nifty Momentum Rotation Stratergy"
```

---

## Strategy 1 — Nifty 50 Monthly Rotation

**What it does:** Picks top 5 Nifty 50 stocks each month based on momentum vs NiftyBees.

**Run these 2 commands one after the other:**

```
python step1_download_data.py
python step2_backtest_momentum.py
```

**Then open dashboard:**

```
python -m streamlit run dashboard_visual.py --server.port 8501 --server.headless true
```

Open browser: **http://localhost:8501**

Takes about: 2 minutes total.

---

## Strategy 2 — Momentum Edge

**What it does:** Scans ALL NSE + BSE stocks (2,600+) for breakout setups using 6 filters.

**Run these 3 commands one after the other:**

```
python build_universe.py
python nse_bse_downloader.py
python momentum_edge_backtest.py
python precompute_momentum_signals.py
```

> `precompute_momentum_signals.py` writes the live signals + recent breakouts to
> disk so the dashboard loads them in ~0.1s instead of recomputing for ~52s on
> every page open. Run it after the backtest whenever the data is refreshed.

**Then open dashboard:**

```
python -m streamlit run momentum_edge_dashboard.py --server.port 8503 --server.headless true
```

Open browser: **http://localhost:8503**

Takes about: 10–15 minutes total (mostly the downloader).

**Note:** If you see "0 signals" — that's because Nifty is in BEAR market regime. Strategy correctly waits for bull market.

---

## Strategy 3 — IPO Edge

**What it does:** Tracks recent IPOs (listed within 12 months) and looks for breakout entries.

**Run these 2 commands one after the other:**

```
python ipo_edge_downloader.py
python ipo_edge_backtest.py
```

**Then open dashboard:**

```
python -m streamlit run ipo_edge_dashboard.py --server.port 8502 --server.headless true
```

Open browser: **http://localhost:8502**

Takes about: 5 minutes total.

---

## Strategy 4 — PEAD (Post-Earnings Announcement Drift)

**What it does:** Catches stocks that beat earnings expectations (SUE in top decile) + strong fundamentals (Piotroski ≥ 7) + cheap valuation (P/B ≤ sector median). Holds 60 trading days or until next earnings.

**First time only — build historical events database:**

```
python pead_build_history.py --start 2022-01-01 --end 2026-05-26
```

**Daily refresh + backtest (run these any time you want fresh signals):**

```
python pead_downloader.py
python pead_backtest.py --start 2022-01-01 --end 2026-05-26
```

**Then open dashboard:**

```
python -m streamlit run pead_dashboard.py --server.port 8504 --server.headless true
```

Open browser: **http://localhost:8504**

Takes about:
- First-time history build: 20–30 min (downloads earnings + fundamentals for full universe)
- Daily refresh + backtest: 3–5 min

**Note:** PEAD only fires signals on days when companies report quarterly or annual results. On non-reporting days you'll see 0 new signals — normal.

---

## See All 4 Together (Master Dashboard)

After running all the data + backtest steps above for the strategies you want, launch the combined dashboard:

```
python -m streamlit run master_dashboard.py --server.port 8500 --server.headless true
```

Open browser: **http://localhost:8500**

---

## Quick "Run Everything" — Copy-Paste Block

If you want to refresh ALL 4 strategies in one go, paste this whole block:

```
cd "c:\Users\User\Documents\Stocks\Nifty Momentum Rotation Stratergy"
python step1_download_data.py
python step2_backtest_momentum.py
python build_universe.py
python nse_bse_downloader.py
python momentum_edge_backtest.py
python precompute_momentum_signals.py
python ipo_edge_downloader.py
python ipo_edge_backtest.py
python pead_downloader.py
python pead_backtest.py --start 2022-01-01 --end 2026-05-26
python -m streamlit run master_dashboard.py --server.port 8500 --server.headless true
```

Then open **http://localhost:8500**

Total time: ~25 minutes (mostly Momentum Edge downloader).

**Note:** This assumes PEAD history is already built. If it's your first time, run this once before the block above:

```
python pead_build_history.py --start 2022-01-01 --end 2026-05-26
```

---

## Stop a Dashboard

Press `Ctrl + C` in the terminal where it's running.

If port is stuck:

```
Get-Process | Where-Object {$_.ProcessName -eq "python"} | Stop-Process -Force
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "ModuleNotFoundError" | Run: `pip install pandas numpy yfinance streamlit matplotlib requests tqdm` |
| "ERR_CONNECTION_REFUSED" in browser | Dashboard not running — start it again with the streamlit command |
| All symbols failing in downloader | Check internet. Yahoo Finance sometimes rate-limits; wait 5 min and retry |
| Dashboard shows old data | Re-run the backtest command for that strategy, then reload browser page |
| Port already in use | Change `--server.port 8501` to a different number like `8504` |

---

## Which Strategy to Use When?

- **Bull market + want simple Nifty 50 exposure** → Strategy 1
- **Want to scan whole market for breakouts** → Strategy 2 (only fires in bull market)
- **Want to ride recent IPO momentum** → Strategy 3
- **Want fundamentals-driven earnings plays** → Strategy 4 (works in any regime, fires on results days)

Check the **market regime** shown at the top of Momentum Edge dashboard — if it says BEAR, don't expect new signals from Strategy 2. PEAD (Strategy 4) is regime-independent — it triggers off company earnings, not market trend.
