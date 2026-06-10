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

// PYTHONUNBUFFERED forces the child to flush stdout per line instead of block-
// buffering it (the default when stdout is a pipe), so progress streams live.
const spawnChild = (b: string, a: string[], o: { cwd: string }) =>
  spawn(b, a, {
    cwd: o.cwd,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
  }) as unknown as SpawnedChild;

export async function POST() {
  if (!tryAcquire()) {
    return NextResponse.json(
      { ok: false, error: "A job is already running" },
      { status: 409 },
    );
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
