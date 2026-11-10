import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { NextResponse } from "next/server";
import { isObj, loadVersionedJson, type VersionedJson } from "@/lib/desk/versioned-json";

/**
 * Server helpers for the portfolio API. Node never writes ledger.json or alerts.json itself:
 * every write goes through `portfolio_monitor.py --append / --ack`, so Python's validation,
 * backups and corrupt-file guarantees stay the only implementation.
 */
export const MAX_BODY_BYTES = 16 * 1024;
export const MAX_TEXT = 500;
const PY_TIMEOUT_MS = 300_000;
const UI_VERSION = 1;

export interface PortfolioPaths {
  repoRoot: string;
  dir: string;
  ledger: string;
  alerts: string;
  uiOut: string;
  pythonBin: string;
  script: string;
}

/** Resolved per call so tests can point PORTFOLIO_DIR / PORTFOLIO_UI_OUT at a temp folder. */
export function portfolioPaths(env: NodeJS.ProcessEnv = process.env): PortfolioPaths {
  const repoRoot = path.resolve(process.cwd(), env.DATA_DIR ?? "..");
  const dir = env.PORTFOLIO_DIR ? path.resolve(env.PORTFOLIO_DIR) : path.join(repoRoot, "portfolio");
  return {
    repoRoot,
    dir,
    ledger: path.join(dir, "ledger.json"),
    alerts: path.join(dir, "alerts.json"),
    uiOut: env.PORTFOLIO_UI_OUT ? path.resolve(env.PORTFOLIO_UI_OUT) : path.join(repoRoot, "ui_portfolio.json"),
    pythonBin: env.PYTHON_BIN ? path.resolve(process.cwd(), env.PYTHON_BIN) : "python",
    script: path.join(repoRoot, "portfolio_monitor.py"),
  };
}

// ---------------------------------------------------------------- lock
let tail: Promise<unknown> = Promise.resolve();

/** Run fn after every earlier locked call has finished (single-process FIFO mutex). */
export function withPortfolioLock<T>(fn: () => Promise<T>): Promise<T> {
  const run = tail.then(fn, fn);
  tail = run.catch(() => undefined);
  return run;
}

// ---------------------------------------------------------------- python
export interface PyResult {
  code: number | null;
  stdout: string;
  stderr: string;
}

/** Run portfolio_monitor.py with extra args; keeps stdout even on non-zero exit. */
export function runMonitor(extra: string[], p: PortfolioPaths = portfolioPaths()): Promise<PyResult> {
  return new Promise((resolve) => {
    let stdout = "";
    let stderr = "";
    let settled = false;
    // `timer` is declared after spawn succeeds; finish() is never called before then.
    const finish = (r: PyResult) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(r);
    };
    let child: ReturnType<typeof spawn>;
    try {
      child = spawn(p.pythonBin, [p.script, "--dir", p.dir, "--out", p.uiOut, ...extra], {
        cwd: p.repoRoot,
        env: { ...process.env, PYTHONUNBUFFERED: "1", PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" },
      });
    } catch (e) {
      settled = true;
      resolve({ code: null, stdout: "", stderr: e instanceof Error ? e.message : String(e) });
      return;
    }
    const timer = setTimeout(() => {
      try { child.kill(); } catch { /* already gone */ }
      finish({ code: null, stdout, stderr: "portfolio monitor timed out" });
    }, PY_TIMEOUT_MS);
    child.stdout?.on("data", (c) => { stdout += String(c); });
    child.stderr?.on("data", (c) => { stderr += String(c); });
    child.on("error", (e) => finish({ code: null, stdout, stderr: e.message }));
    child.on("exit", (code) => finish({ code, stdout, stderr }));
  });
}

/** Last stdout line that parses as a JSON object (Python may print noise first). */
export function lastJsonLine(stdout: string): Record<string, unknown> | null {
  const lines = stdout.split(/\r\n|\r|\n/);
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i].trim();
    if (!line.startsWith("{")) continue;
    try {
      const v: unknown = JSON.parse(line);
      if (isObj(v) && !Array.isArray(v)) return v;
    } catch { /* try the previous line */ }
  }
  return null;
}

/** Write a one-off JSON file for a Python flag, run fn with its path, always clean up. */
export async function withTempJson<T>(value: unknown, fn: (file: string) => Promise<T>): Promise<T> {
  const folder = await fs.mkdtemp(path.join(os.tmpdir(), "portfolio-"));
  try {
    const file = path.join(folder, "tx.json");
    await fs.writeFile(file, JSON.stringify(value), "utf-8");
    return await fn(file);
  } finally {
    await fs.rm(folder, { recursive: true, force: true });
  }
}

// ---------------------------------------------------------------- reads
export function loadPortfolio(p: PortfolioPaths = portfolioPaths()): Promise<VersionedJson> {
  return loadVersionedJson(p.uiOut, UI_VERSION, (v) => Array.isArray(v.positions) && Array.isArray(v.alerts));
}

export type LedgerRead = { ok: true; transactions: unknown[] } | { ok: false; error: string };

/** Read-only view of ledger.json. A missing file is an empty ledger; a bad file is an error. */
export async function readLedger(p: PortfolioPaths = portfolioPaths()): Promise<LedgerRead> {
  let text: string;
  try {
    text = await fs.readFile(p.ledger, "utf-8");
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT") return { ok: true, transactions: [] };
    return { ok: false, error: "ledger could not be read" };
  }
  try {
    const raw: unknown = JSON.parse(text);
    if (isObj(raw) && Array.isArray(raw.transactions)) return { ok: true, transactions: raw.transactions };
  } catch { /* fall through */ }
  return { ok: false, error: "ledger file is unreadable; it was left untouched" };
}

// ---------------------------------------------------------------- request guards
/** Same rules as /api/update: JSON only, and never from another site. */
export function guardPost(request: Request): NextResponse | null {
  if (!(request.headers.get("content-type") ?? "").includes("application/json")) {
    return NextResponse.json({ ok: false, error: "expected application/json" }, { status: 415 });
  }
  if (request.headers.get("sec-fetch-site") === "cross-site") {
    return NextResponse.json({ ok: false, error: "cross-site request refused" }, { status: 403 });
  }
  return null;
}

export type JsonBody = { ok: true; value: unknown } | { ok: false; response: NextResponse };

export async function readJsonBody(request: Request): Promise<JsonBody> {
  const fail = (error: string, status: number): JsonBody =>
    ({ ok: false, response: NextResponse.json({ ok: false, error }, { status }) });
  const declared = Number(request.headers.get("content-length") ?? 0);
  if (declared > MAX_BODY_BYTES) return fail("request body too large", 413);
  const text = await request.text().catch(() => null);
  if (text === null) return fail("could not read request body", 400);
  if (Buffer.byteLength(text, "utf-8") > MAX_BODY_BYTES) return fail("request body too large", 413);
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch {
    return fail("body is not valid JSON", 400);
  }
}

/** Cheap shape pre-filter; Python stays authoritative for every business rule. */
export function prefilterTransaction(v: unknown): string[] {
  if (!isObj(v) || Array.isArray(v)) return ["transaction must be a JSON object"];
  const errors: string[] = [];
  for (const [k, val] of Object.entries(v)) {
    if (typeof val === "string") {
      if (val.length > MAX_TEXT) errors.push(`${k} is longer than ${MAX_TEXT} characters`);
    } else if (!(val === null || typeof val === "boolean" || (typeof val === "number" && Number.isFinite(val)))) {
      errors.push(`${k} must be a string, number, boolean or null`);
    }
  }
  return errors;
}
