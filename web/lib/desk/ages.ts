/** Saved-data ages: browser-safe types and helpers (no node:fs; see saved-ages.ts for the reader). */
export type SavedName = "Monthly" | "IPO Edge" | "Momentum" | "PEAD";
export interface SavedAge {
  name: SavedName;
  ageDays: number | null;
}

/** The stalest saved file, as the sidebar line "Oldest saved data: …" reports it. */
export function oldestAge(ages: readonly { name: string; ageDays: number | null }[]): { name: string; ageDays: number } | null {
  let oldest: { name: string; ageDays: number } | null = null;
  for (const a of ages) {
    if (a.ageDays != null && (oldest === null || a.ageDays > oldest.ageDays)) oldest = { name: a.name, ageDays: a.ageDays };
  }
  return oldest;
}
