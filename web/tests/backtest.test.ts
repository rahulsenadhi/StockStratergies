import { describe, it, expect, beforeEach } from "vitest";
import { tryAcquire, release, isHeld } from "@/lib/job-lock";

describe("job-lock", () => {
  beforeEach(() => release()); // singleton module — reset between tests

  it("acquires when free, refuses while held", () => {
    expect(isHeld()).toBe(false);
    expect(tryAcquire()).toBe(true);
    expect(isHeld()).toBe(true);
    expect(tryAcquire()).toBe(false); // already held
  });

  it("release frees the lock", () => {
    expect(tryAcquire()).toBe(true);
    release();
    expect(isHeld()).toBe(false);
    expect(tryAcquire()).toBe(true);
  });
});
