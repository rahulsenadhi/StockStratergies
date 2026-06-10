import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import path from "node:path";
import { runRecompute, resolveBacktest, resolveRecompute, type SpawnedChild } from "@/lib/recompute";
import { getStrategy } from "@/lib/data/strategies";
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
  return streamJob(async (onLine) => {
    try {
      const repoRoot = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..");
      let bt: { bin: string; args: string[]; cwd: string };
      try {
        bt = resolveBacktest(strategy.backtest, repoRoot, {
          PYTHON_BIN: process.env.PYTHON_BIN,
        });
      } catch (e) {
        return {
          status: 500,
          body: { ok: false, error: e instanceof Error ? e.message : String(e) },
        };
      }

      // Step 1: run the backtest (regenerates the strategy's CSVs).
      const backtestRun = await runRecompute(spawnChild, {
        ...bt,
        timeoutMs: BACKTEST_TIMEOUT_MS,
        label: "Backtest",
        onLine,
      });
      if (backtestRun.status !== 200) {
        return { status: backtestRun.status, body: backtestRun.body };
      }

      // Step 2: chain a recompute to refresh KPIs + rank in the index.
      const rc = resolveRecompute(process.env, process.cwd());
      const recomputeRun = await runRecompute(spawnChild, {
        ...rc,
        timeoutMs: RECOMPUTE_TIMEOUT_MS,
        label: "Recompute",
        onLine,
      });
      return { status: recomputeRun.status, body: recomputeRun.body };
    } finally {
      release();
    }
  });
}
