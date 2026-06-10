# SSE Backtest Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream a running backtest/rebuild-all/create child's stdout to the UI as live progress (latest line + coarse `[N/5]` phase + mini-log) instead of a blind spinner.

**Architecture:** The POST route keeps the single-job lock, then returns a `ReadableStream` of SSE frames (`event: line` per stdout line, terminal `event: done` with the result JSON). The client reads the stream via `fetch` and runs the existing `router.refresh()`/`push()` on `done`. Pure lib functions (`runRecompute`, `runRebuildAll`) gain an optional `onLine` callback; a server `streamJob` helper wires `onLine → controller.enqueue`. Zero Python changes.

**Tech Stack:** Next.js 16 (App Router, Route Handlers, `ReadableStream`/`Response`), TypeScript, Vitest, React client components. Spec: `docs/superpowers/specs/2026-06-10-s4-sse-progress-design.md`.

**Conventions:**
- Run tests from `web/`: `cd web && npx vitest run <file>`.
- Build gate: `cd web && npm run build` (runs tsc + Turbopack). Must end `✓ Compiled successfully` + `Finished TypeScript`.
- Commit messages: conventional commits, `feat(s4):` / `test(s4):` prefix.
- Do NOT run `git push` (the human pushes).

---

### Task 1: `lib/sse.ts` — pure SSE frame formatter

**Files:**
- Create: `web/lib/sse.ts`
- Test: `web/tests/sse.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// web/tests/sse.test.ts
import { describe, it, expect } from "vitest";
import { sseFrame } from "@/lib/sse";

describe("sseFrame", () => {
  it("formats an event + data frame terminated by a blank line", () => {
    expect(sseFrame("line", "hello")).toBe("event: line\ndata: hello\n\n");
  });
  it("passes JSON data through verbatim (single line)", () => {
    expect(sseFrame("done", '{"ok":true}')).toBe('event: done\ndata: {"ok":true}\n\n');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run tests/sse.test.ts`
Expected: FAIL — `Cannot find module '@/lib/sse'`.

- [ ] **Step 3: Write minimal implementation**

```ts
// web/lib/sse.ts

/**
 * Format a single Server-Sent Events frame. `data` must be a single line
 * (stdout lines are split before framing; JSON has no embedded newlines).
 */
export function sseFrame(event: string, data: string): string {
  return `event: ${event}\ndata: ${data}\n\n`;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run tests/sse.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add web/lib/sse.ts web/tests/sse.test.ts
git commit -m "feat(s4): pure sseFrame formatter"
```

---

### Task 2: `runRecompute` — capture stdout and emit lines via `onLine`

**Files:**
- Modify: `web/lib/recompute.ts` (the `SpawnedChild` interface ~lines 7-13, and `runRecompute` ~lines 35-77)
- Test: `web/tests/recompute.test.ts` (append; existing tests must stay green)

**Context:** Existing fake children in tests have `.stderr` but NO `.stdout`. So `stdout` is OPTIONAL on the interface and accessed defensively (`child.stdout?.on`). The real `child_process.spawn` always has `stdout`.

- [ ] **Step 1: Write the failing test (append to `web/tests/recompute.test.ts`)**

First extend the `makeFakeChild` factory at the top of the file to add a `stdout` EventEmitter:

```ts
// in makeFakeChild(), after `child.stderr = new EventEmitter();` add:
  (child as unknown as { stdout: EventEmitter }).stdout = new EventEmitter();
```

Then append this describe block at the end of the file:

```ts
describe("runRecompute onLine", () => {
  it("emits complete stdout lines, splitting on \\n and \\r, buffering partials", async () => {
    const child = makeFakeChild();
    const stdout = (child as unknown as { stdout: EventEmitter }).stdout;
    const lines: string[] = [];
    const p = runRecompute(() => child as unknown as SpawnedChild, {
      bin: "python", args: [], cwd: ".", timeoutMs: 1000,
      onLine: (l) => lines.push(l),
    });
    stdout.emit("data", "Loading\n[1/5] x\rVali");
    stdout.emit("data", "dated 200\n");
    child.emit("exit", 0);
    await p;
    expect(lines).toEqual(["Loading", "[1/5] x", "Validated 200"]);
  });

  it("does not throw when the child has no stdout (back-compat)", async () => {
    // makeFakeChild has stdout now; simulate a child without it:
    const child = makeFakeChild();
    delete (child as unknown as { stdout?: unknown }).stdout;
    const p = runRecompute(() => child as unknown as SpawnedChild, {
      bin: "python", args: [], cwd: ".", timeoutMs: 1000, onLine: () => {},
    });
    child.emit("exit", 0);
    const r = await p;
    expect(r.status).toBe(200);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run tests/recompute.test.ts`
