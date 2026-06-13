/** Risk-based position sizing. Faithful port of master_dashboard.py's
 *  Interactive Position Sizer (~L7183-7193): pick a portfolio risk %, get the
 *  exact share count so a stop-out loses exactly that amount. */

export interface SizingInputs {
  /** Portfolio capital in ₹. */
  capital: number;
  /** Risk per trade as a % of capital (e.g. 2 = 2%). */
  riskPct: number;
  /** Planned entry price in ₹. */
  entry: number;
  /** Stop-loss distance as a % below entry (e.g. 10 = -10%). */
  stopPct: number;
}

export interface SizingResult {
  stopPrice: number;
  riskPerShare: number;
  riskBudget: number;
  shares: number;
  positionSize: number;
  positionPct: number;
  maxLoss: number;
  target2R: number;
  target3R: number;
}

export function computePositionSizing({
  capital,
  riskPct,
  entry,
  stopPct,
}: SizingInputs): SizingResult {
  const stopPrice = entry * (1 - stopPct / 100);
  const riskPerShare = entry - stopPrice;
  const riskBudget = (capital * riskPct) / 100;
  const shares = riskPerShare > 0 ? Math.floor(riskBudget / riskPerShare) : 0;
  const positionSize = shares * entry;
  const positionPct = capital > 0 ? (positionSize / capital) * 100 : 0;
  const maxLoss = shares * riskPerShare;
  const target2R = entry * (1 + (2 * stopPct) / 100);
  const target3R = entry * (1 + (3 * stopPct) / 100);
  return {
    stopPrice,
    riskPerShare,
    riskBudget,
    shares,
    positionSize,
    positionPct,
    maxLoss,
    target2R,
    target3R,
  };
}
