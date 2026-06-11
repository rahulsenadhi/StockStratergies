# DSL Dry-Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Preview signals" action to the strategy form that validates an entry-formula (DSL) and reports today's matches + recent firing rate, without running a full backtest.

**Architecture:** A thin Python CLI (`dryrun.py`) reuses `generic_backtest` helpers to load the universe, compute features, detect unknown feature names, and emit one JSON blob. A no-lock Next.js route spawns it, collects stdout, parses the JSON, and returns it. The strategy form gets a Preview button + result card. Logic lives in testable pure functions; the route handler stays thin (matches the repo's existing test-the-helper pattern).

**Tech Stack:** Python (pandas, pytest), Next.js route handlers (Node `child_process.spawn`), React (client component), Vitest.

**Spec:** `docs/superpowers/specs/2026-06-11-s4-dsl-dryrun-design.md`

---

## File Structure

- **Create** `dryrun.py` — CLI + pure functions `extract_unknown_features`, `compute_preview`, `run_dryrun`, `main`. Reuses `_load_universe`, `_compute_features`, `_evaluate_signals` from `generic_backtest`.
- **Create** `tests/test_dryrun.py` — pytest for the pure functions + `run_dryrun` paths.
- **Create** `web/lib/spawn-collect.ts` — `collectJob` (spawn → collect stdout → status/body) + `parseDryrunJson` (scan stdout for the JSON blob).
- **Create** `web/tests/spawn-collect.test.ts` — Vitest with fake child + parse cases.
- **Create** `web/app/api/strategy/dryrun/route.ts` — thin POST handler.
- **Create** `web/lib/dryrun-validate.ts` — `validateDryrunBody` pure validator.
- **Create** `web/tests/dryrun-validate.test.ts` — Vitest for the validator.
- **Modify** `web/components/strategy-form.tsx` — add Preview button, state, result card.

---

## Task 1: Python — unknown-feature extraction

**Files:**
- Create: `dryrun.py`
- Test: `tests/test_dryrun.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_dryrun.py`:

```python
"""Unit tests for dryrun.py — DSL dry-run preview (S4 slice).

Real signatures (read dryrun.py before writing):
  extract_unknown_features(formula: str, known: set[str]) -> list[str]
  compute_preview(feat: pd.DataFrame, formula: str, history_days: int = 90) -> dict
  run_dryrun(formula: str, universe: str) -> dict
"""
import pandas as pd
import pytest

import dryrun as D


def test_extract_unknown_flags_typos():
    unknown = D.extract_unknown_features("rsi_14 > 70 AND xyz_bad > 1", D.KNOWN_FEATURES)
    assert unknown == ["xyz_bad"]


def test_extract_unknown_ignores_logical_keywords_and_numbers():
    # AND/OR/NOT (any case) and numeric literals are never "features"
    unknown = D.extract_unknown_features("rsi_14 > 70 and close > 0 OR not volume_z > 2", D.KNOWN_FEATURES)
    assert unknown == []


def test_extract_unknown_dedupes_preserving_order():
    unknown = D.extract_unknown_features("foo > 1 AND bar > 2 AND foo > 3", D.KNOWN_FEATURES)
    assert unknown == ["foo", "bar"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dryrun.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'dryrun'` (or AttributeError).

- [ ] **Step 3: Write minimal implementation**

Create `dryrun.py`:

```python
"""DSL dry-run: validate an entry formula and preview its signals without a full
backtest. Reuses the generic_backtest feature pipeline so counts are honest.

CLI:
    python dryrun.py --formula "rsi_14 > 70 AND close > sma_200" --universe "Nifty 50"

Prints one JSON blob to stdout (see run_dryrun for the contract).
"""
from __future__ import annotations

import argparse
import json
import re

from generic_backtest import _load_universe, _compute_features, _evaluate_signals

# Feature columns produced by generic_backtest._compute_features.
KNOWN_FEATURES = {"close", "volume", "rsi_14", "atr_14", "sma_50", "sma_200", "volume_z"}
_LOGICAL = {"and", "or", "not"}
_IDENT_RE = re.compile(r"[A-Za-z_]\w*")


def extract_unknown_features(formula: str, known: set[str]) -> list[str]:
    """Return identifiers in the formula that are neither a known feature nor a
    logical keyword (AND/OR/NOT). De-duplicated, first-seen order preserved.
    Numeric literals never match the identifier regex."""
    unknown: list[str] = []
    seen: set[str] = set()
    for tok in _IDENT_RE.findall(formula):
        if tok.lower() in _LOGICAL or tok in known or tok in seen:
            continue
        seen.add(tok)
        unknown.append(tok)
    return unknown
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_dryrun.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add dryrun.py tests/test_dryrun.py
git commit -m "feat(dryrun): unknown-feature extraction for DSL preview"
```

---

## Task 2: Python — signal preview window

**Files:**
- Modify: `dryrun.py`
- Test: `tests/test_dryrun.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_dryrun.py`:

```python
def _panel():
    """3 trading days, 2 tickers. rsi>70 fires: AAA day1+day3, BBB day2."""
    dates = pd.to_datetime(["2026-06-01", "2026-06-02", "2026-06-03"])
    aaa = pd.DataFrame({"ticker": "AAA", "rsi_14": [80, 50, 90],
                        "close": [10, 11, 12], "sma_200": [5, 5, 5]}, index=dates)
    bbb = pd.DataFrame({"ticker": "BBB", "rsi_14": [40, 75, 30],
                        "close": [10, 11, 12], "sma_200": [5, 5, 5]}, index=dates)
    return pd.concat([aaa, bbb]).sort_index()


def test_compute_preview_today_matches():
    p = D.compute_preview(_panel(), "rsi_14 > 70")
    assert p["today"]["date"] == "2026-06-03"
    assert p["today"]["count"] == 1          # only AAA fires on the last day
    assert p["today"]["tickers"] == ["AAA"]


def test_compute_preview_history_counts():
    p = D.compute_preview(_panel(), "rsi_14 > 70")
    assert p["history"]["trading_days"] == 3  # fewer than 90 -> all available
    assert p["history"]["signal_rows"] == 3   # AAA d1, BBB d2, AAA d3
    assert p["history"]["distinct_tickers"] == 2


def test_compute_preview_dead_formula_zeroes():
    p = D.compute_preview(_panel(), "rsi_14 > 200")
    assert p["today"]["count"] == 0
    assert p["history"]["signal_rows"] == 0
    assert p["today"]["tickers"] == []


def test_compute_preview_caps_ticker_list_at_25():
    dates = pd.to_datetime(["2026-06-01"])
    frames = [pd.DataFrame({"ticker": f"T{i:02d}", "rsi_14": [99]}, index=dates) for i in range(30)]
    p = D.compute_preview(pd.concat(frames).sort_index(), "rsi_14 > 70")
    assert p["today"]["count"] == 30           # full count reported
    assert len(p["today"]["tickers"]) == 25     # list truncated
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dryrun.py -q`
Expected: FAIL — `AttributeError: module 'dryrun' has no attribute 'compute_preview'`.

- [ ] **Step 3: Write minimal implementation**

Add to `dryrun.py`:

```python
TICKER_LIST_CAP = 25
HISTORY_DAYS = 90


def compute_preview(feat, formula: str, history_days: int = HISTORY_DAYS) -> dict:
    """Evaluate a (pre-validated) formula on the feature panel and return today's
    matches + recent firing stats. `feat` is indexed by trading date and has a
    'ticker' column plus feature columns."""
    mask = _evaluate_signals(feat, formula)
    f = feat.assign(_m=mask)
    dates = f.index.unique().sort_values()
    last_day = dates[-1]
    win_start = dates[-history_days] if len(dates) >= history_days else dates[0]

    today_rows = f[(f.index == last_day) & f["_m"]]
    win_rows = f[(f.index >= win_start) & f["_m"]]
    tickers = sorted(today_rows["ticker"].tolist())
    day_str = last_day.date().isoformat() if hasattr(last_day, "date") else str(last_day)

    return {
        "today": {
            "date": day_str,
            "count": int(len(today_rows)),
            "tickers": tickers[:TICKER_LIST_CAP],
        },
        "history": {
            "trading_days": int(min(len(dates), history_days)),
            "signal_rows": int(len(win_rows)),
            "distinct_tickers": int(win_rows["ticker"].nunique()),
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_dryrun.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add dryrun.py tests/test_dryrun.py
git commit -m "feat(dryrun): today + last-90d signal preview window"
```

---

## Task 3: Python — run_dryrun orchestration + CLI

**Files:**
- Modify: `dryrun.py`
- Test: `tests/test_dryrun.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_dryrun.py`:

```python
def test_run_dryrun_empty_formula():
    r = D.run_dryrun("   ", "Nifty 50")
    assert r == {"ok": False, "error": "empty formula"}


def test_run_dryrun_unknown_feature_short_circuits(monkeypatch):
    # Must NOT touch the universe loader when a feature name is bad.
    def boom(_spec):
        raise AssertionError("universe loader should not be called")
    monkeypatch.setattr(D, "_load_universe", boom)
    r = D.run_dryrun("rsi_14 > 70 AND xyz_bad > 1", "Nifty 50")
    assert r["ok"] is False
    assert r["unknown_features"] == ["xyz_bad"]
    assert "xyz_bad" in r["error"]


def test_run_dryrun_success(monkeypatch):
    monkeypatch.setattr(D, "_load_universe", lambda _spec: {"AAA": "df"})
    monkeypatch.setattr(D, "_compute_features", lambda _ohlcv: _panel())
    r = D.run_dryrun("rsi_14 > 70", "Nifty 50")
    assert r["ok"] is True
    assert r["universe"] == "Nifty 50"
    assert r["today"]["count"] == 1
    assert r["history"]["signal_rows"] == 3


def test_run_dryrun_no_data(monkeypatch):
    monkeypatch.setattr(D, "_load_universe", lambda _spec: {})
    r = D.run_dryrun("rsi_14 > 70", "Bogus")
    assert r["ok"] is False
    assert "Bogus" in r["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dryrun.py -q`
Expected: FAIL — `AttributeError: module 'dryrun' has no attribute 'run_dryrun'`.

- [ ] **Step 3: Write minimal implementation**

Add to `dryrun.py`. Note `_compute_features` is bound at module import; tests monkeypatch `D._compute_features`, so call it via the module-level name (already imported):

```python
def run_dryrun(formula: str, universe: str) -> dict:
    formula = (formula or "").strip()
    if not formula:
        return {"ok": False, "error": "empty formula"}

    unknown = extract_unknown_features(formula, KNOWN_FEATURES)
    if unknown:
        return {
            "ok": False,
            "error": f"unknown feature(s): {', '.join(unknown)}",
            "unknown_features": unknown,
        }

    try:
        ohlcv = _load_universe({"universe": universe})
        if not ohlcv:
            return {"ok": False, "error": f"no data for universe {universe}"}
        feat = _compute_features(ohlcv).sort_index()
        if feat.empty:
            return {"ok": False, "error": "no features computable (too little history)"}
        preview = compute_preview(feat, formula)
        return {"ok": True, "universe": universe, **preview}
    except Exception as e:  # noqa: BLE001 — surface any engine error to the UI
        return {"ok": False, "error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--formula", required=True)
    ap.add_argument("--universe", default="Nifty 50")
    args = ap.parse_args()
    print(json.dumps(run_dryrun(args.formula, args.universe)))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_dryrun.py -q`
Expected: PASS (11 passed).

- [ ] **Step 5: Manual smoke (real data)**

Run: `python dryrun.py --formula "rsi_14 > 70 AND close > sma_200" --universe "Nifty 50"`
Expected: a single JSON line with `"ok": true` and a non-zero `today.count` (load noise from `load_ohlcv` may precede the JSON — that's fine; the route scans for it).

- [ ] **Step 6: Commit**

```bash
git add dryrun.py tests/test_dryrun.py
git commit -m "feat(dryrun): run_dryrun orchestration + CLI entrypoint"
```

---

## Task 4: TS — spawn-collect helper

**Files:**
- Create: `web/lib/spawn-collect.ts`
- Test: `web/tests/spawn-collect.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/tests/spawn-collect.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { EventEmitter } from "node:events";
import { collectJob, parseDryrunJson, type SpawnedChild } from "@/lib/spawn-collect";

function makeFakeChild() {
  const child = new EventEmitter() as EventEmitter & {
    stdout: EventEmitter; stderr: EventEmitter; kill: () => void; killed: boolean;
  };
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.killed = false;
  child.kill = () => { child.killed = true; };
  return child;
}

describe("collectJob", () => {
  it("exit 0 -> 200 with collected stdout", async () => {
    const child = makeFakeChild();
    const p = collectJob(() => child as unknown as SpawnedChild, {
      bin: "python", args: [], cwd: ".", timeoutMs: 1000,
    });
    child.stdout.emit("data", '{"ok":');
    child.stdout.emit("data", "true}\n");
    child.emit("exit", 0);
    const r = await p;
    expect(r.status).toBe(200);
    if (r.status === 200) expect(r.stdout).toBe('{"ok":true}\n');
  });

  it("nonzero exit -> 500 with stderr text", async () => {
    const child = makeFakeChild();
    const p = collectJob(() => child as unknown as SpawnedChild, {
      bin: "python", args: [], cwd: ".", timeoutMs: 1000,
    });
    child.stderr.emit("data", "Traceback: boom");
    child.emit("exit", 1);
    const r = await p;
    expect(r.status).toBe(500);
    if (r.status !== 200) expect(r.error).toBe("Traceback: boom");
  });

  it("timeout -> 504 and kills the child", async () => {
    const child = makeFakeChild();
    const r = await collectJob(() => child as unknown as SpawnedChild, {
      bin: "python", args: [], cwd: ".", timeoutMs: 10,
    });
    expect(r.status).toBe(504);
    expect(child.killed).toBe(true);
  });

  it("throwing spawnFn -> 500", async () => {
    const r = await collectJob(() => { throw new Error("cannot spawn"); }, {
      bin: "python", args: [], cwd: ".", timeoutMs: 1000,
    });
    expect(r.status).toBe(500);
    if (r.status !== 200) expect(r.error).toBe("cannot spawn");
  });
});

describe("parseDryrunJson", () => {
  it("parses the last JSON object line, ignoring leading noise", () => {
    const out = "Loaded 157 tickers\n[features]\n{\"ok\":true,\"today\":{\"count\":3}}\n";
    expect(parseDryrunJson(out)).toEqual({ ok: true, today: { count: 3 } });
  });
  it("returns null when no JSON object is present", () => {
    expect(parseDryrunJson("just logs\nno json here\n")).toBeNull();
  });
  it("returns null on malformed JSON", () => {
    expect(parseDryrunJson("{not valid}")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (in `web/`): `npx vitest run tests/spawn-collect.test.ts`
Expected: FAIL — cannot resolve `@/lib/spawn-collect`.

- [ ] **Step 3: Write minimal implementation**

Create `web/lib/spawn-collect.ts`:

```typescript
/** Spawn a short-lived subprocess, collect its full stdout, and map the outcome
 *  to an HTTP status. Unlike runRecompute (SSE/line-streaming), this buffers the
 *  whole output for one-shot JSON parsing. spawnFn is injected for testability. */

export interface SpawnedChild {
  stdout?: { on(event: "data", listener: (chunk: unknown) => void): void };
  stderr: { on(event: "data", listener: (chunk: unknown) => void): void };
  on(event: "exit", listener: (code: number | null) => void): void;
  on(event: "error", listener: (err: Error) => void): void;
  kill(): void;
}

export type SpawnFn = (bin: string, args: string[], opts: { cwd: string }) => SpawnedChild;

export type CollectOutcome =
  | { status: 200; stdout: string }
  | { status: number; error: string };

const errMsg = (e: unknown): string => (e instanceof Error ? e.message : String(e));

export function collectJob(
  spawnFn: SpawnFn,
  opts: { bin: string; args: string[]; cwd: string; timeoutMs: number; label?: string },
): Promise<CollectOutcome> {
  return new Promise((resolve) => {
    let settled = false;
    let stdout = "";
    let stderr = "";
    let child: SpawnedChild | undefined;

    const done = (o: CollectOutcome) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(o);
    };

    const timer = setTimeout(() => {
      try { child?.kill(); } catch { /* already timing out */ }
      done({ status: 504, error: `${opts.label ?? "Job"} timed out` });
    }, opts.timeoutMs);

    try {
      child = spawnFn(opts.bin, opts.args, { cwd: opts.cwd });
    } catch (e) {
      done({ status: 500, error: errMsg(e) });
      return;
    }

    child.stdout?.on("data", (c) => { stdout += String(c); });
    child.stderr.on("data", (c) => { stderr += String(c); });
    child.on("error", (e) => done({ status: 500, error: errMsg(e) }));
    child.on("exit", (code) => {
      if (code === 0) done({ status: 200, stdout });
      else done({ status: 500, error: stderr.trim() || `exit ${code}` });
    });
  });
}

/** Scan subprocess stdout for the dry-run JSON blob. The Python tool may print
 *  data-loading noise before the JSON, so we take the last line that parses to a
 *  JSON object. Returns null if none parses. */
export function parseDryrunJson(stdout: string): Record<string, unknown> | null {
  const lines = stdout.split(/\r\n|\r|\n/);
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i].trim();
    if (!line.startsWith("{")) continue;
    try {
      const parsed = JSON.parse(line);
      if (parsed && typeof parsed === "object") return parsed as Record<string, unknown>;
    } catch { /* try the previous line */ }
  }
  return null;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (in `web/`): `npx vitest run tests/spawn-collect.test.ts`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add web/lib/spawn-collect.ts web/tests/spawn-collect.test.ts
