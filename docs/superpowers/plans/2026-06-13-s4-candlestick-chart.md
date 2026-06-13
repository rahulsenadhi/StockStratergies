# S4 — Candlestick Price + Indicators Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an interactive candlestick price chart (per-ticker OHLC + toggleable Volume/SMA/EMA/Bollinger/RSI/MACD, full-universe ticker picker) to the per-strategy page, for strategies with OHLCV data.

**Architecture:** Pure `lib/indicators.ts` (TS parity with `core/indicators.py`) + loader `getOhlcv`/`listTickers` extend the seam. A server `price-chart-block` resolves ticker (via `?chart=` param) + computes all indicators once; client `price-chart` (lightweight-charts v5, candles + panes) only toggles visibility. Wired into momentum/ipo/pead strategy-sections; Monthly omitted (close-only).

**Tech Stack:** Next.js 16, TypeScript, Tailwind v4, lightweight-charts v5.2, Vitest.

Spec: `docs/superpowers/specs/2026-06-13-s4-candlestick-chart-design.md`.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `web/lib/indicators.ts` | `sma,ema,rsi,macd,bollinger` (pure) | Create |
| `web/tests/indicators.test.ts` | indicator unit tests | Create |
| `web/lib/data/strategies.ts` | `Ohlcv` type, `getOhlcv`, `listTickers`, `OHLCV_FOLDER_BY_ID` | Modify |
| `web/tests/strategies.test.ts` | getOhlcv/listTickers tests; fixtures | Modify |
| `web/components/price-chart.tsx` | client LWC candlestick + panes + toggles | Create |
| `web/components/ticker-picker.tsx` | client typeahead → `?chart=` | Create |
| `web/components/strategy-sections/price-chart-block.tsx` | server: resolve/load/compute → render | Create |
| `web/components/strategy-sections/{momentum-edge,ipo-edge,pead}.tsx` | render `<PriceChartBlock>` | Modify |
| `web/components/strategy-sections/index.tsx` | thread `chart` prop | Modify |
| `web/app/strategy/[id]/page.tsx` | read `searchParams.chart`, pass down | Modify |

**Conventions:** npm/npx from `web/`; commit from repo root. Branch `feat/s4-candlestick-chart` (already created). lightweight-charts is **v5.2** → `addSeries(SeriesType, options, paneIndex)`. No Python/Streamlit changes.

---

## Task 1: `lib/indicators.ts` (TDD)

**Files:** Create `web/lib/indicators.ts`, `web/tests/indicators.test.ts`

- [ ] **Step 1: Write failing tests**

```ts
// web/tests/indicators.test.ts
import { describe, it, expect } from "vitest";
import { sma, ema, rsi, macd, bollinger } from "@/lib/indicators";

describe("sma", () => {
  it("trailing avg with leading nulls", () => {
    expect(sma([1, 2, 3, 4], 2)).toEqual([null, 1.5, 2.5, 3.5]);
  });
});

describe("ema", () => {
  it("seeds with sma then smooths", () => {
    expect(ema([1, 2, 3, 4], 2)).toEqual([null, 1.5, 2.5, 3.5]);
  });
});

describe("rsi", () => {
  it("nulls during warmup, 100 when only gains", () => {
    const r = rsi([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], 14);
    expect(r.slice(0, 14).every((v) => v === null)).toBe(true);
    expect(r[14]).toBeCloseTo(100, 6);
  });
});

describe("macd", () => {
  it("returns aligned macd/signal/histogram, hist = macd - signal", () => {
    const close = Array.from({ length: 60 }, (_, i) => 100 + i);
    const { macd: m, signal, histogram } = macd(close, 12, 26, 9);
    expect(m.length).toBe(60);
    const i = 59;
    expect(histogram[i]).toBeCloseTo((m[i] as number) - (signal[i] as number), 9);
  });
});

describe("bollinger", () => {
  it("mid = sma(n); upper/lower symmetric around mid", () => {
    const close = [2, 4, 6, 8, 10, 12];
    const { upper, mid, lower } = bollinger(close, 3, 2);
    expect(mid).toEqual(sma(close, 3));
    const i = 5;
    expect((upper[i] as number) - (mid[i] as number)).toBeCloseTo((mid[i] as number) - (lower[i] as number), 9);
  });
});
```

