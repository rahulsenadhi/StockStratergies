export interface GlossaryEntry {
  label: string;
  explain: string;
}

export const GLOSSARY: Record<string, GlossaryEntry> = {
  // ── Indicators ───────────────────────────────────────────────────────────
  SMA50: {
    label: "50-day Simple Moving Average",
    explain: "Average closing price over the last 50 trading days. Tracks short-term trend.",
  },
  SMA150: {
    label: "150-day Simple Moving Average",
    explain: "Average closing price over 150 days. Tracks medium-term trend.",
  },
  SMA200: {
    label: "200-day Simple Moving Average",
    explain: "Average closing price over 200 days. The classic long-term trend line.",
  },
  EMA10: {
    label: "10-day Exponential Moving Average",
    explain: "Weighted average favoring recent prices. Used as a tight trailing stop on IPOs.",
  },
  EMA220: {
    label: "220-day Exponential Moving Average",
    explain: "Long-term exponential trend line. Stock dipping below and reclaiming it is the core Momentum Edge setup.",
  },
  ATR: {
    label: "Average True Range",
    explain: "Average daily price swing over N days. Measures volatility.",
  },
  Choppiness: {
    label: "Choppiness Index (14-day)",
    explain: "Scale from ~38 (clean trend) to ~100 (sideways noise). Above 61.8 = too choppy to enter.",
  },
  "52W_High": {
    label: "52-week High",
    explain: "Highest closing price in the last 252 trading days.",
  },
  ATH: {
    label: "All-Time High",
    explain: "Highest closing price ever recorded for the stock.",
  },
  Momentum_6M: {
    label: "6-month Momentum",
    explain: "Percent return over the last ~126 trading days. Used for ranking and rotation.",
  },
  RS: {
    label: "Relative Strength",
    explain: "(Stock return − benchmark return) ÷ benchmark volatility. Positive = beating the market.",
  },

  // ── Regime ───────────────────────────────────────────────────────────────
  Regime_Filter: {
    label: "Market Regime Filter",
    explain: "Three-condition gate on Nifty 50. When the gate is OFF, no new entries are taken (open positions still managed).",
  },
  Bull_Regime: {
    label: "Bull Regime",
    explain: "Nifty above its 200-day average, 50-day above 200-day, and within 10% of its 52-week high.",
  },
  Bear_Regime: {
    label: "Bear / Sideways Regime",
    explain: "At least one of the bull conditions has failed. New entries are blocked.",
  },

  // ── Entry/exit ───────────────────────────────────────────────────────────
  F1_to_F6: {
    label: "Entry Filters F1–F6",
    explain: "Six trend and quality gates. All six must pass before a stock is considered for entry.",
  },
  Base_Breakout: {
    label: "IPO Base Breakout",
    explain: "IPO consolidates for 4–43 days; entry triggers when price closes above the base on heavy volume.",
  },
  Partial_Booking: {
    label: "Partial Booking",
    explain: "Sell one-third of position at +15% gain, then move stop to entry price (lock in zero risk).",
  },
  Hard_Stop: {
    label: "Hard Stop Loss",
    explain: "Mechanical exit: 15% below entry (Momentum Edge) or 8% (IPO Edge). No discretion.",
  },
  Trailing_Stop: {
    label: "Trailing Stop",
    explain: "Stop that follows price up. IPO Edge uses EMA10 — exits when close drops below it.",
  },

  // ── Trade quality ────────────────────────────────────────────────────────
  Recovery_Speed: {
    label: "Recovery Speed",
    explain: "Days from dip-low back to EMA220. Fast ≤30d, Normal 31–60d, Slow 61–90d.",
  },
  Entry_Type: {
    label: "Entry Type",
    explain: "ATH = today's breakout is a new all-time high. 52W_HIGH_FALLBACK = breaks 52-week high but ATH is higher.",
  },
  Score: {
    label: "Setup Score",
    explain: "0–100 composite of trend strength, recovery speed, and breakout volume. Higher = stronger setup.",
  },
  MAE: {
    label: "Max Adverse Excursion",
    explain: "Deepest paper loss a trade went into before exiting. Tells you where to set stops.",
  },
  MFE: {
    label: "Max Favorable Excursion",
    explain: "Largest paper gain a trade reached before exiting. Tells you what you left on the table.",
  },

  // ── Performance ──────────────────────────────────────────────────────────
  CAGR: {
    label: "Compound Annual Growth Rate",
    explain: "Year-over-year return that, compounded, would produce the same final balance.",
  },
  Drawdown: {
    label: "Drawdown",
    explain: "Drop from a portfolio peak to a subsequent trough, expressed as a percent.",
  },
  Sharpe: {
    label: "Sharpe Ratio",
    explain: "Return per unit of volatility. >1 is decent, >2 is great. Risk-adjusted performance.",
  },
  Win_Rate: {
    label: "Win Rate",
    explain: "Percent of trades closed in profit. High win rate alone is meaningless without payoff size.",
  },
};

export function glossaryTerm(key: string): string {
  return GLOSSARY[key]?.explain ?? key;
}

export function glossaryLabel(key: string): string {
  return GLOSSARY[key]?.label ?? key;
}
