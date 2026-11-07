import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import path from "node:path";
import { type SpawnedChild } from "@/lib/recompute";
import { BUSY_MESSAGE, parseUpdateTarget, runUpdate } from "@/lib/desk/run-update";
import { release, tryAcquire } from "@/lib/job-lock";
import { streamJob } from "@/lib/job-stream";

export const dynamic = "force-dynamic";

// Downloads (e.g. the whole NSE/BSE list) can run for a long time; this only catches real hangs.
const STEP_TIMEOUT_MS = 1_800_000;

const spawnChild = (bin: string, args: string[], o: { cwd: string }) =>
  spawn(bin, args, {
    cwd: o.cwd,
    env: { ...process.env, PYTHONUNBUFFERED: "1", PYTHONIOENCODING: "utf-8" },
  }) as unknown as SpawnedChild;

/** POST { strategy: "all" | "Monthly" | "IPO" | "Momentum" | "PEAD" } → SSE progress, then results. */
export async function POST(request: Request) {
  const body = await request.json().catch(() => null);
  const strategies = parseUpdateTarget(body);
  if (!strategies) {
    return NextResponse.json({ ok: false, error: "unknown strategy" }, { status: 400 });
  }
  if (!tryAcquire()) {
    return NextResponse.json({ ok: false, error: BUSY_MESSAGE }, { status: 409 });
  }
  const repoRoot = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..");
  const pythonBin = process.env.PYTHON_BIN ? path.resolve(process.cwd(), process.env.PYTHON_BIN) : "python";
  return streamJob(async (onLine) => {
    try {
      return await runUpdate(spawnChild, { strategies, cwd: repoRoot, pythonBin, stepTimeoutMs: STEP_TIMEOUT_MS, onLine });
    } finally {
      release();
    }
  });
}
