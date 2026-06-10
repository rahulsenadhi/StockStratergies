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
