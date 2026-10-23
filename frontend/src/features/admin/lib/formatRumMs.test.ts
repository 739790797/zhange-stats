import { describe, expect, it } from "vitest";
import { formatRumMs } from "./formatRumMs";

describe("formatRumMs", () => {
  it("formats wait time", () => {
    expect(formatRumMs(null)).toBe("—");
    expect(formatRumMs(340)).toBe("340 ms");
    expect(formatRumMs(1200)).toBe("1.20 s");
  });
});
