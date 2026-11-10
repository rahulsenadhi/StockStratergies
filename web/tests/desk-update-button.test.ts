import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/use-job-stream", () => ({ runJobStream: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

import { runJobStream } from "@/lib/use-job-stream";
import { dismissJob, performUpdate, resetJobState, startJob } from "@/lib/desk/use-strategy-update";
import type { UpdateResult } from "@/lib/desk/run-update";
import { PageUpdateButtonView } from "@/components/desk/page-update-button";

const mockJob = vi.mocked(runJobStream);
const ok = { strategy: "Monthly", ok: true, failedStep: null, errorTail: "" };

beforeEach(() => { mockJob.mockReset(); resetJobState(); });

describe("performUpdate", () => {
  it("posts the strategy and returns the results", async () => {
    mockJob.mockResolvedValue({ ok: true, status: 200, data: { results: [ok] } });
    const lines: string[] = [];
    const out = await performUpdate("Monthly", (l) => lines.push(l));
    expect(mockJob.mock.calls[0][0]).toBe("/api/update");
    expect(mockJob.mock.calls[0][1]).toEqual({ strategy: "Monthly" });
    expect(out).toEqual({ results: [ok], error: null });
  });
  it("forwards progress lines", async () => {
    mockJob.mockImplementation(async (_u, _b, handlers) => {
      handlers?.onLine?.("step 1");
      return { ok: true, status: 200, data: { results: [] } };
    });
    const lines: string[] = [];
    await performUpdate("all", (l) => lines.push(l));
    expect(lines).toEqual(["step 1"]);
  });
  it("surfaces the busy message on 409", async () => {
    mockJob.mockResolvedValue({ ok: false, status: 409, data: { error: "An update is already running." } });
    expect(await performUpdate("all", () => {})).toEqual({ results: null, error: "An update is already running." });
  });
  it("reports a missing result and thrown errors", async () => {
    mockJob.mockResolvedValueOnce({ ok: true, status: 200, data: {} });
    expect((await performUpdate("all", () => {})).error).toBe("Update finished without a result.");
    mockJob.mockRejectedValueOnce(new Error("network down"));
    expect((await performUpdate("all", () => {})).error).toBe("network down");
  });
});

type ViewProps = { label: string; busy: boolean; disabled: boolean; lines: string[]; results: UpdateResult[] | null; error: string | null; onStart: () => void; onDismiss: () => void };

describe("PageUpdateButtonView", () => {
  const base: ViewProps = { label: "Update Monthly data", busy: false, disabled: false, lines: [], results: null, error: null, onStart: () => {}, onDismiss: () => {} };
  const render = (p: Partial<ViewProps>) => renderToStaticMarkup(h(PageUpdateButtonView, { ...base, ...p }));

  it("shows the label and is enabled when idle", () => {
    const html = render({});
    expect(html).toContain("Update Monthly data");
    expect(html).not.toContain("disabled");
  });
  it("is disabled but keeps its label when another job runs", () => {
    const html = render({ disabled: true });
    expect(html).toContain("disabled");
    expect(html).toContain("Update Monthly data");
  });
  it("shows Updating and progress when its own job runs", () => {
    const html = render({ busy: true, disabled: true, lines: ["fetching"] });
    expect(html).toContain("Updating…");
    expect(html).toContain("fetching");
  });
  it("shows the busy error", () => {
    expect(render({ error: "An update is already running." })).toContain("An update is already running.");
  });
});

describe("shared job store", () => {
  const consumers = async () => {
    const { useStrategyUpdate } = await import("@/lib/desk/use-strategy-update");
    const React = await import("react");
    const seen: ReturnType<typeof useStrategyUpdate>[] = [];
    const C = () => { seen.push(useStrategyUpdate()); return null; };
    return { seen, C, React };
  };
  it("shows one running job, its lines and results to every consumer", async () => {
    let release!: () => void;
    mockJob.mockImplementation(async (_u, _b, handlers) => {
      handlers?.onLine?.("step 1");
      await new Promise<void>((r) => { release = r; });
      return { ok: true, status: 200, data: { results: [ok] } };
    });
    const p = startJob("Monthly");
    const { seen, C, React } = await consumers();
    renderToStaticMarkup(React.createElement(React.Fragment, null, React.createElement(C), React.createElement(C)));
    expect(seen).toHaveLength(2);
    for (const s of seen) { expect(s.running).toBe("Monthly"); expect(s.lines).toEqual(["step 1"]); }
    expect(await startJob("all")).toBe(false);
    release();
    await p;
    seen.length = 0;
    renderToStaticMarkup(React.createElement(React.Fragment, null, React.createElement(C), React.createElement(C)));
    for (const s of seen) { expect(s.running).toBeNull(); expect(s.results).toEqual([ok]); expect(s.error).toBeNull(); }
    dismissJob();
    seen.length = 0;
    renderToStaticMarkup(React.createElement(C));
    expect(seen[0].results).toBeNull();
  });
  it("keeps a failure after the starting component is gone, and shows the 409 busy message", async () => {
    mockJob.mockResolvedValue({ ok: false, status: 409, data: { error: "An update is already running." } });
    await startJob("Momentum");
    const { seen, C, React } = await consumers();
    renderToStaticMarkup(React.createElement(C));
    expect(seen[0].error).toBe("An update is already running.");
    expect(seen[0].running).toBeNull();
  });
  it("disables both buttons while one job runs", async () => {
    let release!: () => void;
    mockJob.mockImplementation(async () => {
      await new Promise<void>((r) => { release = r; });
      return { ok: true, status: 200, data: { results: [] } };
    });
    const p = startJob("Monthly");
    const { PageUpdateButton } = await import("@/components/desk/page-update-button");
    const html = renderToStaticMarkup(h("div", null, h(PageUpdateButton, { strategy: "Monthly", label: "Update Monthly data" }),
      h(PageUpdateButton, { strategy: "Momentum", label: "Update Momentum data" })));
    expect(html.match(/disabled/g)?.length).toBe(2);
    expect(html).toContain("Updating…");
    expect(html).toContain("Update Momentum data");
    release();
    await p;
  });
});
