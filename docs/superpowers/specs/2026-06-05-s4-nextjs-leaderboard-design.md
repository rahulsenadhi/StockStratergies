# S4 (slice 1) — Next.js Local Leaderboard: Design Spec

**Author:** rahulsenadhi
**Date:** 2026-06-05
**Status:** Draft
**Depends on:** S1 (`strategies_index.json` with canonical `kpis_inline` + `rank` + `rank_score`), local data layer (S0a/S0b). Node 24 / npm 11 present.

---

## 1. Goal

Begin the S4 frontend cutover (Streamlit → modern web UI) with the **first strangler-fig slice**: a local **Next.js + TypeScript + Tailwind + shadcn/ui** app that renders the **Strategy Leaderboard** as a dense, sortable ranked table, reading the existing **local** data files directly. Prove the pattern (scaffold + one page + typed data seam) so later slices migrate the remaining pages.

## 2. Non-Goals

- **No cloud** — no Cloudflare Pages/Workers/R2/D1. Runs locally (`npm run dev`). The PRD's cloud serving is deferred (S0b deferred all cloud); this slice is local-consistent.
- **No Streamlit removal** — Streamlit keeps running on its ports; Next.js runs on its own (e.g. 3000). Strangler-fig; nothing removed.
- **No write actions** — read-only leaderboard. No "Recompute" button (needs Python `core.leaderboard.refresh_all`); Streamlit keeps that. Deferred.
- **No other pages** — only the leaderboard this slice. Home/detail/wizard stay in Streamlit.
- **No new charting library** — sparkline is inline SVG.

## 3. Decisions (this session)

- Scope: local Next.js, one page first (strangler-fig). First page = **Strategy Library / leaderboard**.
- Data access: **direct file read + a typed loader** (the single swappable seam toward future cloud).
- Layout: **dense ranked table** (Layout A) — rank · name · type/status · KPI columns · sparkline · score; click-header sort.

## 4. Architecture & File Structure

```
web/                                   NEW — Next.js app (own dir)
  package.json, tsconfig.json, next.config.mjs, tailwind config, postcss,
  components.json (shadcn), .env.local  (DATA_DIR="..")
  app/
    layout.tsx          root layout — dark theme, base font
    page.tsx            redirect → /leaderboard
    leaderboard/page.tsx   server component: getStrategies() → <LeaderboardTable>
  lib/
    data/strategies.ts  TYPED LOADER (only module that knows the data source):
                        Strategy type; getStrategies(); getEquitySeries(csv)
    format.ts           pct(), signed(), naDash()
  components/
    leaderboard-table.tsx  client component — shadcn <Table> + TanStack sortable cols
    sparkline.tsx          inline SVG sparkline
    kpi-cell.tsx           colored +/- value; null → "—"
  tests/
    strategies.test.ts  Vitest — loader + format
```

**Boundaries:**
- `lib/data/strategies.ts` is the sole data-source authority (local files now; API/Workers later) — the future-cloud seam.
- `leaderboard/page.tsx` is a **server component** (reads files at request time; no client data fetch). Only `LeaderboardTable` is a client component (for sort interactivity).
- `web/` is fully isolated; the Python app and Streamlit are untouched.

**Stack:** Next.js (App Router) + TypeScript + Tailwind + shadcn/ui; TanStack Table for client sort; inline-SVG sparkline (no chart lib); Vitest for unit tests.

## 5. Typed Data Contract (`lib/data/strategies.ts`)

```ts
type Kpis = {
  cagr: number; totalReturn: number; volatility: number; sharpe: number;
  maxDd: number; calmar: number | null; winRate: number | null;
  numTrades: number; alpha: number | null; finalEquity: number;
};
type Strategy = {
  id: string; name: string; type: string; status: string;
  kpis: Kpis; rank: number | null; rankScore: number | null;
  equityCsv: string | null; kpisError?: string;
};
```

