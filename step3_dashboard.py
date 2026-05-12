"""
Live Momentum Rotation Screener - Nifty 50 vs NiftyBees benchmark
Batch-downloads prices in 3 API calls instead of 150+ individual calls.
"""

import sys
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')

# Force UTF-8 so emoji and box-drawing characters render on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ─── Universe ──────────────────────────────────────────────────────────────────
NIFTY_50 = {
    'ADANIENT.NS':   'Adani Enterprises',
    'ADANIGREEN.NS': 'Adani Green Energy',
    'ADANIPORTS.NS': 'Adani Ports',
    'APOLLOHOSP.NS': 'Apollo Hospitals',
    'ASIANPAINT.NS': 'Asian Paints',
    'AXISBANK.NS':   'Axis Bank',
    'BAJAJ-AUTO.NS': 'Bajaj Auto',
    'BAJFINANCE.NS': 'Bajaj Finance',
    'BAJAJFINSV.NS': 'Bajaj Finserv',
    'BPCL.NS':       'Bharat Petroleum',
    'BHARTIARTL.NS': 'Bharti Airtel',
    'BRITANNIA.NS':  'Britannia Industries',
    'CIPLA.NS':      'Cipla',
    'COALINDIA.NS':  'Coal India',
    'DIVISLAB.NS':   "Divi's Laboratories",
    'DRREDDY.NS':    "Dr. Reddy's Laboratories",
    'EICHERMOT.NS':  'Eicher Motors',
    'GRASIM.NS':     'Grasim Industries',
    'HCLTECH.NS':    'HCL Technologies',
    'HDFCBANK.NS':   'HDFC Bank',
    'HDFCLIFE.NS':   'HDFC Life Insurance',
    'HEROMOTOCO.NS': 'Hero MotoCorp',
    'HAL.NS':        'Hindustan Aeronautics',
    'HINDUNILVR.NS': 'Hindustan Unilever',
    'ICICIBANK.NS':  'ICICI Bank',
    'INDUSINDBK.NS': 'IndusInd Bank',
    'INFY.NS':       'Infosys',
    'ITC.NS':        'ITC',
    'JSWSTEEL.NS':   'JSW Steel',
    'KOTAKBANK.NS':  'Kotak Mahindra Bank',
    'LT.NS':         'Larsen & Toubro',
    'M&M.NS':        'Mahindra & Mahindra',
    'MARUTI.NS':     'Maruti Suzuki',
    'NESTLEIND.NS':  'Nestle India',
    'NTPC.NS':       'NTPC',
    'ONGC.NS':       'ONGC',
    'POWERGRID.NS':  'Power Grid Corporation',
    'RELIANCE.NS':   'Reliance Industries',
    'SBILIFE.NS':    'SBI Life Insurance',
    'SBIN.NS':       'State Bank of India',
    'SUNPHARMA.NS':  'Sun Pharmaceutical',
    'TATACONSUM.NS': 'Tata Consumer Products',
    'TMCV.NS':       'Tata Motors',
    'TATASTEEL.NS':  'Tata Steel',
    'TECH.NS':       'Tech Mahindra',
    'TITAN.NS':      'Titan Company',
    'ULTRACEMCO.NS': 'UltraTech Cement',
    'UPL.NS':        'UPL',
    'WIPRO.NS':      'Wipro',
    'ZEEL.NS':       'Zee Entertainment',
}

BENCHMARK         = 'NIFTYBEES.NS'
ALLOCATION        = 10_000   # ₹ per stock
TOP_N             = 5
W                 = 105      # display width


# ─── Helpers ───────────────────────────────────────────────────────────────────

def prev_month_end(ref=None):
    if ref is None:
        ref = datetime.now().date()
    return ref.replace(day=1) - timedelta(days=1)


def batch_close(tickers, start, end):
    """One yfinance call → DataFrame[ticker → Close price series]."""
    raw = yf.download(
        tickers,
        start=str(start),
        end=str(end + timedelta(days=1)),
        progress=False,
        auto_adjust=True,
    )
    if raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        return raw['Close']
    # flat columns (single ticker or older yfinance)
    if 'Close' in raw.columns:
        col = tickers[0] if isinstance(tickers, list) and len(tickers) == 1 else tickers
        return raw[['Close']].rename(columns={'Close': col})
    return pd.DataFrame()


def last_price_on_or_before(close_df, target_date):
    """Return last available row on or before target_date as a Series[ticker → price]."""
    ts = pd.Timestamp(target_date)
    mask = pd.to_datetime(close_df.index) <= ts
    sub = close_df.loc[mask]
    return sub.iloc[-1] if not sub.empty else pd.Series(dtype=float)