- [ ] **Step 2: Run, verify fail** — `cd web && npm test` → FAIL (no module).

- [ ] **Step 3: Implement `web/lib/indicators.ts`**

```ts
// Pure technical indicators (parity with core/indicators.py). All return arrays
// aligned to the input length, with leading null during the warmup window.

export function sma(values: number[], n: number): (number | null)[] {
  const out: (number | null)[] = [];
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= n) sum -= values[i - n];
    out.push(i >= n - 1 ? sum / n : null);
  }
  return out;
}

export function ema(values: number[], n: number): (number | null)[] {
  const out: (number | null)[] = [];
  const k = 2 / (n + 1);
  let prev = 0;
  for (let i = 0; i < values.length; i++) {
    if (i < n - 1) {
      out.push(null);
      continue;
    }
    if (i === n - 1) {
      let s = 0;
      for (let j = 0; j < n; j++) s += values[j];
      prev = s / n;
      out.push(prev);
      continue;
    }
    prev = values[i] * k + prev * (1 - k);
    out.push(prev);
  }
  return out;
}

export function rsi(close: number[], n = 14): (number | null)[] {
  const out: (number | null)[] = new Array(close.length).fill(null);
  if (close.length <= n) return out;
  let gain = 0;
  let loss = 0;
  for (let i = 1; i <= n; i++) {
    const d = close[i] - close[i - 1];
    if (d >= 0) gain += d;
    else loss -= d;
  }
  gain /= n;
  loss /= n;
  out[n] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  for (let i = n + 1; i < close.length; i++) {
    const d = close[i] - close[i - 1];
    gain = (gain * (n - 1) + (d > 0 ? d : 0)) / n;
    loss = (loss * (n - 1) + (d < 0 ? -d : 0)) / n;
    out[i] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  }
  return out;
}

export type MacdResult = {
  macd: (number | null)[];
  signal: (number | null)[];
  histogram: (number | null)[];
};

export function macd(close: number[], fast = 12, slow = 26, sig = 9): MacdResult {
  const ef = ema(close, fast);
  const es = ema(close, slow);
  const macdLine: (number | null)[] = close.map((_, i) =>
    ef[i] != null && es[i] != null ? (ef[i] as number) - (es[i] as number) : null,
  );
  const firstIdx = macdLine.findIndex((v) => v != null);
  const signal: (number | null)[] = new Array(close.length).fill(null);
  if (firstIdx >= 0) {
    const compact = macdLine.slice(firstIdx) as number[];
    const sigCompact = ema(compact, sig);
    for (let i = 0; i < sigCompact.length; i++) signal[firstIdx + i] = sigCompact[i];
  }
  const histogram: (number | null)[] = close.map((_, i) =>
    macdLine[i] != null && signal[i] != null ? (macdLine[i] as number) - (signal[i] as number) : null,
  );
  return { macd: macdLine, signal, histogram };
}

export type BollingerResult = {
  upper: (number | null)[];
  mid: (number | null)[];
  lower: (number | null)[];
};

export function bollinger(close: number[], n = 20, k = 2): BollingerResult {
  const mid = sma(close, n);
  const upper: (number | null)[] = [];
  const lower: (number | null)[] = [];
  for (let i = 0; i < close.length; i++) {
    if (mid[i] == null) {
      upper.push(null);
      lower.push(null);
      continue;
    }
    const m = mid[i] as number;
    let s = 0;
    for (let j = i - n + 1; j <= i; j++) s += (close[j] - m) ** 2;
    const sd = Math.sqrt(s / n);
    upper.push(m + k * sd);
    lower.push(m - k * sd);
  }
  return { upper, mid, lower };
}
```

- [ ] **Step 4: Run, verify pass** — `cd web && npm test` → PASS.

- [ ] **Step 5: Commit**

```bash
cd .. && git add web/lib/indicators.ts web/tests/indicators.test.ts && git commit -m "feat(s4): lib/indicators (sma/ema/rsi/macd/bollinger, TS parity)"
```

