import { GLOSSARY } from "@/lib/glossary";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function GlossaryPage() {
  const entries = Object.entries(GLOSSARY).sort(([a], [b]) => a.localeCompare(b));

  return (
    <main className="mx-auto max-w-5xl p-8">
      <h1 className="mb-1 text-2xl font-bold">Glossary</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        {entries.length} terms · hover a term anywhere in the app to see its definition
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-40">Term</TableHead>
            <TableHead className="w-64">Name</TableHead>
            <TableHead>What it means</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map(([key, { label, explain }]) => (
            <TableRow key={key}>
              <TableCell className="font-mono text-xs">{key}</TableCell>
              <TableCell className="font-medium">{label}</TableCell>
              <TableCell className="text-muted-foreground">{explain}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </main>
  );
}
