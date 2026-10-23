import { describe, expect, it } from "vitest";
import {
  intersectBox,
  scrollForThumbOffset,
  thumbMetrics,
  thumbSize,
} from "./overlayScrollbar";

describe("thumbMetrics", () => {
  it("stays empty when the content fits", () => {
    expect(thumbMetrics(0, 100, 100, 100)).toBeNull();
    expect(thumbMetrics(0, 100, 101, 100)).toBeNull();
  });

  it("keeps a minimum thumb and parks it at the end when fully scrolled", () => {
    expect(thumbSize(100, 400, 100)).toBe(28);
    const end = thumbMetrics(300, 100, 400, 100);
    expect(end).toEqual({ offset: 72, size: 28 });
    expect(thumbMetrics(0, 100, 400, 100)).toEqual({ offset: 0, size: 28 });
  });

  it("uses the viewport ratio when that thumb is already large enough", () => {
    expect(thumbSize(80, 100, 200)).toBe(160);
    expect(thumbMetrics(20, 80, 100, 200)).toEqual({ offset: 40, size: 160 });
  });
});

describe("scrollForThumbOffset", () => {
  it("maps a thumb drag back onto the same scroll position", () => {
    expect(scrollForThumbOffset(0, 100, 400, 100)).toBe(0);
    expect(scrollForThumbOffset(36, 100, 400, 100)).toBe(150);
    expect(scrollForThumbOffset(72, 100, 400, 100)).toBe(300);
    expect(scrollForThumbOffset(400, 100, 400, 100)).toBe(300);
    expect(scrollForThumbOffset(-10, 100, 400, 100)).toBe(0);
  });
});

describe("intersectBox", () => {
  it("returns the overlap and nothing when the boxes miss", () => {
    expect(
      intersectBox(
        { top: 0, left: 0, right: 100, bottom: 80 },
        { top: 20, left: 40, right: 90, bottom: 70 },
      ),
    ).toEqual({ top: 20, left: 40, right: 90, bottom: 70 });
    expect(
      intersectBox(
        { top: 0, left: 0, right: 10, bottom: 10 },
        { top: 20, left: 20, right: 30, bottom: 30 },
      ),
    ).toBeNull();
  });
});
