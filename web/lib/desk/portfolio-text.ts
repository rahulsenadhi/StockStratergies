/** Client-safe display contracts. All balances, P&L, levels and costs come from Python. */
import { formatNumber, formatRupees, formatSigned, orDash, type Tone } from "@/lib/desk/format";

type Num = number | null;
export const SCHEDULER_NOTICE = "Checks run when data is updated or when you press Check now. Nothing runs while the app is closed.";
export const RECONSTRUCTED_LABEL = "Approximate reconstruction from saved prices — no alert existed at the time";
export const UNKNOWN_DATE = "Buy date unknown";
export interface Evaluation {
  symbol: string; action: string; rule: string | null; explanation: string;
  last_close: Num; last_bar_date: string | null; data_status: string; evaluated_at: string | null;
  levels: { hard_stop: Num; ema220: Num; ema_distance_pct: Num; highest_close_since_entry: Num; ema_immature: boolean; bars: Num };
  incomplete_bar_ignored: boolean; volume_ratio20: Num; drawdown_from_peak: Num; held_days: Num;
  reconstructed_first_exit: { date: string; rule: string; close: Num; level: Num } | null;
  reconstruction_note: string | null;
  /** Set only on STALE rows: what the rules say on the old bar. Not a signal to act on. */
  rule_result: { action: string; rule: string | null } | null;
}
export interface PortfolioPosition {
  symbol: string; name: string; exchange: string; open_qty: number; avg_price: Num; avg_price_incl_charges: Num;
  realised_pnl: Num; realised_charges: Num; charges_known: boolean; allocated_charges: Num;
  first_buy_date: string | null; date_known: boolean; closed: boolean;
  unrealised_pnl: Num; unrealised_pnl_pct: Num; unrealised_pnl_net: Num;
  lots: { buy_id: string; date: string | null; qty: Num; price: Num; charges_alloc: Num }[];
  estimated_exit_costs: Record<string, unknown> | null; evaluation: Evaluation;
}
export interface Transaction {
  id: string; type: string; symbol: string; exchange: string; trade_date: string | null; as_of: string | null;
  price: Num; quantity: Num; charges: Num; notes: string; source: string; voids: string | null; created_at: string | null;
}
export interface PortfolioAlert {
  id: string; symbol: string; action: string; rule: string | null; message: string;
  trigger_bar_date: string | null; created_at: string | null; acknowledged_at: string | null;
}
export interface PortfolioView {
  positions: PortfolioPosition[]; closed: PortfolioPosition[]; alerts: PortfolioAlert[];
  monitor: { last_run: string | null; last_good_check: string | null; ok: boolean; errors: string[] };
  transactions: Transaction[]; evaluations: Record<string, Evaluation[]>;
  errors: string[]; ledgerReadable: boolean; snapshotReady: boolean;
}
export const record = (v: unknown): Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v) ? v as Record<string, unknown> : {};
export const list = (v: unknown): unknown[] => Array.isArray(v) ? v : [];
export const str = (v: unknown): string => typeof v === "string" ? v : "";
export const num = (v: unknown): Num => typeof v === "number" && Number.isFinite(v) ? v : null;
const nullable = (v: unknown) => str(v) || null;

