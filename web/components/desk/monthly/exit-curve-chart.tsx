"use client";

import { useEffect, useRef } from "react";
import { createChart, LineSeries, LineStyle, type Time, type UTCTimestamp } from "lightweight-charts";
import { deskChartOptions, toSeriesData, useThemeName } from "@/components/desk/chart-kit";

const HEIGHT = 260;
const AXIS_HEIGHT = 28;
const HOLD_COLOUR = "#7c9cff";
/** Trace names, styles and axis titles of master_dashboard._exit_playbook_card (plotly_dark colourway). */
const TRACES = [
  { key: "median", name: "Median return %", colour: "#636efa", style: LineStyle.Solid },
  { key: "p25", name: "p25", colour: "#EF553B", style: LineStyle.Dotted },
  { key: "p75", name: "p75", colour: "#00cc96", style: LineStyle.Dotted },
] as const;
const X_TITLE = "Days held";
const Y_TITLE = "Return %";

type CurveRow = Record<string, number | null>;

/** Return-by-day curve: saved median/p25/p75 per day held, with a dashed marker at the exploratory hold. */
export function ExitCurveChart({ curve, holdDays }: { curve: CurveRow[]; holdDays: number | null }) {
  const ref = useRef<HTMLDivElement>(null);
  const markerRef = useRef<HTMLDivElement>(null);
  const theme = useThemeName();

  useEffect(() => {
    const el = ref.current;
    const marker = markerRef.current;
    if (!el || !marker) return;
    const days = curve.filter((c) => c.day != null);
    const base = deskChartOptions(HEIGHT, (p: number) => p.toFixed(1));
    // Days held are plain numbers on the time axis, shown as numbers rather than dates.
    const asDay = (t: Time) => String(t);
    const chart = createChart(el, {
      ...base,
      localization: { ...base.localization, timeFormatter: asDay },
      timeScale: { ...base.timeScale, tickMarkFormatter: asDay },
    });
    for (const t of TRACES) {
      const s = chart.addSeries(LineSeries, {
        color: t.colour, lineWidth: 2, lineStyle: t.style, priceLineVisible: false, lastValueVisible: false,
      });
      s.setData(toSeriesData<Time>(days.map((c) => [c.day as UTCTimestamp, c[t.key] ?? null])));
    }
    const place = () => {
      const x = holdDays == null ? null : chart.timeScale().timeToCoordinate(holdDays as UTCTimestamp);
      marker.style.display = x == null ? "none" : "block";
      if (x != null) marker.style.left = `${x}px`;
    };
    chart.timeScale().fitContent();
    chart.timeScale().subscribeSizeChange(place);
    chart.timeScale().subscribeVisibleLogicalRangeChange(place);
    place();
    return () => chart.remove();
  }, [curve, holdDays, theme]);

  return (
    <div>
      <div className="desk-legend" aria-hidden="true">
        {TRACES.map((t) => (
          <span key={t.key} className="rd-note"><span className="rd-dot" style={{ background: t.colour }} />{t.name}</span>
        ))}
        <span className="rd-note" style={{ marginLeft: "auto" }}>{Y_TITLE} · {X_TITLE}</span>
      </div>
      <div style={{ position: "relative" }}>
        <div ref={ref} style={{ width: "100%", height: HEIGHT }} role="img"
          aria-label={`${Y_TITLE} by ${X_TITLE.toLowerCase()}: median, p25 and p75${holdDays == null ? "" : `, marker at ${holdDays} days`}`} />
        <div ref={markerRef} aria-hidden="true" style={{
          position: "absolute", top: 0, bottom: AXIS_HEIGHT, width: 0, display: "none", pointerEvents: "none",
          borderLeft: `1px dashed ${HOLD_COLOUR}`,
        }} />
      </div>
    </div>
  );
}
