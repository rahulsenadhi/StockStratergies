import { describe, it, expect } from "vitest";
import { sma, ema, rsi, macd, bollinger } from "@/lib/indicators";

describe("sma", () => {
  it("trailing avg with leading nulls", () => {
    expect(sma([1, 2, 3, 4], 2)).toEqual([null, 1.5, 2.5, 3.5]);
  });
});

describe("ema", () => {
  it("seeds with sma then smooths", () => {
    expect(ema([1, 2, 3, 4], 2)).toEqual([null, 1.5, 2.5, 3.5]);
  });
});

describe("rsi", () => {
  it("nulls during warmup, 100 when only gains", () => {
    const r = rsi([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], 14);
    expect(r.slice(0, 14).every((v) => v === null)).toBe(true);
    expect(r[14]).toBeCloseTo(100, 6);
  });
});

describe("macd", () => {
  it("returns aligned macd/signal/histogram, hist = macd - signal", () => {
    const close = Array.from({ length: 60 }, (_, i) => 100 + i);
    const { macd: m, signal, histogram } = macd(close, 12, 26, 9);
    expect(m.length).toBe(60);
    const i = 59;
    expect(histogram[i]).toBeCloseTo((m[i] as number) - (signal[i] as number), 9);
  });
});

describe("bollinger", () => {
  it("mid = sma(n); upper/lower symmetric around mid", () => {
    const close = [2, 4, 6, 8, 10, 12];
    const { upper, mid, lower } = bollinger(close, 3, 2);
    expect(mid).toEqual(sma(close, 3));
    const i = 5;
    expect((upper[i] as number) - (mid[i] as number)).toBeCloseTo((mid[i] as number) - (lower[i] as number), 9);
  });
});
