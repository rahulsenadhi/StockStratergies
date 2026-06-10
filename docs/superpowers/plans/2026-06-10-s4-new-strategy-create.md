# New-Strategy Create Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A single-page form that creates a user strategy — writes `strategies/{sid}.json` + a Research stub into the index, runs `generic_backtest.py --spec`, and the strategy appears on the leaderboard.

**Architecture:** Pure helpers (`deriveStrategyId`, `summarizeExits`) + async write helpers (`writeStrategySpec`, `appendStrategyStub`, atomic tmp+rename) on the loader seam → `POST /api/strategy` validates, writes spec+stub, spawns `generic_backtest.py --spec` via the shared `job-lock` + `runRecompute` (generic_backtest fills KPIs and calls `refresh_all` itself) → `"use client"` `StrategyForm` on a new `/strategy/new` page, linked from the leaderboard header.

**Tech Stack:** Next.js 16 Route Handler + client form, TypeScript, `node:child_process`, Vitest.

**Spec:** `docs/superpowers/specs/2026-06-10-s4-new-strategy-create-design.md`

**Grounding facts:**
- `web/lib/data/strategies.ts` top imports already include `import { promises as fs } from "fs";` and `import path from "path";` and `const DEFAULT_DATA_DIR = process.env.DATA_DIR ?? "..";`. `mapStrategy` maps empty `kpis_inline`→null KPIs, empty `equity_csv`→null (so a Research stub renders, unranked→last). `getStrategy(id, dataDir?)` returns `Strategy|null`.
- `generic_backtest.py --spec strategies/{sid}.json`: derives sid from filename, runs backtest, updates the (pre-existing) index stub with kpis/csvs, then calls `refresh_all()`. It reads `spec.universe`, `spec.entry_formula`, `spec.exits.{time_enabled,time_days,hard_stop_enabled,hard_stop_pct,trail_enabled,trail_pct}`, `spec.sizing.{method,max_positions,initial_cash}`.
- Infra from slices 9/10: `web/lib/job-lock.ts` (`tryAcquire`/`release`), `web/lib/recompute.ts` `runRecompute(spawnFn, {bin,args,cwd,timeoutMs,label?})` + type `SpawnedChild`.
- Leaderboard header (current) is a flex div with `<h1>` + `<RecomputeButton/>` (full source in Task 4).
- Tests: `web/tests/`, `cd web && npm run test`. `@` alias → `web/`. Atomic-write test pattern: `fsp.mkdtemp` (see existing strategies.test.ts).
- Timestamps in route code: `new Date().toISOString()` is fine in app/route code (the Date restriction only applies to Workflow scripts).

**File structure:**
- `web/lib/data/strategies.ts` — add `deriveStrategyId`, `summarizeExits`, `StrategyStub`, `writeStrategySpec`, `appendStrategyStub` (Tasks 1-2).
- `web/app/api/strategy/route.ts` — NEW POST handler (Task 3).
- `web/components/strategy-form.tsx` — NEW client form (Task 4).
- `web/app/strategy/new/page.tsx` — NEW RSC shell (Task 4).
- `web/app/leaderboard/page.tsx` — add "+ New strategy" link (Task 4).
- Tests: `web/tests/strategy-create.test.ts` NEW (Tasks 1-2).

---

### Task 1: Pure helpers `deriveStrategyId` + `summarizeExits`

**Files:**
- Modify: `web/lib/data/strategies.ts`
- Test: `web/tests/strategy-create.test.ts` (new)

- [ ] **Step 1: Write the failing tests**

