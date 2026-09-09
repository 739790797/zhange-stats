import { describe, expect, it } from "vitest";
import {
  mergeRaidPrepOcrSelection,
  newRaidPrepOcrIds,
} from "./tarkovRaidPrepOcr";

describe("merge selection", () => {
  it("merges and caps", () => {
    expect(mergeRaidPrepOcrSelection(["a", "b"], ["b", "c"], 40)).toEqual([
      "a",
      "b",
      "c",
    ]);
    expect(mergeRaidPrepOcrSelection(["a"], ["b", "c"], 2)).toEqual(["a", "b"]);
  });

  it("reports only new ids", () => {
    expect(newRaidPrepOcrIds(["a", "b"], ["b", "c", "a"])).toEqual(["c"]);
  });
});
