"use client";

import { useCallback, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { runJobStream } from "@/lib/use-job-stream";
import type { UpdateStrategy } from "@/lib/desk/update-steps";
import type { UpdateResult } from "@/lib/desk/run-update";

export type UpdateTarget = "all" | UpdateStrategy;

export const MAX_LINES = 6;

export interface UpdateOutcome {
  results: UpdateResult[] | null;
  error: string | null;
}

/** POST /api/update and fold every response shape (409/400, results, malformed, thrown) into one outcome. */
export async function performUpdate(
  strategy: UpdateTarget,
  onLine: (line: string) => void,
): Promise<UpdateOutcome> {
  try {
    const r = await runJobStream("/api/update", { strategy }, { onLine });
    if (r.status === 409 || r.status === 400) {
      return { results: null, error: String(r.data.error ?? "Update could not start.") };
    }
    if (Array.isArray(r.data.results)) return { results: r.data.results as UpdateResult[], error: null };
    return { results: null, error: String(r.data.error ?? "Update finished without a result.") };
  } catch (e) {
    return { results: null, error: e instanceof Error ? e.message : "Update failed to start." };
  }
}

export interface JobState {
  running: UpdateTarget | null;
  lines: string[];
  results: UpdateResult[] | null;
  error: string | null;
}

// One job state shared by every button on the page and the sidebar, so a job started from any of
// them (and its result or failure) is seen by all, even after the starting component unmounts.
const IDLE: JobState = { running: null, lines: [], results: null, error: null };
let state: JobState = IDLE;
const listeners = new Set<() => void>();

function setState(next: JobState): void {
  state = next;
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

/** Start a job unless one is running; resolves when it finishes. Exported for tests. */
export async function startJob(strategy: UpdateTarget): Promise<boolean> {
  if (state.running !== null) return false;
  setState({ running: strategy, lines: [], results: null, error: null });
  const outcome = await performUpdate(strategy, (l) =>
    setState({ ...state, lines: [...state.lines, l].slice(-MAX_LINES) }));
  setState({ running: null, lines: state.lines, results: outcome.results, error: outcome.error });
  return true;
}

export function dismissJob(): void {
  setState({ ...state, results: null, lines: [] });
}

/** Test helper: back to idle. */
export function resetJobState(): void {
  setState(IDLE);
}

export function useStrategyUpdate() {
  const router = useRouter();
  const job = useSyncExternalStore(subscribe, () => state, () => state);

  const start = useCallback(async (strategy: UpdateTarget) => {
    if (await startJob(strategy)) router.refresh();
  }, [router]);

  return { ...job, start, dismiss: dismissJob };
}
