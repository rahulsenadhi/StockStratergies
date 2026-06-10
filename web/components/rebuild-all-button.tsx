"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface RebuildAllResponse {
  ok?: boolean;
  ran?: string[];
  failed?: { id: string; error: string }[];
  recompute?: { status: number; error?: string };
  error?: string;
}

export function RebuildAllButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);

  async function onClick() {
    setLoading(true);
    setSummary(null);
    setIsError(false);
    try {
      const res = await fetch("/api/rebuild-all", { method: "POST" });
      const data = (await res.json().catch(() => ({}))) as RebuildAllResponse;
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
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        onClick={onClick}
        disabled={loading}
        className="rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-50"
      >
        {loading ? "Rebuilding all… (several min)" : "⟳ Rebuild All"}
      </button>
      {summary && (
        <span className={`text-sm ${isError ? "text-red-500" : "text-muted-foreground"}`}>
          {summary}
        </span>
      )}
    </div>
  );
}
