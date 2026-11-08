import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { BigValue, Checklist, ContextBar, StatBar } from "@/components/desk/primitives";
import { Tabs } from "@/components/desk/tabs";
import { GlossaryDisclosure } from "@/components/desk/glossary";
import { ExitResearch } from "@/components/desk/exit-research";
import { EXIT_EMPTY } from "@/lib/desk/exit-text";
import { GLOSSARY } from "@/lib/glossary";

const render = (el: Parameters<typeof renderToStaticMarkup>[0]) => renderToStaticMarkup(el);

describe("ContextBar", () => {
  it("matches the Python context_bar output with a basis note", () => {
    expect(render(h(ContextBar, { items: [["Universe", "Nifty 50 (current list)"]], basis: "Gross · before costs and slippage" }))).toBe(
      '<div class="rd-ctx" role="group" aria-label="Result context"><span class="rd-ctx__item"><span class="rd-ctx__label">Universe</span><span class="rd-ctx__value">Nifty 50 (current list)</span></span><span class="rd-ctx__basis">Gross · before costs and slippage</span></div>',
    );
  });
  it("omits the basis note and escapes text", () => {
    expect(render(h(ContextBar, { items: [["A", "x & y"]] }))).toBe(
      '<div class="rd-ctx" role="group" aria-label="Result context"><span class="rd-ctx__item"><span class="rd-ctx__label">A</span><span class="rd-ctx__value">x &amp; y</span></span></div>',
    );
  });
});

describe("BigValue", () => {
  it("shrinks the decimals", () => {
    expect(render(h(BigValue, { text: "+20.9%", tone: "gain" }))).toBe(
      '<span class="rd-big rd-big--gain">+20<span class="rd-big__dec">.9%</span></span>',
    );
  });
  it("renders a value without decimals", () => {
    expect(render(h(BigValue, { text: "12", tone: "info" }))).toBe('<span class="rd-big rd-big--info">12</span>');
  });
  it("has no tone class when tone is omitted", () => {
    expect(render(h(BigValue, { text: "12" }))).toBe('<span class="rd-big">12</span>');
  });
});

describe("StatBar", () => {
  it("matches the Python stat_bar output", () => {
    expect(render(h(StatBar, { label: "Win rate", value: "55%", tone: "gain" }))).toBe(
      '<div class="rd-bar rd-bar--gain"><span>Win rate</span><span class="rd-bar__val">55%</span></div>',
    );
  });
});

describe("Checklist", () => {
  const checks = [
    { title: "Out-of-sample", label: "Covered", tone: "gain" as const, note: "Held" },
    { title: "Costs", label: "Not tested", tone: "warn" as const, note: "" },
  ];
  it("renders one li.rd-check per row with the pill, and the note only when present", () => {
    expect(render(h(Checklist, { checks }))).toBe(
      '<ul class="rd-checks" aria-label="Validation status">' +
        '<li class="rd-check"><span class="rd-check__title">Out-of-sample</span><span class="rd-pill rd-pill--gain">Covered</span><span class="rd-check__note">Held</span></li>' +
        '<li class="rd-check"><span class="rd-check__title">Costs</span><span class="rd-pill rd-pill--warn">Not tested</span></li>' +
        "</ul>",
    );
  });
});

describe("Tabs", () => {
  const tabs = [
    { id: "a", label: "Alpha", content: h("p", null, "A body") },
    { id: "b", label: "Beta", content: h("p", null, "B body") },
  ];
  it("selects the first tab and renders only its panel", () => {
    const html = render(h(Tabs, { tabs }));
    expect(html).toContain('role="tablist"');
    expect(html).toMatch(/id="tab-a"[^>]*aria-selected="true"|aria-selected="true"[^>]*id="tab-a"/);
    expect(html).toMatch(/id="tab-b"[^>]*aria-selected="false"|aria-selected="false"[^>]*id="tab-b"/);
    expect(html).toContain("A body");
    expect(html).not.toContain("B body");
    expect(html.match(/role="tabpanel"/g)).toHaveLength(1);
  });
});

describe("GlossaryDisclosure", () => {
  it("lists every glossary entry", () => {
    const html = render(h(GlossaryDisclosure));
    expect(html).toContain("Glossary — What do these words mean?");
    for (const g of Object.values(GLOSSARY)) expect(html).toContain(g.label.replace(/&/g, "&amp;"));
  });
});

describe("ExitResearch", () => {
  it("renders the empty text when there is no recommendation", () => {
    expect(render(h(ExitResearch, { rec: null, title: "x" }))).toContain(EXIT_EMPTY);
  });
  it("renders the given title with a recommendation", () => {
    const html = render(h(ExitResearch, {
      title: "Exit research: Test page",
      rec: { hold_days: 2, hold_median_return: 0.44, hold_win_rate: 0.56, stop_pct: -12.8, sample_size: 152,
        data_quality: "close", targets: [{ pct: 7.6, book_pct: 40, hit_rate: 0.6 }] },
    }));
    expect(html).toContain("Exit research: Test page");
    expect(html).toContain("2 days");
  });
});
