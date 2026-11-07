// Fit and scroll audit for the Research Desk. Run with the Playwright browser tool:
//   browser_run_code_unsafe({ filename: ".../web/tests/fit/fit-audit.js" })
// against `npm run dev` on http://localhost:3000. Returns one line per viewport and
// "ALL PASS" or the failing checks. See README.md in this folder.
async (page) => {
  const BASE = "http://localhost:3000";
  const PAGES = ["/"];
  const VIEWPORTS = [[1280, 600], [1280, 560], [1024, 700], [1920, 1000], [390, 844]];
  const lines = [];
  let failures = 0;

  const wheelToEnd = async (selector, x, y) => {
    await page.evaluate((s) => { document.querySelector(s).scrollTop = 0; }, selector);
    let prev = -1;
    for (let i = 0; i < 80; i++) {
      await page.mouse.move(x, y);
      await page.mouse.wheel(0, 500);
      await page.waitForTimeout(40);
      const [top, max] = await page.evaluate((s) => {
        const el = document.querySelector(s);
        return [el.scrollTop, el.scrollHeight - el.clientHeight];
      }, selector);
      if (top >= max - 2) return true;
      if (top === prev) return false; // stalled: something is trapping the wheel
      prev = top;
    }
    return false;
  };

  for (const path of PAGES) {
    for (const [w, h] of VIEWPORTS) {
      await page.setViewportSize({ width: w, height: h });
      await page.goto(BASE + path);
      await page.waitForTimeout(2500);
      const phone = w < 768;
      const checks = await page.evaluate(() => {
        const vw = document.documentElement.clientWidth;
        const scrollsX = (el) => {
          const ox = getComputedStyle(el).overflowX;
          return (ox === "auto" || ox === "scroll" || ox === "hidden") && el.scrollWidth > el.clientWidth + 1;
        };
        let offscreen = 0;
        const sideways = new Set();
        for (const el of document.querySelectorAll(".desk-main *")) {
          if (el.offsetParent === null) continue;
          const r = el.getBoundingClientRect();
          if (r.width === 0) continue;
          let a = el.parentElement, clipped = false;
          while (a) { if (scrollsX(a)) { clipped = true; sideways.add(a.className.toString().split(" ")[0]); break; } a = a.parentElement; }
          if (!clipped && r.right > vw + 1) offscreen++;
        }
        const btn = [...document.querySelectorAll("button")].find((b) => b.innerText.includes("Update all data"));
        const br = btn ? btn.getBoundingClientRect() : null;
        return {
          pageOverflowX: document.documentElement.scrollWidth - vw,
        // Only .desk-main should scroll; a document scrollbar means a double scroll.
        docOverflowY: document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight,
          offscreen,
          sideways: [...sideways],
          updateVisible: !!br && br.top >= 0 && br.bottom <= innerHeight && br.width > 0,
        };
      });
      const fail = [];
      if (checks.pageOverflowX > 0) fail.push(`page wider than screen by ${checks.pageOverflowX}px`);
      if (checks.docOverflowY > 0) fail.push(`document scrolls too (${checks.docOverflowY}px): double scrollbar`);
      if (checks.offscreen > 0) fail.push(`${checks.offscreen} elements past the right edge`);
      const badSideways = checks.sideways.filter((c) => c !== "rd-table-wrap" || !phone);
      if (badSideways.length) fail.push(`sideways scroll in: ${badSideways.join(", ")}`);
      if (!(await wheelToEnd(".desk-main", Math.round(w * 0.6), Math.round(h / 2)))) fail.push("page wheel-scroll stalls");

      if (phone) {
        await page.locator('button[aria-label="Open menu"]').click();
        await page.waitForTimeout(400);
        const open = await page.evaluate(() => document.querySelector(".desk-sidebar").getBoundingClientRect().left >= 0);
        const vis = await page.evaluate(() => {
          const b = [...document.querySelectorAll("button")].find((x) => x.innerText.includes("Update all data"));
          const r = b.getBoundingClientRect();
          return r.top >= 0 && r.bottom <= innerHeight;
        });
        if (!open) fail.push("slide-over menu did not open");
        if (!vis) fail.push("Update all data not visible in the phone menu");
        if (!(await wheelToEnd(".desk-nav", 120, Math.round(h / 3)))) fail.push("phone nav wheel-scroll stalls");
        await page.mouse.click(w - 12, 12); // tap outside the menu, on the dimmed backdrop
        await page.waitForTimeout(400);
        const closed = await page.evaluate(() => document.querySelector(".desk-sidebar").getBoundingClientRect().right <= 0);
        if (!closed) fail.push("tapping outside did not close the menu");
      } else {
        if (!checks.updateVisible) fail.push("Update all data not visible");
        const navScrolls = await page.evaluate(() => { const n = document.querySelector(".desk-nav"); return n.scrollHeight > n.clientHeight; });
        if (navScrolls && !(await wheelToEnd(".desk-nav", 120, Math.round(h / 3)))) fail.push("nav wheel-scroll stalls");
      }

      failures += fail.length;
      lines.push(`${path} ${w}x${h}: ${fail.length ? "FAIL — " + fail.join("; ") : "pass"}`);
    }
  }
  lines.push(failures ? `${failures} FAILED CHECKS` : "ALL PASS");
  return lines.join("\n");
}
