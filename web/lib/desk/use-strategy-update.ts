"use client";

import { useCallback, useState, useSyncExternalStore } from "react";
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

// One running flag shared by every button on the page, so they disable each other.
let runningTarget: UpdateTarget | null = null;
const listeners = new Set<() => void>();

function setRunningTarget(next: UpdateTarget | null): void {
  runningTarget = next;
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

export function useStrategyUpdate() {
  const router = useRouter();
  const running = useSyncExternalStore(subscribe, () => runningTarget, () => null);
  const [lines, setLines] = useState<string[]>([]);
  const [results, setResults] = useState<UpdateResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(async (strategy: UpdateTarget) => {
    if (runningTarget !== null) return;
    setRunningTarget(strategy);
    setLines([]);
    setResults(null);
    setError(null);
    const outcome = await performUpdate(strategy, (l) => setLines((prev) => [...prev, l].slice(-MAX_LINES)));
    setResults(outcome.results);
    setError(outcome.error);
    setRunningTarget(null);
    router.refresh();
  }, [router]);

  const dismiss = useCallback(() => { setResults(null); setLines([]); }, []);

  return { running, lines, results, error, start, dismiss };
}
