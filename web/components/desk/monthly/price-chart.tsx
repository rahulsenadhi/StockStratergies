"use client";

import { useEffect, useRef } from "react";
import { createChart, LineSeries, type Time } from "lightweight-charts";
import { deskChartOptions, toSeriesData, useThemeName } from "@/components/desk/monthly/chart-kit";
import { formatRupees } from "@/lib/desk/format";

const HEIGHT = 180;

/** Detail-rail closing price chart (Python _render_monthly_detail): saved closes drawn as is. */
export function PriceChart({ points, colour, label }: { points: [string, number][]; colour: string; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const theme = useThemeName();

  useEffect(() => {
    const el = ref.current;
    if (!el || points.length === 0) return;
    const chart = createChart(el, deskChartOptions(HEIGHT, (p: number) => formatRupees(p, 2)));
    const series = chart.addSeries(LineSeries, { color: colour, lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    series.setData(toSeriesData<Time>(points));
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [points, colour, theme]);

  return <div ref={ref} style={{ width: "100%", height: HEIGHT }} role="img" aria-label={label} />;
}
