# S4 — Candlestick Price + Indicators Chart: Design Spec

**Author:** rahulsenadhi
**Date:** 2026-06-13
**Status:** Draft
**Depends on:** S4 Next.js app (`web/`, loader seam, lightweight-charts v5, strategy-sections dispatcher), `core/indicators.py` (parity reference).
**Program:** Slice A of the 3-slice Momentum-parity program (see memory `s4-momentum-parity-program`).

---

## 1. Goal

Add an interactive **candlestick price chart with technical indicators** to the per-strategy page — the biggest gap vs the Streamlit Momentum page. Per-ticker OHLC candles + toggleable Volume, SMA/EMA overlays, Bollinger Bands, RSI, and MACD, with a full-universe ticker picker.

## 2. Non-Goals

- No live/intraday data (daily EOD only).
- No drawing tools, no multi-ticker compare on one chart.
- No new indicators beyond the six (Volume, SMA, EMA, Bollinger, RSI, MACD).
- No chart for close-only strategies (Monthly Rotation has no OHLC).
- No cloud.

## 3. Decisions (this session)

- Indicators: **full set** — candles + Volume + SMA/EMA + Bollinger + RSI + MACD, all toggleable.
- Ticker selection: **full-universe searchable picker** over the strategy's OHLCV folder, via `?chart=TICKER` search param; default = strategy's top live signal (else first ticker).
- Indicators computed **server-side once**; client toggles visibility (no refetch on toggle).
- Best-effort per strategy via `OHLCV_FOLDER_BY_ID`: momentum_edge→`data/nse_bse`, ipo_edge→`ipo_data`, pead→`data/nse_bse`. **monthly_rotation omitted** (its `data/` is close-only — `Date,<TICKER>`, no OHLC).

## 4. Architecture & Files

```
web/
  lib/indicators.ts             NEW (pure TS, parity with core/indicators.py):
    sma(values,n), ema(values,n), rsi(close,14) [Wilder], macd(close,12,26,9),
    bollinger(close,20,2); arrays aligned to bars (leading null during warmup)
  lib/data/strategies.ts        EXTEND:
    type Ohlcv = { time: string; open: number; high: number; low: number; close: number; volume: number }
    getOhlcv(ticker, folder, dir?): Promise<Ohlcv[]>   (dated, sorted, dedup, cap ~1500 recent)
    listTickers(folder, dir?): Promise<string[]>        (CSV stems, drop ^-benchmarks)
    OHLCV_FOLDER_BY_ID: Record<string,string>           (the per-strategy map above)
  components/
    price-chart.tsx             NEW client (LWC v5) — candles + panes + overlays + toggle row
    ticker-picker.tsx           NEW client — typeahead over tickers; pushes ?chart= param
  components/strategy-sections/price-chart-block.tsx  NEW (server) —
    resolve folder via OHLCV_FOLDER_BY_ID; ticker = chart ?? defaultTicker ?? tickers[0];
    getOhlcv → computeIndicators(lib/indicators) → render <TickerPicker> + <PriceChart>
  components/strategy-sections/{momentum-edge,ipo-edge,pead}.tsx  EXTEND — render <PriceChartBlock>
  app/strategy/[id]/page.tsx    EXTEND — read searchParams.chart (Next 16 async), thread to section
  tests/indicators.test.ts      NEW — sma/ema/rsi/macd/bollinger vs known values
  tests/strategies.test.ts      EXTEND — getOhlcv, listTickers
```

**Boundaries:**
- Indicators in a pure `lib/indicators.ts` (no React/IO) — unit-testable, parity with Python.
- `price-chart-block` (server) does all loading + indicator compute; `price-chart` (client) only renders + toggles. Toggling never refetches.
- Ticker selection is URL-state (`?chart=`), so the RSC reloads server-side — no client data API, consistent with the loader-seam pattern.
- Best-effort: a strategy without an OHLCV folder renders no chart block.

## 5. Indicators (`lib/indicators.ts`, parity with `core/indicators.py`)

All take a numeric series (close, except volume) and return an array aligned to the bars, with leading `null` during the warmup window:
- `sma(values, n)` — simple moving average.
- `ema(values, n)` — exponential MA (standard `2/(n+1)` smoothing).
- `rsi(close, 14)` — **Wilder smoothing** (match `core.indicators.rsi`).
- `macd(close, 12, 26, 9)` → `{ macd, signal, histogram }`.
- `bollinger(close, 20, 2)` → `{ upper, mid, lower }` (mid = SMA20, ±2σ).
- Volume is passed through from OHLCV (colored by candle direction in the chart).

## 6. Data Flow