Create `web/tests/strategy-create.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { deriveStrategyId, summarizeExits } from "@/lib/data/strategies";

describe("deriveStrategyId", () => {
  it("lowercases and replaces spaces/hyphens with underscore", () => {
    expect(deriveStrategyId("My Cool Strat")).toBe("my_cool_strat");
    expect(deriveStrategyId("RSI-Breakout")).toBe("rsi_breakout");
  });
  it("trims surrounding whitespace", () => {
    expect(deriveStrategyId("  Edge  ")).toBe("edge");
  });
  it("leaves an all-symbol name as something the route regex will reject", () => {
    // derive does not strip symbols; the route guards with ^[a-z0-9_]+$
    expect(/^[a-z0-9_]+$/.test(deriveStrategyId("@@@"))).toBe(false);
    expect(/^[a-z0-9_]+$/.test(deriveStrategyId("Good Name 2"))).toBe(true);
  });
});

describe("summarizeExits", () => {
  it("joins enabled exits", () => {
    expect(
      summarizeExits({
        time_enabled: true, time_days: 30,
        hard_stop_enabled: true, hard_stop_pct: 8,
        trail_enabled: true, trail_pct: 12,
      }),
    ).toBe("hold 30d · hard stop 8% · trail 12%");
  });
  it("omits disabled exits", () => {
    expect(
      summarizeExits({ time_enabled: true, time_days: 60, hard_stop_enabled: false, trail_enabled: false }),
    ).toBe("hold 60d");
  });
  it("returns em dash when none enabled", () => {
    expect(summarizeExits({})).toBe("—");
  });
});
```

- [ ] **Step 2: Run, verify it fails**

Run: `cd web && npm run test -- strategy-create`
Expected: FAIL — `deriveStrategyId`/`summarizeExits` not exported.

- [ ] **Step 3: Add the helpers to `web/lib/data/strategies.ts`**

Append near the other exported helpers (e.g. after `mapStrategy`):

```typescript
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
```

- [ ] **Step 4: Run, verify it passes**

Run: `cd web && npm run test -- strategy-create`
Expected: PASS — all `deriveStrategyId` + `summarizeExits` cases green.

- [ ] **Step 5: Commit**

```bash
git add web/lib/data/strategies.ts web/tests/strategy-create.test.ts
git commit -m "feat(s4): deriveStrategyId + summarizeExits pure helpers"
```

---

### Task 2: Write helpers `writeStrategySpec` + `appendStrategyStub`

**Files:**
- Modify: `web/lib/data/strategies.ts`
- Test: `web/tests/strategy-create.test.ts`

- [ ] **Step 1: Write the failing tests**

Add to `web/tests/strategy-create.test.ts` (add imports: `import path from "node:path"; import os from "node:os"; import { promises as fsp } from "node:fs";` and extend the `@/lib/data/strategies` import with `writeStrategySpec, appendStrategyStub, type StrategyStub`):

```typescript
function makeStub(id: string): StrategyStub {
  return {
    id, name: id, type: "Custom", status: "Research", description: "d",
    universe: "Nifty 50", entry_rule: "x > 1", exit_rule: "hold 30d",
    sizing: { method: "Equal weight (capped)", max_positions: 5, initial_cash: 1000000 },
    trades_csv: "", equity_csv: "", kpis_inline: {},
    last_run: "2026-06-10T00:00:00.000Z", created: "2026-06-10T00:00:00.000Z",
    page_key: "Library",
  };
}

describe("writeStrategySpec", () => {
  it("writes strategies/{sid}.json with the exact object", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "spec-"));
    const spec = { name: "X", entry_formula: "a AND b", exits: {}, sizing: {} };
    await writeStrategySpec("my_strat", spec, dir);
    const written = JSON.parse(
      await fsp.readFile(path.join(dir, "strategies", "my_strat.json"), "utf-8"),
    );
    expect(written).toEqual(spec);
  });
});

describe("appendStrategyStub", () => {
  async function seed(): Promise<string> {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "idx-"));
    await fsp.writeFile(
      path.join(dir, "strategies_index.json"),
      JSON.stringify({ strategies: [{ id: "existing", name: "Existing" }] }, null, 2),
    );
    return dir;
  }
  it("appends a stub to the index", async () => {
    const dir = await seed();
    await appendStrategyStub(makeStub("new_one"), dir);
    const idx = JSON.parse(await fsp.readFile(path.join(dir, "strategies_index.json"), "utf-8"));
    expect(idx.strategies.map((s: { id: string }) => s.id)).toEqual(["existing", "new_one"]);
    expect(idx.strategies[1].status).toBe("Research");
  });
  it("throws on duplicate id", async () => {
    const dir = await seed();
    await expect(appendStrategyStub(makeStub("existing"), dir)).rejects.toThrow(/already exists/);
  });
});
```

- [ ] **Step 2: Run, verify it fails**

Run: `cd web && npm run test -- strategy-create`
Expected: FAIL — `writeStrategySpec`/`appendStrategyStub` not exported.

