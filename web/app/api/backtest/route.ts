import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import path from "node:path";
import { runRecompute, resolveBacktest, resolveRecompute, type SpawnedChild } from "@/lib/recompute";
import { getStrategy } from "@/lib/data/strategies";
import { tryAcquire, release } from "@/lib/job-lock";

export const dynamic = "force-dynamic";

// momentum_edge runs ~563s standalone and exceeds 600s under Rebuild All contention; 20min gives margin
const BACKTEST_TIMEOUT_MS = 1_200_000;
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
    return NextResponse.json(
      { ok: false, error: "A job is already running" },
      { status: 409 },
    );
  }
  try {
    const repoRoot = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..");
    let bt: { bin: string; args: string[]; cwd: string };
    try {
      bt = resolveBacktest(strategy.backtest, repoRoot, {
        PYTHON_BIN: process.env.PYTHON_BIN,
      });
    } catch (e) {
      return NextResponse.json(
        { ok: false, error: e instanceof Error ? e.message : String(e) },
        { status: 500 },
      );
    }

    // Step 1: run the backtest (regenerates the strategy's CSVs).
    const backtestRun = await runRecompute(spawnChild, {
      ...bt,
      timeoutMs: BACKTEST_TIMEOUT_MS,
      label: "Backtest",
    });
    if (backtestRun.status !== 200) {
      return NextResponse.json(backtestRun.body, { status: backtestRun.status });
    }

    // Step 2: chain a recompute to refresh KPIs + rank in the index.
    const rc = resolveRecompute(process.env, process.cwd());
    const recomputeRun = await runRecompute(spawnChild, {
      ...rc,
      timeoutMs: RECOMPUTE_TIMEOUT_MS,
      label: "Recompute",
    });
    return NextResponse.json(recomputeRun.body, { status: recomputeRun.status });
  } finally {
    release();
  }
}
