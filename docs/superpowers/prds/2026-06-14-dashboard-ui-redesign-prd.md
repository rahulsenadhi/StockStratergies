# Product Requirements Document: Dashboard UI/UX Redesign (Figma-driven)

**Author**: rahul.senadhi
**Date**: 2026-06-14
**Status**: Draft
**Stakeholders**: rahul.senadhi (sole user + owner)
**Related**: `docs/superpowers/design/saas-redesign-spec.md`, `docs/superpowers/specs/2026-06-03-ui-v2-design.md`, `docs/superpowers/specs/2026-06-04-platform-v2-prd.md`, `docs/superpowers/design/figma-prompts.md`

---

## 1. Executive Summary

Redesign the visual layer of the **NSE Strategy Hub** Streamlit dashboard (`master_dashboard.py`, port 8500) to a consistent, institutional, density-first design system — Linear / Vercel / Notion grade. Designs are authored in **Figma** (Figma Make from supplied prompts), then translated into the existing OKLCH token + `<style>` block — visual tokens only, no React. The goal is a screen-by-screen polish across all 11 pages without losing the information density that makes the tool useful, and without re-litigating the card-bloat restyle that was already rejected.

## 2. Background & Context

The Hub is a personal, single-user platform for an Indian "Disciplined Retail Quant" (the owner) running 4 strategies — Monthly Rotation, IPO Edge, Momentum Edge, PEAD — plus Suggestions, Insights, History & Proof, Strategy Library, and a Builder wizard (`master_dashboard.py` ≈ 8,963 lines; `pead_dashboard.py`).

A design foundation already exists and partially shipped:
- OKLCH "SuperDesign Modern Dark" tokens + light override (`master_dashboard.py:181-303`).
- IBM Plex Sans (UI) + IBM Plex Mono (numbers), 0.625rem radius, subtle shadows.
- A modern HTML table component (`_modern_table()`, `master_dashboard.py:4696`) with sortable, theme-aware, tabular-num cells replacing `st.dataframe`.
- Decided principles in `ui-v2-design.md` + `saas-redesign-spec.md`: 8px grid, tabular figures globally, one primary CTA/page, no emoji as structural icons, light/dark parity, micro-interactions only.

Two prior learnings constrain this work (from project memory + git history):
1. A **card-bloat restyle was rejected** — density must be preserved. A density-*preserving* fintech-SaaS polish (sidebar shell + dense tables + mono tabular) was accepted.
2. Streamlit cannot host React; styling flows through one injected `<style>` block. Figma output is therefore a **design source**, not a code source.

What prompted this: owner wants to lift the visual quality of the Streamlit dashboards using Figma as the design tool, feeding generated screens back for translation into CSS.

## 3. Objectives & Success Metrics

**Goals**
1. One unified, documented design system applied across all 11 pages (tokens, type scale, spacing, components) — no per-page visual drift.
2. Density preserved or increased on every screen versus today (no fewer rows/KPIs visible above the fold).
3. Institutional polish: tabular numerals on 100% of numeric cells, hairline borders, consistent KPI tiles, status chips, section headers.
4. Full dark + light parity on every redesigned page.
5. A repeatable Figma→CSS workflow so future screens are designed once and translated, not hand-tweaked.

**Non-Goals**
1. Re-introducing the rejected card-bloat layout, hero illustrations, or decorative padding. (Density-first is non-negotiable.)
2. Porting React/Figma components into Streamlit — translation of visual tokens only.
3. Changing any strategy logic, data pipeline, KPIs, or page information architecture (what's shown, not how it's styled).
4. The Next.js app (`web/`) — separate frontend, separate effort. This PRD is Streamlit-only.
5. Backend performance / data-freshness work — covered by Platform v2 PRD, out of scope here.
6. New pages beyond what exists (Strategy Library and Builder are styled if present, not newly specced).

**Success Metrics** (n=1; framed as checkable acceptance gates)
| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Pages on unified design system | partial (~3) | 11 / 11 | Visual audit checklist per page |
| Numeric cells using tabular figures | partial | 100% | DevTools spot-check on every table/KPI |
| Pages passing dark + light parity | not tracked | 11 / 11 | Toggle each page in both themes; no broken contrast |
| Density regression vs today | n/a | 0 screens worse | Above-the-fold row/KPI count before vs after |
| Reused components (vs bespoke per page) | low | KPI tile, chip, table, section header used everywhere | Code grep for shared helpers |
| Accessibility: contrast ≥4.5:1, focus rings | partial | all interactive elements | Manual a11y pass |

## 4. Target Users & Segments

**Primary (only):** The owner — "Disciplined Retail Quant": 3+ yrs market experience, codes Python, ₹5–50 lakh portfolio, works evenings/weekends on desktop. Uses the Hub to scan signals, judge strategy health, and decide entries with confidence. Values scannable density over decoration; needs numbers that don't jitter and screens that read fast at a glance.

No secondary users in scope (OSS forkers deferred to 2027 per strategy canvas).

## 5. User Stories & Requirements

