export type DryrunValidation =
  | { ok: true; formula: string; universe: string }
  | { ok: false; error: string };

interface DryrunBody {
  entry_formula?: unknown;
  universe?: unknown;
}

const DEFAULT_UNIVERSE = "Nifty 50";

export function validateDryrunBody(body: DryrunBody): DryrunValidation {
  const formula = typeof body.entry_formula === "string" ? body.entry_formula.trim() : "";
  if (!formula) return { ok: false, error: "entry_formula is required" };
  const universe =
    typeof body.universe === "string" && body.universe.trim() ? body.universe.trim() : DEFAULT_UNIVERSE;
  return { ok: true, formula, universe };
}