---

## Task 2: loader — `getOhlcv` + `listTickers` + folder map (TDD)

**Files:** Modify `web/lib/data/strategies.ts`, `web/tests/strategies.test.ts`; fixtures `web/tests/fixtures/ohlcv/AAA.csv`, `^BENCH.csv`

- [ ] **Step 1: Create fixtures**

`web/tests/fixtures/ohlcv/AAA.csv`:
```
Date,Open,High,Low,Close,Volume
2024-01-01,100,105,99,104,1000
2024-01-01,100,105,99,103,1100
2024-01-02,104,108,103,107,1200
```
`web/tests/fixtures/ohlcv/^BENCH.csv`:
```
Date,Open,High,Low,Close,Volume
2024-01-01,100,100,100,100,0
```

- [ ] **Step 2: Write failing tests** (append to `web/tests/strategies.test.ts`)

```ts
import { getOhlcv, listTickers } from "@/lib/data/strategies";
import path from "path";
const OHLCV_FIX = path.join(import.meta.dirname, "fixtures", "ohlcv");

describe("getOhlcv", () => {
  it("parses OHLCV, dedups date (keep last), sorts", async () => {
    const r = await getOhlcv("AAA", "", OHLCV_FIX);
    expect(r.length).toBe(2);
    expect(r[0]).toEqual({ time: "2024-01-01", open: 100, high: 105, low: 99, close: 103, volume: 1100 });
    expect(r[1].time).toBe("2024-01-02");
  });
  it("missing file -> []", async () => {
    expect(await getOhlcv("NOPE", "", OHLCV_FIX)).toEqual([]);
  });
});

describe("listTickers", () => {
  it("returns stems, drops ^-files", async () => {
    const t = await listTickers("", OHLCV_FIX);
    expect(t).toContain("AAA");
    expect(t.some((x) => x.startsWith("^"))).toBe(false);
  });
  it("missing dir -> []", async () => {
    expect(await listTickers("nope", path.join(import.meta.dirname, "fixtures"))).toEqual([]);
  });
});
```
> Note: tests pass `folder=""` and point `dataDir` at the fixture dir, so `path.join(dataDir, "", "AAA.csv")` resolves inside the fixture. Real callers pass a real folder + default dataDir.

- [ ] **Step 3: Run, verify fail** — `cd web && npm test` → FAIL.

- [ ] **Step 4: Implement** (append to `web/lib/data/strategies.ts`; `fs` promises + `path` already imported)

```ts
export type Ohlcv = {
  time: string; open: number; high: number; low: number; close: number; volume: number;
};

const MAX_BARS = 1500;

export async function getOhlcv(
  ticker: string,
  folder: string,
  dataDir: string = DEFAULT_DATA_DIR,
  maxBars: number = MAX_BARS,
): Promise<Ohlcv[]> {
  try {
    const txt = await fs.readFile(path.join(dataDir, folder, `${ticker}.csv`), "utf-8");
    const lines = txt.trim().split(/\r?\n/);
    if (lines.length < 2) return [];
    const h = lines[0].split(",").map((x) => x.trim().toLowerCase());
    const di = h.indexOf("date"), oi = h.indexOf("open"), hi = h.indexOf("high");
    const li = h.indexOf("low"), ci = h.indexOf("close"), vi = h.indexOf("volume");
    if ([di, oi, hi, li, ci].some((x) => x < 0)) return [];
    const seen = new Map<string, Ohlcv>();
    for (const ln of lines.slice(1)) {
      const c = ln.split(",");
      const time = String(c[di] ?? "").slice(0, 10);
      if (!time) continue;
      const row: Ohlcv = {
        time, open: Number(c[oi]), high: Number(c[hi]), low: Number(c[li]),
        close: Number(c[ci]), volume: vi >= 0 ? Number(c[vi]) || 0 : 0,
      };
      if ([row.open, row.high, row.low, row.close].some(Number.isNaN)) continue;
      seen.set(time, row); // dedup: keep last for a date
    }
    const rows = [...seen.values()].sort((a, b) => a.time.localeCompare(b.time));
    return rows.length > maxBars ? rows.slice(rows.length - maxBars) : rows;
  } catch {
    return [];
  }
}

export async function listTickers(
  folder: string,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<string[]> {
  try {
    const files = await fs.readdir(path.join(dataDir, folder));
    return files
      .filter((f) => f.endsWith(".csv") && !f.startsWith("^"))
      .map((f) => f.slice(0, -4))
      .sort();
  } catch {
    return [];
  }
}

export const OHLCV_FOLDER_BY_ID: Record<string, string> = {
  momentum_edge: "data/nse_bse",
  ipo_edge: "ipo_data",
  pead: "data/nse_bse",
};
```
> If `fs` is imported as `import { promises as fs } from "fs"`, `fs.readdir` is available. Confirm the existing import; if it's a named `readFile` import, add `readdir`.

