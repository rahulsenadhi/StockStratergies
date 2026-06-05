"use client";

import { useEffect, useRef } from "react";
import { createChart, LineSeries, ColorType } from "lightweight-charts";
import type { EquityPoint } from "@/lib/data/strategies";

export type Series = { name: string; color: string; points: EquityPoint[] };

export function MultiLineChart({ series, height = 320 }: { series: Series[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || series.length === 0) return;
    const chart = createChart(el, {
      height,
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#8b93a1" },
      grid: { vertLines: { color: "#20242c" }, horzLines: { color: "#20242c" } },
      rightPriceScale: { borderColor: "#20242c" },
      timeScale: { borderColor: "#20242c" },
    });
    for (const s of series) {
      const line = chart.addSeries(LineSeries, { color: s.color, lineWidth: 2 });
      line.setData(s.points);
    }
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [series, height]);

  if (!series || series.length === 0) {
    return (
      <div className="flex h-[320px] items-center justify-center rounded border border-border text-sm text-muted-foreground">
        No equity data
      </div>
    );
  }
  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-3 text-xs">
        {series.map((s) => (
          <span key={s.name} className="flex items-center gap-1">
            <span className="inline-block h-2 w-3 rounded" style={{ background: s.color }} />
            {s.name}
          </span>
        ))}
      </div>
      <div ref={ref} className="w-full" />
    </div>
  );
}
