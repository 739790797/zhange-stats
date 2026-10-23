import { describe, expect, it } from "vitest";
import { visibleRefetchInterval } from "./visibleRefetchInterval";

describe("visibleRefetchInterval", () => {
  it("returns the interval when the tab is visible", () => {
    expect(visibleRefetchInterval(15_000, false)).toBe(15_000);
  });

  it("pauses when the tab is hidden", () => {
    expect(visibleRefetchInterval(15_000, true)).toBe(false);
  });
});
