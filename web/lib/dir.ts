export function upDown(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "text-muted-foreground";
  if (n > 0) return "text-up";
  if (n < 0) return "text-down";
  return "text-muted-foreground";
}