def pct(curr, prev):
    try:
        c, p = float(curr), float(prev)
        if p == 0 or pd.isna(c) or pd.isna(p):
            return None
        return (c - p) / p * 100
    except (TypeError, ValueError):
        return None


def signal_label(rs):
    if rs is None or pd.isna(rs):
        return 'NO DATA'
    if rs > 3:
        return '🟢 Strong BUY'
    if rs >= 1:
        return '🟡 Mild BUY'
    if rs >= 0:
        return '🟠 Weak'
    return '🔴 AVOID / SELL'


def next_rebalance():
    today = datetime.now().date()
    m, y = today.month, today.year
    if m == 12:
        first_next = today.replace(year=y + 1, month=1, day=1)
    else:
        first_next = today.replace(month=m + 1, day=1)
    last = first_next - timedelta(days=1)
    while last.weekday() >= 5:          # skip Saturday / Sunday
        last -= timedelta(days=1)
    return last


def sep(ch='─'):
    return ch * W


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    today = datetime.now().date()
    pme   = prev_month_end(today)       # previous month-end
    ppme  = prev_month_end(pme)         # two months ago end (HOLD detection)

    all_tickers = [BENCHMARK] + list(NIFTY_50.keys())

    print('\n' + sep('═'))
    print(' ' * 28 + 'MOMENTUM ROTATION LIVE SCREENER')
    print(sep('═'))
    print(f"  Run Date        : {datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}")
    print(f"  Prev Month End  : {pme}    (RS base date)")
    print(f"  2-Month-Ago End : {ppme}   (used for HOLD detection only)")
    print(sep('═'))

    # ── Batch downloads (3 calls total) ──────────────────────────────────────
    print('\n  [1/3] Fetching live current prices …')
    curr_df = batch_close(all_tickers, today - timedelta(days=7), today)

    print('  [2/3] Fetching previous month-end prices …')
    pme_df  = batch_close(all_tickers, pme  - timedelta(days=10), pme)

    print('  [3/3] Fetching two-month-ago prices (HOLD detection) …')
    ppme_df = batch_close(all_tickers, ppme - timedelta(days=10), ppme)

    if curr_df.empty or pme_df.empty:
        print('\n  ✗ ERROR: Could not fetch price data. Check internet connection.')
        return

    # ffill so today's incomplete session or holiday rows don't produce NaN
    curr_prices = curr_df.ffill().iloc[-1]
    pme_prices  = last_price_on_or_before(pme_df.ffill(),  pme)
    ppme_prices = last_price_on_or_before(ppme_df.ffill(), ppme)

    # ── Benchmark ─────────────────────────────────────────────────────────────
    b_curr = curr_prices.get(BENCHMARK)
    b_pme  = pme_prices.get(BENCHMARK)
    b_ppme = ppme_prices.get(BENCHMARK)

    b_return      = pct(b_curr, b_pme)
    b_prev_return = pct(b_pme,  b_ppme)

    if b_return is None:
        print('\n  ✗ ERROR: Cannot compute NiftyBees return. Aborting.')
        return

    print(f'\n  NiftyBees return this month : {b_return:+.2f}%')

    # ── HOLD detection: last month's top-5 ───────────────────────────────────
    prev_rs = {}
    for t in NIFTY_50:
        r = pct(pme_prices.get(t), ppme_prices.get(t))
        if r is not None and b_prev_return is not None:
            prev_rs[t] = r - b_prev_return

    last_month_top5 = set()
    if prev_rs:
        ranked_prev = sorted(prev_rs.items(), key=lambda x: x[1], reverse=True)
        last_month_top5 = {t for t, s in ranked_prev[:TOP_N] if s > 0}

    # ── Build current rankings ────────────────────────────────────────────────
    rows, failed = [], 0
    for ticker, company in NIFTY_50.items():
        cp = curr_prices.get(ticker)
        pp = pme_prices.get(ticker)
        ret = pct(cp, pp)
        if ret is None:
            failed += 1
            continue
        rows.append({
            'Ticker':              ticker,
            'Company':             company,
            'Current_Price':       float(cp),
            'Prev_Month_End_Price': float(pp),
            'Return_%':            ret,
            'Benchmark_Return_%':  b_return,
            'RS_Score':            ret - b_return,
        })

    if not rows:
        print('\n  ✗ No data rows — nothing to display.')
        return

    df = pd.DataFrame(rows).sort_values('RS_Score', ascending=False).reset_index(drop=True)
    df['Rank']   = df.index + 1
    df['Signal'] = df['RS_Score'].apply(signal_label)

    qualifiers = df[df['RS_Score'] > 0]
    avoided    = df[df['RS_Score'] < 0]

    # ════════════════════════════════════════════════════════════════════════════
    # DISPLAY
    # ════════════════════════════════════════════════════════════════════════════

    HDR = (f"  {'Rk':<4} {'Ticker':<14} {'Company':<32} {'Curr Price':>11} "
           f"{'Return%':>9} {'RS Score':>10}  Signal")

    def print_row(r):
        print(f"  {int(r['Rank']):<4} {r['Ticker']:<14} {r['Company']:<32} "
              f"₹{r['Current_Price']:>10,.2f} "
              f"{r['Return_%']:>+8.2f}% "
              f"{r['RS_Score']:>+9.2f}  {r['Signal']}")

    # ── Benchmark block ───────────────────────────────────────────────────────
    print('\n' + sep('═'))
    print('  BENCHMARK : NiftyBees ETF  (NIFTYBEES.NS)')
    print(sep())
    print(f"  Current Price              : ₹{b_curr:>10,.2f}")
    print(f"  Prev Month-End Price ({pme}): ₹{b_pme:>10,.2f}")
    print(f"  Benchmark Monthly Return   : {b_return:>+.2f}%")
    print()
    print(f"  ✅ Qualifying (RS > 0)     : {len(qualifiers):>3}  stocks")
    print(f"  ❌ Avoid      (RS < 0)     : {len(avoided):>3}  stocks")
    print(f"  ⚠️  No data               : {failed:>3}  tickers")
    print(f"  Total universe             : {len(NIFTY_50):>3}  stocks")

    # ── Top 10 qualifiers ─────────────────────────────────────────────────────
    top10 = qualifiers.head(10)
    print('\n' + sep('═'))
    print('  TOP 10 QUALIFYING STOCKS — by RS Score (Highest → Lowest)')
    print(sep())
    print(HDR)
    print(sep())
    for _, r in top10.iterrows():
        print_row(r)

    # ── Bottom 5 avoid ────────────────────────────────────────────────────────
    if not avoided.empty:
        bottom5 = avoided.sort_values('RS_Score').head(5)
        print('\n' + sep('═'))
        print('  BOTTOM 5 — STOCKS TO AVOID / EXIT  (RS < 0)')
        print(sep())
        print(HDR)
        print(sep())
        for _, r in bottom5.iterrows():
            print_row(r)

    # ── Top 5 picks with ₹10,000 allocation ──────────────────────────────────
    top5 = qualifiers.head(TOP_N)
    print('\n' + sep('═'))
    print(f'  CURRENT TOP {TOP_N} PICKS — ₹{ALLOCATION:,} ALLOCATION PER STOCK')
    print(sep())
    print(f"  {'Rk':<4} {'Ticker':<14} {'Company':<32} {'Curr Price':>11} "
          f"{'RS Score':>10}  {'Action':<22} {'Shares':>7}  {'Alloc':>10}")
    print(sep())
    for _, r in top5.iterrows():
        ticker  = r['Ticker']
        price   = r['Current_Price']
        shares  = int(ALLOCATION // price) if price > 0 else 0
        in_hold = ticker in last_month_top5
        action  = '🟢 HOLD' if in_hold else r['Signal']
        print(f"  {int(r['Rank']):<4} {ticker:<14} {r['Company']:<32} "
              f"₹{price:>10,.2f} "
              f"{r['RS_Score']:>+9.2f}  "
              f"{action:<22} {shares:>7}  ₹{ALLOCATION:>9,}")

    # ── Rebalance info ────────────────────────────────────────────────────────
    rebal     = next_rebalance()
    days_left = (rebal - today).days
    print('\n' + sep('═'))
    print('  REBALANCING INFO')
    print(sep())
    print(f"  Next Rebalance Date : {rebal}  ({rebal.strftime('%A')})  —  {days_left} days away")

    # ── Legend ────────────────────────────────────────────────────────────────
    print('\n' + sep('═'))
    print('  SIGNAL LEGEND')
    print(sep())
    print('  🟢 Strong BUY   RS > +3%           🟡 Mild BUY    RS +1% to +3%')
    print('  🟠 Weak         RS 0% to +1%        🔴 AVOID/SELL  RS < 0%')
    print(f'  🟢 HOLD         Was in Top {TOP_N} last month AND still qualifies today')
    print(sep('═'))

    # ── Save CSV ──────────────────────────────────────────────────────────────
    save_cols = ['Rank', 'Ticker', 'Company', 'Current_Price', 'Prev_Month_End_Price',
                 'Return_%', 'Benchmark_Return_%', 'RS_Score', 'Signal']
    df[save_cols].to_csv('live_rankings.csv', index=False)
    print(f'\n  ✓ Full rankings ({len(df)} stocks) saved to live_rankings.csv')
    print('  ✓ Dashboard generated successfully!\n')


if __name__ == '__main__':
    main()