export function mapEvaluation(value: unknown): Evaluation {
  const v = record(value), l = record(v.levels), r = record(v.reconstructed_first_exit), rr = record(l.rule_result);
  return { symbol: str(v.symbol), action: str(v.action) || "DATA UNAVAILABLE", rule: nullable(v.rule),
    explanation: str(v.explanation) || "No saved evaluation. Check holdings now.", last_close: num(v.last_close),
    last_bar_date: nullable(v.last_bar_date), data_status: str(v.data_status) || "DATA UNAVAILABLE", evaluated_at: nullable(v.evaluated_at),
    levels: { hard_stop: num(l.hard_stop), ema220: num(l.ema220), ema_distance_pct: num(l.ema_distance_pct),
      highest_close_since_entry: num(l.highest_close_since_entry), ema_immature: l.ema_immature === true, bars: num(l.bars) },
    incomplete_bar_ignored: v.incomplete_bar_ignored === true, volume_ratio20: num(v.volume_ratio20),
    drawdown_from_peak: num(v.drawdown_from_peak), held_days: num(v.held_days),
    reconstructed_first_exit: str(r.date) ? { date: str(r.date), rule: str(r.rule), close: num(r.close), level: num(r.level) } : null,
    reconstruction_note: nullable(v.reconstruction_note),
    rule_result: str(rr.action) ? { action: str(rr.action), rule: nullable(rr.rule) } : null };
}
/** Rule column text; STALE rows show the old-bar result so the user sees what is pending. */
export function ruleText(e: Evaluation): string {
  if (e.action === "STALE" && e.rule_result) {
    const verdict = e.rule_result.rule ? `${e.rule_result.action} (${e.rule_result.rule})` : e.rule_result.action;
    return `Prices end ${e.last_bar_date ?? "unknown"}; on that bar: ${verdict}`;
  }
  return e.rule ?? (e.action === "HOLD" ? "No exit triggered" : e.data_status);
}
export function mapPosition(value: unknown): PortfolioPosition {
  const v = record(value);
  return { symbol: str(v.symbol), name: str(v.name) || str(v.symbol), exchange: str(v.exchange), open_qty: num(v.open_qty) ?? 0,
    avg_price: num(v.avg_price), avg_price_incl_charges: num(v.avg_price_incl_charges), realised_pnl: num(v.realised_pnl),
    realised_charges: num(v.realised_charges), charges_known: v.charges_known === true, allocated_charges: num(v.allocated_charges),
    first_buy_date: nullable(v.first_buy_date), date_known: v.date_known === true, closed: v.closed === true,
    unrealised_pnl: num(v.unrealised_pnl), unrealised_pnl_pct: num(v.unrealised_pnl_pct), unrealised_pnl_net: num(v.unrealised_pnl_net),
    lots: list(v.lots).map((item) => { const l = record(item); return { buy_id: str(l.buy_id), date: nullable(l.date), qty: num(l.qty), price: num(l.price), charges_alloc: num(l.charges_alloc) }; }),
    estimated_exit_costs: v.estimated_exit_costs ? record(v.estimated_exit_costs) : null, evaluation: mapEvaluation(v.evaluation) };
}
export function mapTransaction(value: unknown): Transaction {
  const v = record(value);
  return { id: str(v.id), type: str(v.type), symbol: str(v.symbol), exchange: str(v.exchange), trade_date: nullable(v.trade_date),
    as_of: nullable(v.as_of), price: num(v.price), quantity: num(v.quantity), charges: num(v.charges), notes: str(v.notes),
    source: str(v.source), voids: nullable(v.voids), created_at: nullable(v.created_at) };
}
export function mapAlert(value: unknown): PortfolioAlert {
  const v = record(value);
  return { id: str(v.id), symbol: str(v.symbol), action: str(v.action), rule: nullable(v.rule), message: str(v.message),
    trigger_bar_date: nullable(v.trigger_bar_date), created_at: nullable(v.created_at), acknowledged_at: nullable(v.acknowledged_at) };
}
export function actionTone(action: string): Tone {
  return ({ HOLD: "gain", REVIEW: "warn", REDUCE: "info", EXIT: "loss" } as Record<string, Tone>)[action] ?? "muted";
}
/** Sign before the currency symbol (-₹1,234.50); the shared formatter would print ₹-1,234.50 for P&L. */
export const money = (v: Num | undefined) => orDash(v, (n) => n < 0 ? `-${formatRupees(-n, 2)}` : formatRupees(n, 2));
export const count = (v: Num | undefined) => orDash(v, (n) => formatNumber(n, 0));
export const percent = (v: Num | undefined) => orDash(v, (n) => `${formatSigned(n, 2)}%`);
export const charges = (v: Num | undefined) => v == null ? "Not recorded" : money(v);
export const held = (p: PortfolioPosition) => p.date_known ? orDash(p.evaluation.held_days, (n) => `${n} days`) : UNKNOWN_DATE;
export const drawdown = (p: PortfolioPosition) => p.date_known ? percent(p.evaluation.drawdown_from_peak) : UNKNOWN_DATE;
export function stamp(value: string | null): string {
  if (!value) return "Not checked yet";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : `${new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", dateStyle: "medium", timeStyle: "short" }).format(date)} IST`;
}
/** Scanner pages use bare NSE symbols (HAL) and .BO for BSE; the ledger universe uses HAL.NS / X.BO. */
export function ledgerSymbol(symbol: string): string {
  const s = symbol.trim().toUpperCase();
  return /\.(NS|BO)$/.test(s) ? s : `${s}.NS`;
}
export function purchaseHref(symbol: string, signal?: string): string {
  return `/portfolio?add=${encodeURIComponent(ledgerSymbol(symbol))}${signal ? `&signal=${encodeURIComponent(signal)}` : ""}#add-purchase`;
}
export const PENDING_HOLDINGS = [
  { symbol: "ANDHRSUGAR.NS", name: "The Andhra Sugars Limited" },
  { symbol: "APLAPOLLO.NS", name: "APL Apollo Tubes Limited" },
  { symbol: "BHARATGEAR.NS", name: "Bharat Gears Limited" },
  { symbol: "JAYBARMARU.NS", name: "Jay Bharat Maruti Limited" },
  { symbol: "MAHLOG.NS", name: "Mahindra Logistics Limited" },
  { symbol: "PFOCUS.NS", name: "Prime Focus Limited" },
  { symbol: "TMCV.NS", name: "Tata Motors CV · ISIN INE1TAE01010" },
];
