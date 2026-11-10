"use client";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { EmptyState, SectionHead } from "@/components/desk/primitives";
import { AlertsList } from "@/components/desk/portfolio/alerts-list";
import { HoldingRail } from "@/components/desk/portfolio/holding-rail";
import { ClosedPositions, HoldingsTable } from "@/components/desk/portfolio/holdings-table";
import { MonitorStatus } from "@/components/desk/portfolio/monitor-status";
import { TransactionForm, type SaveTransaction } from "@/components/desk/portfolio/transaction-form";
import { TransactionHistory } from "@/components/desk/portfolio/transaction-history";
import { list, PENDING_HOLDINGS, purchaseHref, record, str, type PortfolioView } from "@/lib/desk/portfolio-text";

export function PortfolioDesk({ data, add = "", signal = "" }: { data: PortfolioView; add?: string; signal?: string }) {
  const router = useRouter();
  const [selected, setSelected] = useState<string | null>(data.positions[0]?.symbol ?? null);
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [acked, setAcked] = useState<string[]>([]);
  const current = [...data.positions, ...data.closed].find((p) => p.symbol === selected) ?? data.positions[0];

  async function post(url: string, body: Record<string, unknown>): Promise<{ ok: boolean; errors: string[] }> {
    if (inFlight.current) return { ok: false, errors: ["A portfolio request is already running."] };
    inFlight.current = true; setBusy(true); setError(""); setNotice("");
    try {
      const response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const payload = record(await response.json());
      if (!response.ok || payload.ok !== true) {
        const errors = list(payload.errors).map(str).filter(Boolean);
        if (!errors.length) errors.push(str(payload.error) || "The request could not be completed.");
        setError(errors.join(" ")); router.refresh(); return { ok: false, errors };
      }
      const monitor = record(payload.monitor);
      setNotice(monitor.ok === false ? `Transaction saved. ${str(monitor.note) || "The holdings check did not complete."} Use Check holdings now before relying on displayed balances.` : url.endsWith("/check") ? "Holdings check completed using saved prices." : url.endsWith("/ack") ? "Alert acknowledged. No sale was recorded." : "Transaction saved and holdings checked.");
      router.refresh(); return { ok: true, errors: [] };
    } catch {
      const message = "The response could not be confirmed. Refresh the page and check transaction history before retrying.";
      setError(message); return { ok: false, errors: [message] };
    } finally { inFlight.current = false; setBusy(false); }
  }
  const save: SaveTransaction = (body) => post("/api/portfolio/transactions", body);
  async function voidTransaction(id: string): Promise<boolean> {
    return (await save({ type: "VOID", voids: id, notes: "Voided from My portfolio", source: "manual" })).ok;
  }
  const writeDisabled = !data.ledgerReadable;

  return <div className="desk-stack portfolio-desk">
    <MonitorStatus monitor={data.monitor} busy={busy} onCheck={() => { void post("/api/portfolio/check", {}); }} />
    {data.errors.length ? <div className="portfolio-error" role="alert">{data.errors.map((e, i) => <p key={i}>{e}</p>)}</div> : null}
    {error ? <p role="alert" className="portfolio-error">{error}</p> : null}{notice ? <p role="status" className="rd-note">{notice}</p> : null}
    <AlertsList alerts={data.alerts.map((a) => acked.includes(a.id) ? { ...a, acknowledged_at: "acknowledged" } : a)} busy={busy}
      onAcknowledge={async (id) => { if ((await post("/api/portfolio/alerts/ack", { alert_id: id })).ok) setAcked((old) => [...old, id]); }} />
    <section className="desk-stack" aria-label="Holdings"><SectionHead title="Holdings" meta={`${data.positions.length} open`} right={<a className="desk-btn" href="#add-purchase">Add purchase</a>} />
      <p className="rd-note">Average price and unrealised P&L are before charges. Realised P&L includes recorded charges; missing buy charges remain excluded. Select a holding for every figure and its history.</p>
      <HoldingsTable positions={data.positions} selected={current?.symbol ?? null} onSelect={(p) => setSelected(p.symbol)} />
      {current ? <HoldingRail position={current} transactions={data.transactions} evaluations={data.evaluations[current.symbol] ?? []} busy={busy || writeDisabled} onVoid={voidTransaction} /> : <EmptyState title={writeDisabled ? "Holdings cannot be confirmed" : "No open holdings recorded"} reason={writeDisabled ? "The ledger could not be read. Resolve the saved-file error before adding transactions." : "Add a purchase or an opening balance to start monitoring. Holdings are checked even when absent from the entry scanner."} />}
    </section>
    <div className="portfolio-forms">
      <TransactionForm key={`buy-${add}-${signal}`} kind="BUY" holdings={data.positions} initialSymbol={add} signal={signal} busy={busy} disabled={writeDisabled} onSave={save} />
      <TransactionForm key={`sale-${current?.symbol ?? "empty"}`} kind="SELL" holdings={data.positions} initialSymbol={current?.closed ? "" : current?.symbol} busy={busy} disabled={writeDisabled} onSave={save} />
    </div>
    <section className="desk-stack"><SectionHead title="Closed positions" meta={`${data.closed.length} closed`} /><ClosedPositions positions={data.closed} selected={current?.symbol ?? null} onSelect={(p) => setSelected(p.symbol)} /></section>
    <details className="desk-disclosure"><summary>All transaction history · {data.transactions.length}</summary><div><TransactionHistory transactions={data.transactions} busy={busy || writeDisabled} onVoid={voidTransaction} /></div></details>
    {data.ledgerReadable && data.transactions.length === 0 ? <section className="desk-card desk-stack"><SectionHead title="Holdings pending your details" />
      <p className="rd-note">These are the seven companies you named. No transactions have been created here. Use an opening balance if the buy date or charges are unknown.</p>
      <div className="rd-list">{PENDING_HOLDINGS.map((p) => <div className="rd-li portfolio-pending" key={p.symbol}><span className="rd-li__main"><span className="rd-li__title">{p.name}</span><span className="rd-li__sub">{p.symbol} · NSE</span></span><Link className="desk-btn" href={purchaseHref(p.symbol)}>Add purchase</Link></div>)}</div>
    </section> : null}
  </div>;
}
