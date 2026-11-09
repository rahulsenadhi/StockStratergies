import fs from "node:fs/promises";
import path from "node:path";

export interface UniverseEntry {
  symbol: string;
  name: string;
  exchange: string;
  isin: string;
}

export const MAX_RESULTS = 20;
const MAX_QUERY = 100;
const BOM = String.fromCharCode(0xfeff);
const cache = new Map<string, Promise<UniverseEntry[]>>();

/** Minimal RFC 4180 reader (quoted fields, doubled quotes, commas and newlines inside quotes). */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  const endRow = () => {
    row.push(field);
    field = "";
    if (row.some((x) => x !== "")) rows.push(row);
    row = [];
  };
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      endRow();
    } else field += c;
  }
  endRow();
  return rows;
}

export function universeCsvPath(repoRoot: string): string {
  return path.join(repoRoot, "data", "universe", "combined_universe.csv");
}

/** Read combined_universe.csv once per file and keep it in memory. */
export function loadUniverse(file: string): Promise<UniverseEntry[]> {
  let hit = cache.get(file);
  if (!hit) {
    hit = fs.readFile(file, "utf-8").then((text) => {
      const [head, ...body] = parseCsv(text.startsWith(BOM) ? text.slice(1) : text);
      const col = (n: string) => (head ?? []).findIndex((h) => h.trim().toLowerCase() === n);
      const [s, n, i, e] = [col("symbol"), col("name"), col("isin"), col("exchange")];
      if (s < 0) throw new Error("universe csv has no Symbol column");
      const seen = new Set<string>();
      const out: UniverseEntry[] = [];
      for (const r of body) {
        const symbol = (r[s] ?? "").trim();
        if (!symbol || seen.has(symbol)) continue;
        seen.add(symbol);
        out.push({ symbol, name: (r[n] ?? "").trim(), exchange: (r[e] ?? "").trim(), isin: (r[i] ?? "").trim() });
      }
      return out;
    });
    hit.catch(() => cache.delete(file)); // do not cache a failed read
    cache.set(file, hit);
  }
  return hit;
}

/** Case-insensitive substring match on symbol or name; symbol-prefix hits rank first. */
export function searchUniverse(entries: UniverseEntry[], query: string): UniverseEntry[] {
  const q = query.trim().toLowerCase().replace(/\s+/g, " ").slice(0, MAX_QUERY);
  if (!q) return [];
  const prefix: UniverseEntry[] = [];
  const rest: UniverseEntry[] = [];
  for (const e of entries) {
    const sym = e.symbol.toLowerCase();
    if (sym.startsWith(q)) prefix.push(e);
    else if (sym.includes(q) || e.name.toLowerCase().includes(q)) rest.push(e);
  }
  return [...prefix, ...rest].slice(0, MAX_RESULTS);
}
