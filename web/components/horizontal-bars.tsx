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

export function HorizontalBars({ data }: { data: Bar[] }) {
  if (data.length === 0) return null;
  const max = Math.max(...data.map((d) => d.value), 0);
  return (
    <div className="flex flex-col gap-1.5">
      {data.map((d, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <span className="w-36 shrink-0 text-muted-foreground">{d.label}</span>
          <div className="relative h-5 flex-1 rounded bg-muted/30">
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
