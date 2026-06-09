import type { ReactNode } from "react";

export function barWidthPct(value: number, maxValue: number): number {
  if (maxValue <= 0) return 0;
  return Math.max(0, Math.min(100, (value / maxValue) * 100));
}

export type Bar = {
  label: string;
  value: number;
  valueLabel?: string;
  highlight?: boolean;
};

interface HorizontalBarsProps {
  data: Bar[];
}

export function HorizontalBars({ data }: HorizontalBarsProps): ReactNode {
  if (!data?.length) return null;
  // Bars are scaled against the max value; negative values clamp to zero-width
  // (the numeric valueLabel still shows them). Current callers (funnel counts,
  // decile returns) are non-negative in practice.
  const max = Math.max(...data.map((d) => d.value), 0);
  return (
    <div className="flex flex-col gap-1.5">
      {data.map((d) => (
        <div key={d.label} className="flex items-center gap-2 text-xs">
          <span className="w-36 shrink-0 text-muted-foreground">{d.label}</span>
          <div className="relative h-5 flex-1 rounded bg-muted/30" aria-hidden>
            <div
              className={`h-full rounded ${d.highlight ? "bg-green-500" : "bg-sky-500/70"}`}
              style={{ width: `${barWidthPct(d.value, max)}%` }}
            />
          </div>
          <span className="w-24 shrink-0 text-right tabular-nums">
            {d.valueLabel ?? d.value}
          </span>
        </div>
      ))}
    </div>
  );
}
