"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { runJobStream } from "@/lib/use-job-stream";
import { JobProgress } from "@/components/job-progress";

export function RebuildAllButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);
  const [lines, setLines] = useState<string[]>([]);
  const [phase, setPhase] = useState<string | null>(null);

  async function onClick() {
    setLoading(true);
    setSummary(null);
    setIsError(false);
    setLines([]);
    setPhase(null);
    try {
      const res = await runJobStream("/api/rebuild-all", undefined, {
        onLine: (l) => setLines((prev) => [...prev.slice(-199), l]),
        onPhase: (p) => setPhase(p),
      });
      const data = res.data as {
        ok?: boolean;
        ran?: string[];
        failed?: { id: string }[];
        error?: string;
      };
      if (res.status === 409) {
        setIsError(true);
        setSummary(data.error ?? "A job is already running");
        return;
      }
      router.refresh();
      const ran = data.ran?.length ?? 0;
      const failed = data.failed ?? [];
      if (failed.length > 0) {
        setIsError(true);
        setSummary(`Rebuilt ${ran} · failed: ${failed.map((f) => f.id).join(", ")}`);
      } else if (data.ok === false) {
        setIsError(true);
        setSummary(`Rebuilt ${ran} · recompute failed`);
      } else {
        setSummary(`Rebuilt ${ran}`);
      }
    } catch (e) {
      setIsError(true);
      setSummary(e instanceof Error ? e.message : "Network error");
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
        {loading ? "Rebuilding all…" : "⟳ Rebuild All"}
      </button>
      {loading && <JobProgress phase={phase} lines={lines} />}
      {summary && (
        <span className={`text-sm ${isError ? "text-red-500" : "text-muted-foreground"}`}>
          {summary}
        </span>
      )}
    </div>
  );
}
