# Restore Slice 4 — Suggestions / "Buy These Now" (plan)

Spec: `2026-06-12-restore-4-suggestions-design.md`. Status: DONE (this session).

## Tasks
1. **Python precompute** `precompute_suggestions.py` — pure fns `edge_buckets`,
   `build_{monthly,momentum,ipo}_suggestions`, `compute_regime`, `assemble`
   (faithful ports of master_dashboard `_edge_buckets`/`_build_*`/`_regime_snapshot`)
   + I/O `load_benchmark`/`_read_csv`/`build_all`/`main` → writes `suggestions.json`.
2. **pytest** `tests/test_suggestions.py` — edge_buckets (basic/min_n/empty/score),
   monthly + momentum builders (stop/target/position/confidence/filters), compute_regime
   (short→Unknown, rising→Bull), assemble (sort/rerank/summary). 16 tests.
3. **TS loader** `getSuggestions(dataDir?)` + `SuggestionPick`/`SuggestionsRegime`/
   `SuggestionsFeed` types in `lib/data/strategies.ts` (reads suggestions.json,
   null on missing/malformed). **vitest** `tests/suggestions.test.ts` (4 tests).
4. **UI** `components/suggestions-feed.tsx` (RegimeBanner + KPI strip + dense PickCards)
   + `app/suggestions/page.tsx` (force-dynamic RSC) + "Buy Now" nav link in app-shell.

## Verification
- pytest 16 pass · vitest 183 pass (+4) · tsc clean · `npm run build` clean
  (/suggestions = dynamic).
- Runtime (`next start -p 3123`): /suggestions 200, renders Buy-These-Now + BEAR banner
  + Picks-Today/Confidence KPIs + ZYDUSWELL pick card + Max-size; /, /leaderboard,
  /glossary, /strategy/momentum_edge all still 200.
- Real precompute: regime Bear → 9 picks (5 momentum + 4 monthly; IPO suspended in bear).

## Notes / follow-ups
- IPO pool empty (no ipo_edge_signals.csv yet); faithful degradation — add the file +
  it flows automatically (bull-only).
- Per-strategy filter tabs deferred (single ranked list shipped).
- Refresh = manual `python precompute_suggestions.py`; wire into the data pipeline /
  a future Update button (restore slice 6).
- Rationale HTML `<b>` stripped to plain text for the dense layout.
