import { describe, expect, it } from "vitest";
import {
  SVG_OVERLAY_MAX_PX,
  svgBasemapZoomLimit,
  svgOverlayMaxZoom,
  svgOverlayScale,
} from "./tarkovMapSvgOverlay";

describe("svg overlay zoom cap", () => {
  it("keeps the long side at the cap", () => {
    const zoom = svgOverlayMaxZoom(314, 229);
    expect(314 * 2 ** zoom).toBeCloseTo(SVG_OVERLAY_MAX_PX);
    expect(svgOverlayScale(10_000, 6_000)).toBeCloseTo(10_000 / SVG_OVERLAY_MAX_PX);
    expect(10_000 / svgOverlayScale(10_000, 6_000)).toBeCloseTo(SVG_OVERLAY_MAX_PX);
  });

  it("does not scale a map that already fits", () => {
    expect(svgOverlayScale(1200, 800)).toBe(1);
    expect(svgOverlayScale(SVG_OVERLAY_MAX_PX, 100)).toBe(1);
  });

  it("uses the tile max zoom when the svg would still fit there", () => {
    expect(svgBasemapZoomLimit(100, 80, 5, 1)).toBe(5);
  });

  it("stops svg zoom before the tile max when the map would get huge", () => {
    const limit = svgBasemapZoomLimit(314, 229, 7, 1);
    expect(limit).toBeLessThan(7);
    expect(limit).toBeGreaterThan(1);
    expect(314 * 2 ** limit).toBeCloseTo(SVG_OVERLAY_MAX_PX);
  });

  it("never goes below the map minimum zoom", () => {
    expect(svgBasemapZoomLimit(20_000, 10_000, 7, 2)).toBe(2);
  });
});
