"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function RecomputeButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onClick() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/recompute", { method: "POST" });
      const data = (await res.json().catch(() => ({}))) as {
        ok?: boolean;
        error?: string;
      };
      if (res.ok && data.ok) {
        router.refresh(); // re-pull the force-dynamic leaderboard RSC
      } else {
        setError(data.error ?? `Recompute failed (${res.status})`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Network error");
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
        {loading ? "Recomputing…" : "↻ Recompute"}
      </button>
      {error && <span className="text-sm text-red-500">{error}</span>}
    </div>
  );
}
