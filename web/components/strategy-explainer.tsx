interface Explain {
  how: string;
  risk?: string;
}

const EXPLAINERS: Record<string, Explain> = {
  monthly_rotation: {
    how: "Every month, we rank all 50 Nifty stocks by their recent price strength (RS Score). We buy the top 5 and hold them for the month. If a stock falls out of the top 5, we sell it and replace it with the new entrant. Simple, systematic, no guessing.",
  },
  ipo_edge: {
    how: "When a stock lists on NSE, it often trades sideways for ~40 days (the \"base\"). Once it breaks above that base with strong volume, we enter. We exit when it drops below its 10-day average or hits a hard stop. A partial profit is booked at +15% gain.",
  },
  momentum_edge: {
    how: "We look for strong NSE stocks that recently dipped below their long-term average (220-day line), then bounced back up — showing the dip was temporary, not a collapse. We only buy when the stock is also breaking to an all-time high (ATH), meaning buyers are fully in control. Hold strategy: sit tight until ONE of these fires — (1) price falls 15% from entry (hard stop), (2) close drops below the 220-day EMA, OR (3) price hits a profit target. No emotional exits.",
  },
  pead: {
    how: "Post-Earnings-Announcement Drift (PEAD) — we rank stocks by SUE (Standardised Unexpected Earnings), how many standard deviations the latest EPS beat the last 4 same-period results. We go long only the top decile (biggest positive surprises) that also pass a Piotroski F-Score filter (≥7, strong balance sheet) and trade below their sector P/B median. Hold is ~60 days to capture the drift after the earnings release.",
    risk: "Earnings surprises are backward-looking. Future results may not repeat, and thin-coverage stocks can have noisy SUE estimates. Position sizes should be kept small until a live track record builds.",
  },
};

export function StrategyExplainer({ id }: { id: string }) {
  const e = EXPLAINERS[id];
  if (!e) return null;
  return (
    <div className="space-y-2 text-sm">
      <div className="rounded border border-border bg-muted/40 p-3">
        <p className="mb-1 font-medium">How it works</p>
        <p className="text-muted-foreground">{e.how}</p>
      </div>
      {e.risk && <p className="text-xs text-muted-foreground">{e.risk}</p>}
    </div>
  );
}
