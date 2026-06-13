import { CircleCheck, CircleX, MinusCircle } from "lucide-react";
import { computeConfidence, type ConfidenceLevel } from "@/lib/confidence";
import { cn } from "@/lib/utils";
import type { Kpis } from "@/lib/data/strategies";

function levelClass(level: ConfidenceLevel): string {
  switch (level) {
    case "HIGH":
      return "text-green-500";
    case "MODERATE":
      return "text-amber-500";
    case "CAUTION":
      return "text-orange-500";
    case "LOW":
      return "text-red-500";
    default:
      return "text-muted-foreground";
  }
}

const VERDICT: Record<ConfidenceLevel, string> = {
  HIGH: "Strong, well-rounded track record — the strategy passes nearly every health check.",
  MODERATE: "Solid but with caveats — most checks pass; mind the ones that don't.",
  CAUTION: "Mixed evidence — roughly half the checks fail. Size positions conservatively.",
  LOW: "Weak track record — most health checks fail. Treat with skepticism.",
  "NO DATA": "Not enough backtest data to score confidence yet.",
};

function PassIcon({ pass }: { pass: boolean | null }) {
  if (pass === true) return <CircleCheck size={15} className="text-green-500" strokeWidth={2} />;
  if (pass === false) return <CircleX size={15} className="text-red-500" strokeWidth={2} />;
  return <MinusCircle size={15} className="text-muted-foreground" strokeWidth={2} />;
}

export function ConfidenceVerdict({
  kpis,
  annualReturns = [],
}: {
  kpis: Kpis;
  annualReturns?: (number | null)[];
}) {
  const c = computeConfidence(kpis, annualReturns);

  return (
    <section className="space-y-2">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">Confidence Verdict</h3>
        <div className="flex items-baseline gap-2">
          <span className={cn("text-2xl font-bold font-mono tabular-nums", levelClass(c.level))}>
            {c.score}
          </span>
          <span className="text-xs text-muted-foreground">/ 100</span>
          <span className={cn("text-sm font-semibold", levelClass(c.level))}>{c.level}</span>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">{VERDICT[c.level]}</p>

      {c.criteria.length > 0 && (
        <ul className="divide-y divide-border rounded-md border border-border">
          {c.criteria.map((cr) => (
            <li key={cr.label} className="flex items-center gap-3 px-3 py-1.5 text-sm">
              <PassIcon pass={cr.pass} />
              <span className="font-medium">{cr.label}</span>
              <span className="ml-auto font-mono tabular-nums text-muted-foreground">
                {cr.value}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
