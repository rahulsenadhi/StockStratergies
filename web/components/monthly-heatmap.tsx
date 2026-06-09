import type { ReactNode } from "react";
import type { MonthlyReturnsRow } from "@/lib/data/strategies";
import { pct } from "@/lib/format";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const FULL_SATURATION = 0.1; // ±10% monthly return = full color

/** Symmetric fixed scale: green positive, red negative, alpha = |r|/10% clamped to 1. null -> transparent. */
export function cellColor(r: number | null): string {
  if (r == null) return "transparent";
  const intensity = Math.min(Math.abs(r) / FULL_SATURATION, 1);
  const rgb = r >= 0 ? "34,197,94" : "239,68,68"; // green / red
  return `rgba(${rgb},${intensity})`;
}

interface MonthlyHeatmapProps {
  rows: MonthlyReturnsRow[];
}

export function MonthlyHeatmap({ rows }: MonthlyHeatmapProps): ReactNode {
  if (rows.length === 0) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-center text-xs">
        <thead>
          <tr className="text-muted-foreground">
            <th className="px-2 py-1 text-left font-medium">Year</th>
            {MONTHS.map((m) => (
              <th key={m} className="px-2 py-1 font-medium">{m}</th>
            ))}
            <th className="px-2 py-1 font-semibold">Annual</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.year}>
              <td className="px-2 py-1 text-left font-medium">{row.year}</td>
              {row.months.map((r, i) => (
                <td
                  key={`${row.year}-${i}`}
                  className="px-2 py-1 tabular-nums"
                  style={{ backgroundColor: cellColor(r) }}
                >
                  {r == null ? "—" : pct(r)}
                </td>
              ))}
              <td
                className="px-2 py-1 font-semibold tabular-nums"
                style={{ backgroundColor: cellColor(row.annual) }}
              >
                {row.annual == null ? "—" : pct(row.annual)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