git commit -m "feat(s4): spawn-collect helper for one-shot subprocess JSON"
```

---

## Task 5: TS — dry-run body validator

**Files:**
- Create: `web/lib/dryrun-validate.ts`
- Test: `web/tests/dryrun-validate.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/tests/dryrun-validate.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { validateDryrunBody } from "@/lib/dryrun-validate";

describe("validateDryrunBody", () => {
  it("accepts a non-empty formula and trims it; defaults universe", () => {
    const r = validateDryrunBody({ entry_formula: "  rsi_14 > 70  " });
    expect(r).toEqual({ ok: true, formula: "rsi_14 > 70", universe: "Nifty 50" });
  });
  it("keeps a provided universe", () => {
    const r = validateDryrunBody({ entry_formula: "x > 1", universe: "Nifty 500" });
    expect(r).toEqual({ ok: true, formula: "x > 1", universe: "Nifty 500" });
  });
  it("rejects an empty/whitespace formula", () => {
    expect(validateDryrunBody({ entry_formula: "   " })).toEqual({ ok: false, error: "entry_formula is required" });
  });
  it("rejects a missing/non-string formula", () => {
    expect(validateDryrunBody({})).toEqual({ ok: false, error: "entry_formula is required" });
    expect(validateDryrunBody({ entry_formula: 42 })).toEqual({ ok: false, error: "entry_formula is required" });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (in `web/`): `npx vitest run tests/dryrun-validate.test.ts`
Expected: FAIL — cannot resolve `@/lib/dryrun-validate`.

- [ ] **Step 3: Write minimal implementation**

Create `web/lib/dryrun-validate.ts`:

```typescript
export type DryrunValidation =
  | { ok: true; formula: string; universe: string }
  | { ok: false; error: string };

interface DryrunBody {
  entry_formula?: unknown;
  universe?: unknown;
}

const DEFAULT_UNIVERSE = "Nifty 50";

export function validateDryrunBody(body: DryrunBody): DryrunValidation {
  const formula = typeof body.entry_formula === "string" ? body.entry_formula.trim() : "";
  if (!formula) return { ok: false, error: "entry_formula is required" };
  const universe =
    typeof body.universe === "string" && body.universe.trim() ? body.universe.trim() : DEFAULT_UNIVERSE;
  return { ok: true, formula, universe };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (in `web/`): `npx vitest run tests/dryrun-validate.test.ts`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add web/lib/dryrun-validate.ts web/tests/dryrun-validate.test.ts
git commit -m "feat(s4): dry-run request body validator"
```

---

## Task 6: TS — dry-run API route

**Files:**
- Create: `web/app/api/strategy/dryrun/route.ts`

This handler composes the already-tested `validateDryrunBody`, `collectJob`, and `parseDryrunJson`. No new logic to unit-test; verified by manual exercise in Step 3.

- [ ] **Step 1: Write the route**

Create `web/app/api/strategy/dryrun/route.ts`:

```typescript
import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import path from "node:path";
import { collectJob, parseDryrunJson, type SpawnedChild } from "@/lib/spawn-collect";
import { validateDryrunBody } from "@/lib/dryrun-validate";

export const dynamic = "force-dynamic";

const DRYRUN_TIMEOUT_MS = 120_000;

const spawnChild = (b: string, a: string[], o: { cwd: string }) =>
  spawn(b, a, {
    cwd: o.cwd,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
  }) as unknown as SpawnedChild;

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  const v = validateDryrunBody(body);
  if (!v.ok) return NextResponse.json({ ok: false, error: v.error }, { status: 400 });

  const repoRoot = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..");
  const out = await collectJob(spawnChild, {
    bin: process.env.PYTHON_BIN ?? "python",
    args: ["dryrun.py", "--formula", v.formula, "--universe", v.universe],
    cwd: repoRoot,
    timeoutMs: DRYRUN_TIMEOUT_MS,
    label: "Preview",
  });

  if (out.status !== 200) {
    return NextResponse.json({ ok: false, error: out.error }, { status: out.status });
  }

  const parsed = parseDryrunJson(out.stdout);
  if (!parsed) {
    return NextResponse.json({ ok: false, error: "could not parse preview output" }, { status: 500 });
  }
  // Formula-invalid / unknown-feature is a valid request with a bad formula:
  // pass the python JSON through as HTTP 200 with ok:false.
  return NextResponse.json(parsed, { status: 200 });
}
```

- [ ] **Step 2: Verify the build/type-check passes**

Run (in `web/`): `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Manual exercise (dev server running)**

Start the dev server if not running (`npm run dev` in `web/`), then:

```bash
curl -s -X POST http://localhost:3000/api/strategy/dryrun \
  -H 'content-type: application/json' \
  -d '{"entry_formula":"rsi_14 > 70 AND close > sma_200","universe":"Nifty 50"}'
```
Expected: `{"ok":true,"universe":"Nifty 50","today":{...},"history":{...}}`.

Then a bad feature:
```bash
curl -s -X POST http://localhost:3000/api/strategy/dryrun \
  -H 'content-type: application/json' \
  -d '{"entry_formula":"rsi_14 > 70 AND xyz_bad > 1"}'
```
Expected: HTTP 200, `{"ok":false,"error":"unknown feature(s): xyz_bad","unknown_features":["xyz_bad"]}`.

Then empty formula:
```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:3000/api/strategy/dryrun \
  -H 'content-type: application/json' -d '{"entry_formula":"  "}'
```
Expected: `400`.

- [ ] **Step 4: Commit**

```bash
git add web/app/api/strategy/dryrun/route.ts
git commit -m "feat(s4): /api/strategy/dryrun route (no lock, JSON one-shot)"
```

---

## Task 7: Frontend — Preview button + result card

**Files:**
- Modify: `web/components/strategy-form.tsx`

This repo has no React component unit tests; verification is manual (Step 4), consistent with existing practice.

- [ ] **Step 1: Add preview state and handler**

In `web/components/strategy-form.tsx`, add a result type near the top (after imports):

```typescript
type DryrunResult =
  | { ok: true; universe: string; today: { date: string; count: number; tickers: string[] }; history: { trading_days: number; signal_rows: number; distinct_tickers: number } }
  | { ok: false; error: string; unknown_features?: string[] };
```

Inside `StrategyForm`, after the existing `useState` declarations (after `initialCash`), add:

```typescript
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState<DryrunResult | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  async function onPreview() {
    setPreviewing(true);
    setPreview(null);
    setPreviewError(null);
    try {
      const res = await fetch("/api/strategy/dryrun", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ entry_formula: entryFormula, universe }),
      });
      const data = (await res.json()) as DryrunResult;
      if (!res.ok && !("ok" in data)) {
        setPreviewError(`Preview failed (${res.status})`);
      } else {
        setPreview(data);
      }
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : "Network error");
    } finally {
      setPreviewing(false);
    }
  }
