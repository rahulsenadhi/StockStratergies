// Shared single-process in-flight lock so heavy jobs (recompute, backtest) cannot overlap.
let held = false;

export function tryAcquire(): boolean {
  if (held) return false;
  held = true;
  return true;
}

export function release(): void {
  held = false;
}

export function isHeld(): boolean {
  return held;
}
