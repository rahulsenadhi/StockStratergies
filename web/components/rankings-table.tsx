import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
        <TableRow>
          <TableHead className="w-10">#</TableHead>
          <TableHead>Ticker</TableHead>
          <TableHead>Company</TableHead>
          <TableHead className="text-right">Price</TableHead>
          <TableHead className="text-right">Return</TableHead>
          <TableHead className="text-right">RS Score</TableHead>
          <TableHead>Signal</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r, i) => {
          const held = r.rank != null && r.rank <= 5;
          return (
            <TableRow
              key={i}
              className={held ? "border-l-2 border-l-green-500 bg-green-500/5" : ""}
            >
              <TableCell className="font-bold text-green-500">{r.rank ?? "—"}</TableCell>
              <TableCell className="font-medium">{r.ticker}</TableCell>
              <TableCell className="text-xs text-muted-foreground">{r.company}</TableCell>
              <TableCell className="text-right">{fmtPrice(r.price)}</TableCell>
              <TableCell className="text-right">{fmtPctNum(r.returnPct)}</TableCell>
              <TableCell className="text-right">{fmtPctNum(r.rsScore)}</TableCell>
              <TableCell className="text-xs">{r.signal}</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
