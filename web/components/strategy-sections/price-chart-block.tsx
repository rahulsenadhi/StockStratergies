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
