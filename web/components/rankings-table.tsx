import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { upDown } from "@/lib/dir";
import type { RankingRow } from "@/lib/data/strategies";

const fmtPrice = (v: number | null): string =>
  v == null ? "—" : `₹${v.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
const fmtPctNum = (v: number | null): string =>
  v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

export function RankingsTable({ rows }: { rows: RankingRow[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">No rankings available.</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow className="sticky top-0 z-10 bg-background">
          <TableHead className="w-10 px-3 py-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            #
          </TableHead>
          <TableHead className="px-3 py-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Ticker
          </TableHead>
          <TableHead className="px-3 py-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Company
          </TableHead>
          <TableHead className="px-3 py-1.5 text-right text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Price
          </TableHead>
          <TableHead className="px-3 py-1.5 text-right text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Return
          </TableHead>
          <TableHead className="px-3 py-1.5 text-right text-xs font-medium uppercase tracking-wide text-muted-foreground">
            RS Score
          </TableHead>
          <TableHead className="px-3 py-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Signal
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r, i) => {
          const held = r.rank != null && r.rank <= 5;
          return (
            <TableRow
              key={i}
              className={cn(
                "border-b border-border hover:bg-muted/40 transition-colors",
                i % 2 !== 0 && "bg-muted/10",
                held && "border-l-2 border-l-accent-blue bg-accent-blue/5",
              )}
            >
              <TableCell className="px-3 py-1.5 font-mono tabular-nums font-medium text-accent-blue">
                {r.rank ?? "—"}
              </TableCell>
              <TableCell className="px-3 py-1.5 font-medium">{r.ticker}</TableCell>
              <TableCell className="px-3 py-1.5 text-xs text-muted-foreground">
                {r.company}
              </TableCell>
              <TableCell className="px-3 py-1.5 text-right font-mono tabular-nums">
                {fmtPrice(r.price)}
              </TableCell>
              <TableCell
                className={cn(
                  "px-3 py-1.5 text-right font-mono tabular-nums",
                  upDown(r.returnPct),
                )}
              >
                {fmtPctNum(r.returnPct)}
              </TableCell>
              <TableCell className="px-3 py-1.5 text-right font-mono tabular-nums">
                {fmtPctNum(r.rsScore)}
              </TableCell>
              <TableCell className="px-3 py-1.5 text-xs">{r.signal}</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
