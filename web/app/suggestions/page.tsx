import { getSuggestions } from "@/lib/data/strategies";
import { SuggestionsFeedView } from "@/components/suggestions-feed";

export const dynamic = "force-dynamic"; // read suggestions.json at request time

export default async function SuggestionsPage() {
  const feed = await getSuggestions();

  return (
    <main className="mx-auto max-w-5xl px-6 py-4">
      <h1 className="mb-1 text-2xl font-bold">Buy These Now — Risk-Filtered Picks</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Live signals re-ranked by historical edge. Only setups that historically won are
        surfaced; the regime gate, position sizing, and stop-losses are applied automatically.
      </p>

      {feed === null ? (
        <div className="rounded-md border border-border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
          No suggestions feed yet. Run{" "}
          <code className="font-mono text-foreground">python precompute_suggestions.py</code>{" "}
          to generate <code className="font-mono text-foreground">suggestions.json</code>.
        </div>
      ) : (
        <SuggestionsFeedView feed={feed} />
      )}
    </main>
  );
}