- `getStrategies(): Promise<Strategy[]>` — reads `$DATA_DIR/strategies_index.json`, maps each entry's `kpis_inline` (decimals; `win_rate`/`calmar`/`alpha` may be JSON `null`) into `Kpis` **preserving null** (never coerce to 0). Returns sorted by `rank` ascending (un-ranked last). Missing/malformed file → `[]`.
- `getEquitySeries(csv: string): Promise<number[]>` — resolves `csv` against `$DATA_DIR`, reads, picks value column (`Portfolio_Value` | `Equity` | `equity`), downsamples to ≤80 points. Missing/unreadable → `[]`.
- `$DATA_DIR` from `process.env.DATA_DIR` (default `".."` — repo root relative to `web/`).

## 6. Data Flow

```
GET /leaderboard
 → leaderboard/page.tsx (RSC):
     const rows = await getStrategies()
     // sparkline points fetched per row (server-side) and passed down
     for r of rows: r.series = await getEquitySeries(r.equityCsv)
 → <LeaderboardTable rows={rows} />  (client)
     TanStack table; default sort rank asc; header click re-sorts
     columns: rank | name (+type/status) | CAGR | Sharpe | MaxDD | WinRate | Alpha | Score | sparkline
     KPI cells via <KpiCell>: pct + sign color; null → "—"
```

Formatting (`format.ts`): `pct(0.261) → "+26.1%"`, `signed(2.45) → "2.45"`, `naDash(null) → "—"`.

## 7. Error Handling

- `strategies_index.json` missing/malformed → `getStrategies()` returns `[]` → page shows empty-state ("No strategies — run a backtest"). No crash.
- Entry with `kpis_error` or absent kpis → row renders; KPI cells "—"; sparkline empty. Never throws.
- Equity CSV missing/unreadable → `getEquitySeries` returns `[]` → sparkline renders nothing; row intact.
- `winRate: null` (Monthly/PEAD) → "—" (handled at the type boundary — the same null class S1's smoke caught).
- Loader try/catch per file; one bad strategy never breaks the table.

## 8. Testing

- **Vitest (pure loader/format — no Next runtime):**
  - parse fixture `strategies_index.json` → typed `Strategy[]`, sorted by rank.
  - `win_rate: null` stays `null`; entry with `kpis_error` → kpis null, still included.
  - missing index file → `[]`.
  - `getEquitySeries`: column resolution (`Portfolio_Value` vs `equity`); downsample caps ≤80; missing file → `[]`.
  - `format.ts`: `pct`/`signed`/`naDash` incl. null.
- **Typecheck/build:** `npm run build` (or `tsc --noEmit`) passes — catches type errors.
- **Verification (run the app — slice end):** `npm run dev`, load `/leaderboard`; confirm 4 strategies render ranked (PEAD #1), header-sort works, sparklines draw, null win-rate shows "—".

## 9. Open Questions

| Question | Resolution |
|---|---|
| Next.js dev port? | 3000 default (Streamlit uses 8500–8503). No conflict. |
| Style theme — match Streamlit dark or fresh shadcn default? | shadcn default dark (modern, the UX-upgrade goal); revisit polish in a later slice. |
| Equity CSV path resolution for hardcoded strategies (relative vs absolute in index)? | Resolve against `$DATA_DIR`; the loader normalizes. Confirm each entry's `equity_csv` resolves during build of the loader tests. |
| Recompute / write actions? | Deferred — read-only slice. Streamlit retains Recompute. Revisit when a local API/sidecar slice is scoped. |
| node_modules / build artifacts in git? | Add `web/node_modules`, `web/.next` to `.gitignore`. |

## 10. Future Slices (context, not this spec)

After this proves the pattern: migrate Home, strategy-detail (charts), Monthly/IPO/Momentum/PEAD pages; then a local API/sidecar for write actions (Recompute, run-backtest); then — only if remote access is wanted — the deferred cloud (Workers/R2/Access) reusing the same typed loader seam.
