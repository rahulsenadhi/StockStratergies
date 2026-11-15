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

export { hexRgba } from "@/lib/desk/colour";

/** Shared desk chart look (Home GrowthChart and the Monthly charts): no grid columns, no scroll/zoom. */
/** `priceFormatter` applies to every pane; omit it when panes need different formats (set priceFormat per series). */
export function deskChartOptions(height: number, priceFormatter?: (p: number) => string): DeepPartial<ChartOptions> {
  const muted = readCss("--rd-text-muted", "#77756E");
  const line = readCss("--rd-line", "#E7E4DD");
  return {
    height,
    autoSize: true,
    layout: {
      background: { type: ColorType.Solid, color: "transparent" }, textColor: muted, fontFamily: "inherit",
      panes: { separatorColor: line, separatorHoverColor: line, enableResize: false },
    },
    grid: { vertLines: { visible: false }, horzLines: { color: line } },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false },
    handleScroll: false,
    handleScale: false,
    ...(priceFormatter ? { localization: { priceFormatter } } : {}),
  };
}

/** Saved [time, value] points as chart data; a value saved as NaN (null) becomes a gap, never a guess. */
export function toSeriesData<T>(points: readonly [T, number | null][]): ({ time: T; value: number } | { time: T })[] {
  return points.map(([time, value]) => (value == null ? { time } : { time, value }));
}
