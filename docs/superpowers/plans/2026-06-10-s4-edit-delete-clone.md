# S4 Edit / Delete / Clone Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add edit, delete, and clone for user-created strategies (those with a `strategies/{id}.json` spec) in the S4 Next.js app, reusing the slice-9/10/11/12 write + SSE infra.

**Architecture:** Three loader write/read helpers + an extracted validator on the `web/lib/data/strategies.ts` seam. A new `app/api/strategy/[id]/route.ts` exposes PUT (edit → overwrite spec + index patch + streamed re-backtest) and DELETE (remove entry + spec + CSVs). The create route is refactored to share the validator. `StrategyForm` is parameterized (`mode`/`initial`/`strategyId`/`lockName`); the edit page reuses it via PUT, clone reuses it via the create form prefilled from `?from={id}`. A two-step `DeleteStrategyButton` and Edit/Clone links render on the detail page only when a spec exists.

**Tech Stack:** Next.js 16 (async `params`/`searchParams`), TypeScript, Tailwind v4, Vitest, `node:fs/promises`, `node:child_process`. Heed `web/AGENTS.md` (Next-16 breaking changes — read `node_modules/next/dist/docs/` before writing route/page code).

---

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `web/lib/data/strategies.ts` | Loader seam — add `getStrategySpec`, `updateStrategyIndexEntry`, `deleteStrategy`, `validateStrategyFields`, type `StrategyFields` | Modify |
| `web/lib/use-job-stream.ts` | Add optional `method` to `runJobStream` (default POST) | Modify |
| `web/app/api/strategy/route.ts` | Create route — call shared `validateStrategyFields` | Modify |
| `web/app/api/strategy/[id]/route.ts` | PUT (edit) + DELETE | Create |
| `web/components/strategy-form.tsx` | Parameterize: `mode`/`initial`/`strategyId`/`lockName` | Modify |
| `web/app/strategy/new/page.tsx` | Clone prefill from `?from={id}` | Modify |
| `web/app/strategy/[id]/edit/page.tsx` | Edit page shell | Create |
| `web/components/delete-strategy-button.tsx` | Two-step delete | Create |
| `web/app/strategy/[id]/page.tsx` | Render Edit/Clone/Delete when spec exists | Modify |
| `web/tests/strategy-edit-delete.test.ts` | Unit tests for new loader helpers + validator | Create |

---

## Task 1: Loader helper — `getStrategySpec`

**Files:**
- Modify: `web/lib/data/strategies.ts`
- Test: `web/tests/strategy-edit-delete.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/tests/strategy-edit-delete.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import path from "node:path";
import os from "node:os";
import { promises as fsp } from "node:fs";
import { getStrategySpec } from "@/lib/data/strategies";

async function tmpDir(prefix: string): Promise<string> {
  return fsp.mkdtemp(path.join(os.tmpdir(), prefix));
}

describe("getStrategySpec", () => {
  it("returns the parsed spec object when the file exists", async () => {
    const dir = await tmpDir("spec-");
    await fsp.mkdir(path.join(dir, "strategies"), { recursive: true });
    const spec = { name: "X", entry_formula: "a AND b", exits: {}, sizing: {} };
    await fsp.writeFile(path.join(dir, "strategies", "x.json"), JSON.stringify(spec));
    expect(await getStrategySpec("x", dir)).toEqual(spec);
  });
  it("returns null when the spec file is absent", async () => {
    const dir = await tmpDir("spec-");
    expect(await getStrategySpec("missing", dir)).toBeNull();
  });
  it("returns null when the spec file is unparseable", async () => {
    const dir = await tmpDir("spec-");
    await fsp.mkdir(path.join(dir, "strategies"), { recursive: true });
    await fsp.writeFile(path.join(dir, "strategies", "bad.json"), "{not json");
    expect(await getStrategySpec("bad", dir)).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run tests/strategy-edit-delete.test.ts`
Expected: FAIL — `getStrategySpec` is not exported.

- [ ] **Step 3: Add the helper**

In `web/lib/data/strategies.ts`, after `appendStrategyStub` (~line 532), add:

```ts
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run tests/strategy-edit-delete.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add web/lib/data/strategies.ts web/tests/strategy-edit-delete.test.ts
git commit -m "feat(s4): getStrategySpec loader (eligibility probe + clone source)"
```

---

## Task 2: Loader helper — `updateStrategyIndexEntry`

