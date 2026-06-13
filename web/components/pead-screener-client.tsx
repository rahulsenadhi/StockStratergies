"use client";

import { useMemo, useState } from "react";
import { Download } from "lucide-react";
import { filterScreener, toCsv } from "@/lib/pead-screener";
import { cn } from "@/lib/utils";
import type { PeadScreenerRow } from "@/lib/data/strategies";

const num = (v: number | null, d = 2): string => (v == null ? "—" : v.toFixed(d));
const field = "rounded-md border px-3 py-1.5 text-sm w-full font-mono tabular-nums";
const TH = "px-3 py-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground";
const THR = `${TH} text-right`;

export function PeadScreenerClient({
  rows,
  sectors,
}: {
  rows: PeadScreenerRow[];
  sectors: string[];
}) {
  const [sueMin, setSueMin] = useState(-3);
  const [pioMin, setPioMin] = useState(5);
  const [pbMax, setPbMax] = useState(10);
  const [selected, setSelected] = useState<string[]>([]);

  const filtered = useMemo(
    () => filterScreener(rows, { sueMin, pioMin, pbMax, sectors: selected }),
    [rows, sueMin, pioMin, pbMax, selected],
  );

  const toggleSector = (s: string): void =>
    setSelected((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]));

  const download = (): void => {
    const blob = new Blob([toCsv(filtered)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "pead_screener.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <label className="block">
          <span className="text-xs font-medium text-muted-foreground">SUE min</span>
          <input
            type="number"
            step={0.1}
            className={field}
            value={Number.isFinite(sueMin) ? sueMin : ""}
            onChange={(e) => setSueMin(parseFloat(e.target.value))}
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-muted-foreground">Piotroski min (0–9)</span>
          <input
            type="number"
            step={1}
            min={0}
            max={9}
            className={field}
            value={Number.isFinite(pioMin) ? pioMin : ""}
            onChange={(e) => setPioMin(parseFloat(e.target.value))}
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-muted-foreground">P/B max</span>
          <input
            type="number"
            step={0.5}
            className={field}
            value={Number.isFinite(pbMax) ? pbMax : ""}
            onChange={(e) => setPbMax(parseFloat(e.target.value))}
          />
        </label>
      </div>

      {sectors.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {sectors.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => toggleSector(s)}
              className={cn(
                "rounded border px-2 py-0.5 text-xs transition-colors",
                selected.includes(s)
                  ? "border-accent-blue/40 bg-accent-blue/15 text-accent-blue"
                  : "border-border text-muted-foreground hover:bg-muted/50",
              )}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{filtered.length}</span> of {rows.length}{" "}
          events match
        </p>
        <button
          type="button"
          onClick={download}
          disabled={filtered.length === 0}
          className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-50"
        >
          <Download size={14} strokeWidth={1.75} /> Download CSV
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="sticky top-0 z-10 border-b border-border bg-background">
              <th className={`${TH} text-left`}>Ticker</th>
              <th className={`${TH} text-left`}>Sector</th>
              <th className={`${TH} text-left`}>Result</th>
              <th className={THR}>SUE</th>
              <th className={THR}>Decile</th>
              <th className={THR}>Piotroski</th>
              <th className={THR}>P/B</th>
              <th className={THR}>Sector P/B</th>
              <th className={`${TH} text-right`}>Long?</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r, i) => (
              <tr
                key={`${r.ticker}-${r.resultDate}-${i}`}
                className={cn(
                  "border-b border-border transition-colors hover:bg-muted/40",
                  i % 2 !== 0 && "bg-muted/10",
                )}
              >
                <td className="px-3 py-1.5 font-medium">{r.ticker.replace(".NS", "")}</td>
                <td className="px-3 py-1.5 text-muted-foreground">{r.sector ?? "—"}</td>
                <td className="px-3 py-1.5 font-mono tabular-nums text-muted-foreground">
                  {r.resultDate ?? "—"}
                </td>
                <td className="px-3 py-1.5 text-right font-mono tabular-nums">{num(r.sue)}</td>
                <td className="px-3 py-1.5 text-right font-mono tabular-nums">
                  {r.sueDecile == null ? "—" : r.sueDecile.toFixed(0)}
                </td>
                <td className="px-3 py-1.5 text-right font-mono tabular-nums">
                  {r.piotroski == null ? "—" : r.piotroski.toFixed(0)}
                </td>
                <td className="px-3 py-1.5 text-right font-mono tabular-nums">{num(r.pb)}</td>
                <td className="px-3 py-1.5 text-right font-mono tabular-nums text-muted-foreground">
                  {num(r.pbSectorMedian)}
                </td>
                <td className="px-3 py-1.5 text-right">
                  {r.qualifiesLong ? (
                    <span className="text-xs font-medium text-green-500">Yes</span>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
