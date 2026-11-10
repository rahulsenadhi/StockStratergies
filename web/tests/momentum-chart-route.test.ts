import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

let dir: string;
let GET: (r: Request) => Promise<Response>;
const req = (q: string) => new Request(`http://localhost/api/desk/momentum-chart${q}`);

beforeAll(async () => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), "mchart-"));
  fs.mkdirSync(path.join(dir, "ui_momentum_charts"));
  const file = (n: string, body: object) =>
    fs.writeFileSync(path.join(dir, "ui_momentum_charts", `${n}.json`), JSON.stringify(body));
  file("M&M", { version: 1, symbol: "M&M", rows: [], traces: [], shapes: [], badges: [], since_line: null, note: null });
  file("NOTEONLY", { version: 1, symbol: "NOTEONLY", note: "Not enough history" });
  file("OLD", { version: 9, symbol: "OLD", traces: [] });
  process.env.DATA_DIR = dir;
  ({ GET } = await import("@/app/api/desk/momentum-chart/route"));
});
afterAll(() => fs.rmSync(dir, { recursive: true, force: true }));

describe("GET /api/desk/momentum-chart", () => {
  it("returns a saved chart for a symbol with an ampersand, uncached", async () => {
    const res = await GET(req("?symbol=M%26M"));
    expect(res.status).toBe(200);
    expect(res.headers.get("Cache-Control")).toBe("no-store");
    expect((await res.json()).symbol).toBe("M&M");
  });
  it("serves a note-only file as a valid chart", async () => {
    const res = await GET(req("?symbol=NOTEONLY"));
    expect(res.status).toBe(200);
    expect((await res.json()).note).toBe("Not enough history");
  });
  it("rejects a path-like symbol with 400", async () => {
    const res = await GET(req("?symbol=..%2Fx"));
    expect(res.status).toBe(400);
    expect(res.headers.get("Cache-Control")).toBe("no-store");
  });
  it("rejects a lower-case or overlong symbol with 400", async () => {
    expect((await GET(req("?symbol=abc"))).status).toBe(400);
    expect((await GET(req(`?symbol=${"A".repeat(21)}`))).status).toBe(400);
  });
  it("returns 404 when no symbol is given or no file exists", async () => {
    expect((await GET(req(""))).status).toBe(404);
    const res = await GET(req("?symbol=NOPE"));
    expect(res.status).toBe(404);
    expect(res.headers.get("Cache-Control")).toBe("no-store");
  });
  it("returns 500 for a file with an unknown version", async () => {
    expect((await GET(req("?symbol=OLD"))).status).toBe(500);
  });
});