Expected: FAIL — the new `onLine` block fails (lines empty / `onLine` not in opts type). Existing tests still pass.

- [ ] **Step 3: Implement — add `stdout` to interface, `onLine` to opts, capture + split**

In `web/lib/recompute.ts`, change the `SpawnedChild` interface to add optional `stdout`:

```ts
export interface SpawnedChild {
  stdout?: { on(event: "data", listener: (chunk: unknown) => void): void };
  stderr: { on(event: "data", listener: (chunk: unknown) => void): void };
  on(event: "exit", listener: (code: number | null) => void): void;
  on(event: "error", listener: (err: Error) => void): void;
  kill(): void;
}
```

Add `onLine` to the `runRecompute` opts type:

```ts
  opts: { bin: string; args: string[]; cwd: string; timeoutMs: number; label?: string; onLine?: (line: string) => void },
```

Inside `runRecompute`, after the existing `child.stderr.on("data", ...)` handler, add stdout line pumping:

```ts
    let outBuf = "";
    const pump = (flush: boolean) => {
      if (!opts.onLine) return;
      const parts = outBuf.split(/\r\n|\r|\n/);
      outBuf = flush ? "" : (parts.pop() ?? "");
      for (const line of parts) if (line.length > 0) opts.onLine(line);
    };
    child.stdout?.on("data", (c) => {
      outBuf += String(c);
      pump(false);
    });
```

Then flush on exit — change the existing exit handler to pump first:

```ts
    child.on("exit", (code) => {
      pump(true);
      if (code === 0) done(200, { ok: true, durationMs: Date.now() - start });
      else done(500, { ok: false, error: stderr.trim() || `exit ${code}` });
    });
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `cd web && npx vitest run tests/recompute.test.ts`
Expected: PASS (all original tests + 2 new).

- [ ] **Step 5: Commit**

```bash
git add web/lib/recompute.ts web/tests/recompute.test.ts
git commit -m "feat(s4): runRecompute captures stdout lines via onLine"
```

---

### Task 3: `runRebuildAll` — thread `onLine` + per-strategy header lines

**Files:**
- Modify: `web/lib/rebuild-all.ts` (opts type ~lines 20-28, loop ~lines 33-57)
- Test: `web/tests/rebuild-all.test.ts` (append)

- [ ] **Step 1: Write the failing test (append to `web/tests/rebuild-all.test.ts`)**

```ts
describe("runRebuildAll onLine", () => {
  it("emits a '▶ running <id>' header before each backtest and threads onLine", async () => {
    const { fn } = scriptedSpawn([{ code: 0 }, { code: 0 }, { code: 0 }]);
    const lines: string[] = [];
    await runRebuildAll(fn, {
      ...baseOpts,
      backtests: [
        { id: "a", argv: ["a.py"] },
        { id: "b", argv: ["b.py"] },
      ],
      onLine: (l) => lines.push(l),
    });
    expect(lines).toContain("▶ running a");
    expect(lines).toContain("▶ running b");
    expect(lines).toContain("▶ recompute");
    // headers are in order
    expect(lines.indexOf("▶ running a")).toBeLessThan(lines.indexOf("▶ running b"));
  });
});
```

Note: `scriptedSpawn` children have no stdout, so only the header lines (emitted directly by `runRebuildAll`) appear — that is what we assert.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run tests/rebuild-all.test.ts`
Expected: FAIL — `onLine` not in opts type / headers missing. Existing tests pass.

- [ ] **Step 3: Implement**

In `web/lib/rebuild-all.ts`, add `onLine` to the opts type:

