import type { ReactNode } from "react";
import { SectionHead, StatusPill } from "@/components/desk/primitives";
import { TransactionHistory } from "@/components/desk/portfolio/transaction-history";
import { actionTone, charges, count, drawdown, held, money, needsConfirmation, num, percent, RECONSTRUCTED_LABEL, stamp, str, UNKNOWN_DATE, type Evaluation, type PortfolioPosition, type Transaction } from "@/lib/desk/portfolio-text";

function Row({ label, children }: { label: string; children: ReactNode }) {
  return <div className="rd-li portfolio-fact"><span className="rd-li__sub">{label}</span><span className="rd-li__val">{children}</span></div>;
}
const COSTS = [["brokerage", "Brokerage"], ["stt", "STT"], ["exchange_txn", "Exchange transaction"], ["sebi", "SEBI"], ["gst", "GST"], ["stamp_duty", "Stamp duty"], ["dp_charge", "DP charge"], ["total", "Total estimate"]];

export function HoldingRail({ position: p, transactions, evaluations, busy, onVoid }: {
  position: PortfolioPosition; transactions: Transaction[]; evaluations: Evaluation[]; busy: boolean; onVoid: (id: string) => Promise<boolean>;
}) {
  const ev = p.evaluation, recon = ev.reconstructed_first_exit;
  const selectedTx = transactions.filter((t) => t.symbol === p.symbol || transactions.some((original) => original.symbol === p.symbol && original.id === t.voids));
  return <aside className="desk-stack portfolio-rail" aria-label={`${p.name} holding detail`}>
    <section className="desk-card desk-stack">
      <SectionHead title={p.name} right={<StatusPill label={p.closed ? "Closed" : ev.action} tone={p.closed ? "muted" : actionTone(ev.action)} />} />
      <p className="rd-note">{p.symbol} · {p.exchange}{needsConfirmation(p.symbol) ? " · please confirm company identity" : ""}</p>
      {p.symbol === "TMCV.NS" ? <p className="rd-note">Tata Motors CV · ISIN INE1TAE01010</p> : null}
      {!p.closed ? <><p className="portfolio-copy">{ev.explanation}</p><strong>Rule: {ev.rule ?? (ev.action === "HOLD" ? "No exit triggered" : ev.data_status)}</strong></> : <p className="rd-note">This position is fully closed. No current exit check is needed.</p>}
      <div className="rd-list">
        <Row label="Open quantity">{count(p.open_qty)}</Row><Row label="Average price, before charges">{money(p.avg_price)}</Row>
        <Row label="Average price, with buy charges">{p.avg_price_incl_charges == null ? "Not recorded" : money(p.avg_price_incl_charges)}</Row>
        <Row label="Realised P&L">{money(p.realised_pnl)}</Row>
        {!p.closed ? <><Row label="Last close">{money(ev.last_close)}</Row><Row label="Unrealised P&L before charges">{money(p.unrealised_pnl)} · {percent(p.unrealised_pnl_pct)}</Row>
          <Row label="Unrealised P&L after recorded buy charges">{p.unrealised_pnl_net == null ? "Unavailable" : money(p.unrealised_pnl_net)}</Row>
          <Row label="Held">{held(p)}</Row><Row label="Hard stop">{money(ev.levels.hard_stop)}</Row>
          <Row label="220-day EMA">{money(ev.levels.ema220)}{ev.levels.ema_immature ? " · immature" : ""}</Row>
          <Row label="Distance above EMA">{percent(ev.levels.ema_distance_pct)}</Row>
          <Row label="Highest close since buy">{p.date_known ? money(ev.levels.highest_close_since_entry) : UNKNOWN_DATE}</Row>
          <Row label="Drawdown from peak">{drawdown(p)}</Row><Row label="20-day volume ratio">{ev.volume_ratio20 == null ? "—" : `${ev.volume_ratio20}×`}</Row>
          <Row label="Data as of">{ev.last_bar_date ?? "Unavailable"} · {ev.data_status}</Row>
          <Row label="Evaluated">{stamp(ev.evaluated_at)}</Row></> : null}
      </div>
      {!p.charges_known ? <p className="rd-note">Buy charges are not fully recorded. Realised P&L excludes those missing charges.</p> : null}
      {ev.incomplete_bar_ignored ? <p className="rd-note">Today’s incomplete price bar was ignored.</p> : null}
    </section>
    {!p.closed ? <details className="desk-disclosure"><summary>Estimated exit costs</summary><div>
      {p.estimated_exit_costs ? <><p>Estimate for {count(num(p.estimated_exit_costs.quantity))} shares at {money(num(p.estimated_exit_costs.price))}. Rates as of {str(p.estimated_exit_costs.as_of) || "not recorded"}; verify with your broker.</p>
        {COSTS.map(([key, label]) => <Row key={key} label={label}>{money(num(p.estimated_exit_costs?.[key]))}</Row>)}
        <p>{str(p.estimated_exit_costs.note)}</p></> : <p>No estimate available without a saved price.</p>}
    </div></details> : null}
    <details className="desk-disclosure"><summary>Charges paid and FIFO lots</summary><div>
      <Row label="Buy charges allocated to open lots">{charges(p.allocated_charges)}</Row><Row label="Charges allocated to realised trades">{charges(p.realised_charges)}</Row>
      {p.lots.map((lot) => <div className="portfolio-history-row" key={lot.buy_id}><p>{count(lot.qty)} shares at {money(lot.price)}</p><p>{lot.date ?? UNKNOWN_DATE} · Allocated charges: {charges(lot.charges_alloc)}</p></div>)}
      {!p.lots.length ? <p>No open lots.</p> : null}
    </div></details>
    <details className="desk-disclosure"><summary>Transaction history · {selectedTx.length}</summary><div><TransactionHistory transactions={selectedTx} allTransactions={transactions} busy={busy} onVoid={onVoid} /></div></details>
    <details className="desk-disclosure"><summary>Evaluation history · last {evaluations.length}</summary><div>
      {evaluations.length ? evaluations.slice().reverse().map((e, i) => <div className="portfolio-history-row" key={`${e.evaluated_at}-${i}`}><strong>{stamp(e.evaluated_at)}</strong><p><StatusPill label={e.action} tone={actionTone(e.action)} /> {e.rule ?? "No rule recorded"}</p><p>{e.explanation}</p><p>Bar: {e.last_bar_date ?? "Unavailable"} · Close: {money(e.last_close)}</p></div>) : <p>No recorded evaluations yet.</p>}
    </div></details>
    {!p.closed ? <section className="desk-card"><SectionHead title="Reconstructed first exit" />
      <p className="rd-note">{RECONSTRUCTED_LABEL}. Uses the current open average price; mixed-price lots can change the reconstructed date.</p>
      {!p.date_known ? <p>{UNKNOWN_DATE}</p> : recon ? <p>{recon.date} · {recon.rule} · Close {money(recon.close)} · Level {money(recon.level)}</p> : <p>{ev.reconstruction_note ?? "No reconstruction is available."}</p>}
    </section> : null}
    <p className="rd-note">DVM scores: not recorded</p>
  </aside>;
}
