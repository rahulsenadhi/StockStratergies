import { pct, signed } from "@/lib/format";

export function KpiCell({
  value, kind = "pct",
}: { value: number | null; kind?: "pct" | "num" }) {
  if (value == null) return <span className="text-muted-foreground">—</span>;
  const cls = value >= 0 ? "text-green-500" : "text-red-500";
  return <span className={cls}>{kind === "pct" ? pct(value) : signed(value)}</span>;
}