```ts
  opts: {
    backtests: RebuildBacktest[];
    repoRoot: string;
    env: { PYTHON_BIN?: string };
    recompute: { bin: string; args: string[]; cwd: string };
    backtestTimeoutMs: number;
    recomputeTimeoutMs: number;
    onLine?: (line: string) => void;
  },
```

In the backtest loop, emit a header and thread `onLine` into the `runRecompute` call:

```ts
  for (const bt of opts.backtests) {
    let cmd: { bin: string; args: string[]; cwd: string };
    try {
      cmd = resolveBacktest(bt.argv, opts.repoRoot, opts.env);
    } catch (e) {
      failed.push({ id: bt.id, error: errMsg(e) });
      continue;
    }
    opts.onLine?.(`▶ running ${bt.id}`);
    const run = await runRecompute(spawnFn, {
      ...cmd,
      timeoutMs: opts.backtestTimeoutMs,
      label: `Backtest ${bt.id}`,
      onLine: opts.onLine,
    });
    if (run.status === 200) {
      ran.push(bt.id);
    } else {
      failed.push({ id: bt.id, error: run.body.ok ? "" : run.body.error });
    }
  }
```

And before the final recompute:

```ts
  opts.onLine?.("▶ recompute");
  const rc = await runRecompute(spawnFn, {
    ...opts.recompute,
    timeoutMs: opts.recomputeTimeoutMs,
    label: "Recompute",
    onLine: opts.onLine,
  });
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `cd web && npx vitest run tests/rebuild-all.test.ts`
Expected: PASS (existing + new). Note the existing `calls` order tests are unaffected (headers don't spawn).

- [ ] **Step 5: Commit**

```bash
git add web/lib/rebuild-all.ts web/tests/rebuild-all.test.ts
git commit -m "feat(s4): runRebuildAll threads onLine + per-strategy headers"
```

---

### Task 4: `lib/job-stream.ts` — server `streamJob` helper

**Files:**
- Create: `web/lib/job-stream.ts`
- Test: `web/tests/job-stream.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// web/tests/job-stream.test.ts
import { describe, it, expect } from "vitest";
import { streamJob } from "@/lib/job-stream";

