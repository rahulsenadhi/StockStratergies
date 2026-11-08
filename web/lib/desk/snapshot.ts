import fs from "node:fs/promises";
import path from "node:path";
import { isObj, loadVersionedJson } from "@/lib/desk/versioned-json";
import type { Tone } from "@/lib/desk/format";

/** Written by precompute_ui_home.py after every data update (schema version 1). */
export const SNAPSHOT_FILE = "ui_snapshot.json";
export const SNAPSHOT_VERSION = 1;
const DEFAULT_DATA_DIR = process.env.DATA_DIR ?? "..";

export interface Regime {
  status?: "Bull" | "Bear" | "Unknown" | string;
  bars_since_flip?: number | null;
  close?: number | null;
  sma50?: number | null;
  sma200?: number | null;
  high52?: number | null;
  pct_from_high?: number | null;
  date?: string;
}

export interface PriceFreshness {
  latest_bar?: string;
  file_mtime?: string;
  age_hours?: number | null;
  source_file?: string;
}

export interface Candidate {
  strategy: string;
  short: string;
  ticker: string;
  company: string;
  status: string;
  status_tone: Tone;
  key_measure: string;
  change: number | null;
  data: string;
}

export interface StrategyRow {
  id: string;
  title: string;
  status: string;
  num_trades: number;
  unit: string;
  small_sample: boolean;
  max_dd_pct: number;
  cagr_pct: number;
}

export interface GrowthSeries {
  id: string;
  title: string;
  colour: string;
  start: string;
  last_pct: number | null;
  points: [string, number][];
}

export type GrowthWindow = "1Y" | "3Y" | "5Y" | "Max";

export interface UiSnapshot {
  version: number;
  generated_at: string;
  frame: { regime: Regime; freshness: PriceFreshness };
  home: {
    candidates: Candidate[];
    pead_has_signals: boolean;
    strategies: StrategyRow[];
    growth: Record<GrowthWindow, GrowthSeries[]>;
  };
}

export type SnapshotResult =
  | { ok: true; snapshot: UiSnapshot }
  | { ok: false; reason: "missing" | "invalid" | "version" };

function hasShape(v: Record<string, unknown>): boolean {
  const { frame, home } = v;
  if (!isObj(frame) || !isObj(home)) return false;
  if (!isObj(frame.regime) || !isObj(frame.freshness)) return false;
  return Array.isArray(home.candidates) && Array.isArray(home.strategies) && isObj(home.growth);
}

/**
 * The snapshot stores the price file's age as of when it was written. Re-measure it now
 * from that file (Python _data_freshness used the same file) so "Data updated …" and
 * "Prices up to … · N days old" age between updates. Returns a new snapshot.
 */
export async function withLiveFreshness(
  snapshot: UiSnapshot,
  dataDir: string = DEFAULT_DATA_DIR,
  now: Date = new Date(),
): Promise<UiSnapshot> {
  const rel = snapshot.frame.freshness.source_file;
  if (!rel) return snapshot;
  try {
    const { mtimeMs } = await fs.stat(path.join(dataDir, ...rel.split(/[\\/]/)));
    const age_hours = Math.max(0, (now.getTime() - mtimeMs) / 3_600_000);
    return { ...snapshot, frame: { ...snapshot.frame, freshness: { ...snapshot.frame.freshness, age_hours } } };
  } catch {
    return snapshot;
  }
}

/** Read and check the saved snapshot. Never throws: a broken file becomes an empty state. */
export async function loadSnapshot(dataDir: string = DEFAULT_DATA_DIR): Promise<SnapshotResult> {
  const res = await loadVersionedJson(path.join(dataDir, SNAPSHOT_FILE), SNAPSHOT_VERSION, hasShape);
  return res.ok ? { ok: true, snapshot: res.value as unknown as UiSnapshot } : res;
}
