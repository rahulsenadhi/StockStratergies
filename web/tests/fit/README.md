# Fit and scroll audit

`fit-audit.js` checks that each desk page fits the screen and scrolls normally at
1280×600 (the main laptop view: 1920×1080 at 150% Windows scaling), 1280×560,
1024×700, 1920×1000 and 390×844 (phone). Per size it fails on:

- the page or document scrolling sideways, or a second (document) scrollbar
- anything past the right edge outside an element meant to scroll sideways
- mouse-wheel scrolling that stalls before the bottom of the page or the sidebar nav
- "Update all data" not visible
- on a phone: the menu not opening, not closing on an outside tap, or wide content
  other than data tables scrolling sideways

It needs no extra npm package. Start the app (`npm run dev`), then run the file with
the Playwright browser tool (`browser_run_code_unsafe` with `filename` set to this
file). It returns one line per size and `ALL PASS` when everything passes. Add each
new page's path to `PAGES` when it moves to Next.js.
