import { promises as fs } from "fs";
import path from "path";

const DEFAULT_DATA_DIR = process.env.DATA_DIR ?? "..";

export type Kpis = {
  cagr: number | null; totalReturn: number | null; volatility: number | null; sharpe: number | null; maxDd: number | null;
  calmar: number | null; winRate: number | null; numTrades: number | null;
  alpha: number | null; finalEquity: number | null;
};

export type Strategy = {
  id: string; name: string; type: string; status: string;
  kpis: Kpis; rank: number | null; rankScore: number | null;
  equityCsv: string | null; tradesCsv: string | null; lastRun: string | null; liveSignalsCsv: string | null;
  funnelJson: string | null; recentBreakoutsCsv: string | null; decileSpreadCsv: string | null;
  backtest: string[] | null; kpisError?: string;
};

const numOrNull = (v: unknown): number | null =>
  typeof v === "number" && !Number.isNaN(v) ? v : null;

export type ParsedCsv = { header: string[]; rows: string[][] };

/** Read a CSV: trim, split on newlines, require >=1 data row, return header + raw row cells.
 *  Missing/unreadable/header-only -> { header: [], rows: [] }. Best-effort, never throws. */
export async function parseCsvLines(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
  lowercaseHeader = false,
): Promise<ParsedCsv> {
  if (!csv) return { header: [], rows: [] };
  try {
    const txt = await fs.readFile(path.join(dataDir, csv), "utf-8");
    const lines = txt.trim().split(/\r?\n/);
    if (lines.length < 2) return { header: [], rows: [] };
    const header = lines[0].split(",").map((h) => {
      const t = h.trim();
      return lowercaseHeader ? t.toLowerCase() : t;
    });
    const rows = lines.slice(1).map((l) => l.split(","));
    return { header, rows };
  } catch {
    return { header: [], rows: [] };
  }
}

const cell = (cells: string[], i: number): string =>
  i >= 0 ? (cells[i] ?? "").trim() : "";

const numCell = (cells: string[], i: number): number | null => {
  const v = cell(cells, i);
  if (v === "") return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
};