```
GET /strategy/momentum_edge?chart=TATASTEEL  (RSC, force-dynamic)
 → page passes searchParams.chart to <StrategySection strategy chart=...>
 → momentum-edge section renders <PriceChartBlock strategy chart=...>
 → PriceChartBlock (server):
     folder = OHLCV_FOLDER_BY_ID[strategy.id]; if !folder → render null
     tickers = await listTickers(folder)
     ticker  = chart && tickers.includes(chart) ? chart : (defaultTicker(strategy) ?? tickers[0])
     ohlcv   = await getOhlcv(ticker, folder)
     ind     = { sma50, sma200, ema21, bbUpper, bbMid, bbLower, rsi, macd, macdSignal, macdHist }
 → <TickerPicker tickers={tickers} current={ticker}/>   (client; pushes ?chart=)
   <PriceChart ohlcv={ohlcv} indicators={ind} ticker={ticker}/>  (client; toggles)
```
- `defaultTicker(strategy)`: first ticker of the strategy's live signals (via `getLiveSignals(strategy.liveSignalsCsv)`), normalized (strip `.NS` to match folder stems if needed); else `tickers[0]`.
- `getOhlcv`: read `{folder}/{ticker}.csv` (`Date,O,H,L,C,V`) → `{time:"YYYY-MM-DD",open,high,low,close,volume}[]`, sorted, dedup by date (LWC requirement), keep most-recent ~1500 bars. Missing/unreadable → `[]`.
- `listTickers`: dir glob `*.csv` stems, drop names starting `^`.

## 7. Charts (`price-chart.tsx`, lightweight-charts v5, client)

- Main pane: `CandlestickSeries` (OHLC). Overlays (same pane, LineSeries): SMA50, SMA200, EMA21, Bollinger upper/mid/lower.
- Panes (LWC v5 multi-pane): Volume (HistogramSeries, green/red by candle), RSI (LineSeries + 30/70 guide lines), MACD (Histogram + macd & signal lines).
- **Toggle row** (chips/checkboxes): SMA50 · SMA200 · EMA · Bollinger · Volume · RSI · MACD. Candles always on. State client-side; toggling sets series visible/hidden (no refetch). Defaults on: candles, Volume, SMA50, SMA200. Off: EMA, Bollinger, RSI, MACD.
- Dark theme (match app); `chart.remove()` cleanup on unmount; empty `ohlcv` → "No price data" placeholder.
- Indicator arrays may contain leading nulls → mapped to LWC whitespace (gaps), candles still render.

## 8. Error Handling

- Strategy without OHLCV folder → `PriceChartBlock` renders null.
- `?chart=` ticker not in folder → fall back to default; default missing → first ticker; none → "No price data".
- File missing/unreadable/empty → `getOhlcv` `[]` → placeholder.
- Indicator warmup (n > series length) → all-null array; chart shows candles only (no crash).
- dedup + sort guards (LWC rejects duplicate/unsorted times).
- All loader reads wrapped in try/catch → `[]` / `[]`.

## 9. Testing

- **Vitest `indicators.test.ts`** (pure, known/hand-computed values):
  - `sma`/`ema` on a known series (exact); warmup leading nulls of correct length.
  - `rsi` matches a textbook 14-period example (±1e-6).
  - `macd` → macd/signal/histogram on a known series.
  - `bollinger` → mid=SMA20, upper/lower = mid ±2σ.
- **`strategies.test.ts`** (extend): `getOhlcv` parses OHLCV, sorts, dedups dates, missing→[]; `listTickers` returns stems, drops `^`-files, missing dir→[].
- **Typecheck/build:** `cd web && npx tsc --noEmit && npm run build`.
- **Run verification (slice end):** `npm run dev`; `/strategy/momentum_edge` shows the candlestick chart for the default ticker; the picker search switches ticker (URL `?chart=` updates, chart reloads); toggles show/hide each indicator; `/strategy/monthly_rotation` shows NO chart; existing sections + other routes unaffected.

## 10. Open Questions

| Question | Resolution |
|---|---|
| LWC v5 candlestick/multi-pane API? | `addSeries(CandlestickSeries, …)`, `addSeries(HistogramSeries, …)`; panes via the v5 pane API (`{ pane: n }` or `addPane`). Confirm exact v5.x signature against installed types during build. |
| Default SMA/EMA periods? | SMA 50 + 200, EMA 21 (common). Bollinger 20/2, RSI 14, MACD 12/26/9 (match core). |
| Bar cap? | ~1500 most-recent (≈6y daily) — enough context, keeps the chart responsive. |
| PEAD OHLCV folder? | `data/nse_bse` (PEAD trades the wide universe). Confirm a sample PEAD ticker resolves during the run. |
| Ticker `.NS` suffix mismatch (signals vs folder stems)? | `defaultTicker` normalizes to the folder's stem convention; if no match, fall back to `tickers[0]`. |

## 11. Future (program context)

Slice B — per-signal conditions checklist; Slice C — strategy-health panel. Then per-strategy live screeners, write-action API, cloud — all reuse the loader seam.
