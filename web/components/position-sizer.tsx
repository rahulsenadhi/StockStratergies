"use client";

import { useMemo, useState } from "react";
import { computePositionSizing } from "@/lib/position-sizing";
import { cn } from "@/lib/utils";

const fmtRs = (v: number, decimals = 0): string =>
  `₹${v.toLocaleString("en-IN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;

const field = "rounded-md border px-3 py-1.5 text-sm w-full font-mono tabular-nums";
const STAT_LABEL = "text-[10px] uppercase tracking-wide text-muted-foreground";
const STAT_VALUE = "text-lg font-bold font-mono tabular-nums";

function NumberField({
  label,
  value,
  onChange,
  step,
  min,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
  min?: number;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <input
        type="number"
        className={field}
        value={Number.isFinite(value) ? value : ""}
        step={step}
        min={min}
        onChange={(e) => onChange(parseFloat(e.target.value))}
      />
    </label>
  );
}

function ResultTile({
  label,
  value,
  sub,
  valueClass,
}: {
  label: string;
  value: string;
  sub: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-md border border-border bg-muted/20 px-3 py-2.5">
      <div className={STAT_LABEL}>{label}</div>
      <div className={cn(STAT_VALUE, valueClass)}>{value}</div>
      <div className="mt-0.5 text-[10px] text-muted-foreground">{sub}</div>
    </div>
  );
}

/** Risk-based position sizer. defaultStopPct seeds the stop input (from the
 *  strategy's exit recommendation when available). Fully client-side. */
export function PositionSizer({ defaultStopPct = 10 }: { defaultStopPct?: number }) {
  const [capital, setCapital] = useState(500_000);
  const [riskPct, setRiskPct] = useState(2);
  const [entry, setEntry] = useState(1000);
  const [stopPct, setStopPct] = useState(Math.abs(defaultStopPct) || 10);

  const safe = (v: number, fallback = 0): number => (Number.isFinite(v) ? v : fallback);
  const r = useMemo(
    () =>
      computePositionSizing({
        capital: safe(capital),
        riskPct: safe(riskPct),
        entry: safe(entry),
        stopPct: safe(stopPct),
      }),
    [capital, riskPct, entry, stopPct],
  );

  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold">Position Sizer — buy size that limits loss</h3>
        <p className="text-xs text-muted-foreground">
          Risk-based sizing: pick the % of your portfolio you are willing to lose if the stop
          hits — we compute the max shares so a stop-out loses exactly that. Rule of thumb:
          1–2% risk per trade.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <NumberField label="Portfolio capital (₹)" value={capital} onChange={setCapital} step={10_000} min={0} />
        <NumberField label="Risk per trade (%)" value={riskPct} onChange={setRiskPct} step={0.1} min={0} />
        <NumberField label="Planned entry (₹)" value={entry} onChange={setEntry} step={10} min={0} />
        <NumberField label="Stop-loss %" value={stopPct} onChange={setStopPct} step={0.5} min={0} />
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <ResultTile
          label="Buy Quantity"
          value={r.shares.toLocaleString("en-IN")}
          sub={`${fmtRs(r.positionSize)} deployed (${r.positionPct.toFixed(1)}% of capital)`}
          valueClass="text-green-500"
        />
        <ResultTile
          label="Stop Price"
          value={fmtRs(r.stopPrice, 2)}
          sub={`risk/share ${fmtRs(r.riskPerShare, 2)}`}
          valueClass="text-red-500"
        />
        <ResultTile
          label="Max Loss if Stop Hit"
          value={fmtRs(r.maxLoss)}
          sub={`= ${safe(riskPct).toFixed(1)}% of portfolio`}
          valueClass="text-red-500"
        />
        <ResultTile
          label="Target 2:1 / 3:1"
          value={fmtRs(r.target2R, 2)}
          sub={`3:1 target ${fmtRs(r.target3R, 2)}`}
          valueClass="text-green-500"
        />
      </div>

      <p className="text-xs leading-relaxed text-muted-foreground">
        📋 Trade plan: buy {r.shares.toLocaleString("en-IN")} shares at {fmtRs(safe(entry), 2)},
        place stop at {fmtRs(r.stopPrice, 2)} (−{safe(stopPct).toFixed(1)}%), book partial
        profit at {fmtRs(r.target2R, 2)} (+{(safe(stopPct) * 2).toFixed(1)}%). If the stop hits
        you lose {fmtRs(r.maxLoss)} = {safe(riskPct).toFixed(1)}% of your {fmtRs(safe(capital))}{" "}
        capital.
      </p>
    </section>
  );
}
