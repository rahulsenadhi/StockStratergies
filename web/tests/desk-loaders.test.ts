import { afterEach, beforeEach, describe, expect, test } from "vitest";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { loadSnapshot } from "@/lib/desk/snapshot";
import { oldestAge, savedDataAges } from "@/lib/desk/saved-ages";

const DAY = 86_400_000;

function snapshot(version = 1) {
  return {
    version,
    generated_at: "2026-11-07T09:40:00",
    frame: { regime: { status: "Bear" }, freshness: { latest_bar: "06 Nov 2026", age_hours: 1.5 } },
    home: {
      candidates: [
        { strategy: "Monthly Rotation", short: "Monthly", ticker: "AAA", company: "Aaa", status: "Top 5 · #1",
          status_tone: "info", key_measure: "RS +7.7% vs Nifty", change: 15.8, data: "updated today" },
        { strategy: "Momentum Edge", short: "Momentum", ticker: "BBB", company: "Bbb", status: "Watch Zone",
          status_tone: "warn", key_measure: "score 56", change: -20.7, data: "updated today" },
      ],
      pead_has_signals: false,
      strategies: [],
      growth: { "1Y": [], "3Y": [], "5Y": [], Max: [] },
    },
  };
}

let dir: string;
beforeEach(async () => { dir = await fs.mkdtemp(path.join(os.tmpdir(), "desk-")); });
afterEach(async () => { await fs.rm(dir, { recursive: true, force: true }); });

describe("loadSnapshot", () => {
  test("reads a valid v1 snapshot", async () => {
    await fs.writeFile(path.join(dir, "ui_snapshot.json"), JSON.stringify(snapshot()));
    const r = await loadSnapshot(dir);
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.snapshot.home.candidates).toHaveLength(2);
  });
  test("missing file", async () => {
    expect(await loadSnapshot(dir)).toEqual({ ok: false, reason: "missing" });
  });
  test("half-written file", async () => {
    await fs.writeFile(path.join(dir, "ui_snapshot.json"), JSON.stringify(snapshot()).slice(0, 60));
    expect(await loadSnapshot(dir)).toEqual({ ok: false, reason: "invalid" });
  });
  test("wrong shape", async () => {
    await fs.writeFile(path.join(dir, "ui_snapshot.json"), JSON.stringify({ version: 1, home: {} }));
    expect(await loadSnapshot(dir)).toEqual({ ok: false, reason: "invalid" });
  });
  test("newer schema version", async () => {
    await fs.writeFile(path.join(dir, "ui_snapshot.json"), JSON.stringify(snapshot(2)));
    expect(await loadSnapshot(dir)).toEqual({ ok: false, reason: "version" });
  });
});

describe("savedDataAges", () => {
  test("whole days in the Streamlit order; missing file is null", async () => {
    const now = new Date("2026-11-07T12:00:00");
    const touch = async (rel: string, ageMs: number) => {
      const p = path.join(dir, rel);
      await fs.mkdir(path.dirname(p), { recursive: true });
      await fs.writeFile(p, "x");
      const t = new Date(now.getTime() - ageMs);
      await fs.utimes(p, t, t);
    };
    await touch("live_rankings.csv", 60_000);
    await touch("ipo_edge_equity.csv", DAY + 60_000);
    await touch("momentum_edge_equity.csv", 30 * DAY + 60_000);
    const ages = await savedDataAges(dir, now);
    expect(ages).toEqual([
      { name: "Monthly", ageDays: 0 },
      { name: "IPO Edge", ageDays: 1 },
      { name: "Momentum", ageDays: 30 },
      { name: "PEAD", ageDays: null },
    ]);
    expect(oldestAge(ages)).toEqual({ name: "Momentum", ageDays: 30 });
  });
  test("oldestAge is null when no file exists", () => {
    expect(oldestAge([{ name: "PEAD", ageDays: null }])).toBeNull();
  });
});