- [ ] **Step 5: Run, verify pass** — `cd web && npm test` → PASS.

- [ ] **Step 6: Commit**

```bash
cd .. && git add web/lib/data/strategies.ts web/tests/strategies.test.ts web/tests/fixtures/ohlcv && git commit -m "feat(s4): getOhlcv + listTickers + OHLCV_FOLDER_BY_ID"
```

---

## Task 3: `price-chart.tsx` (client, lightweight-charts v5)

**Files:** Create `web/components/price-chart.tsx`

- [ ] **Step 1: Confirm v5 pane API** — `cd web && npm ls lightweight-charts` (expect 5.2.x). v5 series: `chart.addSeries(SeriesType, options, paneIndex)`. Confirm `CandlestickSeries`, `HistogramSeries`, `LineSeries` exports + that the 3rd `addSeries` arg is the pane index (creating the pane if absent). Adapt if the installed 5.2 signature differs.

- [ ] **Step 2: Implement `web/components/price-chart.tsx`**

```tsx
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
```
> The `addSeries(Type, options, paneIndex)` 3rd-arg pane form is v5. If 5.2 requires `chart.addPane()` first or a different option, adapt (Step 1) — keep the same series/toggle behavior.

- [ ] **Step 3: Typecheck + build** — `cd web && npx tsc --noEmit && npm run build` → succeed.

- [ ] **Step 4: Commit**

```bash
cd .. && git add web/components/price-chart.tsx && git commit -m "feat(s4): price-chart (LWC v5 candles + indicator panes + toggles)"
```

---

## Task 4: `ticker-picker.tsx` (client typeahead → `?chart=`)

**Files:** Create `web/components/ticker-picker.tsx`

- [ ] **Step 1: Implement**

```tsx
"use client";

import { useState } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";

export function TickerPicker({ tickers, current }: { tickers: string[]; current: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [q, setQ] = useState("");

  const matches = q
    ? tickers.filter((t) => t.toLowerCase().includes(q.toLowerCase())).slice(0, 20)
    : [];

  const pick = (t: string) => {
    const next = new URLSearchParams(params.toString());
    next.set("chart", t);
    setQ("");
    router.push(`${pathname}?${next.toString()}`);
  };

  return (
    <div className="relative mb-2 max-w-xs">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={`Search ticker (current: ${current})`}
        className="w-full rounded border border-border bg-background px-2 py-1 text-sm"
      />
      {matches.length > 0 && (
        <ul className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded border border-border bg-background text-sm shadow">
          {matches.map((t) => (
            <li key={t}>
              <button onClick={() => pick(t)} className="block w-full px-2 py-1 text-left hover:bg-muted/40">
                {t}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Typecheck** — `cd web && npx tsc --noEmit` → no errors.

- [ ] **Step 3: Commit**

```bash
cd .. && git add web/components/ticker-picker.tsx && git commit -m "feat(s4): ticker-picker typeahead"
```

---

## Task 5: `price-chart-block` (server) + section/page wiring

**Files:** Create `web/components/strategy-sections/price-chart-block.tsx`; Modify `momentum-edge.tsx`, `ipo-edge.tsx`, `pead.tsx`, `index.tsx`, `app/strategy/[id]/page.tsx`

- [ ] **Step 1: Implement `web/components/strategy-sections/price-chart-block.tsx`**

```tsx
import type { ReactNode } from "react";
import {
  getOhlcv, listTickers, getLiveSignals, OHLCV_FOLDER_BY_ID,
} from "@/lib/data/strategies";
import type { Strategy } from "@/lib/data/strategies";
import { sma, ema, rsi, macd, bollinger } from "@/lib/indicators";
import { PriceChart, type Indicators } from "@/components/price-chart";
import { TickerPicker } from "@/components/ticker-picker";

