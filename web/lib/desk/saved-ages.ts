import fs from "node:fs/promises";
import path from "node:path";

const DEFAULT_DATA_DIR = process.env.DATA_DIR ?? "..";
const DAY_MS = 86_400_000;

export type SavedName = "Monthly" | "IPO Edge" | "Momentum" | "PEAD";
export interface SavedAge {
  name: SavedName;
  ageDays: number | null;
}

/** Same files and order as master_dashboard._saved_data_ages. */
const SAVED_FILES: readonly [SavedName, string][] = [
  ["Monthly", "live_rankings.csv"],
  ["IPO Edge", "ipo_edge_equity.csv"],
  ["Momentum", "momentum_edge_equity.csv"],
  ["PEAD", "pead_data/live_signals.csv"],
];

/** Whole days since each saved file was written (Python _file_age_days); null when missing. */
export async function savedDataAges(dataDir: string = DEFAULT_DATA_DIR, now: Date = new Date()): Promise<SavedAge[]> {
  return Promise.all(
    SAVED_FILES.map(async ([name, rel]) => {
      try {
        const { mtimeMs } = await fs.stat(path.join(dataDir, rel));
        return { name, ageDays: Math.max(0, Math.floor((now.getTime() - mtimeMs) / DAY_MS)) };
      } catch {
        return { name, ageDays: null };
      }
    }),
  );
}

/** The stalest saved file, as the sidebar line "Oldest saved data: …" reports it. */
export function oldestAge(ages: readonly { name: string; ageDays: number | null }[]): { name: string; ageDays: number } | null {
  let oldest: { name: string; ageDays: number } | null = null;
  for (const a of ages) {
    if (a.ageDays != null && (oldest === null || a.ageDays > oldest.ageDays)) oldest = { name: a.name, ageDays: a.ageDays };
  }
  return oldest;
}
