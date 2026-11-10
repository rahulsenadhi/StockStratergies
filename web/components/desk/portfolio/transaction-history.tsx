"use client";
import { useState } from "react";
import { charges, count, money, stamp, UNKNOWN_DATE, type Transaction } from "@/lib/desk/portfolio-text";

export function TransactionHistory({ transactions, allTransactions = transactions, busy, onVoid }: {
  transactions: Transaction[]; allTransactions?: Transaction[]; busy: boolean; onVoid: (id: string) => Promise<boolean>;
}) {
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const voided = new Set(allTransactions.filter((t) => t.type === "VOID").map((t) => t.voids));
  return <div className="desk-stack">
    {!transactions.length ? <p className="rd-note">No transactions recorded.</p> : transactions.slice().reverse().map((tx) => <div key={tx.id} className="portfolio-history-row">
      <div className="desk-row"><strong>{tx.type} {tx.symbol || allTransactions.find((t) => t.id === tx.voids)?.symbol}{voided.has(tx.id) ? " · Voided" : ""}</strong>
        {tx.type !== "VOID" && !voided.has(tx.id) ? <button type="button" className="desk-btn" disabled={busy} onClick={() => setConfirmId(tx.id)}>Void</button> : null}</div>
      {tx.type === "VOID" ? <p className="rd-note">Correction of transaction {tx.voids}</p> : <>
        <p className="portfolio-copy">{count(tx.quantity)} shares at {money(tx.price)} · Charges: {charges(tx.charges)}</p>
        <p className="rd-note">{tx.trade_date ?? UNKNOWN_DATE}{tx.source === "opening_balance" ? ` · Opening balance as of ${tx.as_of ?? "not recorded"}` : ""}</p>
      </>}
      <p className="rd-note">Recorded {stamp(tx.created_at)}</p>{tx.notes ? <p className="portfolio-copy">{tx.notes}</p> : null}
      {confirmId === tx.id ? <div className="portfolio-confirm desk-stack" role="alertdialog" aria-label={`Void ${tx.type} ${tx.symbol}`} aria-describedby={`void-note-${tx.id}`}>
        <p id={`void-note-${tx.id}`} className="portfolio-copy">Void this transaction? A correction stays in history and balances are recomputed. Dependent sales may prevent voiding a purchase.</p>
        <div className="desk-row"><button type="button" className="desk-btn" disabled={busy} onClick={async () => { if (await onVoid(tx.id)) setConfirmId(null); }}>Confirm void</button>
          <button type="button" className="desk-btn" disabled={busy} onClick={() => setConfirmId(null)}>Cancel</button></div>
      </div> : null}
    </div>)}
  </div>;
}
