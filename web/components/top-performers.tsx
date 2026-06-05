import Link from "next/link";
import { pct, signed } from "@/lib/format";
import type { Strategy } from "@/lib/data/strategies";

export function TopPerformers({ items }: { items: Strategy[] }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">No strategies.</p>;
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {items.map((s) => (
        <Link key={s.id} href={`/strategy/${s.id}`} className="rounded-lg border border-border p-3 hover:bg-muted/30">
          <div className="font-medium">{s.name}</div>
          <div className="text-xs text-muted-foreground">{s.type} · {s.status}</div>
          <div className="mt-2 text-sm">Sharpe {signed(s.kpis.sharpe)} · CAGR {pct(s.kpis.cagr)}</div>
        </Link>
      ))}
    </div>
  );
}
