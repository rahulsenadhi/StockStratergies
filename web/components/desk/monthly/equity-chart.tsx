"use client";

import { useEffect, useRef } from "react";
import { BaselineSeries, createChart, LineSeries, LineStyle, type Time } from "lightweight-charts";
import { deskChartOptions, hexRgba, readCss, toSeriesData, useThemeName } from "@/components/desk/chart-kit";
import type { ChartTrace } from "@/lib/desk/monthly-text";

const HEIGHT = 270;
const FILL_ALPHA = 0.07;

/**
 * "Simulated account vs Nifty" (Python chart_equity): the saved % points of one window drawn as is.
 * Solid trace = area filled to 0% at 7%; dashed trace = dotted benchmark line; dashed 0% line.
 */
export function EquityChart({ traces }: { traces: ChartTrace[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const theme = useThemeName();

  useEffect(() => {
    const el = ref.current;
    if (!el || traces.length === 0) return;
    const muted = readCss("--rd-text-muted", "#77756E");
    const chart = createChart(el, deskChartOptions(HEIGHT, (p: number) => `${p.toFixed(0)}%`));
    traces.forEach((t, i) => {
      const data = toSeriesData<Time>(t.points);
      const series = t.dash
        ? chart.addSeries(LineSeries, {
          color: t.colour, lineWidth: 1, lineStyle: LineStyle.Dotted, priceLineVisible: false, lastValueVisible: false,
        })
        : chart.addSeries(BaselineSeries, {
          baseValue: { type: "price", price: 0 },
          topLineColor: t.colour, bottomLineColor: t.colour, lineWidth: 2,
          topFillColor1: hexRgba(t.colour, FILL_ALPHA), topFillColor2: hexRgba(t.colour, FILL_ALPHA),
          bottomFillColor1: hexRgba(t.colour, FILL_ALPHA), bottomFillColor2: hexRgba(t.colour, FILL_ALPHA),
          priceLineVisible: false, lastValueVisible: false,
        });
      series.setData(data);
      if (i === 0) {
        series.createPriceLine({ price: 0, color: muted, lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: false });
      }
    });
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [traces, theme]);

  return (
    <div>
      <div className="desk-legend" aria-hidden="true">
        {traces.map((t) => (
          <span key={t.name} className="rd-note"><span className="rd-dot" style={{ background: t.colour }} />{t.name}</span>
        ))}
      </div>
      <div ref={ref} style={{ width: "100%", height: HEIGHT }} role="img"
        aria-label={`${traces.map((t) => t.name).join(" vs ")}: change since the start of the window`} />
    </div>
  );
}