- [ ] **Step 3: Add the write helpers to `web/lib/data/strategies.ts`**

Append:

```typescript
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
```

- [ ] **Step 4: Run, verify it passes**

Run: `cd web && npm run test -- strategy-create`
Expected: PASS — write/append/duplicate cases green.

- [ ] **Step 5: Commit**

```bash
git add web/lib/data/strategies.ts web/tests/strategy-create.test.ts
git commit -m "feat(s4): writeStrategySpec + appendStrategyStub atomic write helpers"
```

---

### Task 3: `POST /api/strategy` route handler

**Files:**
- Create: `web/app/api/strategy/route.ts`

- [ ] **Step 1: Create the route handler**

```typescript
import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import path from "node:path";
import { runRecompute, type SpawnedChild } from "@/lib/recompute";
import {
  getStrategy,
  deriveStrategyId,
  summarizeExits,
  writeStrategySpec,
  appendStrategyStub,
  type ExitsSpec,
  type StrategyStub,
} from "@/lib/data/strategies";
import { tryAcquire, release } from "@/lib/job-lock";

export const dynamic = "force-dynamic";

const CREATE_TIMEOUT_MS = 600_000;
const SID_RE = /^[a-z0-9_]+$/;

const spawnChild = (b: string, a: string[], o: { cwd: string }) =>
  spawn(b, a, o) as unknown as SpawnedChild;

type CreateBody = {
  name?: unknown; description?: unknown; type?: unknown; universe?: unknown;
  entry_formula?: unknown; exits?: ExitsSpec; sizing?: Record<string, unknown>;
};

function bad(error: string) {
  return NextResponse.json({ ok: false, error }, { status: 400 });
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as CreateBody;

  const name = typeof body.name === "string" ? body.name.trim() : "";
  if (!name) return bad("name is required");
  const sid = deriveStrategyId(name);
  if (!SID_RE.test(sid)) return bad("name must contain letters, numbers, spaces or hyphens");

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

  if (await getStrategy(sid)) {
    return NextResponse.json(
      { ok: false, error: "A strategy with that name already exists" },
      { status: 409 },
    );
  }

  if (!tryAcquire()) {
    return NextResponse.json(
      { ok: false, error: "A job is already running" },
      { status: 409 },
    );
  }
  try {
    const description = typeof body.description === "string" ? body.description : "";
    const type = typeof body.type === "string" && body.type ? body.type : "Custom";
    const universe = typeof body.universe === "string" && body.universe ? body.universe : "Nifty 50";

    const spec = {
      name, description, type, universe,
      entry_mode: "Formula DSL",
      entry_formula: entryFormula,
      exits,
      sizing,
    };

    const now = new Date().toISOString();
    const stub: StrategyStub = {
      id: sid, name, type, status: "Research", description, universe,
      entry_rule: entryFormula, exit_rule: summarizeExits(exits),
      sizing, trades_csv: "", equity_csv: "", kpis_inline: {},
      last_run: now, created: now, page_key: "Library",
    };

    try {
      await writeStrategySpec(sid, spec);
      await appendStrategyStub(stub);
    } catch (e) {
      // duplicate id race or IO error
      const msg = e instanceof Error ? e.message : String(e);
      const status = msg.includes("already exists") ? 409 : 500;
      return NextResponse.json({ ok: false, error: msg }, { status });
    }

    const repoRoot = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..");
    const run = await runRecompute(spawnChild, {
      bin: process.env.PYTHON_BIN ?? "python",
      args: ["generic_backtest.py", "--spec", `strategies/${sid}.json`],
      cwd: repoRoot,
      timeoutMs: CREATE_TIMEOUT_MS,
      label: "Backtest",
    });
    if (run.status !== 200) {
      // Stub persists as Research (matches Streamlit). Surface the error.
      return NextResponse.json(run.body, { status: run.status });
    }
    return NextResponse.json({ ok: true, sid }, { status: 200 });
  } finally {
    release();
  }
}
```

- [ ] **Step 2: Typecheck + build**

Run: `cd web && npx tsc --noEmit` then `npm run build`
Expected: both clean. `/api/strategy` listed as a dynamic API route. If Next-16 flags `POST(request: Request)`, consult `web/AGENTS.md` + `node_modules/next/dist/docs/`.

