import { getDataFreshness, freshnessTier } from "@/lib/data/strategies";
import { cn } from "@/lib/utils";

const TONE: Record<string, string> = {
  fresh: "border-green-600/40 bg-green-600/10 text-green-500",
  stale: "border-amber-500/40 bg-amber-500/10 text-amber-500",
  old: "border-red-600/40 bg-red-600/10 text-red-500",
  none: "border-border bg-muted/30 text-muted-foreground",
};

export async function DataFreshness() {
  const f = await getDataFreshness();
  const tier = freshnessTier(f.ageHours);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium",
        TONE[tier.tone],
      )}
      title={
        f.sourceFile
          ? `Latest bar ${f.latestBar} · updated ${tier.label} · ${f.sourceFile}`
          : "No price data found"
      }
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {f.latestBar ? `Data: ${f.latestBar}` : "No data"}
      <span className="text-muted-foreground">· {tier.label}</span>
    </span>
  );
}
