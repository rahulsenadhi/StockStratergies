"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries, HistogramSeries, LineSeries, LineStyle, createChart, createSeriesMarkers,
  type ISeriesApi, type SeriesType, type Time,
} from "lightweight-charts";
import { deskChartOptions, readCss, useThemeName } from "@/components/desk/chart-kit";
import { abbreviateIndian, priceAxisText } from "@/lib/desk/format";
import { EmptyState } from "@/components/desk/primitives";
import { Segmented } from "@/components/desk/segmented";
import {
  CHART_EMPTY, CHART_ERROR, DEFAULT_PERIOD, PERIODS, mapChart,
  type ChartPlan, type ChartToggles, type MomentumChartFile, type Period, type SeriesSpec, type ToggleKey,
} from "@/lib/desk/momentum-chart-map";

const PRICE_PANE_HEIGHT = 340;
const SUB_PANE_HEIGHT = 120;
/** The saved RSI line is near-white (made for the dark Streamlit chart); on light it is drawn in the text colour. */
const NEAR_WHITE = "#F8FAFC";
const TOGGLES: { key: ToggleKey; label: string }[] = [
  { key: "bb", label: "Bollinger" }, { key: "rsi", label: "RSI(14)" },
  { key: "macd", label: "MACD" }, { key: "vol", label: "Volume + OBV" },
];
const ALL_ON: ChartToggles = { bb: true, rsi: true, macd: true, vol: true };

export type ChartState =
  | { status: "loading" }
  | { status: "ready"; chart: MomentumChartFile }
  | { status: "empty"; reason: string | null }
  | { status: "error" };

const DASH: Record<string, LineStyle> = { solid: LineStyle.Solid, dot: LineStyle.Dotted, dash: LineStyle.Dashed };

/** Volume/OBV and other lower panes: large values in K, L, Cr instead of raw digits. */
const SUB_PANE_FORMAT = { type: "custom", formatter: abbreviateIndian, minMove: 0.01 } as const;

const chartHeight = (plan: ChartPlan) => PRICE_PANE_HEIGHT + (plan.paneCount - 1) * SUB_PANE_HEIGHT;

function addSeries(chart: ReturnType<typeof createChart>, s: SeriesSpec, text: string): ISeriesApi<SeriesType> {
  const common = { priceLineVisible: false, lastValueVisible: false };
  if (s.kind === "candles") {
    return chart.addSeries(CandlestickSeries, {
      upColor: s.colour, borderUpColor: s.colour, wickUpColor: s.colour,
      downColor: s.colourDown, borderDownColor: s.colourDown, wickDownColor: s.colourDown, ...common,
    }, s.pane);
  }
  if (s.kind === "hist") {
    return chart.addSeries(HistogramSeries, { ...common, priceFormat: SUB_PANE_FORMAT, base: 0 }, s.pane);
  }
  const color = s.colour.toUpperCase() === NEAR_WHITE.toUpperCase() ? text : s.colour;
  return chart.addSeries(LineSeries, {
    ...common, color, lineWidth: 1, ...(s.pane > 0 ? { priceFormat: SUB_PANE_FORMAT } : {}), lineStyle: DASH[s.dash] ?? LineStyle.Solid, crosshairMarkerVisible: false,
  }, s.pane);
}

/** Draw a plan on a new chart; the caller removes the chart. */
function draw(el: HTMLElement, plan: ChartPlan): ReturnType<typeof createChart> {
  const height = chartHeight(plan);
  const base = deskChartOptions(height, priceAxisText);
  const chart = createChart(el, { ...base, height, handleScroll: false, handleScale: false });
  const text = readCss("--rd-text", "#1D1D1B");
  const apis = plan.series.map((s) => {
    const api = addSeries(chart, s, text);
    api.setData(s.data as never);
    return api;
  });
  plan.lines.forEach((l) => {
    const host = apis[plan.series.findIndex((s) => s.pane === l.pane && s.kind !== "hist")];
    host?.createPriceLine({
      price: l.value, color: l.colour, lineWidth: 1, lineStyle: DASH[l.dash] ?? LineStyle.Dashed,
      axisLabelVisible: l.title !== "", title: l.title,
    });
  });
  const candles = apis[plan.series.findIndex((s) => s.kind === "candles")];
  if (candles && plan.markers.length) {
    createSeriesMarkers(candles, plan.markers.map((m) => ({ ...m, time: m.time as Time })));
  }
  const panes = chart.panes();
  panes.forEach((p, i) => p.setStretchFactor(i === 0 ? PRICE_PANE_HEIGHT : SUB_PANE_HEIGHT));
  chart.timeScale().fitContent();
  return chart;
}