async function defaultTicker(strategy: Strategy, tickers: string[]): Promise<string | null> {
  if (strategy.liveSignalsCsv) {
    const sigs = await getLiveSignals(strategy.liveSignalsCsv, undefined, 1);
    const raw = sigs[0]?.ticker?.replace(/\.NS$/i, "");
    if (raw && tickers.includes(raw)) return raw;
  }
  return tickers[0] ?? null;
}

export async function PriceChartBlock({
  strategy, chart,
}: { strategy: Strategy; chart?: string }): Promise<ReactNode> {
  const folder = OHLCV_FOLDER_BY_ID[strategy.id];
  if (!folder) return null;
  const tickers = await listTickers(folder);
  if (tickers.length === 0) return null;

  const ticker = chart && tickers.includes(chart) ? chart : await defaultTicker(strategy, tickers);
  if (!ticker) return null;

  const ohlcv = await getOhlcv(ticker, folder);
  const close = ohlcv.map((b) => b.close);
  const m = macd(close);
  const bb = bollinger(close, 20, 2);
  const indicators: Indicators = {
    sma50: sma(close, 50), sma200: sma(close, 200), ema21: ema(close, 21),
    bbUpper: bb.upper, bbMid: bb.mid, bbLower: bb.lower,
    rsi: rsi(close, 14), macd: m.macd, macdSignal: m.signal, macdHist: m.histogram,
  };

  return (
    <section>
      <h2 className="mb-2 text-lg font-semibold">Price &amp; Indicators</h2>
      <TickerPicker tickers={tickers} current={ticker} />
      <PriceChart ohlcv={ohlcv} indicators={indicators} ticker={ticker} />
    </section>
  );
}
```
> `getLiveSignals(csv, dataDir?, limit)` — pass `undefined` for dataDir to use the default. If its signature differs, adapt the call (it returns `{ticker,company,signal}[]`).

- [ ] **Step 2: Render the block in the three sections**

In each of `momentum-edge.tsx`, `ipo-edge.tsx`, `pead.tsx`: import `PriceChartBlock`, accept an optional `chart?: string` prop on the section's props, and render `<PriceChartBlock strategy={strategy} chart={chart} />` as the FIRST element of the returned fragment (above existing content). Example for `momentum-edge.tsx` — change the signature + add the block:
```tsx
import { PriceChartBlock } from "@/components/strategy-sections/price-chart-block";
// ...
export async function MomentumEdgeSection({ strategy, chart }: { strategy: Strategy; chart?: string }): Promise<ReactNode> {
  // ... existing loads ...
  return (
    <>
      <PriceChartBlock strategy={strategy} chart={chart} />
      {/* ...existing sections unchanged... */}
    </>
  );
}
```
Apply the same two changes (prop + first child) to `ipo-edge.tsx` and `pead.tsx`. Do NOT change `monthly-rotation.tsx` (no OHLCV).

- [ ] **Step 3: Thread `chart` through `index.tsx`**

```tsx
export function StrategySection({ strategy, chart }: { strategy: Strategy; chart?: string }): ReactNode {
  switch (strategy.id) {
    case "monthly_rotation":
      return <MonthlyRotationSection strategy={strategy} />;
    case "ipo_edge":
      return <IpoEdgeSection strategy={strategy} chart={chart} />;
    case "momentum_edge":
      return <MomentumEdgeSection strategy={strategy} chart={chart} />;
    case "pead":
      return <PeadSection strategy={strategy} chart={chart} />;
    default:
      return null;
  }
}
```

- [ ] **Step 4: Read `searchParams.chart` in the page**

In `web/app/strategy/[id]/page.tsx`, the page is an async RSC. Next 16: `searchParams` is a Promise. Add/extend the props to include it and await:
```tsx
export default async function StrategyPage({
  params, searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ chart?: string }>;
}) {
  const { id } = await params;
  const { chart } = await searchParams;
  // ... existing strategy load ...
  // change the render line:
  //   <StrategySection strategy={s} chart={chart} />
}
```
Update the `<StrategySection strategy={s} />` usage to `<StrategySection strategy={s} chart={chart} />`. Keep everything else unchanged.

- [ ] **Step 5: Typecheck + build**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: succeeds; `/strategy/[id]` still builds.

- [ ] **Step 6: Commit**

```bash
cd .. && git add web/components/strategy-sections web/app/strategy && git commit -m "feat(s4): price-chart-block + section/page wiring (?chart= param)"
```

---

## Task 6: Verify + memory

- [ ] **Step 1: Full Vitest + typecheck + build**

```bash
cd web && npm test && npx tsc --noEmit && npm run build
```
Expected: all green (indicators + getOhlcv/listTickers tests added).

- [ ] **Step 2: Run + verify**

```bash
cd web && npx next start -p 3011   # after build
```
- `curl -s "http://localhost:3011/strategy/momentum_edge" | grep -oE "Price & Indicators|Search ticker"` → present.
- `curl -s -o /dev/null -w "%{http_code}" "http://localhost:3011/strategy/momentum_edge?chart=HINDZINC"` → 200.
- `curl -s "http://localhost:3011/strategy/monthly_rotation" | grep -c "Price & Indicators"` → 0 (Monthly has no chart).
- Browser `/strategy/momentum_edge`: candlestick chart renders for the default ticker; typing in the picker + selecting a ticker updates `?chart=` and reloads the chart; toggles show/hide SMA/EMA/Bollinger/Volume/RSI/MACD; other sections + routes unaffected.
Stop the server after.

> Charts render to `<canvas>` (client JS) — curl confirms section heading + picker; verify candles/panes visually in the browser. Report which path used.

- [ ] **Step 3: Memory (controller, not subagent)**

Update `s4_momentum_parity_program.md`: Slice A done — candlestick chart shipped (lib/indicators, getOhlcv/listTickers, price-chart + ticker-picker + price-chart-block, wired into momentum/ipo/pead; Monthly omitted). Note Slice B (conditions checklist) next.

---

## Self-Review

**Spec coverage:**
- §4 files (indicators, loaders+map, price-chart, ticker-picker, price-chart-block, section/page wiring) → Tasks 1–5. ✓
- §5 indicators (sma/ema/rsi-Wilder/macd/bollinger, warmup nulls) → Task 1. ✓
- §6 data flow (folder resolve, ticker via ?chart= or default top-signal, getOhlcv, compute all) → Tasks 2,5. ✓
- §7 charts (candles + overlays + Volume/RSI/MACD panes, toggle row, empty placeholder, cleanup) → Task 3. ✓
- §8 errors (no folder→null, bad ticker→default→first→placeholder, warmup nulls, dedup/sort, try/catch) → Tasks 2,3,5. ✓
- §9 testing (indicators known-values, getOhlcv/listTickers, build, run incl. Monthly-no-chart) → Tasks 1,2,6. ✓

**Placeholder scan:** complete code throughout; the LWC pane-API and getLiveSignals-signature notes are verify-against-installed cautions with a concrete default, not gaps.

**Type consistency:** `Ohlcv {time,open,high,low,close,volume}`; `Indicators {sma50,sma200,ema21,bbUpper,bbMid,bbLower,rsi,macd,macdSignal,macdHist}` shared block→chart; `sma/ema/rsi→(number|null)[]`, `macd→MacdResult`, `bollinger→BollingerResult`; `OHLCV_FOLDER_BY_ID`; `getOhlcv(ticker,folder,dir?,maxBars?)`, `listTickers(folder,dir?)`; section props `{strategy, chart?}`. Consistent across tasks. ✓
