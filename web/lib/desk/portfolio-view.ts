import fs from "node:fs/promises";
import { createReadStream } from "node:fs";
import { createInterface } from "node:readline";
import path from "node:path";
import { loadPortfolio, portfolioPaths, readLedger, type PortfolioPaths } from "@/lib/desk/portfolio";
import { list, mapAlert, mapEvaluation, mapPosition, mapTransaction, record, str, type Evaluation, type PortfolioView } from "@/lib/desk/portfolio-text";

/** Read-only history, bounded to the most recent 20 evaluations per holding in memory. */
export async function readEvaluations(file: string): Promise<{ evaluations: Record<string, Evaluation[]>; error?: string }> {
  const evaluations: Record<string, Evaluation[]> = {};
  let malformed = false;
  try {
    const lines = createInterface({ input: createReadStream(file, { encoding: "utf8" }), crlfDelay: Infinity });
    for await (const line of lines) {
      if (!line.trim()) continue;
      try {
        const ev = mapEvaluation(JSON.parse(line));
        if (!ev.symbol) { malformed = true; continue; }
        const rows = evaluations[ev.symbol] ?? [];
        rows.push(ev);
        evaluations[ev.symbol] = rows.slice(-20);
      } catch { malformed = true; }
    }
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code !== "ENOENT") return { evaluations, error: "Evaluation history could not be read." };
  }
  return { evaluations, ...(malformed ? { error: "Some evaluation history entries could not be read; valid entries are shown." } : {}) };
}

export async function loadPortfolioView(p: PortfolioPaths = portfolioPaths()): Promise<PortfolioView> {
  const [snapshot, ledger, history, alertRead] = await Promise.all([
    loadPortfolio(p), readLedger(p), readEvaluations(path.join(p.dir, "evaluations.jsonl")),
    fs.readFile(p.alerts, "utf8").then((text) => ({ text, error: "" })).catch((e: NodeJS.ErrnoException) => ({ text: "", error: e.code === "ENOENT" ? "" : "Alerts could not be read." })),
  ]);
  const value = snapshot.ok ? snapshot.value : {}, monitor = record(value.monitor);
  const errors: string[] = [];
  if (!snapshot.ok) errors.push(snapshot.reason === "missing" ? "No saved holding check yet. Check holdings now to build it." : "Saved portfolio results could not be read. Check holdings now to rebuild them.");
  if (!ledger.ok) errors.push(ledger.error);
  if (history.error) errors.push(history.error);
  if (alertRead.error) errors.push(alertRead.error);
  let alerts = list(value.alerts).map(mapAlert);
  // The ack endpoint deliberately does not rewrite the snapshot. Use authoritative saved acknowledgements.
  if (alertRead.text) {
    try {
      const doc = record(JSON.parse(alertRead.text));
      if (doc.version !== 1 || !Array.isArray(doc.alerts)) throw new Error("invalid alerts");
      const ack = new Map(list(doc.acknowledgements).map((a) => { const v = record(a); return [str(v.alert_id), str(v.acknowledged_at)]; }));
      alerts = doc.alerts.map(mapAlert).map((a) => ({ ...a, acknowledged_at: ack.get(a.id) || null }));
    } catch { errors.push("Alerts file could not be read; showing the last saved alerts."); }
  }
  return { positions: list(value.positions).map(mapPosition).filter((p) => p.symbol), closed: list(value.closed).map(mapPosition).filter((p) => p.symbol),
    alerts, monitor: { last_run: str(monitor.last_run) || null,
      last_good_check: str(monitor.last_good_check) || (monitor.ok === true ? str(monitor.last_run) : "") || null,
      ok: monitor.ok === true, errors: list(monitor.errors).map(str).filter(Boolean) },
    transactions: ledger.ok ? ledger.transactions.map(mapTransaction).filter((t) => t.id) : [], evaluations: history.evaluations,
    errors, ledgerReadable: ledger.ok, snapshotReady: snapshot.ok };
}
