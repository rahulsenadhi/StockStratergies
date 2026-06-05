import Link from "next/link";
import { pct } from "@/lib/format";
import type { Strategy } from "@/lib/data/strategies";

export function RecentBacktests({ items }: { items: Strategy[] }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">No strategies.</p>;
  return (
    <ul className="divide-y divide-border rounded-lg border border-border">
      {items.map((s) => (
        <li key={s.id}>
          <Link href={`/strategy/${s.id}`} className="flex items-center justify-between p-3 hover:bg-muted/30">
            <span>{s.name}</span>
            <span className="text-sm text-muted-foreground">
              {s.lastRun ? s.lastRun.slice(0, 10) : "—"} · CAGR {pct(s.kpis.cagr)}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
