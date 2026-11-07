import { describe, expect, test } from "vitest";
import { nextSort, previewRows, sortRows, type SortSpec } from "@/lib/desk/table";

type Row = { v: number | string | null; id: number };
const byV = (r: Row) => r.v;

describe("sortRows", () => {
  test("numbers sort numerically and nulls stay last both ways", () => {
    const rows: Row[] = [{ v: 2, id: 1 }, { v: null, id: 2 }, { v: -1, id: 3 }, { v: 10, id: 4 }];
    expect(sortRows(rows, byV, "asc").map((r) => r.v)).toEqual([-1, 2, 10, null]);
    expect(sortRows(rows, byV, "desc").map((r) => r.v)).toEqual([10, 2, -1, null]);
  });
  test("strings use localeCompare and the sort is stable", () => {
    const rows: Row[] = [{ v: "b", id: 1 }, { v: "a", id: 2 }, { v: "b", id: 3 }];
    expect(sortRows(rows, byV, "asc").map((r) => r.id)).toEqual([2, 1, 3]);
  });
  test("does not mutate the input", () => {
    const rows: Row[] = [{ v: 2, id: 1 }, { v: 1, id: 2 }];
    sortRows(rows, byV, "asc");
    expect(rows.map((r) => r.id)).toEqual([1, 2]);
  });
});

describe("previewRows", () => {
  const rows = Array.from({ length: 20 }, (_, i) => i);
  test("shows 15 until expanded", () => {
    expect(previewRows(rows, false)).toHaveLength(15);
    expect(previewRows(rows, true)).toHaveLength(20);
    expect(previewRows(rows.slice(0, 10), false)).toHaveLength(10);
  });
});

describe("nextSort", () => {
  test("first click sorts descending, second ascending, other column resets", () => {
    const none: SortSpec = null;
    expect(nextSort(none, "move")).toEqual({ key: "move", dir: "desc" });
    expect(nextSort({ key: "move", dir: "desc" }, "move")).toEqual({ key: "move", dir: "asc" });
    expect(nextSort({ key: "move", dir: "asc" }, "move")).toEqual({ key: "move", dir: "desc" });
    expect(nextSort({ key: "move", dir: "asc" }, "status")).toEqual({ key: "status", dir: "desc" });
  });
});
