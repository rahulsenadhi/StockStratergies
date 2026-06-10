"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const ARM_RESET_MS = 5000;

export function DeleteStrategyButton({ id }: { id: string }) {
  const router = useRouter();
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onClick() {
    if (!armed) {
      setArmed(true);
      setTimeout(() => setArmed(false), ARM_RESET_MS);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/strategy/${id}`, { method: "DELETE" });
      const data = (await res.json().catch(() => ({}))) as { ok?: boolean; error?: string };
      if (res.ok && data.ok) {
        router.push("/leaderboard");
      } else {
        setError(data.error ?? `Delete failed (${res.status})`);
        setArmed(false);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Network error");
      setArmed(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex items-center gap-2">
      <button
        onClick={onClick}
        disabled={busy}
        className="rounded-md border px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
      >
        {busy ? "Deleting…" : armed ? "Confirm delete?" : "Delete"}
      </button>
      {error && <span className="text-sm text-red-500">{error}</span>}
    </span>
  );
}