```

- [ ] **Step 2: Add the button + result card under the formula field**

Replace the entry-formula `<label>` block (the `Entry formula (DSL)` label, currently `strategy-form.tsx:119-124`) with:

```tsx
      <label className="block">
        <span className="text-sm font-medium">Entry formula (DSL)</span>
        <textarea className={field} rows={2} value={entryFormula}
          onChange={(e) => setEntryFormula(e.target.value)}
          placeholder="rsi_14 > 70 AND close > sma_200" required />
        <div className="mt-1.5 flex items-center gap-2">
          <button type="button" onClick={onPreview} disabled={previewing || !entryFormula.trim()}
            className="rounded-md border px-3 py-1 text-xs font-medium hover:bg-accent disabled:opacity-50">
            {previewing ? "Previewing…" : "Preview signals"}
          </button>
          <span className="text-xs text-muted-foreground">Validate the formula without running a full backtest</span>
        </div>
        {previewError && <p className="mt-1.5 text-sm text-red-500">{previewError}</p>}
        {preview && !preview.ok && (
          <p className="mt-1.5 text-sm text-red-500">
            {preview.unknown_features?.length
              ? `Unknown feature(s): ${preview.unknown_features.join(", ")}`
              : preview.error}
          </p>
        )}
        {preview && preview.ok && preview.today.count === 0 && preview.history.signal_rows === 0 && (
          <p className="mt-1.5 text-sm text-amber-600">Formula valid but never fires — check thresholds</p>
        )}
        {preview && preview.ok && (preview.today.count > 0 || preview.history.signal_rows > 0) && (
          <div className="mt-1.5 rounded-md border p-2 text-sm">
            <p className="font-medium text-green-600">
              ✓ {preview.today.count} ticker{preview.today.count === 1 ? "" : "s"} match today ({preview.today.date})
            </p>
            {preview.today.tickers.length > 0 && (
              <p className="text-xs text-muted-foreground">
                {preview.today.tickers.join(", ")}
                {preview.today.count > preview.today.tickers.length ? ` +${preview.today.count - preview.today.tickers.length} more` : ""}
              </p>
            )}
            <p className="mt-1 text-xs text-muted-foreground">
              {preview.history.signal_rows} signals over last {preview.history.trading_days} trading days · {preview.history.distinct_tickers} distinct tickers
            </p>
          </div>
        )}
      </label>
