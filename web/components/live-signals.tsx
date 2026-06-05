import type { LiveSignal } from "@/lib/data/strategies";

export type LivePanel = { name: string; picks: LiveSignal[] };

export function LiveSignals({ panels }: { panels: LivePanel[] }) {
  if (!panels.length) {
    return <p className="text-sm text-muted-foreground">No live signals available.</p>;
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {panels.map((p) => (
        <div key={p.name} className="rounded-lg border border-border p-3">
          <div className="mb-2 font-medium">{p.name}</div>
          <ul className="space-y-1 text-sm">
            {p.picks.map((s, i) => (
              <li key={i} className="flex items-center justify-between gap-2">
                <span>
                  <span className="font-mono">{s.ticker}</span>{" "}
                  <span className="text-muted-foreground">{s.company}</span>
                </span>
                <span className="text-muted-foreground">{s.signal}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
