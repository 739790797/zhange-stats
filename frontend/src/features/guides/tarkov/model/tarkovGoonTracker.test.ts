import { describe, expect, it } from "vitest";
import {
  formatGoonElapsed,
  goonSightingHint,
  isGoonMapSlug,
  sameGoonMap,
} from "./tarkovGoonTracker";

describe("tarkovGoonTracker", () => {
  it("only treats the four rotation maps as goon maps", () => {
    expect(isGoonMapSlug("customs")).toBe(true);
    expect(isGoonMapSlug("factory")).toBe(false);
    expect(sameGoonMap("customs", "customs")).toBe(true);
    expect(sameGoonMap("woods", "customs")).toBe(false);
  });

  it("formats elapsed time in Chinese", () => {
    const now = Date.parse("2026-09-01T08:00:00+08:00");
    expect(formatGoonElapsed("2026-09-01T00:00:10Z", now)).toBe("刚刚");
    expect(formatGoonElapsed("2026-09-01T07:48:00+08:00", now)).toBe("12分钟前");
    expect(formatGoonElapsed("2026-09-01T05:00:00+08:00", now)).toBe("3小时前");
    expect(formatGoonElapsed("2026-08-30T08:00:00+08:00", now)).toBe("2天前");
  });

  it("builds the map-row sighting hint", () => {
    const now = Date.parse("2026-09-01T08:00:00+08:00");
    expect(goonSightingHint("2026-09-01T07:48:00+08:00", now)).toBe(
      "三狗出没（12分钟前上报）",
    );
    expect(goonSightingHint("2026-09-01T00:00:10Z", now)).toBe(
      "三狗出没（刚刚上报）",
    );
  });
});
