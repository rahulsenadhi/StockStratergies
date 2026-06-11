"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { runJobStream } from "@/lib/use-job-stream";
import { JobProgress } from "@/components/job-progress";

type DryrunResult =
  | { ok: true; universe: string; today: { date: string; count: number; tickers: string[] }; history: { trading_days: number; signal_rows: number; distinct_tickers: number } }
  | { ok: false; error: string; unknown_features?: string[] };

export interface StrategyFormValues {
  name: string;
  type: string;
  description: string;
  universe: string;
  entryFormula: string;
  timeEnabled: boolean; timeDays: number;
  hardStopEnabled: boolean; hardStopPct: number;
  trailEnabled: boolean; trailPct: number;
  maxPositions: number; initialCash: number;
}

const DEFAULTS: StrategyFormValues = {
  name: "", type: "Momentum", description: "", universe: "Nifty 50", entryFormula: "",
  timeEnabled: true, timeDays: 30,
  hardStopEnabled: true, hardStopPct: 8,
  trailEnabled: false, trailPct: 12,
  maxPositions: 5, initialCash: 1000000,
};

export interface StrategyFormProps {
  mode?: "create" | "edit";
  initial?: Partial<StrategyFormValues>;
  strategyId?: string;
  lockName?: boolean;
}

export function StrategyForm({ mode = "create", initial, strategyId, lockName }: StrategyFormProps) {
  const router = useRouter();
  const init = { ...DEFAULTS, ...initial };
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [phase, setPhase] = useState<string | null>(null);

  const [name, setName] = useState(init.name);
  const [type, setType] = useState(init.type);
  const [description, setDescription] = useState(init.description);
  const [universe, setUniverse] = useState(init.universe);
  const [entryFormula, setEntryFormula] = useState(init.entryFormula);
  const [timeEnabled, setTimeEnabled] = useState(init.timeEnabled);
  const [timeDays, setTimeDays] = useState(init.timeDays);
  const [hardStopEnabled, setHardStopEnabled] = useState(init.hardStopEnabled);
  const [hardStopPct, setHardStopPct] = useState(init.hardStopPct);
  const [trailEnabled, setTrailEnabled] = useState(init.trailEnabled);
  const [trailPct, setTrailPct] = useState(init.trailPct);
  const [maxPositions, setMaxPositions] = useState(init.maxPositions);
  const [initialCash, setInitialCash] = useState(init.initialCash);

  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState<DryrunResult | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  async function onPreview() {
    setPreviewing(true);
    setPreview(null);
    setPreviewError(null);
    try {
      const res = await fetch("/api/strategy/dryrun", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ entry_formula: entryFormula, universe }),
      });
      const data = (await res.json()) as DryrunResult;
      if (!res.ok && !("ok" in data)) {
        setPreviewError(`Preview failed (${res.status})`);
      } else {
        setPreview(data);
      }
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : "Network error");
    } finally {
      setPreviewing(false);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setLines([]);
    setPhase(null);
    try {
      const url = mode === "edit" ? `/api/strategy/${strategyId}` : "/api/strategy";
      const httpMethod = mode === "edit" ? "PUT" : "POST";
      const res = await runJobStream(url, {
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
      }, httpMethod);
      const data = res.data as { ok?: boolean; sid?: string; error?: string };
      if (res.ok && data.ok) {
        router.push(`/strategy/${mode === "edit" ? strategyId : data.sid}`);
      } else {
        setError(data.error ?? `${mode === "edit" ? "Save" : "Create"} failed (${res.status})`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error");
    } finally {
      setLoading(false);
      setPhase(null);
    }
  }

  const field = "rounded-md border px-3 py-1.5 text-sm w-full";
  const submitLabel = mode === "edit"
    ? (loading ? "Saving & re-backtesting…" : "Save changes")
    : (loading ? "Creating & backtesting…" : "Create strategy");
  return (
    <form onSubmit={onSubmit} className="max-w-xl space-y-4">
      <label className="block">
        <span className="text-sm font-medium">Name</span>
        <input className={field} value={name} onChange={(e) => setName(e.target.value)}
          required readOnly={lockName} disabled={lockName} />
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
        <div className="mt-1.5 flex items-center gap-2">
          <button type="button" onClick={onPreview} disabled={previewing || !entryFormula.trim()}
            className="rounded-md border px-3 py-1 text-xs font-medium hover:bg-accent disabled:opacity-50">
            {previewing ? "Previewing…" : "Preview signals"}
          </button>
          <span className="text-xs text-muted-foreground">Validate the formula without running a full backtest</span>
        </div>
        {previewError && <p className="mt-1.5 text-sm text-red-500">{previewError}</p>}
        {preview && !preview.ok && (
          <p className="mt-1.5 text-sm text-red-500">
            {preview.unknown_features?.length
              ? `Unknown feature(s): ${preview.unknown_features.join(", ")}`
              : preview.error}
          </p>
        )}
        {preview && preview.ok && preview.today.count === 0 && preview.history.signal_rows === 0 && (
          <p className="mt-1.5 text-sm text-amber-600">Formula valid but never fires — check thresholds</p>
        )}
        {preview && preview.ok && (preview.today.count > 0 || preview.history.signal_rows > 0) && (
          <div className="mt-1.5 rounded-md border p-2 text-sm">
            <p className="font-medium text-green-600">
              ✓ {preview.today.count} ticker{preview.today.count === 1 ? "" : "s"} match today ({preview.today.date})
            </p>
            {preview.today.tickers.length > 0 && (
              <p className="text-xs text-muted-foreground">
                {preview.today.tickers.join(", ")}
                {preview.today.count > preview.today.tickers.length ? ` +${preview.today.count - preview.today.tickers.length} more` : ""}
              </p>
            )}
            <p className="mt-1 text-xs text-muted-foreground">
              {preview.history.signal_rows} signals over last {preview.history.trading_days} trading days · {preview.history.distinct_tickers} distinct tickers
            </p>
          </div>
        )}
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
        {submitLabel}
      </button>
      {loading && <JobProgress phase={phase} lines={lines} />}
      {error && <p className="text-sm text-red-500">{error}</p>}
    </form>
  );
}
