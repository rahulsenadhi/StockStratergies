"use client";

import { useSyncExternalStore } from "react";
import { ColorType, type ChartOptions, type DeepPartial } from "lightweight-charts";

/** A CSS custom property from the page theme (charts draw on canvas, so they read tokens once per theme). */
export function readCss(name: string, fallback: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

function subscribeTheme(onChange: () => void): () => void {
  const obs = new MutationObserver(onChange);
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => obs.disconnect();
}

/** Current light/dark theme; charts list it as an effect dependency so they redraw on a theme switch. */
export function useThemeName(): string {
  return useSyncExternalStore(
    subscribeTheme,
    () => document.documentElement.dataset.theme ?? "light",
    () => "light",
  );
}

/** "#7c9cff" + 0.07 -> "rgba(124,156,255,0.07)" (Python _hex_rgba, used for the 7% area fill). */
export function hexRgba(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const n = Number.parseInt(full.slice(0, 6), 16);
  if (Number.isNaN(n)) return hex;
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
}

/** Shared desk chart look (Home GrowthChart and the Monthly charts): no grid columns, no scroll/zoom. */
export function deskChartOptions(height: number, priceFormatter: (p: number) => string): DeepPartial<ChartOptions> {
  const muted = readCss("--rd-text-muted", "#77756E");
  const line = readCss("--rd-line", "#E7E4DD");
  return {
    height,
    autoSize: true,
    layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: muted, fontFamily: "inherit" },
    grid: { vertLines: { visible: false }, horzLines: { color: line } },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false },
    handleScroll: false,
    handleScale: false,
    localization: { priceFormatter },
  };
}

/** Saved [time, value] points as chart data; a value saved as NaN (null) becomes a gap, never a guess. */
export function toSeriesData<T>(points: readonly [T, number | null][]): ({ time: T; value: number } | { time: T })[] {
  return points.map(([time, value]) => (value == null ? { time } : { time, value }));
}
