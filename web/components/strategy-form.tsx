"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { runJobStream } from "@/lib/use-job-stream";
import { JobProgress } from "@/components/job-progress";

export function StrategyForm() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [phase, setPhase] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [type, setType] = useState("Momentum");
  const [description, setDescription] = useState("");
  const [universe, setUniverse] = useState("Nifty 50");
  const [entryFormula, setEntryFormula] = useState("");
  const [timeEnabled, setTimeEnabled] = useState(true);
  const [timeDays, setTimeDays] = useState(30);
  const [hardStopEnabled, setHardStopEnabled] = useState(true);
  const [hardStopPct, setHardStopPct] = useState(8);
  const [trailEnabled, setTrailEnabled] = useState(false);
  const [trailPct, setTrailPct] = useState(12);
  const [maxPositions, setMaxPositions] = useState(5);
  const [initialCash, setInitialCash] = useState(1000000);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setLines([]);
    setPhase(null);
    try {
      const res = await runJobStream("/api/strategy", {
        name, type, description, universe,
        entry_formula: entryFormula,
        exits: {
          time_enabled: timeEnabled, time_days: timeDays,
          hard_stop_enabled: hardStopEnabled, hard_stop_pct: hardStopPct,
          trail_enabled: trailEnabled, trail_pct: trailPct,
        },
        sizing: {
          method: "Equal weight (capped)",
          max_positions: maxPositions, initial_cash: initialCash,
        },
      }, {
        onLine: (l) => setLines((prev) => [...prev.slice(-199), l]),
        onPhase: (p) => setPhase(p),
      });
      const data = res.data as { ok?: boolean; sid?: string; error?: string };
      if (res.ok && data.ok && data.sid) {
        router.push(`/strategy/${data.sid}`);
      } else {
        setError(data.error ?? `Create failed (${res.status})`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error");
    } finally {
      setLoading(false);
      setPhase(null);
    }
  }

  const field = "rounded-md border px-3 py-1.5 text-sm w-full";
  return (
    <form onSubmit={onSubmit} className="max-w-xl space-y-4">
      <label className="block">
        <span className="text-sm font-medium">Name</span>
        <input className={field} value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Type</span>
        <input className={field} value={type} onChange={(e) => setType(e.target.value)} />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Description</span>
        <input className={field} value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Universe</span>
        <input className={field} value={universe} onChange={(e) => setUniverse(e.target.value)} />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Entry formula (DSL)</span>
        <textarea className={field} rows={2} value={entryFormula}
          onChange={(e) => setEntryFormula(e.target.value)}
          placeholder="rsi_14 > 70 AND close > sma_200" required />
      </label>

      <fieldset className="space-y-2 rounded-md border p-3">
        <legend className="px-1 text-sm font-medium">Exits (enable at least one)</legend>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={timeEnabled} onChange={(e) => setTimeEnabled(e.target.checked)} />
          Time exit after
          <input type="number" className="w-20 rounded border px-2 py-1" value={timeDays}
            onChange={(e) => setTimeDays(Number(e.target.value))} /> days
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={hardStopEnabled} onChange={(e) => setHardStopEnabled(e.target.checked)} />
          Hard stop at
          <input type="number" className="w-20 rounded border px-2 py-1" value={hardStopPct}
            onChange={(e) => setHardStopPct(Number(e.target.value))} /> %
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={trailEnabled} onChange={(e) => setTrailEnabled(e.target.checked)} />
          Trailing stop at
          <input type="number" className="w-20 rounded border px-2 py-1" value={trailPct}
            onChange={(e) => setTrailPct(Number(e.target.value))} /> %
        </label>
      </fieldset>

      <fieldset className="space-y-2 rounded-md border p-3">
        <legend className="px-1 text-sm font-medium">Sizing</legend>
        <label className="flex items-center gap-2 text-sm">
          Max positions
          <input type="number" className="w-24 rounded border px-2 py-1" value={maxPositions}
            onChange={(e) => setMaxPositions(Number(e.target.value))} />
        </label>
        <label className="flex items-center gap-2 text-sm">
          Initial cash
          <input type="number" className="w-32 rounded border px-2 py-1" value={initialCash}
            onChange={(e) => setInitialCash(Number(e.target.value))} />
        </label>
      </fieldset>

      <button type="submit" disabled={loading}
        className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-accent disabled:opacity-50">
        {loading ? "Creating & backtesting…" : "Create strategy"}
      </button>
      {loading && <JobProgress phase={phase} lines={lines} />}
      {error && <p className="text-sm text-red-500">{error}</p>}
    </form>
  );
}