**P0 — Must Have**
| # | User Story | Acceptance Criteria |
|---|-----------|---------------------|
| 1 | As the user, I want a single design system so every page looks consistent | Tokens, type scale (H1 32/700, H2 22/600, body 14, label 11), 8px spacing, radius, shadow defined once and used on all 11 pages |
| 2 | As the user, I want all numbers tabular and mono so tables don't jitter | `font-feature-settings:"tnum"` + IBM Plex Mono on 100% of numeric cells and KPI values |
| 3 | As the user, I want consistent KPI tiles instead of mixed `st.metric`/bespoke HTML | One `_kpi_tile(label,value,sub,trend)` helper used on Home, all 4 strategy pages, Suggestions, History |
| 4 | As the user, I want the dense table styling applied everywhere | All screener/trade/ranking tables use `_modern_table()`; 30–32px rows, sticky header, right-aligned mono numerics, hover tint, status pills |
| 5 | As the user, I want dark + light to both look right on every page | Each page toggled in both themes shows correct surfaces, borders, contrast; no black-rectangle charts in light |
| 6 | As the user, I want each page redesigned without losing density | Above-the-fold information count ≥ today on every page |
| 7 | As the user, I want a Figma→CSS workflow I can repeat | `figma-prompts.md` prompts produce frames; documented translation path frame→token→`<style>` |

**P1 — Should Have**
| # | User Story | Acceptance Criteria |
|---|-----------|---------------------|
| 8 | As the user, I want consistent status chips (Live/Paper/Research/Paused; Buy/Watch/Forming) | Single `_status_chip()` helper, text + dot, no color-only meaning |
| 9 | As the user, I want a consistent section header on every page | `_section_header(title, subtitle, action)` with hairline divider + single primary CTA |
| 10 | As the user, I want sparklines and KPIs aligned to the grid in Library/Home cards | Strategy cards use shared sparkline + KPI components, 8px rhythm |
| 11 | As the user, I want accessible focus + reduced-motion | `:focus-visible` rings on all controls; hover/scale wrapped in `prefers-reduced-motion` |

**P2 — Nice to Have / Future**
| # | User Story | Acceptance Criteria |
|---|-----------|---------------------|
| 12 | As the user, I want SVG (Lucide) icons replacing emoji in nav/headers | Emoji removed from structural chrome on new screens |
| 13 | As the user, I want the redesign carried to the Next.js app tokens | Shared token values mirrored in `web/` Tailwind theme (separate effort) |
| 14 | As the user, I want a documented component inventory page | Living style-guide screen listing every shared component |

## 6. Solution Overview

**Approach:** design-in-Figma → translate-to-CSS, screen by screen, on the existing token foundation.

1. **Figma authoring.** Use `docs/superpowers/design/figma-prompts.md` (Prompt 0 = design system; Prompts 1–5 = screens) in Figma Make. Prompts embed exact hex equivalents of the OKLCH tokens, IBM Plex fonts, 8px grid, and density rules so generated frames map ~1:1 back.
2. **Handoff.** Owner exports frames as screenshots/PNGs (or shares the Figma file URL for MCP extraction once the claude.ai Figma connector is authorized via `/mcp`).
3. **Translation.** For each frame, extract color/type/spacing/component specs and fold them into the existing `:root` tokens + `<style>` block in `master_dashboard.py` (and `pead_dashboard.py`). No React. Prefer consolidating bespoke inline HTML into the shared helpers (`_kpi_tile`, `_status_chip`, `_section_header`, `_modern_table`, sparkline).
4. **Verify.** Each page reviewed in dark + light, density checked vs baseline, a11y pass.

**Key design decisions (locked):**
- Density-first; reject any frame that trades rows/KPIs for whitespace.
- Keep IBM Plex Sans/Mono and the OKLCH token system — extend, don't replace.
- One primary CTA per page; status by chip+text; tabular numerals everywhere.
- Translation targets shared helpers to kill per-page drift.

**Technical notes / risks:**
- `master_dashboard.py` is a single ~9k-line file; CSS lives in one block — edits are concentrated and low-collision but the file is large.
- Streamlit's DOM wrapping limits some hover/selector control (already noted in spec `master_dashboard.py:282-284`); rely on the bordered-container element itself.
- Figma Make output is sRGB/hex; OKLCH conversion is approximate — re-anchor to existing token values, don't blindly paste hex.

## 7. Open Questions
| Question | Owner | Deadline |
|----------|-------|----------|
| Figma Make (AI-generated) vs hand-designed Figma + Dev Mode MCP — which path? | rahul | before Phase 1 |
| Authorize the claude.ai Figma MCP connector (for direct frame pull), or stay screenshot-only? | rahul | before Phase 2 |
| Roll redesign to all 11 pages, or pilot 1 page first then approve? | rahul | before Phase 1 |
| Keep emoji icons (current) or migrate to Lucide SVG (P2)? | rahul | Phase 3 |

## 8. Timeline & Phasing

**Phase 0 — Design system in Figma (this week)**
- Run Prompt 0; generate token + component library frames; owner approves look.

**Phase 1 — Token + global polish pass (~1–2 evenings)**
- Fold approved tokens into `:root`; apply tabular figures globally; tighten heading scale; consolidate KPI tiles + chips into shared helpers. Pilot on **one page** (recommend Momentum Edge — densest, most-used) for sign-off before fan-out.

**Phase 2 — Per-page translation (~3–4 evenings)**
- Generate + translate screens in order: Home → Monthly Rotation → IPO Edge → PEAD → Suggestions → Insights → History & Proof → Library/Builder. Each: dark+light parity + density check.

**Phase 3 — Polish + a11y (~1 evening)**
- Focus rings, reduced-motion, optional Lucide SVG swap (P2), final dark/light sweep, component-inventory note.

**Dependencies:** Figma Make access (Phase 0); optional Figma MCP auth via `/mcp` (Phase 2, screenshot fallback otherwise). No backend dependency — purely additive CSS/markup.

**Estimate:** ~6–8 focused evenings, pilot-one-page-first.

---

### Next options
- Tighten scope — challenge which P1s should drop to P2.
- Run a **pre-mortem** on this PRD (what makes a UI redesign fail for n=1).
- Break Phase 1–2 into engineering tasks / user stories.
