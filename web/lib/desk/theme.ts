/** Light/dark theme: saved choice in localStorage, else the system setting. */
export const THEME_KEY = "desk-theme";
export type Theme = "light" | "dark";

/** Runs in <head> before first paint, so the page never flashes the wrong theme. */
export const THEME_BOOT_SCRIPT =
  `(function(){var t;try{t=localStorage.getItem("${THEME_KEY}")}catch(e){}` +
  `if(t!=="light"&&t!=="dark"){t=window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}` +
  `document.documentElement.dataset.theme=t})();`;
