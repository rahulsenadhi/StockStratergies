import { GLOSSARY } from "@/lib/glossary";
import { cn } from "@/lib/utils";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const TH =
  "px-3 py-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground";

export default function GlossaryPage() {
  const entries = Object.entries(GLOSSARY).sort(([a], [b]) => a.localeCompare(b));

  return (
    <main className="mx-auto max-w-7xl px-6 py-4">
      <h1 className="mb-1 text-2xl font-bold">Glossary</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        {entries.length} terms · hover a term anywhere in the app to see its definition
      </p>
      <Table>
        <TableHeader>
          <TableRow className="sticky top-0 z-10 bg-background">
            <TableHead className={cn("w-40", TH)}>Term</TableHead>
            <TableHead className={cn("w-64", TH)}>Name</TableHead>
            <TableHead className={TH}>What it means</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map(([key, { label, explain }], i) => (
            <TableRow
              key={key}
              className={cn(
                "border-b border-border transition-colors hover:bg-muted/40",
                i % 2 !== 0 && "bg-muted/10",
              )}
            >
              <TableCell className="px-3 py-1.5 font-mono text-xs text-accent-blue">
                {key}
              </TableCell>
              <TableCell className="px-3 py-1.5 font-medium">{label}</TableCell>
              <TableCell className="px-3 py-1.5 text-muted-foreground">
                {explain}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </main>
  );
}
