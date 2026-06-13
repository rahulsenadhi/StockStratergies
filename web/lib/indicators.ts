// Pure technical indicators (parity with core/indicators.py). All return arrays
// aligned to the input length, with leading null during the warmup window.

export function sma(values: number[], n: number): (number | null)[] {
  const out: (number | null)[] = [];
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= n) sum -= values[i - n];
    out.push(i >= n - 1 ? sum / n : null);
  }
  return out;
}

export function ema(values: number[], n: number): (number | null)[] {
  const out: (number | null)[] = [];
  const k = 2 / (n + 1);
  let prev = 0;
  for (let i = 0; i < values.length; i++) {
    if (i < n - 1) {
      out.push(null);
      continue;
    }
    if (i === n - 1) {
      let s = 0;
      for (let j = 0; j < n; j++) s += values[j];
      prev = s / n;
      out.push(prev);
      continue;
    }
    prev = values[i] * k + prev * (1 - k);
    out.push(prev);
  }
  return out;
}

export function rsi(close: number[], n = 14): (number | null)[] {
  const out: (number | null)[] = new Array(close.length).fill(null);
  if (close.length <= n) return out;
  let gain = 0;
  let loss = 0;
  for (let i = 1; i <= n; i++) {
    const d = close[i] - close[i - 1];
    if (d >= 0) gain += d;
    else loss -= d;
  }
  gain /= n;
  loss /= n;
  out[n] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  for (let i = n + 1; i < close.length; i++) {
    const d = close[i] - close[i - 1];
    gain = (gain * (n - 1) + (d > 0 ? d : 0)) / n;
    loss = (loss * (n - 1) + (d < 0 ? -d : 0)) / n;
    out[i] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  }
  return out;
}

export type MacdResult = {
  macd: (number | null)[];
  signal: (number | null)[];
  histogram: (number | null)[];
};

export function macd(close: number[], fast = 12, slow = 26, sig = 9): MacdResult {
  const ef = ema(close, fast);
  const es = ema(close, slow);
  const macdLine: (number | null)[] = close.map((_, i) =>
    ef[i] != null && es[i] != null ? (ef[i] as number) - (es[i] as number) : null,
  );
  const firstIdx = macdLine.findIndex((v) => v != null);
  const signal: (number | null)[] = new Array(close.length).fill(null);
  if (firstIdx >= 0) {
    const compact = macdLine.slice(firstIdx) as number[];
    const sigCompact = ema(compact, sig);
    for (let i = 0; i < sigCompact.length; i++) signal[firstIdx + i] = sigCompact[i];
  }
  const histogram: (number | null)[] = close.map((_, i) =>
    macdLine[i] != null && signal[i] != null ? (macdLine[i] as number) - (signal[i] as number) : null,
  );
  return { macd: macdLine, signal, histogram };
}

export type BollingerResult = {
  upper: (number | null)[];
  mid: (number | null)[];
  lower: (number | null)[];
};

export function bollinger(close: number[], n = 20, k = 2): BollingerResult {
  const mid = sma(close, n);
  const upper: (number | null)[] = [];
  const lower: (number | null)[] = [];
  for (let i = 0; i < close.length; i++) {
    if (mid[i] == null) {
      upper.push(null);
      lower.push(null);
      continue;
    }
    const m = mid[i] as number;
    let s = 0;
    for (let j = i - n + 1; j <= i; j++) s += (close[j] - m) ** 2;
    const sd = Math.sqrt(s / n);
    upper.push(m + k * sd);
    lower.push(m - k * sd);
  }
  return { upper, mid, lower };
}