**Files:**
- Modify: `web/lib/data/strategies.ts`
- Test: `web/tests/strategy-edit-delete.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `web/tests/strategy-edit-delete.test.ts` (add `updateStrategyIndexEntry` to the import from `@/lib/data/strategies`):

```ts
describe("updateStrategyIndexEntry", () => {
  async function seed(): Promise<string> {
    const dir = await tmpDir("idx-");
    await fsp.writeFile(
      path.join(dir, "strategies_index.json"),
      JSON.stringify({ strategies: [
        { id: "a", name: "A", status: "Live" },
        { id: "b", name: "B", status: "Live" },
      ] }, null, 2),
    );
    return dir;
  }
  it("shallow-merges the patch into the matching entry, leaving others untouched", async () => {
    const dir = await seed();
    await updateStrategyIndexEntry("a", { status: "Research", entry_rule: "x > 1" }, dir);
    const idx = JSON.parse(await fsp.readFile(path.join(dir, "strategies_index.json"), "utf-8"));
    expect(idx.strategies[0]).toMatchObject({ id: "a", name: "A", status: "Research", entry_rule: "x > 1" });
    expect(idx.strategies[1]).toEqual({ id: "b", name: "B", status: "Live" });
  });
  it("throws when the id is absent", async () => {
    const dir = await seed();
    await expect(updateStrategyIndexEntry("nope", { status: "X" }, dir)).rejects.toThrow(/not found/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run tests/strategy-edit-delete.test.ts -t updateStrategyIndexEntry`
Expected: FAIL — `updateStrategyIndexEntry` not exported.

- [ ] **Step 3: Add the helper**

In `web/lib/data/strategies.ts`, after `getStrategySpec`, add:

```ts
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run tests/strategy-edit-delete.test.ts -t updateStrategyIndexEntry`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add web/lib/data/strategies.ts web/tests/strategy-edit-delete.test.ts
git commit -m "feat(s4): updateStrategyIndexEntry loader (edit index patch)"
```

---

## Task 3: Loader helper — `deleteStrategy`

**Files:**
- Modify: `web/lib/data/strategies.ts`
- Test: `web/tests/strategy-edit-delete.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `web/tests/strategy-edit-delete.test.ts` (add `deleteStrategy` to the import):

```ts
describe("deleteStrategy", () => {
  async function seed(): Promise<string> {
    const dir = await tmpDir("del-");
    await fsp.mkdir(path.join(dir, "strategies"), { recursive: true });
    await fsp.writeFile(path.join(dir, "strategies", "doomed.json"), JSON.stringify({ name: "Doomed" }));
    await fsp.writeFile(path.join(dir, "doomed_trades.csv"), "h\n1");
    await fsp.writeFile(path.join(dir, "doomed_equity.csv"), "h\n1");
    await fsp.writeFile(
      path.join(dir, "strategies_index.json"),
      JSON.stringify({ strategies: [
        { id: "doomed", name: "Doomed", trades_csv: "doomed_trades.csv", equity_csv: "doomed_equity.csv" },
        { id: "keep", name: "Keep" },
      ] }, null, 2),
    );
    return dir;
  }
  it("removes the entry, spec file, and CSVs; returns true", async () => {
    const dir = await seed();
    expect(await deleteStrategy("doomed", dir)).toBe(true);
    const idx = JSON.parse(await fsp.readFile(path.join(dir, "strategies_index.json"), "utf-8"));
    expect(idx.strategies.map((s: { id: string }) => s.id)).toEqual(["keep"]);
    await expect(fsp.access(path.join(dir, "strategies", "doomed.json"))).rejects.toThrow();
    await expect(fsp.access(path.join(dir, "doomed_trades.csv"))).rejects.toThrow();
    await expect(fsp.access(path.join(dir, "doomed_equity.csv"))).rejects.toThrow();
  });
  it("returns false and leaves the index intact when the id is absent", async () => {
    const dir = await seed();
    expect(await deleteStrategy("ghost", dir)).toBe(false);
    const idx = JSON.parse(await fsp.readFile(path.join(dir, "strategies_index.json"), "utf-8"));
    expect(idx.strategies).toHaveLength(2);
  });
  it("tolerates already-missing spec/CSV files (no throw)", async () => {
    const dir = await seed();
    await fsp.rm(path.join(dir, "strategies", "doomed.json"));
    await fsp.rm(path.join(dir, "doomed_trades.csv"));
    expect(await deleteStrategy("doomed", dir)).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run tests/strategy-edit-delete.test.ts -t deleteStrategy`
Expected: FAIL — `deleteStrategy` not exported.

- [ ] **Step 3: Add the helper**

In `web/lib/data/strategies.ts`, after `updateStrategyIndexEntry`, add:

```ts
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
  for (const c of csvs) await unlinkQuiet(c);
  return true;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run tests/strategy-edit-delete.test.ts -t deleteStrategy`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add web/lib/data/strategies.ts web/tests/strategy-edit-delete.test.ts
git commit -m "feat(s4): deleteStrategy loader (entry + spec + CSVs)"
```

---

## Task 4: Extract `validateStrategyFields` + refactor create route

**Files:**
- Modify: `web/lib/data/strategies.ts`
- Modify: `web/app/api/strategy/route.ts`
- Test: `web/tests/strategy-edit-delete.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `web/tests/strategy-edit-delete.test.ts` (add `validateStrategyFields` to the import):

```ts
describe("validateStrategyFields", () => {
  const ok = {
    entry_formula: "rsi_14 > 70",
    exits: { time_enabled: true, time_days: 30 },
    sizing: { max_positions: 5, initial_cash: 1_000_000 },
  };
  it("accepts a valid body", () => {
    expect(validateStrategyFields(ok)).toEqual({ ok: true });
  });
  it("rejects an empty entry_formula", () => {
    expect(validateStrategyFields({ ...ok, entry_formula: "  " })).toEqual({
      ok: false, error: "entry formula is required",
    });
  });
  it("rejects when no exit is enabled", () => {
    expect(validateStrategyFields({ ...ok, exits: {} })).toEqual({
      ok: false, error: "enable at least one exit rule",
    });
  });
  it("rejects non-positive sizing", () => {
    expect(validateStrategyFields({ ...ok, sizing: { max_positions: 0, initial_cash: 1 } })).toEqual({
      ok: false, error: "max positions and initial cash must be positive numbers",
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run tests/strategy-edit-delete.test.ts -t validateStrategyFields`
Expected: FAIL — `validateStrategyFields` not exported.

- [ ] **Step 3: Add the validator to the loader**

In `web/lib/data/strategies.ts`, after `summarizeExits` (~line 494), add:

```ts
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
```

- [ ] **Step 4: Run the new unit test to verify it passes**

Run: `cd web && npx vitest run tests/strategy-edit-delete.test.ts -t validateStrategyFields`
Expected: PASS (4 tests).

- [ ] **Step 5: Refactor the create route to use it**

In `web/app/api/strategy/route.ts`, replace the inline entry_formula/exits/sizing block (lines 48–61) with a call to the shared validator, keeping the name/sid checks above it.

Replace lines 48–61:

```ts
  const entryFormula = typeof body.entry_formula === "string" ? body.entry_formula.trim() : "";
  if (!entryFormula) return bad("entry formula is required");

  const exits: ExitsSpec = body.exits ?? {};
  if (!exits.time_enabled && !exits.hard_stop_enabled && !exits.trail_enabled) {
    return bad("enable at least one exit rule");
  }

  const sizing = body.sizing ?? {};
  const maxPositions = Number(sizing.max_positions);
  const initialCash = Number(sizing.initial_cash);
  if (!(maxPositions > 0) || !(initialCash > 0)) {
    return bad("max positions and initial cash must be positive numbers");
  }
```

with:

```ts
  const v = validateStrategyFields(body);
  if (!v.ok) return bad(v.error);

  const entryFormula = (body.entry_formula as string).trim();
  const exits: ExitsSpec = body.exits ?? {};
  const sizing = body.sizing ?? {};
```

Add `validateStrategyFields` to the import from `@/lib/data/strategies` at the top of the file.

- [ ] **Step 6: Run the full web test suite to verify nothing regressed**

Run: `cd web && npx vitest run`
Expected: PASS — all prior tests + the new edit/delete suite green (existing `strategy-create.test.ts` unchanged).

- [ ] **Step 7: tsc check**

Run: `cd web && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add web/lib/data/strategies.ts web/app/api/strategy/route.ts web/tests/strategy-edit-delete.test.ts
git commit -m "refactor(s4): extract validateStrategyFields, share with create route"
```

---

## Task 5: `runJobStream` — optional `method`

**Files:**
- Modify: `web/lib/use-job-stream.ts`

- [ ] **Step 1: Add the parameter**

In `web/lib/use-job-stream.ts`, change the signature + fetch to accept an optional `method` (default `"POST"`), so edit can PUT through the same SSE driver.

Replace the function signature (line 21) and the `fetch` call (lines 26–30):

```ts
export async function runJobStream(
  url: string,
  body?: unknown,
  handlers: JobStreamHandlers = {},
  method: "POST" | "PUT" = "POST",
): Promise<JobStreamResult> {
  const res = await fetch(url, {
    method,
    headers: body !== undefined ? { "content-type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
```

(No other change; existing POST callers pass no 4th arg → unchanged behavior.)

- [ ] **Step 2: Verify existing stream tests still pass**

Run: `cd web && npx vitest run tests/use-job-stream.test.ts`
Expected: PASS — default `method="POST"` preserves behavior. (If the file name differs, run `cd web && npx vitest run` and confirm the use-job-stream tests pass.)

- [ ] **Step 3: tsc check**

Run: `cd web && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web/lib/use-job-stream.ts
git commit -m "feat(s4): runJobStream optional method (PUT for edit)"
```

---

## Task 6: PUT + DELETE route — `app/api/strategy/[id]/route.ts`

**Files:**
- Create: `web/app/api/strategy/[id]/route.ts`

> No unit test here (route wiring is build-gated + runtime-verified in Task 10, matching how slices 9–12 tested routes). The loader helpers it calls are unit-tested in Tasks 1–4.

- [ ] **Step 1: Read the Next-16 route-handler docs**

Run: `ls web/node_modules/next/dist/docs/`
Read the route-handler / dynamic-segment guidance (heed `web/AGENTS.md`). Confirm `params` is a Promise in this Next version (the detail page already does `await params`).

- [ ] **Step 2: Create the route**

Create `web/app/api/strategy/[id]/route.ts`:

```ts
import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import path from "node:path";
import { runRecompute, type SpawnedChild } from "@/lib/recompute";
import {
  getStrategySpec,
  validateStrategyFields,
  summarizeExits,
  writeStrategySpec,
  updateStrategyIndexEntry,
  deleteStrategy,
  type ExitsSpec,
} from "@/lib/data/strategies";
import { tryAcquire, release } from "@/lib/job-lock";
import { streamJob } from "@/lib/job-stream";

export const dynamic = "force-dynamic";

const EDIT_TIMEOUT_MS = 600_000;
const SID_RE = /^[a-z0-9_]+$/;

// PYTHONUNBUFFERED forces per-line stdout flush so SSE progress streams live.
const spawnChild = (b: string, a: string[], o: { cwd: string }) =>
  spawn(b, a, {
    cwd: o.cwd,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
  }) as unknown as SpawnedChild;

type EditBody = {
  description?: unknown; type?: unknown; universe?: unknown;
  entry_formula?: unknown; exits?: ExitsSpec; sizing?: Record<string, unknown>;
};

function err(error: string, status: number) {
  return NextResponse.json({ ok: false, error }, { status });
}

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  if (!SID_RE.test(id)) return err("invalid strategy id", 400);

  const existing = await getStrategySpec(id);
  if (!existing) return err("strategy not found", 404);

  const body = (await request.json().catch(() => ({}))) as EditBody;
  const v = validateStrategyFields(body);
  if (!v.ok) return err(v.error, 400);

  if (!tryAcquire()) return err("A job is already running", 409);

  return streamJob(async (onLine) => {
    try {
      const name = typeof existing.name === "string" ? existing.name : id; // name frozen
      const entryFormula = (body.entry_formula as string).trim();
      const exits: ExitsSpec = body.exits ?? {};
      const sizing = body.sizing ?? {};
      const description = typeof body.description === "string" ? body.description : "";
      const type = typeof body.type === "string" && body.type ? body.type : "Custom";
      const universe = typeof body.universe === "string" && body.universe ? body.universe : "Nifty 50";

      const spec = {
        name, description, type, universe,
        entry_mode: "Formula DSL",
        entry_formula: entryFormula,
        exits, sizing,
      };

      await writeStrategySpec(id, spec);
      await updateStrategyIndexEntry(id, {
        status: "Research",
        entry_rule: entryFormula,
        exit_rule: summarizeExits(exits),
        description, type, universe, sizing,
      });

      const repoRoot = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..");
      const run = await runRecompute(spawnChild, {
        bin: process.env.PYTHON_BIN ?? "python",
        args: ["generic_backtest.py", "--spec", `strategies/${id}.json`],
        cwd: repoRoot,
        timeoutMs: EDIT_TIMEOUT_MS,
        label: "Backtest",
        onLine,
      });
      if (run.status !== 200) return { status: run.status, body: run.body };
      return { status: 200, body: { ok: true, sid: id } };
    } finally {
      release();
    }
  });
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  if (!SID_RE.test(id)) return err("invalid strategy id", 400);
  if (!(await getStrategySpec(id))) return err("strategy not found", 404);
  if (!tryAcquire()) return err("A job is already running", 409);
  try {
    const ok = await deleteStrategy(id);
    return ok ? NextResponse.json({ ok: true }) : err("strategy not found", 404);
  } catch (e) {
    return err(e instanceof Error ? e.message : String(e), 500);
  } finally {
    release();
  }
}
```

- [ ] **Step 3: tsc + build check**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: clean (no type errors; build succeeds).

- [ ] **Step 4: Commit**

```bash
git add web/app/api/strategy/[id]/route.ts
git commit -m "feat(s4): PUT (edit) + DELETE strategy route"
```

---

## Task 7: Parameterize `StrategyForm`

**Files:**
- Modify: `web/components/strategy-form.tsx`

- [ ] **Step 1: Add props + initializers + edit endpoint**

Rewrite `web/components/strategy-form.tsx` to accept props (defaults preserve create behavior):

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { runJobStream } from "@/lib/use-job-stream";
import { JobProgress } from "@/components/job-progress";

export interface StrategyFormValues {
  name: string;
  type: string;
  description: string;
  universe: string;
  entryFormula: string;
  timeEnabled: boolean; timeDays: number;
  hardStopEnabled: boolean; hardStopPct: number;
  trailEnabled: boolean; trailPct: number;
  maxPositions: number; initialCash: number;
}

const DEFAULTS: StrategyFormValues = {
  name: "", type: "Momentum", description: "", universe: "Nifty 50", entryFormula: "",
  timeEnabled: true, timeDays: 30,
  hardStopEnabled: true, hardStopPct: 8,
  trailEnabled: false, trailPct: 12,
  maxPositions: 5, initialCash: 1000000,
};

export interface StrategyFormProps {
  mode?: "create" | "edit";
  initial?: Partial<StrategyFormValues>;
  strategyId?: string;
  lockName?: boolean;
}

export function StrategyForm({ mode = "create", initial, strategyId, lockName }: StrategyFormProps) {
  const router = useRouter();
  const init = { ...DEFAULTS, ...initial };
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [phase, setPhase] = useState<string | null>(null);

  const [name, setName] = useState(init.name);
  const [type, setType] = useState(init.type);
  const [description, setDescription] = useState(init.description);
  const [universe, setUniverse] = useState(init.universe);
  const [entryFormula, setEntryFormula] = useState(init.entryFormula);
  const [timeEnabled, setTimeEnabled] = useState(init.timeEnabled);
  const [timeDays, setTimeDays] = useState(init.timeDays);
  const [hardStopEnabled, setHardStopEnabled] = useState(init.hardStopEnabled);
  const [hardStopPct, setHardStopPct] = useState(init.hardStopPct);
  const [trailEnabled, setTrailEnabled] = useState(init.trailEnabled);
  const [trailPct, setTrailPct] = useState(init.trailPct);
  const [maxPositions, setMaxPositions] = useState(init.maxPositions);
  const [initialCash, setInitialCash] = useState(init.initialCash);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setLines([]);
    setPhase(null);
    try {
      const url = mode === "edit" ? `/api/strategy/${strategyId}` : "/api/strategy";
      const httpMethod = mode === "edit" ? "PUT" : "POST";
      const res = await runJobStream(url, {
        name, type, description, universe,
        entry_formula: entryFormula,
        exits: {
          time_enabled: timeEnabled, time_days: timeDays,
          hard_stop_enabled: hardStopEnabled, hard_stop_pct: hardStopPct,
          trail_enabled: trailEnabled, trail_pct: trailPct,
        },
        sizing: {
          method: "Equal weight (capped)",
          max_positions: maxPositions, initial_cash: initialCash,
        },
      }, {
        onLine: (l) => setLines((prev) => [...prev.slice(-199), l]),
        onPhase: (p) => setPhase(p),
      }, httpMethod);
      const data = res.data as { ok?: boolean; sid?: string; error?: string };
      if (res.ok && data.ok) {
        router.push(`/strategy/${mode === "edit" ? strategyId : data.sid}`);
      } else {
        setError(data.error ?? `${mode === "edit" ? "Save" : "Create"} failed (${res.status})`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error");
    } finally {
      setLoading(false);
      setPhase(null);
    }
  }

  const field = "rounded-md border px-3 py-1.5 text-sm w-full";
  const submitLabel = mode === "edit"
    ? (loading ? "Saving & re-backtesting…" : "Save changes")
    : (loading ? "Creating & backtesting…" : "Create strategy");
  return (
    <form onSubmit={onSubmit} className="max-w-xl space-y-4">
      <label className="block">
        <span className="text-sm font-medium">Name</span>
        <input className={field} value={name} onChange={(e) => setName(e.target.value)}
          required readOnly={lockName} disabled={lockName} />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Type</span>
        <input className={field} value={type} onChange={(e) => setType(e.target.value)} />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Description</span>
        <input className={field} value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Universe</span>
        <input className={field} value={universe} onChange={(e) => setUniverse(e.target.value)} />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Entry formula (DSL)</span>
        <textarea className={field} rows={2} value={entryFormula}
          onChange={(e) => setEntryFormula(e.target.value)}
          placeholder="rsi_14 > 70 AND close > sma_200" required />
      </label>

      <fieldset className="space-y-2 rounded-md border p-3">
        <legend className="px-1 text-sm font-medium">Exits (enable at least one)</legend>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={timeEnabled} onChange={(e) => setTimeEnabled(e.target.checked)} />
          Time exit after
          <input type="number" className="w-20 rounded border px-2 py-1" value={timeDays}
            onChange={(e) => setTimeDays(Number(e.target.value))} /> days
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={hardStopEnabled} onChange={(e) => setHardStopEnabled(e.target.checked)} />
          Hard stop at
          <input type="number" className="w-20 rounded border px-2 py-1" value={hardStopPct}
            onChange={(e) => setHardStopPct(Number(e.target.value))} /> %
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={trailEnabled} onChange={(e) => setTrailEnabled(e.target.checked)} />
          Trailing stop at
          <input type="number" className="w-20 rounded border px-2 py-1" value={trailPct}
            onChange={(e) => setTrailPct(Number(e.target.value))} /> %
        </label>
      </fieldset>

      <fieldset className="space-y-2 rounded-md border p-3">
        <legend className="px-1 text-sm font-medium">Sizing</legend>
        <label className="flex items-center gap-2 text-sm">
          Max positions
          <input type="number" className="w-24 rounded border px-2 py-1" value={maxPositions}
            onChange={(e) => setMaxPositions(Number(e.target.value))} />
        </label>
        <label className="flex items-center gap-2 text-sm">
          Initial cash
          <input type="number" className="w-32 rounded border px-2 py-1" value={initialCash}
            onChange={(e) => setInitialCash(Number(e.target.value))} />
        </label>
      </fieldset>

      <button type="submit" disabled={loading}
        className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-accent disabled:opacity-50">
        {submitLabel}
      </button>
      {loading && <JobProgress phase={phase} lines={lines} />}
      {error && <p className="text-sm text-red-500">{error}</p>}
    </form>
  );
}
```

- [ ] **Step 2: tsc + build check**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: clean. (`/strategy/new` still renders `<StrategyForm />` with no props = create mode unchanged.)

- [ ] **Step 3: Commit**

```bash
git add web/components/strategy-form.tsx
git commit -m "feat(s4): parameterize StrategyForm (mode/initial/strategyId/lockName)"
```

---

## Task 8: Edit page — `app/strategy/[id]/edit/page.tsx`

**Files:**
- Create: `web/app/strategy/[id]/edit/page.tsx`

- [ ] **Step 1: Create the page**

Maps the stored spec into `StrategyFormValues` and renders the form in edit mode with the name locked.

Create `web/app/strategy/[id]/edit/page.tsx`:

```tsx
import { notFound } from "next/navigation";
import Link from "next/link";
import { getStrategySpec, type ExitsSpec } from "@/lib/data/strategies";
import { StrategyForm, type StrategyFormValues } from "@/components/strategy-form";

export const dynamic = "force-dynamic";

function specToInitial(spec: Record<string, unknown>): Partial<StrategyFormValues> {
  const exits = (spec.exits ?? {}) as ExitsSpec;
  const sizing = (spec.sizing ?? {}) as Record<string, unknown>;
  const str = (v: unknown, d: string) => (typeof v === "string" ? v : d);
  const num = (v: unknown, d: number) => (typeof v === "number" ? v : d);
  return {
    name: str(spec.name, ""),
    type: str(spec.type, "Momentum"),
    description: str(spec.description, ""),
    universe: str(spec.universe, "Nifty 50"),
    entryFormula: str(spec.entry_formula, ""),
    timeEnabled: exits.time_enabled ?? false,
    timeDays: exits.time_days ?? 30,
    hardStopEnabled: exits.hard_stop_enabled ?? false,
    hardStopPct: exits.hard_stop_pct ?? 8,
    trailEnabled: exits.trail_enabled ?? false,
    trailPct: exits.trail_pct ?? 12,
    maxPositions: num(sizing.max_positions, 5),
    initialCash: num(sizing.initial_cash, 1000000),
  };
}

export default async function EditStrategyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const spec = await getStrategySpec(id);
  if (!spec) notFound();

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-8">
      <Link href={`/strategy/${id}`} className="text-sm text-muted-foreground">← Back to strategy</Link>
      <h1 className="text-2xl font-bold">Edit Strategy</h1>
      <p className="text-sm text-muted-foreground">
        Saving re-runs the backtest (1–3 min) and refreshes KPIs. The name is fixed — use Clone to rename.
      </p>
      <StrategyForm mode="edit" strategyId={id} lockName initial={specToInitial(spec)} />
    </main>
  );
}
```

- [ ] **Step 2: tsc + build check**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add web/app/strategy/[id]/edit/page.tsx
git commit -m "feat(s4): edit-strategy page (prefilled form, name locked)"
```

---

## Task 9: Clone prefill on the new-strategy page

**Files:**
- Modify: `web/app/strategy/new/page.tsx`

- [ ] **Step 1: Read `?from={id}` and prefill**

Rewrite `web/app/strategy/new/page.tsx` to read the optional `from` query param, load that strategy's spec, and prefill the create form with name `Copy of {name}`. Reuses the same spec→initial mapping shape as the edit page.

```tsx
import Link from "next/link";
import { getStrategySpec, type ExitsSpec } from "@/lib/data/strategies";
import { StrategyForm, type StrategyFormValues } from "@/components/strategy-form";

export const dynamic = "force-dynamic";

function cloneInitial(spec: Record<string, unknown>): Partial<StrategyFormValues> {
  const exits = (spec.exits ?? {}) as ExitsSpec;
  const sizing = (spec.sizing ?? {}) as Record<string, unknown>;
  const str = (v: unknown, d: string) => (typeof v === "string" ? v : d);
  const num = (v: unknown, d: number) => (typeof v === "number" ? v : d);
  return {
    name: `Copy of ${str(spec.name, "strategy")}`,
    type: str(spec.type, "Momentum"),
    description: str(spec.description, ""),
    universe: str(spec.universe, "Nifty 50"),
    entryFormula: str(spec.entry_formula, ""),
    timeEnabled: exits.time_enabled ?? true,
    timeDays: exits.time_days ?? 30,
    hardStopEnabled: exits.hard_stop_enabled ?? true,
    hardStopPct: exits.hard_stop_pct ?? 8,
    trailEnabled: exits.trail_enabled ?? false,
    trailPct: exits.trail_pct ?? 12,
    maxPositions: num(sizing.max_positions, 5),
    initialCash: num(sizing.initial_cash, 1000000),
  };
}

export default async function NewStrategyPage({
  searchParams,
}: { searchParams: Promise<{ from?: string }> }) {
  const { from } = await searchParams;
  const sourceSpec = from ? await getStrategySpec(from) : null;
  const initial = sourceSpec ? cloneInitial(sourceSpec) : undefined;

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-8">
      <Link href="/leaderboard" className="text-sm text-muted-foreground">← Leaderboard</Link>
      <h1 className="text-2xl font-bold">{sourceSpec ? "Clone Strategy" : "New Strategy"}</h1>
      <p className="text-sm text-muted-foreground">
        Define a formula-based strategy. Creating runs a backtest (1–3 min) and adds it to the leaderboard.
      </p>
      <StrategyForm initial={initial} />
    </main>
  );
}
```

- [ ] **Step 2: tsc + build check**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: clean. (No `?from` → `initial` undefined → identical to prior create behavior.)

- [ ] **Step 3: Commit**

```bash
git add web/app/strategy/new/page.tsx
git commit -m "feat(s4): clone — prefill create form from ?from={id}"
```

---

## Task 10: Delete button + detail-page wiring + runtime verify

**Files:**
- Create: `web/components/delete-strategy-button.tsx`
- Modify: `web/app/strategy/[id]/page.tsx`

- [ ] **Step 1: Create the two-step delete button**

Create `web/components/delete-strategy-button.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const ARM_RESET_MS = 5000;

export function DeleteStrategyButton({ id }: { id: string }) {
  const router = useRouter();
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onClick() {
    if (!armed) {
      setArmed(true);
      setTimeout(() => setArmed(false), ARM_RESET_MS);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/strategy/${id}`, { method: "DELETE" });
      const data = (await res.json().catch(() => ({}))) as { ok?: boolean; error?: string };
      if (res.ok && data.ok) {
        router.push("/leaderboard");
      } else {
        setError(data.error ?? `Delete failed (${res.status})`);
        setArmed(false);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Network error");
      setArmed(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex items-center gap-2">
      <button
        onClick={onClick}
        disabled={busy}
        className="rounded-md border px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
      >
        {busy ? "Deleting…" : armed ? "Confirm delete?" : "Delete"}
      </button>
      {error && <span className="text-sm text-red-500">{error}</span>}
    </span>
  );
}
```

- [ ] **Step 2: Wire Edit/Clone/Delete into the detail page**

In `web/app/strategy/[id]/page.tsx`: import `getStrategySpec` and `DeleteStrategyButton`, probe the spec, and render the actions row only when it exists.

Add to the imports:

```tsx
import { getStrategy, getEquityCurve, computeDrawdown, getTrades, getMonthlyReturns, getStrategySpec } from "@/lib/data/strategies";
import { DeleteStrategyButton } from "@/components/delete-strategy-button";
```

After `const s = await getStrategy(id); if (!s) notFound();` add:

```tsx
  const spec = await getStrategySpec(id);
```

Replace the header block (the `<div className="flex items-start justify-between">…</div>`) with:

```tsx
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{s.name}</h1>
          <p className="text-sm text-muted-foreground">{s.type} · {s.status}</p>
        </div>
        <div className="flex items-center gap-2">
          {spec && <Link href={`/strategy/${id}/edit`} className="rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-accent">Edit</Link>}
          {spec && <Link href={`/strategy/new?from=${id}`} className="rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-accent">Clone</Link>}
          {spec && <DeleteStrategyButton id={id} />}
          {s.backtest && <BacktestButton strategyId={s.id} />}
        </div>
      </div>
```

- [ ] **Step 3: tsc + build check**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: clean.

- [ ] **Step 4: Full test suite**

Run: `cd web && npx vitest run`
Expected: all green (no new units this task; confirms no regression).

- [ ] **Step 5: Runtime verification**

Run: `cd web && npx next start -p 3022` (after the build above), then in another shell:

1. Create a throwaway strategy via the UI (`/strategy/new`, formula `rsi_14 > 70 AND close > sma_200`) OR `curl -X POST localhost:3022/api/strategy -H 'content-type: application/json' -d '{"name":"Tmp Edit Test","entry_formula":"rsi_14 > 70 AND close > sma_200","exits":{"time_enabled":true,"time_days":30},"sizing":{"max_positions":5,"initial_cash":1000000}}'` → note `sid` (`tmp_edit_test`).
2. `GET /strategy/tmp_edit_test` → Edit / Clone / Delete present.
3. `GET /strategy/tmp_edit_test/edit` → 200, Name read-only, fields prefilled.
4. `PUT /api/strategy/tmp_edit_test` with a changed formula → SSE stream → `{ok:true,sid:tmp_edit_test}`; index entry `kpis_updated` bumped.
5. Clone: `GET /strategy/new?from=tmp_edit_test` → 200, title "Clone Strategy", name `Copy of …`.
6. Built-in guard: `GET /strategy/momentum_edge` → no Edit/Clone/Delete; `PUT /api/strategy/momentum_edge` → 404; `DELETE /api/strategy/momentum_edge` → 404.
7. Bad id: `DELETE /api/strategy/..%2Fx` (or any non-`^[a-z0-9_]+$`) → 400.
8. Concurrency: start a PUT, immediately `POST /api/recompute` → 409 "A job is already running".
9. `DELETE /api/strategy/tmp_edit_test` → `{ok:true}`; `GET /strategy/tmp_edit_test` → 404; `strategies/tmp_edit_test.json` + its CSVs gone; entry removed from `strategies_index.json`.
10. `/leaderboard`, `/`, an existing built-in strategy page still 200.

Record the actual outputs. If the backtest fails for environment/data reasons (not wiring), report it — do not alter the Python. Deterministic gates: spec/index/CSV file effects, 400/404/409 paths, pages render.

- [ ] **Step 6: Discard verification churn, commit code**

Discard any throwaway-strategy data the verify run wrote (e.g. `git checkout strategies_index.json` and remove `strategies/tmp_edit_test.json` + its CSVs if a created one lingers). Then:

```bash
git add web/components/delete-strategy-button.tsx web/app/strategy/[id]/page.tsx
git commit -m "feat(s4): delete button + Edit/Clone/Delete on detail page"
```

---

## Final verification

- [ ] `cd web && npx vitest run` — all tests green (new edit/delete suite + refactored create + prior suites).
- [ ] `cd web && npx tsc --noEmit` — no type errors.
- [ ] `cd web && npm run build` — clean.
- [ ] Runtime checks (Task 10 Step 5) recorded.
- [ ] Security pass (use security-reviewer at the route task / before merge): id regex-gated before fs/spawn; fixed array argv, no shell; writes confined to repo `strategies/` + index; delete best-effort; single-process job-lock shared with create/backtest/recompute.

---

## Notes for the implementer

- **Read `web/AGENTS.md` + the Next-16 docs** before route/page code — `params` and `searchParams` are Promises here.
- **DRY:** `specToInitial` (edit) and `cloneInitial` (new) are near-identical spec→form mappers; if you prefer, extract one shared helper (e.g. `web/lib/spec-to-form.ts`) and have clone wrap it to override `name`. Optional — both are tiny pure functions; keep duplicated only if extraction adds more ceremony than it removes.
- **Name freeze on edit:** the PUT route deliberately ignores any `name` in the body and reuses the stored spec's name. The form locks the field as a UX cue, but the server is the source of truth.
- **No rollback** on edit-backtest failure (spec already overwritten, status→Research) — matches the create slice's stub-persists behavior. Documented YAGNI.
