"use client";

import { useEffect, useRef } from "react";
import { createChart, LineSeries, LineStyle, type Time } from "lightweight-charts";
import { deskChartOptions, readCss, toSeriesData, useThemeName } from "@/components/desk/chart-kit";
import { formatRupees } from "@/lib/desk/format";
import type { StockDetail } from "@/lib/desk/momentum-text";

const HEIGHT = 160;

/** Rail chart: saved close line, dotted 220-day average and the dashed level line with its label. */
export function RailChart({ chart, colour, label }: { chart: NonNullable<StockDetail["chart"]>; colour: string; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const theme = useThemeName();

  useEffect(() => {
    const el = ref.current;
    if (!el || chart.close.length === 0) return;
    const muted = readCss("--rd-text-muted", "#77756E");
    const api = createChart(el, deskChartOptions(HEIGHT, (p: number) => formatRupees(p, 0)));
    const close = api.addSeries(LineSeries, { color: colour, lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    close.setData(toSeriesData<Time>(chart.close));
    api.addSeries(LineSeries, {
      color: muted, lineWidth: 1, lineStyle: LineStyle.Dotted, priceLineVisible: false, lastValueVisible: false,
    }).setData(toSeriesData<Time>(chart.ema220));
    if (chart.level) {
      close.createPriceLine({
        price: chart.level.value, color: muted, lineStyle: LineStyle.Dashed, lineWidth: 1,
        axisLabelVisible: false, title: `${chart.level.label} ${formatRupees(chart.level.value, 0)}`,
      });
    }
    api.timeScale().fitContent();
    return () => api.remove();
  }, [chart, colour, theme]);

  return <div ref={ref} style={{ width: "100%", height: HEIGHT }} role="img" aria-label={label} />;
}