export function mapStrategy(raw: any): Strategy {
  const k = raw.kpis_inline ?? {};
  const errored = Boolean(raw.kpis_error);
  const kv = (v: unknown) => (errored ? null : numOrNull(v));
  const s: Strategy = {
    id: raw.id,
    name: raw.name ?? raw.id,
    type: raw.type ?? "—",
    status: raw.status ?? "—",
    kpis: {
      cagr: kv(k.cagr), totalReturn: kv(k.total_return), volatility: kv(k.volatility),
      sharpe: kv(k.sharpe), maxDd: kv(k.max_dd), calmar: kv(k.calmar),
      winRate: kv(k.win_rate), numTrades: kv(k.num_trades),
      alpha: kv(k.alpha), finalEquity: kv(k.final_equity),
    },
    rank: numOrNull(raw.rank),
    rankScore: numOrNull(raw.rank_score),
    equityCsv: raw.equity_csv ?? null,
    tradesCsv: raw.trades_csv ?? null,
    lastRun: raw.last_run ?? null,
    liveSignalsCsv: raw.live_signals_csv ?? null,
    funnelJson: raw.funnel_json ?? null,
    recentBreakoutsCsv: raw.recent_breakouts_csv ?? null,
    decileSpreadCsv: raw.decile_spread_csv ?? null,
    backtest:
      Array.isArray(raw.backtest) && raw.backtest.every((x: unknown) => typeof x === "string")
        ? raw.backtest
        : null,
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

export async function getStrategy(
  id: string,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<Strategy | null> {
  const all = await getStrategies(dataDir);
  return all.find((s) => s.id === id) ?? null;
}

const EQUITY_COLS = ["Portfolio_Value", "Equity", "equity"];

export type EquityPoint = { time: string; value: number };
const MAX_CURVE_POINTS = 2000;
const DATE_COLS = ["Date", "date", "Datetime"];

export async function readEquityCurveRaw(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<EquityPoint[]> {
  if (!csv) return [];
  try {
    const txt = await fs.readFile(path.join(dataDir, csv), "utf-8");
    const lines = txt.trim().split(/\r?\n/);
    if (lines.length < 2) return [];
    const header = lines[0].split(",").map((h) => h.trim());
    const dateIdx = header.findIndex((h) => DATE_COLS.includes(h));
    const di = dateIdx >= 0 ? dateIdx : 0;
    let vi = -1;
    for (const c of EQUITY_COLS) {
      vi = header.indexOf(c);
      if (vi >= 0) break;
    }
    if (vi < 0) {
      const first = lines[1].split(",");
      vi = header.findIndex((_, i) => i !== di && !Number.isNaN(Number(first[i])));
    }
    if (vi < 0) return [];
    let pts: EquityPoint[] = lines
      .slice(1)
      .map((l) => {
        const cells = l.split(",");
        return { time: String(cells[di] ?? "").slice(0, 10), value: Number(cells[vi]) };
      })
      .filter((p) => p.time !== "" && !Number.isNaN(p.value));
    pts.sort((a, b) => a.time.localeCompare(b.time));
    const deduped: EquityPoint[] = [];
    for (const p of pts) {
      if (deduped.length && deduped[deduped.length - 1].time === p.time) {
        deduped[deduped.length - 1] = p; // keep last value for a repeated date
      } else {
        deduped.push(p);
      }
    }
    return deduped;
  } catch {
    return [];
  }
}

export async function getEquityCurve(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<EquityPoint[]> {
  let pts = await readEquityCurveRaw(csv, dataDir);
  if (pts.length > MAX_CURVE_POINTS) {
    const step = Math.ceil(pts.length / MAX_CURVE_POINTS);
    const sampled = pts.filter((_, i) => i % step === 0);
    const last = pts[pts.length - 1];
    if (sampled[sampled.length - 1] !== last) sampled.push(last);
    pts = sampled;
  }
  return pts;
}

export type MonthlyReturnsRow = {
  year: number;
  months: (number | null)[]; // length 12, index 0 = Jan
  annual: number | null;
};

export async function getMonthlyReturns(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<MonthlyReturnsRow[]> {
  const curve = await readEquityCurveRaw(csv, dataDir);
  if (curve.length < 2) return [];

  const anchor = curve[0].value; // series opening value

  // Month-end value per YYYY-MM: last value that month (curve already sorted asc).
  const monthEnds = new Map<string, number>();
  for (const p of curve) {
    monthEnds.set(p.time.slice(0, 7), p.value);
  }

  let prev = anchor;
  const byYear = new Map<number, MonthlyReturnsRow>();
  for (const key of [...monthEnds.keys()].sort()) {
    const year = Number(key.slice(0, 4));
    const monthIdx = Number(key.slice(5, 7)) - 1; // 0-11
    const monthEnd = monthEnds.get(key)!;
    const r = prev > 0 ? monthEnd / prev - 1 : null;
    prev = monthEnd; // advance anchor to this month-end regardless

    let row = byYear.get(year);
    if (!row) {
      row = { year, months: Array(12).fill(null), annual: null };
      byYear.set(year, row);
    }
    row.months[monthIdx] = r;
  }

  const rows = [...byYear.values()].sort((a, b) => a.year - b.year);
  for (const row of rows) {
    const present = row.months.filter((m): m is number => m != null);
    row.annual = present.length
      ? present.reduce((acc, m) => acc * (1 + m), 1) - 1
      : null;
  }
  return rows;
}

export function computeDrawdown(curve: EquityPoint[]): EquityPoint[] {
  let peak = -Infinity;
  return curve.map((p) => {
    peak = Math.max(peak, p.value);
    const value = peak > 0 ? p.value / peak - 1 : 0;
    return { time: p.time, value };
  });
}

export function rebaseToReturn(curve: EquityPoint[]): EquityPoint[] {
  if (curve.length === 0) return [];
  const v0 = curve[0].value;
  if (v0 <= 0) return [];
  return curve.map((p) => ({ time: p.time, value: p.value / v0 - 1 }));
}

/** CAGR from a dated equity curve. Expects RAW absolute values (not rebased — a rebased series starts at 0 and returns null). */
export function annualizedReturn(curve: EquityPoint[]): number | null {
  if (curve.length < 2) return null;
  const first = curve[0];
  const last = curve[curve.length - 1];
  if (first.value <= 0) return null;
  const days =
    (new Date(last.time).getTime() - new Date(first.time).getTime()) / 86_400_000;
  const years = Math.max(days / 365.25, 0.01);
  return Math.pow(last.value / first.value, 1 / years) - 1;
}

const BENCHMARK_COL = "Benchmark_Value";

export type EquityWithBenchmark = {
  strategy: EquityPoint[];
  benchmark: EquityPoint[];
  benchmarkCagr: number | null;
};

export async function getEquityWithBenchmark(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<EquityWithBenchmark> {
  const empty: EquityWithBenchmark = { strategy: [], benchmark: [], benchmarkCagr: null };
  if (!csv) return empty;
  try {
    const rawStrategy = await getEquityCurve(csv, dataDir);
    const strategy = rebaseToReturn(rawStrategy);
    const txt = await fs.readFile(path.join(dataDir, csv), "utf-8");
    const lines = txt.trim().split(/\r?\n/);
    if (lines.length < 2) return { strategy, benchmark: [], benchmarkCagr: null };
    const header = lines[0].split(",").map((h) => h.trim());
    const dateIdx = header.findIndex((h) => DATE_COLS.includes(h));
    const di = dateIdx >= 0 ? dateIdx : 0;
    const bi = header.indexOf(BENCHMARK_COL);
    if (bi < 0) return { strategy, benchmark: [], benchmarkCagr: null };
    // Deliberate second read: parse the benchmark column independently of getEquityCurve.
    // Consistent with this module's simple no-cache, per-call-read contract.
    const rawBench: EquityPoint[] = lines
      .slice(1)
      .map((l) => {
        const cells = l.split(",");
        return { time: String(cells[di] ?? "").slice(0, 10), value: Number(cells[bi]) };
      })
      .filter((p) => p.time !== "" && !Number.isNaN(p.value));
    rawBench.sort((a, b) => a.time.localeCompare(b.time));
    return {
      strategy,
      benchmark: rebaseToReturn(rawBench),
      benchmarkCagr: annualizedReturn(rawBench),
    };
  } catch {
    return empty;
  }
}

export type TradesData = { columns: string[]; rows: Record<string, string>[] };
const MAX_TRADE_COLS = 8;

export async function getTrades(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<TradesData> {
  if (!csv) return { columns: [], rows: [] };
  try {
    const txt = await fs.readFile(path.join(dataDir, csv), "utf-8");
    const lines = txt.trim().split(/\r?\n/);
    if (lines.length < 2) return { columns: [], rows: [] };
    const columns = lines[0].split(",").map((h) => h.trim()).slice(0, MAX_TRADE_COLS);
    const rows = lines.slice(1).map((l) => {
      const cells = l.split(",");
      const row: Record<string, string> = {};
      columns.forEach((c, i) => {
        row[c] = (cells[i] ?? "").trim();
      });
      return row;
    });
    return { columns, rows };
  } catch {
    return { columns: [], rows: [] };
  }
}

export type LiveSignal = { ticker: string; company: string; signal: string };
const LIVE_LIMIT = 5;

export async function getLiveSignals(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
  limit: number = LIVE_LIMIT,
): Promise<LiveSignal[]> {
  const { header, rows } = await parseCsvLines(csv, dataDir, true);
  if (header.length === 0) return [];
  const ti = header.indexOf("ticker");
  const ci = header.indexOf("company");
  const si = header.indexOf("signal");
  if (ti < 0 || si < 0) return [];
  return rows
    .slice(0, limit)
    .map((cells) => {
      const ticker = cell(cells, ti);
      return {
        ticker,
        company: ci >= 0 && cell(cells, ci) !== "" ? cell(cells, ci) : ticker,
        signal: cell(cells, si),
      };
    })
    .filter((r) => r.ticker !== "");
}

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
    const step = Math.max(1, Math.ceil(vals.length / MAX_POINTS));
    return vals.filter((_, i) => i % step === 0);
  } catch {
    return [];
  }
}

export type DecilePoint = { decile: number; fwdReturn: number };

/** PEAD SUE-decile -> forward 60d return. Case-insensitive header, bad rows skipped, sorted by decile asc. */
export async function getDecileSpread(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<DecilePoint[]> {
  const { header, rows } = await parseCsvLines(csv, dataDir, true);
  if (header.length === 0) return [];
  const di = header.indexOf("sue_decile");
  const fi = header.indexOf("fwd_60d_return");
  if (di < 0 || fi < 0) return [];
  const out: DecilePoint[] = [];
  for (const cells of rows) {
    const decile = numCell(cells, di);
    const fwdReturn = numCell(cells, fi);
    if (decile === null || fwdReturn === null) continue;
    out.push({ decile, fwdReturn });
  }
  out.sort((a, b) => a.decile - b.decile);
  return out;
}

const BREAKOUTS_LIMIT = 10;

/** Live breakout watchlist. Full column set (TradesData shape, no col cap). Top-N rows. */
export async function getRecentBreakouts(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
  limit: number = BREAKOUTS_LIMIT,
): Promise<TradesData> {
  const { header, rows } = await parseCsvLines(csv, dataDir);
  if (header.length === 0) return { columns: [], rows: [] };
  const out = rows.slice(0, limit).map((cells) => {
    const row: Record<string, string> = {};
    header.forEach((c, i) => {
      row[c] = (cells[i] ?? "").trim();
    });
    return row;
  });
  return { columns: header, rows: out };
}

export type FunnelStage = { label: string; value: number };

const FUNNEL_STAGES: { key: string; label: string }[] = [
  { key: "total", label: "Universe" },
  { key: "sufficient_data", label: "Has Data" },
  { key: "f1", label: "F1 Trend" },
  { key: "f2", label: "F2 Price > SMA50" },
  { key: "f3", label: "F3 MA Align" },
  { key: "f4", label: "F4 vs 52W Low" },
  { key: "f5", label: "F5 Dip Recovered" },
  { key: "f6", label: "F6 Clean Chart" },
  { key: "vol_bk", label: "Vol + Breakout" },
];

/** Momentum filter funnel: fixed key->label map. Missing key -> 0. Unreadable/bad JSON -> []. */
export async function getFunnel(
  jsonPath: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<FunnelStage[]> {
  if (!jsonPath) return [];
  try {
    const txt = await fs.readFile(path.join(dataDir, jsonPath), "utf-8");
    const raw: unknown = JSON.parse(txt);
    if (raw === null || typeof raw !== "object" || Array.isArray(raw)) return [];
    const data = raw as Record<string, unknown>;
    return FUNNEL_STAGES.map(({ key, label }) => {
      const v = data[key];
      return {
        label,
        value: typeof v === "number" && !Number.isNaN(v) ? v : 0,
      };
    });
  } catch {
    return [];
  }
}

export type RankingRow = {
  rank: number | null;
  ticker: string;
  company: string;
  price: number | null;
  returnPct: number | null;
  rsScore: number | null;
  signal: string;
};

/** One edge-filtered, regime-gated pick from the Suggestions feed. */
export type SuggestionPick = {
  rank: number;
  ticker: string;
  company: string;
  strategy: string;
  strategyId: string;
  signal: string;
  close: number;
  stop: number;
  target: number;
  rr: number;
  confidence: number;
  avgPnl: number;
  nHist: number;
  positionPct: number;
  edgeScore: number;
  rationale: string;
};

export type SuggestionsRegime = {
  status: string;
  barsSinceFlip: number;
  close?: number;
  sma50?: number;
  sma200?: number;
  high52?: number;
  pctFromHigh?: number;
  date?: string;
};

export type SuggestionsFeed = {
  regime: SuggestionsRegime;
  summary: {
    picks: number;
    avgConfidence: number;
    totalAllocation: number;
    cashReserve: number;
  };
  picks: SuggestionPick[];
};

// ── Data freshness (port of master_dashboard.py _data_freshness ~L7486) ──────
const FRESHNESS_FOLDERS = ["data/nse_bse", "data", "momentum_edge_data"];
const FRESHNESS_PROBES = ["RELIANCE.NS.csv", "HDFCBANK.NS.csv", "INFY.NS.csv"];

export type DataFreshness = {
  /** Latest bar date (YYYY-MM-DD) across probe files, or null. */
  latestBar: string | null;
  /** Hours since the newest probe-file mtime, or null. */
  ageHours: number | null;
  /** Repo-relative path of the newest probe file, or null. */
  sourceFile: string | null;
};

export type FreshnessTier = {
  label: string;
  tone: "fresh" | "stale" | "old" | "none";
};

/** Chip label + tone from age. Fresh <24h, stale 24-72h, old >72h (port of the
 *  Streamlit freshness chip thresholds). */
export function freshnessTier(ageHours: number | null): FreshnessTier {
  if (ageHours == null) return { label: "No data", tone: "none" };
  if (ageHours < 24) return { label: `${ageHours.toFixed(1)}h ago`, tone: "fresh" };
  if (ageHours < 72) return { label: `${Math.round(ageHours)}h ago`, tone: "stale" };
  return { label: `${Math.round(ageHours / 24)}d ago`, tone: "old" };
}

export async function getDataFreshness(
  dataDir: string = DEFAULT_DATA_DIR,
  now: number = Date.now(),
): Promise<DataFreshness> {
  let latestBar: string | null = null;
  let newestMtime = 0;
  let newestFile: string | null = null;

  for (const folder of FRESHNESS_FOLDERS) {
    for (const probe of FRESHNESS_PROBES) {
      const p = path.join(dataDir, folder, probe);
      try {
        const stat = await fs.stat(p);
        const txt = await fs.readFile(p, "utf-8");
        const lines = txt.trim().split(/\r?\n/);
        const bar = lines[lines.length - 1]?.split(",")[0]?.slice(0, 10);
        if (bar && (latestBar == null || bar > latestBar)) latestBar = bar;
        if (stat.mtimeMs > newestMtime) {
          newestMtime = stat.mtimeMs;
          newestFile = `${folder}/${probe}`;
        }
        break; // first existing probe per folder, like _data_freshness
      } catch {
        continue;
      }
    }
  }

  if (latestBar == null) return { latestBar: null, ageHours: null, sourceFile: null };
  return {
    latestBar,
    ageHours: Math.round(((now - newestMtime) / 3_600_000) * 10) / 10,
    sourceFile: newestFile,
  };
}

/** Read the precomputed Suggestions feed (precompute_suggestions.py -> suggestions.json).
 *  Already camelCased by the precompute. Best-effort: null on missing/unreadable/malformed. */
export async function getSuggestions(
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<SuggestionsFeed | null> {
  try {
    const txt = await fs.readFile(path.join(dataDir, "suggestions.json"), "utf-8");
    const raw: unknown = JSON.parse(txt);
    if (
      raw === null ||
      typeof raw !== "object" ||
      !Array.isArray((raw as SuggestionsFeed).picks) ||
      typeof (raw as SuggestionsFeed).regime !== "object"
    ) {
      return null;
    }
    return raw as SuggestionsFeed;
  } catch {
    return null;
  }
}

const stripSignal = (s: string): string =>
  s.replace(/^[🟢🔴]\s*/u, "").trim();

export function deriveStrategyId(name: string): string {
  return name.trim().toLowerCase().replace(/[ -]/g, "_");
}

export type ExitsSpec = {
  time_enabled?: boolean; time_days?: number;
  hard_stop_enabled?: boolean; hard_stop_pct?: number;
  trail_enabled?: boolean; trail_pct?: number;
};

/** Human summary of enabled exits (port of Streamlit _summarize_exits). */
export function summarizeExits(ex: ExitsSpec): string {
  const parts: string[] = [];
  if (ex.time_enabled) parts.push(`hold ${ex.time_days ?? 60}d`);
  if (ex.hard_stop_enabled) parts.push(`hard stop ${ex.hard_stop_pct ?? 10}%`);
  if (ex.trail_enabled) parts.push(`trail ${ex.trail_pct ?? 8}%`);
  return parts.length ? parts.join(" · ") : "—";
}

export type StrategyFields = {
  entry_formula?: unknown;
  exits?: ExitsSpec;
  sizing?: Record<string, unknown>;
};

export type ValidationResult = { ok: true } | { ok: false; error: string };

/** Validate the spec fields shared by create + edit (NOT name/sid — those are
 *  create-only). entry_formula required, >=1 exit enabled, sizing positive. */
export function validateStrategyFields(body: StrategyFields): ValidationResult {
  const entryFormula = typeof body.entry_formula === "string" ? body.entry_formula.trim() : "";
  if (!entryFormula) return { ok: false, error: "entry formula is required" };

  const exits: ExitsSpec = body.exits ?? {};
  if (!exits.time_enabled && !exits.hard_stop_enabled && !exits.trail_enabled) {
    return { ok: false, error: "enable at least one exit rule" };
  }

  const sizing = body.sizing ?? {};
  const maxPositions = Number(sizing.max_positions);
  const initialCash = Number(sizing.initial_cash);
  if (!(maxPositions > 0) || !(initialCash > 0)) {
    return { ok: false, error: "max positions and initial cash must be positive numbers" };
  }
  return { ok: true };
}

export type StrategyStub = {
  id: string; name: string; type: string; status: string; description: string;
  universe: string; entry_rule: string; exit_rule: string;
  sizing: Record<string, unknown>;
  trades_csv: string; equity_csv: string; kpis_inline: Record<string, never>;
  last_run: string; created: string; page_key: string;
};

async function atomicWrite(filePath: string, contents: string): Promise<void> {
  const tmp = `${filePath}.${process.pid}.tmp`;
  await fs.writeFile(tmp, contents);
  await fs.rename(tmp, filePath);
}

/** Atomically write strategies/{sid}.json under dataDir. */
export async function writeStrategySpec(
  sid: string, spec: unknown, dataDir: string = DEFAULT_DATA_DIR,
): Promise<void> {
  const specDir = path.join(dataDir, "strategies");
  await fs.mkdir(specDir, { recursive: true });
  await atomicWrite(path.join(specDir, `${sid}.json`), JSON.stringify(spec, null, 2));
}

/** Append a Research stub to strategies_index.json; throws if the id already exists. */
export async function appendStrategyStub(
  stub: StrategyStub, dataDir: string = DEFAULT_DATA_DIR,
): Promise<void> {
  const idxPath = path.join(dataDir, "strategies_index.json");
  const idx = JSON.parse(await fs.readFile(idxPath, "utf-8")) as {
    strategies: Array<{ id: string }>;
  };
  if (idx.strategies.some((s) => s.id === stub.id)) {
    throw new Error(`strategy id already exists: ${stub.id}`);
  }
  idx.strategies.push(stub);
  await atomicWrite(idxPath, JSON.stringify(idx, null, 2));
}

/** Read strategies/{id}.json -> parsed object, or null if absent/unparseable.
 *  Doubles as the user-created eligibility probe (built-ins have no spec file). */
export async function getStrategySpec(
  id: string, dataDir: string = DEFAULT_DATA_DIR,
): Promise<Record<string, unknown> | null> {
  try {
    const txt = await fs.readFile(path.join(dataDir, "strategies", `${id}.json`), "utf-8");
    const parsed = JSON.parse(txt);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

/** Shallow-merge `patch` into the strategies_index.json entry with `id`.
 *  Throws if the id is absent. Atomic write, indent=2 (matches refresh_all). */
export async function updateStrategyIndexEntry(
  id: string, patch: Record<string, unknown>, dataDir: string = DEFAULT_DATA_DIR,
): Promise<void> {
  const idxPath = path.join(dataDir, "strategies_index.json");
  const idx = JSON.parse(await fs.readFile(idxPath, "utf-8")) as {
    strategies: Array<Record<string, unknown> & { id: string }>;
  };
  const i = idx.strategies.findIndex((s) => s.id === id);
  if (i < 0) throw new Error(`strategy not found: ${id}`);
  idx.strategies[i] = { ...idx.strategies[i], ...patch };
  await atomicWrite(idxPath, JSON.stringify(idx, null, 2));
}

/** Remove a strategy: index entry + strategies/{id}.json + its trades_csv/equity_csv.
 *  Returns false if the id is absent. File unlinks are best-effort (swallow ENOENT). */
export async function deleteStrategy(
  id: string, dataDir: string = DEFAULT_DATA_DIR,
): Promise<boolean> {
  const idxPath = path.join(dataDir, "strategies_index.json");
  const idx = JSON.parse(await fs.readFile(idxPath, "utf-8")) as {
    strategies: Array<Record<string, unknown> & { id: string }>;
  };
  const entry = idx.strategies.find((s) => s.id === id);
  if (!entry) return false;

  const csvs = [entry.trades_csv, entry.equity_csv].filter(
    (c): c is string => typeof c === "string" && c !== "",
  );
  idx.strategies = idx.strategies.filter((s) => s.id !== id);
  await atomicWrite(idxPath, JSON.stringify(idx, null, 2));

  const unlinkQuiet = async (p: string) => {
    try {
      await fs.unlink(path.join(dataDir, p));
    } catch {
      // already gone — best-effort
    }
  };
  await unlinkQuiet(path.join("strategies", `${id}.json`));
  // generic_backtest.py writes strategies/{id}_kpis.csv but does not record it in the
  // index entry (KPIs live in kpis_inline), so remove it by convention too.
  await unlinkQuiet(path.join("strategies", `${id}_kpis.csv`));
  for (const c of csvs) await unlinkQuiet(c);
  return true;
}

export async function getRankings(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<RankingRow[]> {
  const { header, rows } = await parseCsvLines(csv, dataDir, true);
  if (header.length === 0) return [];
  const idx = (name: string) => header.indexOf(name);
  const ti = idx("ticker");
  if (ti < 0) return [];
  const si = idx("signal");
  const ri = idx("rank");
  const ci = idx("company");
  const pi = idx("current_price");
  const reti = idx("return_%");
  const rsi = idx("rs_score");
  return rows
    .map((cells) => {
      const ticker = cell(cells, ti).replace(/\.NS$/, "");
      const company = ci >= 0 && cell(cells, ci) !== "" ? cell(cells, ci) : ticker;
      return {
        rank: numCell(cells, ri),
        ticker,
        company,
        price: numCell(cells, pi),
        returnPct: numCell(cells, reti),
        rsScore: numCell(cells, rsi),
        signal: si >= 0 ? stripSignal(cell(cells, si)) : "",
      };
    })
    .filter((r) => r.ticker !== "");
}

export type SignalAction = "BUY NOW" | "WATCH" | "FORMING" | string;

export interface ActionableSignal {
  ticker: string;
  company: string;
  signal: string;
  action: SignalAction;
  close: number | null;
  stopPrice: number | null;
  stopPct: number;
  score: number | null;
  entryType: string;
  distAthPct: number | null;
  recovery: string;
  volRatio: number | null;
}

const ACTION_MAP: Record<string, string> = {
  "Breakout Today": "BUY NOW",
  "Near Breakout": "WATCH",
  "Watch Zone": "FORMING",
};

/** Rich live-signals loader used by the "what to buy now" screen.
 *  Reads <dataDir>/<csv>, derives Action label + 15% hard stop per row.
 *  Missing/empty/unreadable file → []. Never throws. */
export async function getActionableSignals(
  csv: string,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<ActionableSignal[]> {
  const { header, rows } = await parseCsvLines(csv, dataDir, true);
  if (header.length === 0) return [];
  const idx = (name: string) => header.indexOf(name.toLowerCase());
  const ti = idx("ticker");
  if (ti < 0) return [];
  const ci = idx("company");
  const si = idx("signal");
  const closi = idx("close");
  const scorei = idx("score");
  const entryTypei = idx("entry type");
  const distAthPcti = idx("dist ath%");
  const recoveryi = idx("recovery");
  const volRatioi = idx("vol ratio");

  const out: ActionableSignal[] = [];
  for (const cells of rows) {
    const ticker = cell(cells, ti);
    if (ticker === "") continue;
    const company = ci >= 0 && cell(cells, ci) !== "" ? cell(cells, ci) : ticker;
    const signal = si >= 0 ? cell(cells, si) : "";
    const close = numCell(cells, closi);
    const stopPrice =
      close === null ? null : Math.round(close * 0.85 * 100) / 100;
    const action = ACTION_MAP[signal] ?? (signal || "—");
    out.push({
      ticker,
      company,
      signal,
      action,
      close,
      stopPrice,
      stopPct: -15,
      score: numCell(cells, scorei),
      entryType: entryTypei >= 0 ? cell(cells, entryTypei) : "",
      distAthPct: numCell(cells, distAthPcti),
      recovery: recoveryi >= 0 ? cell(cells, recoveryi) : "",
      volRatio: numCell(cells, volRatioi),
    });
  }
  return out;
}

export interface ExitTarget {
  pct: number;
  bookPct: number;
  hitRate: number;
}

export interface ExitPlaybook {
  holdDays: number;
  holdMedianReturn: number;
  holdWinRate: number;
  targets: ExitTarget[];
  stopPct: number;
  sampleSize: number;
  dataQuality: "ohlcv" | "close";
  curve: { day: number; median: number }[];
}

/** Read exit_recommendations.json from dataDir and return the ALL-bucket recommendation
 *  for the given strategy id, with snake_case keys mapped to camelCase.
 *  Returns null on any error (missing file, bad JSON, unknown strategy). */
export async function getExitPlaybook(
  id: string,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<ExitPlaybook | null> {
  try {
    const txt = await fs.readFile(path.join(dataDir, "exit_recommendations.json"), "utf-8");
    const parsed: unknown = JSON.parse(txt);
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) return null;
    const data = parsed as Record<string, unknown>;
    const stratEntry = data[id];
    if (stratEntry === null || typeof stratEntry !== "object" || Array.isArray(stratEntry)) return null;
    const buckets = stratEntry as Record<string, unknown>;
    const rec = buckets["ALL"];
    if (rec === null || typeof rec !== "object" || Array.isArray(rec)) return null;
    const r = rec as Record<string, unknown>;
    return {
      holdDays: r.hold_days as number,
      holdMedianReturn: r.hold_median_return as number,
      holdWinRate: r.hold_win_rate as number,
      targets: (r.targets as Array<Record<string, number>>).map((t) => ({
        pct: t.pct,
        bookPct: t.book_pct,
        hitRate: t.hit_rate,
      })),
      stopPct: r.stop_pct as number,
      sampleSize: r.sample_size as number,
      dataQuality: r.data_quality as "ohlcv" | "close",
      curve: (r.curve as Array<Record<string, number>>).map((c) => ({
        day: c.day,
        median: c.median,
      })),
    };
  } catch {
    return null;
  }
}
