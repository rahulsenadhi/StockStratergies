"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart, CandlestickSeries, HistogramSeries, LineSeries, ColorType,
} from "lightweight-charts";
import type { Ohlcv } from "@/lib/data/strategies";

export type Indicators = {
  sma50: (number | null)[];
  sma200: (number | null)[];
  ema21: (number | null)[];
  bbUpper: (number | null)[];
  bbMid: (number | null)[];
  bbLower: (number | null)[];
  rsi: (number | null)[];
  macd: (number | null)[];
  macdSignal: (number | null)[];
  macdHist: (number | null)[];
};

type ToggleKey = "sma50" | "sma200" | "ema" | "bollinger" | "volume" | "rsi" | "macd";
const DEFAULT_ON: Record<ToggleKey, boolean> = {
  sma50: true, sma200: true, ema: false, bollinger: false, volume: true, rsi: false, macd: false,
};
const LABELS: Record<ToggleKey, string> = {
  sma50: "SMA 50", sma200: "SMA 200", ema: "EMA 21", bollinger: "Bollinger",
  volume: "Volume", rsi: "RSI", macd: "MACD",
};

function line(ohlcv: Ohlcv[], values: (number | null)[]) {
  return ohlcv
    .map((b, i) => ({ time: b.time, value: values[i] }))
    .filter((p): p is { time: string; value: number } => p.value != null);
}

export function PriceChart({
  ohlcv, indicators, ticker,
}: { ohlcv: Ohlcv[]; indicators: Indicators; ticker: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [on, setOn] = useState<Record<ToggleKey, boolean>>(DEFAULT_ON);

  useEffect(() => {
    const el = ref.current;
    if (!el || ohlcv.length === 0) return;
    const chart = createChart(el, {
      height: 460,
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#8b93a1" },
      grid: { vertLines: { color: "#20242c" }, horzLines: { color: "#20242c" } },
      rightPriceScale: { borderColor: "#20242c" },
      timeScale: { borderColor: "#20242c" },
    });

    // Pane 0 — candles + overlays
    const candles = chart.addSeries(CandlestickSeries, {}, 0);
    candles.setData(ohlcv.map((b) => ({ time: b.time, open: b.open, high: b.high, low: b.low, close: b.close })));

    const overlay = (vals: (number | null)[], color: string) =>
      chart.addSeries(LineSeries, { color, lineWidth: 1, priceLineVisible: false }, 0).setData(line(ohlcv, vals));
    if (on.sma50) overlay(indicators.sma50, "#3b82f6");
    if (on.sma200) overlay(indicators.sma200, "#f59e0b");
    if (on.ema) overlay(indicators.ema21, "#a855f7");
    if (on.bollinger) {
      overlay(indicators.bbUpper, "#6b7280");
      overlay(indicators.bbMid, "#6b7280");
      overlay(indicators.bbLower, "#6b7280");
    }

    let pane = 1;
    if (on.volume) {
      const vol = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" } }, pane++);
      vol.setData(ohlcv.map((b) => ({
        time: b.time, value: b.volume, color: b.close >= b.open ? "#22c55e88" : "#ef444488",
      })));
    }
    if (on.rsi) {
      chart.addSeries(LineSeries, { color: "#e6e6e6", lineWidth: 1 }, pane++).setData(line(ohlcv, indicators.rsi));
    }
    if (on.macd) {
      const p = pane++;
      chart.addSeries(HistogramSeries, {}, p).setData(
        ohlcv.map((b, i) => ({ time: b.time, value: indicators.macdHist[i] }))
          .filter((x): x is { time: string; value: number } => x.value != null)
          .map((x) => ({ ...x, color: x.value >= 0 ? "#22c55e88" : "#ef444488" })),
      );
      chart.addSeries(LineSeries, { color: "#3b82f6", lineWidth: 1 }, p).setData(line(ohlcv, indicators.macd));
      chart.addSeries(LineSeries, { color: "#f59e0b", lineWidth: 1 }, p).setData(line(ohlcv, indicators.macdSignal));
    }

    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [ohlcv, indicators, on]);

  if (!ohlcv || ohlcv.length === 0) {
    return (
      <div className="flex h-[460px] items-center justify-center rounded border border-border text-sm text-muted-foreground">
        No price data for {ticker}
      </div>
    );
  }
  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-2 text-xs">
        {(Object.keys(LABELS) as ToggleKey[]).map((k) => (
          <button
            key={k}
            onClick={() => setOn((s) => ({ ...s, [k]: !s[k] }))}
            className={`rounded border px-2 py-0.5 ${on[k] ? "border-foreground/40 bg-muted/40" : "border-border text-muted-foreground"}`}
          >
            {LABELS[k]}
          </button>
        ))}
      </div>
      <div ref={ref} className="w-full" />
    </div>
  );
}
