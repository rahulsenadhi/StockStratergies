import { afterEach, beforeEach, describe, expect, test } from "vitest";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { GET as txGet, POST as txPost } from "@/app/api/portfolio/transactions/route";
import { POST as ackPost } from "@/app/api/portfolio/alerts/ack/route";
import { POST as checkPost } from "@/app/api/portfolio/check/route";
import { GET as uniGet } from "@/app/api/portfolio/universe/route";
import { withPortfolioLock } from "@/lib/desk/portfolio";
import { release, tryAcquire } from "@/lib/job-lock";

// Every test runs against a temp portfolio folder: the real portfolio/ is never touched.
let tmp: string;
const saved = { dir: process.env.PORTFOLIO_DIR, out: process.env.PORTFOLIO_UI_OUT };

beforeEach(() => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), "portfolio-api-"));
  process.env.PORTFOLIO_DIR = path.join(tmp, "portfolio");
  process.env.PORTFOLIO_UI_OUT = path.join(tmp, "ui_portfolio.json");
});
afterEach(() => {
  release();
  for (const [k, v] of [["PORTFOLIO_DIR", saved.dir], ["PORTFOLIO_UI_OUT", saved.out]] as const) {
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
  fs.rmSync(tmp, { recursive: true, force: true });
});

const ledgerFile = () => path.join(tmp, "portfolio", "ledger.json");
const ledger = () => JSON.parse(fs.readFileSync(ledgerFile(), "utf-8")).transactions as Record<string, unknown>[];

const post = (body: unknown, headers: Record<string, string> = {}, url = "http://x/api/portfolio/transactions") =>
  new Request(url, {
    method: "POST",
    body: typeof body === "string" ? body : JSON.stringify(body),
    headers: { "content-type": "application/json", ...headers },
  });

const buy = (over: Record<string, unknown> = {}) => ({
  type: "BUY", symbol: "JAYBARMARU.NS", exchange: "NSE", trade_date: "2026-10-01",
  price: 100, quantity: 10, charges: 0, strategy: "momentum_edge", source: "manual", ...over,
});

describe("POST /api/portfolio/transactions", () => {
  test("a valid BUY returns 201, is stored by Python and refreshes the page data", async () => {
    const res = await txPost(post(buy()));
    expect(res.status).toBe(201);
    const json = await res.json();
    expect(json.transaction.id).toBeTruthy();
    expect(ledger().map((t) => t.id)).toEqual([json.transaction.id]);
    expect(json.monitor.ok).toBe(true);
    const ui = JSON.parse(fs.readFileSync(process.env.PORTFOLIO_UI_OUT!, "utf-8"));
    expect(ui.positions[0].symbol).toBe("JAYBARMARU.NS");
    const list = await (await txGet()).json();
    expect(list.transactions).toHaveLength(1);
  }, 120_000);

  test("a SELL larger than the open quantity is 400 with Python's message and nothing is written", async () => {
    await txPost(post(buy()));
    const res = await txPost(post(buy({ type: "SELL", quantity: 11, trade_date: "2026-10-05" })));
    expect(res.status).toBe(400);
    expect((await res.json()).errors.length).toBeGreaterThan(0);
    expect(ledger()).toHaveLength(1);
  }, 120_000);

  test("bad JSON is 400, non-JSON content type 415, cross-site 403, oversize 413", async () => {
    expect((await txPost(post("{nope"))).status).toBe(400);
    expect((await txPost(post(buy(), { "content-type": "text/plain" }))).status).toBe(415);
    expect((await txPost(post(buy(), { "sec-fetch-site": "cross-site" }))).status).toBe(403);
    expect((await txPost(post(buy({ notes: "x".repeat(20_000) })))).status).toBe(413);
    expect((await txPost(post(buy({ notes: "x".repeat(501) })))).status).toBe(400);
    expect((await txPost(post([1]))).status).toBe(400);
    expect((await txPost(post(buy({ symbol: { a: 1 } })))).status).toBe(400);
    expect(fs.existsSync(ledgerFile())).toBe(false);
  });

  test("a corrupt ledger is never overwritten", async () => {
    fs.mkdirSync(path.dirname(ledgerFile()), { recursive: true });
    fs.writeFileSync(ledgerFile(), "{broken");
    const res = await txPost(post(buy()));
    expect(res.status).toBe(500);
    expect(fs.readFileSync(ledgerFile(), "utf-8")).toBe("{broken");
    expect((await txGet()).status).toBe(500);
  }, 120_000);

  test("concurrent POSTs both land with distinct ids", async () => {
    const [a, b] = await Promise.all([
      txPost(post(buy({ quantity: 1 }))),
      txPost(post(buy({ quantity: 2, trade_date: "2026-10-02" }))),
    ]);
    expect([a.status, b.status]).toEqual([201, 201]);
    const ids = ledger().map((t) => t.id);
    expect(new Set(ids).size).toBe(2);
  }, 180_000);
});

describe("portfolio lock", () => {
  test("locked sections run one at a time in call order", async () => {
    const order: string[] = [];
    const slow = (name: string, ms: number) => withPortfolioLock(async () => {
      order.push(`${name}:start`);
      await new Promise((r) => setTimeout(r, ms));
      order.push(`${name}:end`);
    });
    await Promise.all([slow("a", 40), slow("b", 1), slow("c", 1)]);
    expect(order).toEqual(["a:start", "a:end", "b:start", "b:end", "c:start", "c:end"]);
  });
});

describe("POST /api/portfolio/alerts/ack", () => {
  function seedAlerts() {
    fs.mkdirSync(path.join(tmp, "portfolio"), { recursive: true });
    fs.writeFileSync(path.join(tmp, "portfolio", "alerts.json"), JSON.stringify({
      version: 1, state: {}, acknowledgements: [],
      alerts: [{ id: "abc123", symbol: "X.NS", action: "EXIT" }],
    }));
  }
  const ack = (id: unknown) => ackPost(post({ alert_id: id }, {}, "http://x/api/portfolio/alerts/ack"));

  test("writes alerts only, never the ledger", async () => {
    seedAlerts();
    const res = await ack("abc123");
    expect(res.status).toBe(200);
    const alerts = JSON.parse(fs.readFileSync(path.join(tmp, "portfolio", "alerts.json"), "utf-8"));
    expect(alerts.acknowledgements[0].alert_id).toBe("abc123");
    expect(fs.existsSync(ledgerFile())).toBe(false);
  }, 60_000);

  test("unknown id is 404, missing id 400, cross-site 403", async () => {
    seedAlerts();
    expect((await ack("nope")).status).toBe(404);
    expect((await ack(undefined)).status).toBe(400);
    const cross = await ackPost(post({ alert_id: "abc123" }, { "sec-fetch-site": "cross-site" }));
    expect(cross.status).toBe(403);
  }, 60_000);
});

describe("POST /api/portfolio/check", () => {
  const req = (h: Record<string, string> = {}) => post({}, h, "http://x/api/portfolio/check");

  test("409 while another job holds the lock", async () => {
    expect(tryAcquire()).toBe(true);
    expect((await checkPost(req())).status).toBe(409);
  });

  test("403 cross-site, 415 non-JSON", async () => {
    expect((await checkPost(req({ "sec-fetch-site": "cross-site" }))).status).toBe(403);
    expect((await checkPost(req({ "content-type": "text/plain" }))).status).toBe(415);
  });

  test("runs the monitor, writes the page data and releases the lock", async () => {
    const res = await checkPost(req());
    expect(res.status).toBe(200);
    const ui = JSON.parse(fs.readFileSync(process.env.PORTFOLIO_UI_OUT!, "utf-8"));
    expect(ui.positions).toEqual([]);
    expect(tryAcquire()).toBe(true);
  }, 60_000);
});

describe("GET /api/portfolio/universe", () => {
  const search = async (q: string) =>
    (await (await uniGet(new Request(`http://x/api/portfolio/universe?q=${encodeURIComponent(q)}`))).json()).results as
      { symbol: string; name: string; exchange: string; isin: string }[];

  test('"jay bharat" finds JAYBARMARU.NS', async () => {
    const r = await search("jay bharat");
    expect(r.map((x) => x.symbol)).toContain("JAYBARMARU.NS");
    expect(Object.keys(r[0]).sort()).toEqual(["exchange", "isin", "name", "symbol"]);
  });

  test("matches symbols case-insensitively, caps at 20, empty query is empty", async () => {
    expect((await search("jaybarmaru"))[0].symbol).toBe("JAYBARMARU.NS");
    expect((await search("a")).length).toBeLessThanOrEqual(20);
    expect(await search("")).toEqual([]);
  });
});
