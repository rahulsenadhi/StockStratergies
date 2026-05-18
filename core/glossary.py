"""Centralized glossary.

One dict of `term → (short_label, plain_english_explanation)` consumed by all
dashboards. Plain English per user preference (memory: feedback_ux_style.md).

Usage in Streamlit:
    from core.glossary import tooltip, term
    st.markdown(tooltip('EMA220'), unsafe_allow_html=True)
    st.help(term('Choppiness'))

Usage in Plotly hovertext:
    fig.update_traces(hovertemplate=f"%{{y}}<br>{term('SMA50')}")
"""

TERMS: dict[str, tuple[str, str]] = {
    # ── Indicators ───────────────────────────────────────────────────────────
    'SMA50': (
        '50-day Simple Moving Average',
        'Average closing price over the last 50 trading days. Tracks short-term trend.',
    ),
    'SMA150': (
        '150-day Simple Moving Average',
        'Average closing price over 150 days. Tracks medium-term trend.',
    ),
    'SMA200': (
        '200-day Simple Moving Average',
        'Average closing price over 200 days. The classic long-term trend line.',
    ),
    'EMA10': (
        '10-day Exponential Moving Average',
        'Weighted average favoring recent prices. Used as a tight trailing stop on IPOs.',
    ),
    'EMA220': (
        '220-day Exponential Moving Average',
        'Long-term exponential trend line. Stock dipping below and reclaiming it is the core Momentum Edge setup.',
    ),
    'ATR': (
        'Average True Range',
        'Average daily price swing over N days. Measures volatility.',
    ),
    'Choppiness': (
        'Choppiness Index (14-day)',
        'Scale from ~38 (clean trend) to ~100 (sideways noise). Above 61.8 = too choppy to enter.',
    ),
    '52W_High': (
        '52-week High',
        'Highest closing price in the last 252 trading days.',
    ),
    'ATH': (
        'All-Time High',
        'Highest closing price ever recorded for the stock.',
    ),
    'Momentum_6M': (
        '6-month Momentum',
        'Percent return over the last ~126 trading days. Used for ranking and rotation.',
    ),
    'RS': (
        'Relative Strength',
        '(Stock return − benchmark return) ÷ benchmark volatility. Positive = beating the market.',
    ),

    # ── Regime ───────────────────────────────────────────────────────────────
    'Regime_Filter': (
        'Market Regime Filter',
        'Three-condition gate on Nifty 50. When the gate is OFF, no new entries are taken (open positions still managed).',
    ),
    'Bull_Regime': (
        'Bull Regime',
        'Nifty above its 200-day average, 50-day above 200-day, and within 10% of its 52-week high.',
    ),
    'Bear_Regime': (
        'Bear / Sideways Regime',
        'At least one of the bull conditions has failed. New entries are blocked.',
    ),

    # ── Entry/exit ───────────────────────────────────────────────────────────
    'F1_to_F6': (
        'Entry Filters F1–F6',
        'Six trend and quality gates. All six must pass before a stock is considered for entry.',
    ),
    'Base_Breakout': (
        'IPO Base Breakout',
        'IPO consolidates for 4–43 days; entry triggers when price closes above the base on heavy volume.',
    ),
    'Partial_Booking': (
        'Partial Booking',
        'Sell one-third of position at +15% gain, then move stop to entry price (lock in zero risk).',
    ),
    'Hard_Stop': (
        'Hard Stop Loss',
        'Mechanical exit: 15% below entry (Momentum Edge) or 8% (IPO Edge). No discretion.',
    ),
    'Trailing_Stop': (
        'Trailing Stop',
        'Stop that follows price up. IPO Edge uses EMA10 — exits when close drops below it.',
    ),

    # ── Trade quality ────────────────────────────────────────────────────────
    'Recovery_Speed': (
        'Recovery Speed',
        'Days from dip-low back to EMA220. Fast ≤30d, Normal 31–60d, Slow 61–90d.',
    ),
    'Entry_Type': (
        'Entry Type',
        'ATH = today\'s breakout is a new all-time high. 52W_HIGH_FALLBACK = breaks 52-week high but ATH is higher.',
    ),
    'Score': (
        'Setup Score',
        '0–100 composite of trend strength, recovery speed, and breakout volume. Higher = stronger setup.',
    ),
    'MAE': (
        'Max Adverse Excursion',
        'Deepest paper loss a trade went into before exiting. Tells you where to set stops.',
    ),
    'MFE': (
        'Max Favorable Excursion',
        'Largest paper gain a trade reached before exiting. Tells you what you left on the table.',
    ),

    # ── Performance ──────────────────────────────────────────────────────────
    'CAGR': (
        'Compound Annual Growth Rate',
        'Year-over-year return that, compounded, would produce the same final balance.',
    ),
    'Drawdown': (
        'Drawdown',
        'Drop from a portfolio peak to a subsequent trough, expressed as a percent.',
    ),
    'Sharpe': (
        'Sharpe Ratio',
        'Return per unit of volatility. >1 is decent, >2 is great. Risk-adjusted performance.',
    ),
    'Win_Rate': (
        'Win Rate',
        'Percent of trades closed in profit. High win rate alone is meaningless without payoff size.',
    ),
}


def term(key: str) -> str:
    """Return plain-English explanation. Returns the key itself if unknown."""
    entry = TERMS.get(key)
    return entry[1] if entry else key


def label(key: str) -> str:
    """Return the formal full name of a term."""
    entry = TERMS.get(key)
    return entry[0] if entry else key


def tooltip(key: str) -> str:
    """HTML span with hover title. Wrap inline anywhere with unsafe_allow_html=True."""
    entry = TERMS.get(key)
    if not entry:
        return key
    full, explain = entry
    safe = explain.replace('"', '&quot;')
    return (
        f'<span title="{safe}" '
        f'style="text-decoration:underline dotted;cursor:help;">{full}</span>'
    )


def render_sidebar(st_module) -> None:
    """Render an expandable glossary panel in Streamlit's sidebar.

    Pass the streamlit module as argument so this file doesn't import streamlit
    at module load (keeps backtest scripts lightweight).
    """
    with st_module.sidebar.expander('📖 Glossary', expanded=False):
        for key, (full, explain) in sorted(TERMS.items()):
            st_module.markdown(f'**{full}** — {explain}')