describe("streamJob", () => {
  it("streams line frames then a done frame with the result body", async () => {
    const res = streamJob(async (onLine) => {
      onLine("Loading");
      onLine("[1/5] x");
      return { status: 200, body: { ok: true, ran: ["a"] } };
    });
    expect(res.headers.get("content-type")).toContain("text/event-stream");
    const text = await res.text();
    expect(text).toContain("event: line\ndata: Loading\n\n");
    expect(text).toContain("event: line\ndata: [1/5] x\n\n");
    expect(text).toContain('event: done\ndata: {"ok":true,"ran":["a"]}\n\n');
  });

  it("a thrown run becomes a done frame with ok:false", async () => {
    const res = streamJob(async () => {
      throw new Error("kaboom");
    });
    const text = await res.text();
    expect(text).toContain('event: done\ndata: {"ok":false,"error":"kaboom"}\n\n');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run tests/job-stream.test.ts`
Expected: FAIL — `Cannot find module '@/lib/job-stream'`.

- [ ] **Step 3: Write implementation**

```ts
// web/lib/job-stream.ts
import { sseFrame } from "@/lib/sse";

export type JobResult = { status: number; body: unknown };

/**
 * Run a job that may emit progress lines, streaming them as SSE `line` frames,
 * then a terminal `done` frame carrying the result body. The caller acquires the
 * job-lock BEFORE calling this and must release it inside `run`'s own finally.
 * A thrown `run` is captured as a done frame with { ok:false, error }.
 */
export function streamJob(
  run: (onLine: (line: string) => void) => Promise<JobResult>,
): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const enqueue = (frame: string) => {
        try {
          controller.enqueue(encoder.encode(frame));
        } catch {
          // controller closed (client gone) — ignore; job still runs to completion
        }
      };
      let body: unknown;
      try {
        const result = await run((line) => enqueue(sseFrame("line", line)));
        body = result.body;
      } catch (e) {
        body = { ok: false, error: e instanceof Error ? e.message : String(e) };
      }
      enqueue(sseFrame("done", JSON.stringify(body)));
      try {
        controller.close();
      } catch {
        // already closed
      }
    },
  });
  return new Response(stream, {
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
    },
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run tests/job-stream.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add web/lib/job-stream.ts web/tests/job-stream.test.ts
git commit -m "feat(s4): streamJob server helper (SSE line + done frames)"
```

---

### Task 5: `lib/sse-parser.ts` — pure client-side frame parser

**Files:**
- Create: `web/lib/sse-parser.ts`
- Test: `web/tests/sse-parser.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// web/tests/sse-parser.test.ts
import { describe, it, expect } from "vitest";
import { createSseParser, parsePhase } from "@/lib/sse-parser";

describe("createSseParser", () => {
  it("parses a complete frame", () => {
    const p = createSseParser();
    expect(p.push("event: line\ndata: hello\n\n")).toEqual([
      { event: "line", data: "hello" },
    ]);
  });

  it("buffers a frame split across two chunks", () => {
    const p = createSseParser();
    expect(p.push("event: do")).toEqual([]);
    expect(p.push('ne\ndata: {"ok":true}\n\n')).toEqual([
      { event: "done", data: '{"ok":true}' },
    ]);
  });

  it("parses multiple frames in one chunk", () => {
    const p = createSseParser();
    expect(p.push("event: line\ndata: a\n\nevent: line\ndata: b\n\n")).toEqual([
      { event: "line", data: "a" },
      { event: "line", data: "b" },
    ]);
  });
});

describe("parsePhase", () => {
  it("extracts N/M from a [N/M] marker", () => {
    expect(parsePhase("[3/5] Computing indicators")).toBe("3/5");
  });
  it("returns null when there is no marker", () => {
    expect(parsePhase("Validated 200/963")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run tests/sse-parser.test.ts`
Expected: FAIL — `Cannot find module '@/lib/sse-parser'`.

- [ ] **Step 3: Write implementation**

```ts
// web/lib/sse-parser.ts

export interface SseEvent {
  event: string;
  data: string;
}

/** Stateful parser: feed decoded text chunks, get back complete SSE events. */
export function createSseParser(): { push(chunk: string): SseEvent[] } {
  let buf = "";
  return {
    push(chunk: string): SseEvent[] {
      buf += chunk;
      const events: SseEvent[] = [];
      let idx: number;
      while ((idx = buf.indexOf("\n\n")) !== -1) {
        const raw = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        let event = "message";
        let data = "";
        for (const line of raw.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data = line.slice(5).replace(/^ /, "");
        }
        events.push({ event, data });
      }
      return events;
    },
  };
}

/** Extract a coarse "N/M" phase from a "[N/M] …" stdout line, or null. */
export function parsePhase(line: string): string | null {
  const m = line.match(/\[(\d+)\/(\d+)\]/);
  return m ? `${m[1]}/${m[2]}` : null;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run tests/sse-parser.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add web/lib/sse-parser.ts web/tests/sse-parser.test.ts
git commit -m "feat(s4): pure client SSE frame parser + phase extractor"
```

---

### Task 6: `lib/use-job-stream.ts` — client fetch+stream driver

**Files:**
- Create: `web/lib/use-job-stream.ts`
- Test: `web/tests/use-job-stream.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// web/tests/use-job-stream.test.ts
import { describe, it, expect, vi, afterEach } from "vitest";
import { runJobStream } from "@/lib/use-job-stream";

function streamResponse(frames: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const f of frames) controller.enqueue(encoder.encode(f));
      controller.close();
    },
  });
  return new Response(stream, { headers: { "content-type": "text/event-stream" } });
}

afterEach(() => vi.restoreAllMocks());

describe("runJobStream", () => {
  it("invokes onLine/onPhase and resolves with the done payload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        streamResponse([
          "event: line\ndata: [3/5] x\n\n",
          'event: done\ndata: {"ok":true,"ran":["a"]}\n\n',
        ]),
      ),
    );
    const lines: string[] = [];
    const phases: string[] = [];
    const res = await runJobStream("/api/x", { id: "a" }, {
      onLine: (l) => lines.push(l),
      onPhase: (p) => phases.push(p),
    });
    expect(lines).toEqual(["[3/5] x"]);
    expect(phases).toEqual(["3/5"]);
    expect(res.ok).toBe(true);
    expect(res.data).toEqual({ ok: true, ran: ["a"] });
  });

  it("returns the JSON body for a non-stream response (e.g. 409)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ ok: false, error: "A job is already running" }), {
          status: 409,
          headers: { "content-type": "application/json" },
        }),
      ),
    );
    const res = await runJobStream("/api/x", { id: "a" });
    expect(res.status).toBe(409);
    expect(res.ok).toBe(false);
    expect(res.data).toEqual({ ok: false, error: "A job is already running" });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run tests/use-job-stream.test.ts`
Expected: FAIL — `Cannot find module '@/lib/use-job-stream'`.

- [ ] **Step 3: Write implementation**

```ts
// web/lib/use-job-stream.ts
"use client";

