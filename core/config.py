"""Shared defaults for the three strategies.

Pattern: strategy files keep their own CFG dict; they can import these defaults
and override what they need. No strategy file is forced to use these — they are
the single source of truth for *new* code (dashboards, analytics).

Usage:
    from core.config import MOMENTUM_EDGE_DEFAULTS, IPO_EDGE_DEFAULTS, NIFTY_50
    CFG = {**MOMENTUM_EDGE_DEFAULTS, 'initial_capital': 20_00_000}
"""

# ── Universe lists ───────────────────────────────────────────────────────────

NIFTY_50 = [
    'ADANIENT.NS', 'ADANIGREEN.NS', 'ADANIPORTS.NS', 'APOLLOHOSP.NS', 'ASIANPAINT.NS',
    'AXISBANK.NS', 'BAJAJ-AUTO.NS', 'BAJFINANCE.NS', 'BAJAJFINSV.NS', 'BPCL.NS',
    'BHARTIARTL.NS', 'BRITANNIA.NS', 'CIPLA.NS', 'COALINDIA.NS', 'DIVISLAB.NS',
    'DRREDDY.NS', 'EICHERMOT.NS', 'GRASIM.NS', 'HCLTECH.NS', 'HDFCBANK.NS',
    'HDFCLIFE.NS', 'HEROMOTOCO.NS', 'HAL.NS', 'HINDUNILVR.NS', 'ICICIBANK.NS',
    'INDUSINDBK.NS', 'INFY.NS', 'ITC.NS', 'JSWSTEEL.NS', 'KOTAKBANK.NS',
    'LT.NS', 'M&M.NS', 'MARUTI.NS', 'NESTLEIND.NS', 'NTPC.NS',
    'ONGC.NS', 'POWERGRID.NS', 'RELIANCE.NS', 'SBILIFE.NS', 'SBIN.NS',
    'SUNPHARMA.NS', 'TATACONSUM.NS', 'TMCV.NS', 'TATASTEEL.NS', 'TECH.NS',
    'TITAN.NS', 'ULTRACEMCO.NS', 'UPL.NS', 'WIPRO.NS', 'ZEEL.NS',
]

BENCHMARK_TICKER = '^NSEI'
NIFTYBEES_FALLBACK = 'NIFTYBEES.NS'


# ── Momentum Edge defaults ───────────────────────────────────────────────────

MOMENTUM_EDGE_DEFAULTS = {
    'backtest_universe':         'FULL_NSE_BSE',
    'data_folder_legacy':        'momentum_edge_data',
    'data_folder_full':          './data/nse_bse',
    'universe_file':             './data/universe/combined_universe.csv',

    'initial_capital':           10_00_000,
    'max_position_value':         1_00_000,
    'max_positions':             10,

    'use_regime_filter':         True,
    'benchmark_ticker':          BENCHMARK_TICKER,
    'benchmark_file_full':       './data/nse_bse/^NSEI.csv',
    'benchmark_file_legacy':     './data/^NSEI.csv',
    'regime_sma_fast':           50,
    'regime_sma_slow':           200,
    'regime_52w_period':         252,
    'regime_max_dd_from_high':   0.10,

    'sma50_period':              50,
    'sma150_period':             150,
    'ema220_period':             220,
    'high52w_period':            252,
    'low52w_period':             252,
    'vol_avg_period':            20,
    'ema_dip_lookback':          90,
    'choppiness_period':         14,
    'choppiness_threshold':      61.8,
    'momentum_period':           126,

    'min_price_vs_low':          1.25,
    'vol_filter':                True,
    'vol_threshold':             1.5,
    'vol_lookback_days':         50,
    'vol_multiplier':            1.5,

    'prefer_fast_recovery':      True,
    'max_recovery_days':         90,

    'stop_loss_pct':             0.15,

    'min_bars':                  252,
    'min_close_price':           50.0,
    'min_avg_volume':            100_000,

    'trades_out':                'momentum_edge_trades.csv',
    'equity_out':                'momentum_edge_equity.csv',
    'chart_out':                 'momentum_edge_chart.png',
}


# ── IPO Edge defaults ────────────────────────────────────────────────────────

IPO_EDGE_DEFAULTS = {
    'initial_capital':           5_00_000,
    'max_alloc_pct':             0.10,
    'max_positions':             10,

    'skip_initial_days':         3,
    'base_window':               40,
    'min_days_needed':           43,

    'vol_multiplier':            1.5,
    'ema_period':                10,
    'use_ema_filter':            True,

    'min_ipo_day_value_cr':      10,
    'promoter_quality_file':     'ipo_promoter_quality.csv',

    'hard_stop_pct':             0.08,
    'max_hold_days':             90,
    'cooldown_days':             15,
    'partial_booking':           True,
    'partial_target_pct':        0.15,

    'max_ipo_age_days':          252,

    'data_folder':               'ipo_data',
    'trades_out':                'ipo_edge_trades.csv',
    'equity_out':                'ipo_edge_equity.csv',
    'chart_out':                 'ipo_edge_chart.png',
    'benchmark':                 NIFTYBEES_FALLBACK,
}


# ── Nifty Rotation defaults ──────────────────────────────────────────────────

ROTATION_DEFAULTS = {
    'data_folder':               'data',
    'benchmark_ticker':          BENCHMARK_TICKER,
    'benchmark_fallback':        NIFTYBEES_FALLBACK,

    'lookback_months':           6,
    'momentum_period':           126,
    'top_n':                     5,
    'rebalance_freq':            'M',

    'initial_capital':           10_00_000,
    'equal_weight_pct':          0.20,

    'trades_out':                'backtest_results.csv',
    'rebalance_out':             'rebalance_log.csv',
    'rankings_out':              'live_rankings.csv',
}