```

- [ ] **Step 3: Type-check**

Run (in `web/`): `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Manual verification (dev server)**

In the running app, open the Create-strategy form. With Nifty 50 selected:
- Type `rsi_14 > 70 AND close > sma_200` → click Preview → green card with a today count + names + 90-day line appears within a few seconds.
- Type `rsi_14 > 200` → Preview → amber "Formula valid but never fires".
- Type `rsi_14 > 70 AND xyz_bad > 1` → Preview → red "Unknown feature(s): xyz_bad".
- Empty formula → Preview button is disabled.
- Confirm Create/Save still works and Preview never blocks it.

- [ ] **Step 5: Commit**

```bash
git add web/components/strategy-form.tsx
git commit -m "feat(s4): Preview signals button + result card on strategy form"
```

---

## Task 8: Full regression + finish

- [ ] **Step 1: Run the full test suites**

Run (repo root): `python -m pytest tests/test_dryrun.py -q`
Expected: PASS (11 passed).

Run (in `web/`): `npx vitest run`
Expected: all green (153 prior + new spawn-collect + dryrun-validate tests).

- [ ] **Step 2: Type-check the web app**

Run (in `web/`): `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Update memory**

Append the dry-run slice to the S4 line in `MEMORY.md` / `s4_nextjs_frontend.md` (mark "DSL dry-run" done; remaining: cloud).

- [ ] **Step 4: Finish the branch**

Use the `superpowers:finishing-a-development-branch` skill to merge/PR.

---

## Self-Review

**Spec coverage:**
- dryrun.py CLI + reuse of generic_backtest helpers → Tasks 1-3. ✓
- Unknown-feature check (regex, drop AND/OR/NOT + numbers, subtract known cols) → Task 1. ✓
- Eval + today/last-90d windows, ticker cap → Task 2. ✓
- JSON output contract (ok / today / history / error / unknown_features) → Tasks 2-3. ✓
- Route: no lock, spawn, timeout 120s, JSON scan, 200/400/200-ok:false/500 mapping → Tasks 4-6. ✓
- spawn-collect (not bending runRecompute) → Task 4. ✓
- Frontend Preview button, create+edit, error/success/dead-formula cards, spinner, non-blocking → Task 7. ✓
- Tests: python (unknown/dead/firehose/valid) + vitest (validator + collect/parse) → Tasks 1-5. ✓
- Out-of-scope items (caching, per-keystroke, full-period, autocomplete) not implemented. ✓

**Placeholder scan:** none — every code step has full content.

**Type consistency:** `DryrunResult` (frontend) mirrors the python contract and the route passthrough; `CollectOutcome` discriminated on `status === 200`; `validateDryrunBody` returns `{ok,formula,universe}` consumed by the route. Names consistent across tasks.
