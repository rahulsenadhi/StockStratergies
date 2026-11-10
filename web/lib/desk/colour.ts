/** "#7c9cff" + 0.07 -> "rgba(124,156,255,0.07)". A value that is not hex is returned unchanged. */
export function hexRgba(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const n = Number.parseInt(full.slice(0, 6), 16);
  if (Number.isNaN(n)) return hex;
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
}