- [ ] **Step 3: Full suite (no regressions)**

Run: `cd web && npm run test`
Expected: PASS — prior 112 + 6 new strategy-create tests = 118 (route is integration-verified in Task 4).

- [ ] **Step 4: Commit**

```bash
git add web/app/api/strategy/route.ts
git commit -m "feat(s4): POST /api/strategy (validate, write spec+stub, run backtest)"
```

---

### Task 4: `StrategyForm` + `/strategy/new` page + leaderboard link + runtime verify

**Files:**
- Create: `web/components/strategy-form.tsx`
- Create: `web/app/strategy/new/page.tsx`
- Modify: `web/app/leaderboard/page.tsx`

- [ ] **Step 1: Create the client form**

`web/components/strategy-form.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function StrategyForm() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [type, setType] = useState("Momentum");
  const [description, setDescription] = useState("");
  const [universe, setUniverse] = useState("Nifty 50");
  const [entryFormula, setEntryFormula] = useState("");
  const [timeEnabled, setTimeEnabled] = useState(true);
  const [timeDays, setTimeDays] = useState(30);
  const [hardStopEnabled, setHardStopEnabled] = useState(true);
  const [hardStopPct, setHardStopPct] = useState(8);
  const [trailEnabled, setTrailEnabled] = useState(false);
  const [trailPct, setTrailPct] = useState(12);
  const [maxPositions, setMaxPositions] = useState(5);
  const [initialCash, setInitialCash] = useState(1000000);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/strategy", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
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
        }),
      });
      const data = (await res.json().catch(() => ({}))) as { ok?: boolean; sid?: string; error?: string };
      if (res.ok && data.ok && data.sid) {
        router.push(`/strategy/${data.sid}`);
      } else {
        setError(data.error ?? `Create failed (${res.status})`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error");
    } finally {
      setLoading(false);
    }
  }

  const field = "rounded-md border px-3 py-1.5 text-sm w-full";
  return (
    <form onSubmit={onSubmit} className="max-w-xl space-y-4">
      <label className="block">
        <span className="text-sm font-medium">Name</span>
        <input className={field} value={name} onChange={(e) => setName(e.target.value)} required />
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
        {loading ? "Creating & backtesting… (1–3 min)" : "Create strategy"}
      </button>
      {error && <p className="text-sm text-red-500">{error}</p>}
    </form>
  );
}
```

- [ ] **Step 2: Create the page shell**

`web/app/strategy/new/page.tsx`:

```tsx
import Link from "next/link";
import { StrategyForm } from "@/components/strategy-form";

export const dynamic = "force-dynamic";

export default function NewStrategyPage() {
  return (
    <main className="mx-auto max-w-5xl space-y-6 p-8">
      <Link href="/leaderboard" className="text-sm text-muted-foreground">← Leaderboard</Link>
      <h1 className="text-2xl font-bold">New Strategy</h1>
      <p className="text-sm text-muted-foreground">
        Define a formula-based strategy. Creating runs a backtest (1–3 min) and adds it to the leaderboard.
      </p>
      <StrategyForm />
    </main>
  );
}
```

- [ ] **Step 3: Add the "+ New strategy" link to the leaderboard header**

Edit `web/app/leaderboard/page.tsx`. Add the import:

```tsx
import Link from "next/link";
```

Replace the header block:

```tsx
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Strategy Leaderboard</h1>
        <RecomputeButton />
      </div>
```

with:

```tsx
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Strategy Leaderboard</h1>
        <div className="flex items-center gap-2">
          <Link
            href="/strategy/new"
            className="rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-accent"
          >
            + New strategy
          </Link>
          <RecomputeButton />
        </div>
      </div>
```

Leave the subtitle `<p>` and `<LeaderboardTable>` unchanged.

- [ ] **Step 4: Typecheck + build**

Run: `cd web && npx tsc --noEmit` then `npm run build`
Expected: both clean. `/strategy/new` listed as a route.

- [ ] **Step 5: Runtime verify**

Build, then start prod server on a free port (e.g. 3013) via the Bash tool's `run_in_background` (NOT `&`), cwd `web/`, `python` on PATH, `DATA_DIR=".."` from `web/.env.local`. Wait for boot, then:

