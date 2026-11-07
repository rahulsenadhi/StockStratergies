import fs from "node:fs/promises";
import path from "node:path";

const DEFAULT_DATA_DIR = process.env.DATA_DIR ?? "..";
const DAY_MS = 86_400_000;

import type { SavedAge, SavedName } from "@/lib/desk/ages";
export { oldestAge, type SavedAge, type SavedName } from "@/lib/desk/ages";

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
