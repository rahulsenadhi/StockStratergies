import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import type { TradesData } from "@/lib/data/strategies";

export function TradesTable({ columns, rows }: TradesData) {
  if (!columns.length || !rows.length) {
    return <p className="text-sm text-muted-foreground">No trades for this strategy.</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>{columns.map((c) => <TableHead key={c}>{c}</TableHead>)}</TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r, i) => (
          <TableRow key={i}>
            {columns.map((c) => <TableCell key={c}>{r[c]}</TableCell>)}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
