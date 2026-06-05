import { promises as fs } from "fs";
import path from "path";

const DEFAULT_DATA_DIR = process.env.DATA_DIR ?? "..";

export type Kpis = {
  cagr: number; totalReturn: number; volatility: number; sharpe: number; maxDd: number;
  calmar: number | null; winRate: number | null; numTrades: number;
  alpha: number | null; finalEquity: number;
};

export type Strategy = {
  id: string; name: string; type: string; status: string;
  kpis: Kpis; rank: number | null; rankScore: number | null;
  equityCsv: string | null; kpisError?: string;
};

const num = (v: unknown): number => (typeof v === "number" && !Number.isNaN(v) ? v : 0);
const numOrNull = (v: unknown): number | null =>
  typeof v === "number" && !Number.isNaN(v) ? v : null;

export function mapStrategy(raw: any): Strategy {
  const k = raw.kpis_inline ?? {};
  const s: Strategy = {
    id: raw.id,
    name: raw.name ?? raw.id,
    type: raw.type ?? "—",
    status: raw.status ?? "—",
    kpis: {
      cagr: num(k.cagr), totalReturn: num(k.total_return), volatility: num(k.volatility),
      sharpe: num(k.sharpe), maxDd: num(k.max_dd), calmar: numOrNull(k.calmar),
      winRate: numOrNull(k.win_rate), numTrades: num(k.num_trades),
      alpha: numOrNull(k.alpha), finalEquity: num(k.final_equity),
    },
    rank: numOrNull(raw.rank),
    rankScore: numOrNull(raw.rank_score),
    equityCsv: raw.equity_csv ?? null,
  };
  if (raw.kpis_error) s.kpisError = raw.kpis_error;
  return s;
}

export async function getStrategies(dataDir: string = DEFAULT_DATA_DIR): Promise<Strategy[]> {
  try {
    const txt = await fs.readFile(path.join(dataDir, "strategies_index.json"), "utf-8");
    const data = JSON.parse(txt);
    const list: Strategy[] = (data.strategies ?? []).map(mapStrategy);
    list.sort((a, b) => (a.rank ?? 9999) - (b.rank ?? 9999));
    return list;
  } catch {
    return [];
  }
}

const EQUITY_COLS = ["Portfolio_Value", "Equity", "equity"];
const MAX_POINTS = 80;

export async function getEquitySeries(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<number[]> {
  if (!csv) return [];
  try {
    const txt = await fs.readFile(path.join(dataDir, csv), "utf-8");
    const lines = txt.trim().split(/\r?\n/);
    if (lines.length < 2) return [];
    const header = lines[0].split(",");
    let idx = -1;
    for (const c of EQUITY_COLS) {
      idx = header.indexOf(c);
      if (idx >= 0) break;
    }
    if (idx < 0) {
      const first = lines[1].split(",");
      idx = header.findIndex((_, i) => i > 0 && !Number.isNaN(Number(first[i])));
    }
    if (idx < 0) return [];
    const vals = lines
      .slice(1)
      .map((l) => Number(l.split(",")[idx]))
      .filter((v) => !Number.isNaN(v));
    const step = Math.max(1, Math.floor(vals.length / MAX_POINTS));
    return vals.filter((_, i) => i % step === 0);
  } catch {
    return [];
  }
}