```bash
# Form + link render:
curl -s localhost:3013/leaderboard | grep -c "New strategy"
curl -s localhost:3013/strategy/new | grep -c "Entry formula"
# Validation paths (no file written):
curl -s -X POST localhost:3013/api/strategy -H "content-type: application/json" -d '{}'                                  # 400 "name is required"
curl -s -X POST localhost:3013/api/strategy -H "content-type: application/json" -d '{"name":"X","entry_formula":""}'      # 400 entry formula
curl -s -X POST localhost:3013/api/strategy -H "content-type: application/json" -d '{"name":"Monthly Rotation","entry_formula":"a","exits":{"time_enabled":true},"sizing":{"max_positions":5,"initial_cash":1000}}'  # 409 already exists (monthly_rotation)
# Unaffected pages:
curl -s -o /dev/null -w "%{http_code}\n" localhost:3013/
curl -s -o /dev/null -w "%{http_code}\n" localhost:3013/leaderboard
```

Expected: leaderboard grep ≥1; `/strategy/new` grep ≥1; `{}` → 400 `{"ok":false,"error":"name is required"}`; empty formula → 400; the "Monthly Rotation" name derives to `monthly_rotation` which already exists → 409 `{"ok":false,"error":"A strategy with that name already exists"}`; `/` + `/leaderboard` → 200.

Optionally (heavier, writes files + runs a real backtest): POST a NEW unique name with a valid formula (e.g. `{"name":"Web Smoke Test","entry_formula":"rsi_14 > 70 AND close > sma_200","exits":{"time_enabled":true,"time_days":30},"sizing":{"max_positions":5,"initial_cash":1000000}}`). On success it returns `{"ok":true,"sid":"web_smoke_test"}`, writes `strategies/web_smoke_test.json`, and the strategy appears on `/leaderboard`. If `generic_backtest` fails for environment/data reasons, the spec + Research stub still exist (matches design) — report it, do not alter the Python. **If you ran this and it created files, clean them up afterward** (`git checkout strategies_index.json` and `rm strategies/web_smoke_test.json` + its generated CSVs) so the commit stays clean. Deterministic gates are the grep + 400/409 checks. Stop the server when done.

- [ ] **Step 6: Full suite**

Run: `cd web && npm run test`
Expected: PASS — 118.

- [ ] **Step 7: Commit**

```bash
git add web/components/strategy-form.tsx web/app/strategy/new/page.tsx web/app/leaderboard/page.tsx
git commit -m "feat(s4): new-strategy create form + /strategy/new page + leaderboard link"
```

---

## Self-Review

**Spec coverage:**
- `deriveStrategyId` + `summarizeExits` pure helpers → Task 1. ✓
- `writeStrategySpec` + `appendStrategyStub` (atomic, duplicate-throw) + `StrategyStub` → Task 2. ✓
- `POST /api/strategy`: validation (400 name/formula/exit/sizing), dup (409), lock (409), write spec+stub, spawn generic_backtest (600s), stub persists on failure → Task 3. ✓
- Spec shape (entry_mode/exits/sizing) matches generic_backtest reads; stub mirrors `_save_user_strategy` → Tasks 2-3. ✓
- Security: sid sanitized `^[a-z0-9_]+$`, fixed array-args spawn, no shell, formula only into JSON → Task 3. ✓
- UI: `StrategyForm`, `/strategy/new`, leaderboard "+ New strategy" link → Task 4. ✓
- Tests: helpers (vitest); route + form integration-verified (400/409 + grep) → Tasks 1-2 + Task 4. ✓
- Verification: tsc/build, runtime, other pages 200, cleanup of any test artifacts → Task 3-4 steps. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. The optional real-backtest runtime step is explicitly marked optional with cleanup instructions and deterministic gates called out separately.

**Type consistency:** `ExitsSpec` defined in Task 1, consumed by `summarizeExits` (Task 1) and the route (Task 3). `StrategyStub` defined in Task 2, used by `appendStrategyStub` (Task 2) and the route (Task 3) and the test stub factory. `deriveStrategyId`/`summarizeExits`/`writeStrategySpec`/`appendStrategyStub` signatures identical across tasks. `runRecompute`/`SpawnedChild` reused from slices 9/10. Route uses `getStrategy` (existing). The `{ok,sid}` response shape matches what `StrategyForm` reads (`data.sid`). ✓