import { createSseParser, parsePhase } from "@/lib/sse-parser";

export interface JobStreamHandlers {
  onLine?: (line: string) => void;
  onPhase?: (phase: string) => void;
}

export interface JobStreamResult {
  ok: boolean;
  status: number;
  data: Record<string, unknown>;
}

/**
 * POST to `url`, then read the SSE stream, invoking handlers per progress line,
 * and resolve with the terminal `done` payload. Non-stream responses (validation
 * errors / 409) are returned as plain JSON.
 */
export async function runJobStream(
  url: string,
  body?: unknown,
  handlers: JobStreamHandlers = {},
): Promise<JobStreamResult> {
  const res = await fetch(url, {
    method: "POST",
    headers: body !== undefined ? { "content-type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const ctype = res.headers.get("content-type") ?? "";
  if (!ctype.includes("text/event-stream") || !res.body) {
    const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
    return { ok: res.ok, status: res.status, data };
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const parser = createSseParser();
  let done: Record<string, unknown> | null = null;

  for (;;) {
    const { value, done: finished } = await reader.read();
    if (finished) break;
    for (const ev of parser.push(decoder.decode(value, { stream: true }))) {
      if (ev.event === "line") {
        handlers.onLine?.(ev.data);
        const ph = parsePhase(ev.data);
        if (ph) handlers.onPhase?.(ph);
      } else if (ev.event === "done") {
        try {
          done = JSON.parse(ev.data) as Record<string, unknown>;
        } catch {
          done = { ok: false, error: "bad done frame" };
        }
      }
    }
  }

  const data = done ?? { ok: false, error: "stream ended without result" };
  return { ok: data.ok === true, status: 200, data };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run tests/use-job-stream.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add web/lib/use-job-stream.ts web/tests/use-job-stream.test.ts
git commit -m "feat(s4): runJobStream client fetch+SSE driver"
```

---

### Task 7: Wire the three routes to `streamJob`

**Files:**
- Modify: `web/app/api/rebuild-all/route.ts`
- Modify: `web/app/api/backtest/route.ts`
- Modify: `web/app/api/strategy/route.ts`

No unit tests (these handlers are not unit-tested; the lib seam + build are the gates). Build is the gate at Step 4.

- [ ] **Step 1: Rewrite `rebuild-all/route.ts` `POST`**

Replace the body of `POST` (keep imports; add `streamJob` import). The lock is acquired pre-stream; `release()` moves inside the `run` callback's `finally`:

```ts
import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import path from "node:path";
import { resolveRecompute, type SpawnedChild } from "@/lib/recompute";
import { runRebuildAll } from "@/lib/rebuild-all";
import { getStrategies } from "@/lib/data/strategies";
import { tryAcquire, release } from "@/lib/job-lock";
import { streamJob } from "@/lib/job-stream";

export const dynamic = "force-dynamic";

// Slowest backtest is momentum_edge: ~158s cold / ~107s warm after the perf rewrite.
// 6min ceiling = ~2.3x margin over cold (wall-clock can swing ~2x under load) while
// still surfacing genuine hangs quickly.
const BACKTEST_TIMEOUT_MS = 360_000;
const RECOMPUTE_TIMEOUT_MS = 120_000;

const spawnChild = (b: string, a: string[], o: { cwd: string }) =>
  spawn(b, a, o) as unknown as SpawnedChild;

export async function POST() {
  if (!tryAcquire()) {
    return NextResponse.json({ ok: false, error: "A job is already running" }, { status: 409 });
  }
  return streamJob(async (onLine) => {
    try {
      const repoRoot = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..");
      const strategies = await getStrategies();
      const backtests = strategies
        .filter((s) => s.backtest)
        .map((s) => ({ id: s.id, argv: s.backtest as string[] }));
      const recompute = resolveRecompute(process.env, process.cwd());
      const result = await runRebuildAll(spawnChild, {
        backtests,
        repoRoot,
        env: { PYTHON_BIN: process.env.PYTHON_BIN },
        recompute,
        backtestTimeoutMs: BACKTEST_TIMEOUT_MS,
        recomputeTimeoutMs: RECOMPUTE_TIMEOUT_MS,
        onLine,
      });
      return { status: result.status, body: result.body };
    } finally {
      release();
    }
  });
}
```

- [ ] **Step 2: Rewrite `backtest/route.ts` `POST`**

Keep all validation (id/strategy/backtest config) returning `NextResponse.json` BEFORE the lock. Wrap the job in `streamJob`:

```ts
import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import path from "node:path";
import { runRecompute, resolveBacktest, resolveRecompute, type SpawnedChild } from "@/lib/recompute";
import { getStrategy } from "@/lib/data/strategies";
import { tryAcquire, release } from "@/lib/job-lock";
import { streamJob } from "@/lib/job-stream";

export const dynamic = "force-dynamic";

const BACKTEST_TIMEOUT_MS = 360_000;
const RECOMPUTE_TIMEOUT_MS = 120_000;

const spawnChild = (b: string, a: string[], o: { cwd: string }) =>
  spawn(b, a, o) as unknown as SpawnedChild;

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as { id?: unknown };
  const id = body.id;
  if (typeof id !== "string" || id.length === 0) {
    return NextResponse.json({ ok: false, error: "missing id" }, { status: 400 });
  }
  const strategy = await getStrategy(id);
  if (!strategy) {
    return NextResponse.json({ ok: false, error: "unknown strategy" }, { status: 404 });
  }
  if (!strategy.backtest) {
    return NextResponse.json(
      { ok: false, error: "backtest not configured for this strategy" },
      { status: 422 },
    );
  }
  if (!tryAcquire()) {
    return NextResponse.json({ ok: false, error: "A job is already running" }, { status: 409 });
  }
  return streamJob(async (onLine) => {
    try {
      const repoRoot = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..");
      let bt: { bin: string; args: string[]; cwd: string };
      try {
        bt = resolveBacktest(strategy.backtest, repoRoot, { PYTHON_BIN: process.env.PYTHON_BIN });
      } catch (e) {
        return { status: 500, body: { ok: false, error: e instanceof Error ? e.message : String(e) } };
      }
      const backtestRun = await runRecompute(spawnChild, {
        ...bt, timeoutMs: BACKTEST_TIMEOUT_MS, label: "Backtest", onLine,
      });
      if (backtestRun.status !== 200) {
        return { status: backtestRun.status, body: backtestRun.body };
      }
      const rc = resolveRecompute(process.env, process.cwd());
      const recomputeRun = await runRecompute(spawnChild, {
        ...rc, timeoutMs: RECOMPUTE_TIMEOUT_MS, label: "Recompute", onLine,
      });
      return { status: recomputeRun.status, body: recomputeRun.body };
    } finally {
      release();
    }
  });
}
```

- [ ] **Step 3: Rewrite `strategy/route.ts` `POST`**

Keep ALL validation + the dup-check + `tryAcquire` BEFORE the stream (unchanged, lines 33-69). Replace the `try { … } finally { release(); }` block (lines 70-114) with a `streamJob` whose `run` does the write + spawn and releases in `finally`:

```ts
  return streamJob(async (onLine) => {
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
        const msg = e instanceof Error ? e.message : String(e);
        const status = msg.includes("already exists") ? 409 : 500;
        return { status, body: { ok: false, error: msg } };
      }

      const repoRoot = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..");
      const run = await runRecompute(spawnChild, {
        bin: process.env.PYTHON_BIN ?? "python",
        args: ["generic_backtest.py", "--spec", `strategies/${sid}.json`],
        cwd: repoRoot,
        timeoutMs: CREATE_TIMEOUT_MS,
        label: "Backtest",
        onLine,
      });
      if (run.status !== 200) {
        return { status: run.status, body: run.body };
      }
      return { status: 200, body: { ok: true, sid } };
    } finally {
      release();
    }
  });
```

Add the import at the top of `strategy/route.ts`:

```ts
import { streamJob } from "@/lib/job-stream";
```

- [ ] **Step 4: Build gate**

Run: `cd web && npm run build`
Expected: `✓ Compiled successfully` and `Finished TypeScript`. No type errors. (Pre-existing warnings about multiple lockfiles / next.config NFT are fine.)

- [ ] **Step 5: Commit**

```bash
git add web/app/api/rebuild-all/route.ts web/app/api/backtest/route.ts web/app/api/strategy/route.ts
git commit -m "feat(s4): stream backtest/rebuild-all/create progress via streamJob"
```

---

### Task 8: UI — `JobProgress` component + wire the three buttons

**Files:**
- Create: `web/components/job-progress.tsx`
- Modify: `web/components/rebuild-all-button.tsx`
- Modify: `web/components/backtest-button.tsx`
- Modify: `web/components/strategy-form.tsx`

No unit tests (presentational + integration; build gate + runtime verify). Build is the gate at Step 5.

- [ ] **Step 1: Create `components/job-progress.tsx`**

```tsx
// web/components/job-progress.tsx
"use client";

import { useState } from "react";

interface JobProgressProps {
  phase: string | null;
  lines: string[];
}

/** Live progress display: latest line + coarse phase, with a collapsible mini-log. */
export function JobProgress({ phase, lines }: JobProgressProps) {
  const [open, setOpen] = useState(false);
  const latest = lines.length > 0 ? lines[lines.length - 1] : "";
  if (lines.length === 0 && !phase) return null;
  return (
    <div className="flex flex-col items-end gap-1 text-sm text-muted-foreground">
      <span className="font-mono">
        {phase ? `[${phase}] ` : ""}
        {latest}
      </span>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="text-xs underline"
      >
        {open ? "hide log" : "show log"}
      </button>
      {open && (
        <pre className="max-h-40 w-80 overflow-auto rounded border bg-muted p-2 text-left text-xs">
          {lines.slice(-10).join("\n")}
        </pre>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Wire `rebuild-all-button.tsx`**

Replace the `fetch`/`await res.json()` flow with `runJobStream`, tracking `lines`/`phase`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { runJobStream } from "@/lib/use-job-stream";
import { JobProgress } from "@/components/job-progress";

export function RebuildAllButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);
  const [lines, setLines] = useState<string[]>([]);
  const [phase, setPhase] = useState<string | null>(null);

  async function onClick() {
    setLoading(true);
    setSummary(null);
    setIsError(false);
    setLines([]);
    setPhase(null);
    try {
      const res = await runJobStream("/api/rebuild-all", undefined, {
        onLine: (l) => setLines((prev) => [...prev.slice(-199), l]),
        onPhase: (p) => setPhase(p),
      });
      const data = res.data as {
        ok?: boolean;
        ran?: string[];
        failed?: { id: string }[];
        error?: string;
      };
      if (res.status === 409) {
        setIsError(true);
        setSummary(data.error ?? "A job is already running");
        return;
      }
      router.refresh();
      const ran = data.ran?.length ?? 0;
      const failed = data.failed ?? [];
      if (failed.length > 0) {
        setIsError(true);
        setSummary(`Rebuilt ${ran} · failed: ${failed.map((f) => f.id).join(", ")}`);
      } else if (data.ok === false) {
        setIsError(true);
        setSummary(`Rebuilt ${ran} · recompute failed`);
      } else {
        setSummary(`Rebuilt ${ran}`);
      }
    } catch (e) {
      setIsError(true);
      setSummary(e instanceof Error ? e.message : "Network error");
    } finally {
      setLoading(false);
      setPhase(null);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        onClick={onClick}
        disabled={loading}
        className="rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-50"
      >
        {loading ? "Rebuilding all…" : "⟳ Rebuild All"}
      </button>
      {loading && <JobProgress phase={phase} lines={lines} />}
      {summary && (
        <span className={`text-sm ${isError ? "text-red-500" : "text-muted-foreground"}`}>
          {summary}
        </span>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Wire `backtest-button.tsx`**

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { runJobStream } from "@/lib/use-job-stream";
import { JobProgress } from "@/components/job-progress";

export function BacktestButton({ strategyId }: { strategyId: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [phase, setPhase] = useState<string | null>(null);

  async function onClick() {
    setLoading(true);
    setError(null);
    setLines([]);
    setPhase(null);
    try {
      const res = await runJobStream("/api/backtest", { id: strategyId }, {
        onLine: (l) => setLines((prev) => [...prev.slice(-199), l]),
        onPhase: (p) => setPhase(p),
      });
      const data = res.data as { ok?: boolean; error?: string };
      if (res.ok && data.ok) {
        router.refresh();
      } else {
        setError(data.error ?? `Backtest failed (${res.status})`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Network error");
    } finally {
      setLoading(false);
      setPhase(null);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        onClick={onClick}
        disabled={loading}
        className="rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-50"
      >
        {loading ? "Running backtest…" : "▶ Run Backtest"}
      </button>
      {loading && <JobProgress phase={phase} lines={lines} />}
      {error && <span className="text-sm text-red-500">{error}</span>}
    </div>
  );
}
```

- [ ] **Step 4: Wire `strategy-form.tsx`**

Add the two imports, add `lines`/`phase` state near the other `useState` calls, and replace the `fetch` block in `onSubmit`. Imports:

```tsx
import { runJobStream } from "@/lib/use-job-stream";
import { JobProgress } from "@/components/job-progress";
```

State (add after `const [error, setError] = useState<string | null>(null);`):

```tsx
  const [lines, setLines] = useState<string[]>([]);
  const [phase, setPhase] = useState<string | null>(null);
```

Replace the body of `onSubmit`'s `try` (the `fetch` + `res.json` + branch) with:

```tsx
      setLines([]);
      setPhase(null);
      const res = await runJobStream("/api/strategy", {
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
      });
      const data = res.data as { ok?: boolean; sid?: string; error?: string };
      if (res.ok && data.ok && data.sid) {
        router.push(`/strategy/${data.sid}`);
      } else {
        setError(data.error ?? `Create failed (${res.status})`);
      }
```

Then add `<JobProgress>` to the form's JSX, right before the `{error && …}` line:

```tsx
      {loading && <JobProgress phase={phase} lines={lines} />}
      {error && <p className="text-sm text-red-500">{error}</p>}
```

- [ ] **Step 5: Build gate + full test suite**

Run: `cd web && npm run build && npx vitest run`
Expected: build `✓ Compiled successfully` + `Finished TypeScript`; vitest all green (includes the new sse/job-stream/parser/use-job-stream/recompute/rebuild-all tests).

- [ ] **Step 6: Commit**

```bash
git add web/components/job-progress.tsx web/components/rebuild-all-button.tsx web/components/backtest-button.tsx web/components/strategy-form.tsx
git commit -m "feat(s4): live JobProgress on Rebuild All, Backtest, and Create"
```

---

## Final verification (after all tasks)

Runtime-verify via the `verify` skill: `next start` on an isolated port, click **Rebuild All**, observe the latest-line + coarse `[N/5]` phase advancing and the mini-log filling, then the leaderboard refresh when `done` fires. Probe a concurrent click → still surfaces the 409 "A job is already running". Discard any data churn the verification produces.

## Self-Review notes

- **Spec coverage:** fidelity (raw log + `[N/5]`) → Tasks 2/5/8; transport A (POST stream) → Tasks 4/6/7; UI inline+mini-log → Task 8; scope (3 long actions, not recompute) → Task 7 touches only those three routes; error/lock/disconnect handling → Tasks 4 (enqueue guard, done-on-throw) + 7 (lock pre-stream, release in run finally); testing → Tasks 1-6; security unchanged (no new spawn input) → Task 7 keeps trusted argv.
- **Type consistency:** `onLine?: (line: string) => void` identical across recompute opts (Task 2), rebuild-all opts (Task 3), streamJob `run` param (Task 4); `JobResult = { status, body }` (Task 4) matches what each route's `run` returns (Task 7); `runJobStream → { ok, status, data }` (Task 6) matches button usage (Task 8); `JobProgress({ phase, lines })` (Task 8 Step 1) matches all three call sites.
- **No placeholders:** every code step has complete code.
