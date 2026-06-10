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