function ChartCanvas({ plan, label }: { plan: ChartPlan; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const theme = useThemeName();
  const height = chartHeight(plan);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const chart = draw(el, plan);
    return () => chart.remove();
  }, [plan, theme]);
  return <div ref={ref} style={{ width: "100%", height }} role="img" aria-label={label} />;
}

interface ReadyBodyProps { chart: MomentumChartFile; period: Period; toggles: ChartToggles; symbol?: string }

/** Badges, chart and since-line; the plan is memoised so the chart only redraws when its inputs change. */
function ReadyBody({ chart, period, toggles, symbol }: ReadyBodyProps) {
  const plan = useMemo(() => mapChart(chart, period, toggles), [chart, period, toggles]);
  return (
    <>
      {plan.badges.length > 0 && (
        <div className="desk-row" style={{ flexWrap: "wrap", gap: 16, justifyContent: "flex-start" }}>
          {plan.badges.map((b) => (
            <span key={b.label} className="rd-note">
              <span className="rd-dot" style={{ background: b.colour }} />
              {` ${b.label} `}<strong style={{ color: "var(--rd-text)" }}>{b.value}</strong>{` ${b.sub}`}
            </span>
          ))}
        </div>
      )}
      <ChartCanvas plan={plan} label={`${symbol ?? "Stock"} price chart with indicators`} />
      {plan.sinceLine && <p className="rd-note" style={{ margin: 0 }}>{plan.sinceLine}</p>}
    </>
  );
}

interface ViewProps {
  state: ChartState;
  period: Period;
  onPeriod: (p: Period) => void;
  toggles: ChartToggles;
  onToggle: (k: ToggleKey) => void;
  symbol?: string;
}

/** Presentational part: controls, badges, chart and since-line, or the empty/error state. */
export function IndicatorChartView({ state, period, onPeriod, toggles, onToggle, symbol }: ViewProps) {
  if (state.status === "empty") return <EmptyState title={CHART_EMPTY.title} reason={state.reason ?? CHART_EMPTY.reason} />;
  if (state.status === "error") return <EmptyState title={CHART_ERROR} />;
  return (
    <div className="desk-stack" style={{ gap: 8 }}>
      <div className="desk-row" style={{ flexWrap: "wrap", gap: 12 }}>
        <Segmented options={PERIODS} value={period} onChange={onPeriod} ariaLabel="Chart period" />
        <div className="desk-row" style={{ flexWrap: "wrap", gap: 16 }}>
          {TOGGLES.map((t) => (
            <label className="desk-toggle" key={t.key}>
              <input type="checkbox" checked={toggles[t.key]} onChange={() => onToggle(t.key)} /> {t.label}
            </label>
          ))}
        </div>
      </div>
      {state.status === "ready" ? (
        <ReadyBody chart={state.chart} period={period} toggles={toggles} symbol={symbol} />
      ) : (
        <p className="rd-note" role="status" style={{ margin: 0 }}>Loading chart…</p>
      )}
    </div>
  );
}

type Loaded = { symbol: string; state: ChartState };

/** Streamlit's multi-panel indicator chart for the selected stock, read from the saved chart file. */
export function IndicatorChart({ symbol }: { symbol: string }) {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [period, setPeriod] = useState<Period>(DEFAULT_PERIOD);
  const [toggles, setToggles] = useState<ChartToggles>(ALL_ON);

  useEffect(() => {
    const ctrl = new AbortController();
    const done = (state: ChartState) => { if (!ctrl.signal.aborted) setLoaded({ symbol, state }); };
    (async () => {
      try {
        const res = await fetch(`/api/desk/momentum-chart?symbol=${encodeURIComponent(symbol)}`, { signal: ctrl.signal });
        if (res.status === 404) return done({ status: "empty", reason: null });
        if (!res.ok) return done({ status: "error" });
        const chart = (await res.json()) as MomentumChartFile;
        if (!chart.traces?.length) return done({ status: "empty", reason: chart.note ?? null });
        done({ status: "ready", chart });
      } catch {
        done({ status: "error" });
      }
    })();
    return () => ctrl.abort();
  }, [symbol]);

  const state: ChartState = loaded && loaded.symbol === symbol ? loaded.state : { status: "loading" };
  return (
    <IndicatorChartView state={state} symbol={symbol} period={period} onPeriod={setPeriod} toggles={toggles}
      onToggle={(k) => setToggles((t) => ({ ...t, [k]: !t[k] }))} />
  );
}
