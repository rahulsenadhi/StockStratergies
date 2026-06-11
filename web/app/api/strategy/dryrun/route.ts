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
  const v = validateDryrunBody(body as { entry_formula?: unknown; universe?: unknown });
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
