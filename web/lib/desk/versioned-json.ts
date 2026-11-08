import fs from "node:fs/promises";

export const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null;

export type VersionedJson =
  | { ok: true; value: Record<string, unknown> }
  | { ok: false; reason: "missing" | "invalid" | "version" };

/**
 * Read a saved JSON file, check its `version` and shape. Never throws: a broken file becomes
 * a reason. Shared by loadSnapshot and loadMonthly so the error contract lives in one place.
 */
export async function loadVersionedJson(
  file: string,
  version: number,
  hasShape: (v: Record<string, unknown>) => boolean,
): Promise<VersionedJson> {
  let text: string;
  try {
    text = await fs.readFile(file, "utf-8");
  } catch {
    return { ok: false, reason: "missing" };
  }
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    return { ok: false, reason: "invalid" };
  }
  if (!isObj(raw)) return { ok: false, reason: "invalid" };
  if (raw.version !== version) {
    return typeof raw.version === "number" ? { ok: false, reason: "version" } : { ok: false, reason: "invalid" };
  }
  if (!hasShape(raw)) return { ok: false, reason: "invalid" };
  return { ok: true, value: raw };
}
