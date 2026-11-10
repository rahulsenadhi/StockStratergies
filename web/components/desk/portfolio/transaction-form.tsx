"use client";
import { useEffect, useState, type FormEvent } from "react";
import { SectionHead } from "@/components/desk/primitives";
import { record, list, str, type PortfolioPosition } from "@/lib/desk/portfolio-text";

type Stock = { symbol: string; name: string; exchange: string };
export type SaveTransaction = (body: Record<string, unknown>) => Promise<{ ok: boolean; errors: string[] }>;

/** Date in the trading market's timezone, never a guessed purchase date. */
export function marketToday(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

export function TransactionForm({ kind, holdings, initialSymbol = "", signal = "", busy, disabled, onSave }: {
  kind: "BUY" | "SELL"; holdings: PortfolioPosition[]; initialSymbol?: string; signal?: string;
  busy: boolean; disabled: boolean; onSave: SaveTransaction;
}) {
  const buy = kind === "BUY";
  const [query, setQuery] = useState(initialSymbol);
  const [stock, setStock] = useState<Stock | null>(null);
  const [results, setResults] = useState<Stock[]>([]);
  const [searchError, setSearchError] = useState("");
  const [searching, setSearching] = useState(false);
  const [opening, setOpening] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [success, setSuccess] = useState("");
  const [saleSymbol, setSaleSymbol] = useState(initialSymbol || holdings[0]?.symbol || "");
  const selected = holdings.find((p) => p.symbol === saleSymbol) ?? holdings[0];
  const id = buy ? "purchase" : "sale";

  useEffect(() => {
    if (!buy || !query.trim() || stock) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setSearching(true); setSearchError("");
      try {
        const res = await fetch(`/api/portfolio/universe?q=${encodeURIComponent(query)}`, { signal: controller.signal });
        const data = record(await res.json());
        if (!res.ok || data.ok !== true) throw new Error(str(data.error) || "Could not search the stock universe.");
        const found = list(data.results).map((v) => { const r = record(v); return { symbol: str(r.symbol), name: str(r.name), exchange: str(r.exchange) }; });
        setResults(found);
        const exact = found.find((s) => s.symbol.toUpperCase() === query.trim().toUpperCase());
        if (exact) setStock(exact);
      } catch (e) {
        if (!controller.signal.aborted) setSearchError(e instanceof Error ? e.message : "Search failed.");
      } finally { if (!controller.signal.aborted) setSearching(false); }
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [buy, query, stock]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setErrors([]); setSuccess("");
    if (buy && !stock) { setErrors(["Choose a company from the stock search results."]); return; }
    if (!buy && !selected) { setErrors(["Choose an open holding."]); return; }
    const form = event.currentTarget, fields = new FormData(form);
    const body: Record<string, unknown> = { type: kind, symbol: buy ? stock!.symbol : selected!.symbol,
      exchange: buy ? stock!.exchange : selected!.exchange, quantity: Number(fields.get("quantity")), price: Number(fields.get("price")),
      charges: opening && buy && fields.get("charges") === "" ? null : Number(fields.get("charges")),
      trade_date: opening && buy ? null : fields.get("trade_date"), strategy: buy ? fields.get("strategy") : "momentum_edge",
      notes: String(fields.get("notes") ?? ""), source: opening && buy ? "opening_balance" : buy && signal && stock!.symbol === initialSymbol ? "signal" : "manual" };
    if (opening && buy) { body.date_known = false; body.as_of = fields.get("as_of"); }
    if (buy && signal && stock!.symbol === initialSymbol) body.signal_ref = signal;
    const result = await onSave(body);
    if (result.ok) { form.reset(); setSuccess(buy ? "Purchase recorded." : "Sale recorded."); }
    else setErrors(result.errors);
  }

  return <section className="desk-card desk-stack" id={buy ? "add-purchase" : "record-sale"}>
    <SectionHead title={buy ? "Add purchase" : "Record sale"} />
    <p className="rd-note">{buy ? "Enter shares you already bought. Selecting a stock or arriving from a signal records nothing." : "Enter a completed sale. This form does not place an order."}</p>
    <form onSubmit={submit} className="desk-stack">
      <fieldset disabled={busy || disabled || (!buy && !selected)} className="portfolio-fieldset">
        <div className="portfolio-form-grid">
          {buy ? <div className="portfolio-field portfolio-field--wide"><label htmlFor={`${id}-stock`}>Company or symbol</label>
            <input id={`${id}-stock`} value={query} maxLength={100} autoComplete="off" onChange={(e) => { setQuery(e.target.value); setStock(null); setResults([]); }} placeholder="Search NSE or BSE" />
            <span className="rd-note">{stock ? `${stock.name} · ${stock.symbol} · ${stock.exchange}` : searching ? "Searching…" : "Choose a matching company below."}</span>
            {!stock && results.length ? <ul className="portfolio-search" aria-label="Matching companies">{results.map((s) => <li key={s.symbol}><button type="button" onClick={() => { setStock(s); setQuery(s.symbol); setResults([]); }}>{s.name}<span>{s.symbol} · {s.exchange}</span></button></li>)}</ul> : null}
            {!stock && query && !searching && !results.length ? <span className="rd-note">No match selected.</span> : null}
            {searchError ? <p role="alert" className="portfolio-error">{searchError}</p> : null}
          </div> : <div className="portfolio-field portfolio-field--wide"><label htmlFor={`${id}-stock`}>Holding</label><select id={`${id}-stock`} value={selected?.symbol ?? ""} onChange={(e) => setSaleSymbol(e.target.value)}>{!holdings.length ? <option value="">No open holdings</option> : holdings.map((p) => <option key={p.symbol} value={p.symbol}>{p.name} · {p.open_qty} shares · {p.exchange}</option>)}</select></div>}
          {buy ? <label className="desk-toggle portfolio-field--wide"><input type="checkbox" checked={opening} onChange={(e) => setOpening(e.target.checked)} />Buy date unknown — enter an opening balance</label> : null}
          <div className="portfolio-field"><label htmlFor={`${id}-date`}>{opening && buy ? "Balance as of" : "Trade date"}</label><input key={opening ? "as-of" : "trade"} id={`${id}-date`} name={opening && buy ? "as_of" : "trade_date"} type="date" max={marketToday()} required defaultValue={opening && buy ? marketToday() : undefined} /></div>
          <div className="portfolio-field"><label htmlFor={`${id}-price`}>{opening && buy ? "Average buy price (₹)" : "Price per share (₹)"}</label><input id={`${id}-price`} name="price" type="number" min="0.0001" step="0.0001" required /></div>
          <div className="portfolio-field"><label htmlFor={`${id}-qty`}>Quantity{!buy && selected ? ` (max ${selected.open_qty})` : ""}</label><input id={`${id}-qty`} name="quantity" type="number" min="1" step="1" max={!buy ? selected?.open_qty : undefined} required /></div>
          <div className="portfolio-field"><label htmlFor={`${id}-charges`}>Charges paid (₹)</label><input id={`${id}-charges`} name="charges" type="number" min="0" step="0.01" required={!(opening && buy)} placeholder={opening && buy ? "Blank = not recorded" : "Enter 0 if none"} /></div>
          {buy ? <div className="portfolio-field portfolio-field--wide"><label htmlFor={`${id}-strategy`}>Strategy</label><select id={`${id}-strategy`} name="strategy" defaultValue="momentum_edge"><option value="momentum_edge">Momentum Edge</option><option value="other">Other — manual exit review</option></select></div> : null}
          <div className="portfolio-field portfolio-field--wide"><label htmlFor={`${id}-notes`}>Notes (optional)</label><textarea id={`${id}-notes`} name="notes" maxLength={500} rows={2} /></div>
        </div>
        <button className="desk-btn" type="submit" disabled={buy && !stock}>{busy ? "Saving…" : buy ? "Save purchase" : "Save sale"}</button>
      </fieldset>
      {errors.length ? <div role="alert" className="portfolio-error">{errors.map((e, i) => <p key={i}>{e}</p>)}</div> : null}
      {success ? <p role="status" className="rd-note">{success}</p> : null}
      {disabled ? <p role="alert" className="portfolio-error">Transactions are unavailable until the ledger can be read.</p> : null}
    </form>
  </section>;
}
