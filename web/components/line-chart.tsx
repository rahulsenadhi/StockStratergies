"use client";

import { useEffect, useRef } from "react";
import { createChart, AreaSeries, ColorType } from "lightweight-charts";

export type Point = { time: string; value: number };

export function LineChart({
  data,
  color = "#22c55e",
  height = 280,
}: {
  data: Point[];
  color?: string;
  height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || data.length === 0) return;
    const chart = createChart(el, {
      height,
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8b93a1",
      },
      grid: {
        vertLines: { color: "#20242c" },
        horzLines: { color: "#20242c" },
      },
      rightPriceScale: { borderColor: "#20242c" },
      timeScale: { borderColor: "#20242c" },
    });
    // v5 API: addSeries(SeriesDefinition, options)
    const series = chart.addSeries(AreaSeries, {
      lineColor: color,
      topColor: `${color}55`,
      bottomColor: `${color}08`,
      lineWidth: 2,
    });
    series.setData(data);
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [data, color, height]);

  if (!data || data.length === 0) {
    return (
      <div className="flex h-[280px] items-center justify-center rounded border border-border text-sm text-muted-foreground">
        No data
      </div>
    );
  }
  return <div ref={ref} className="w-full" />;
}
