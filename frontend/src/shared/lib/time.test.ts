import { describe, expect, it } from "vitest";
import {
  compareBeijingClock,
  formatBeijing,
  formatUnixBeijing,
  laterBeijingClock,
  parseBeijing,
} from "./time";

describe("parseBeijing", () => {
  it("treats naive strings as Beijing wall clock", () => {
    expect(formatBeijing("2026-08-25 12:00:00")).toBe("2026-08-25 12:00:00");
  });

  it("converts offset timestamps into Beijing", () => {
    expect(formatBeijing("2026-08-25T04:00:00Z")).toBe("2026-08-25 12:00:00");
  });

  it("returns em dash for empty or invalid", () => {
    expect(formatBeijing("")).toBe("—");
    expect(formatBeijing("not-a-date")).toBe("—");
  });
});

describe("formatUnixBeijing", () => {
  it("formats unix seconds as Beijing date", () => {
    // 2026-08-25 00:00:00 UTC → 北京 08:00，日期仍是 25 日
    expect(formatUnixBeijing(1_787_616_000, "YYYY-MM-DD")).toBe("2026-08-25");
  });
});

describe("parseBeijing validity", () => {
  it("is invalid for nullish", () => {
    expect(parseBeijing(null).isValid()).toBe(false);
  });
});

describe("compareBeijingClock", () => {
  it("orders naive Beijing clocks and keeps the later one", () => {
    expect(compareBeijingClock("2026-08-30 20:11:02", "2026-08-30 20:11:02.100")).toBeLessThan(
      0,
    );
    expect(laterBeijingClock("2026-08-30 20:11:02", "2026-08-30 19:00:00")).toBe(
      "2026-08-30 20:11:02",
    );
    expect(laterBeijingClock("", "2026-08-31 00:40:00")).toBe("2026-08-31 00:40:00");
  });
});
