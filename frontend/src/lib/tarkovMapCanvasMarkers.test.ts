import { describe, expect, it } from "vitest";
import {
  CANVAS_MARKER_EVENT,
  canvasIconScreenRect,
  canvasIconViewSize,
  hitTestCanvasIcons,
  ICON_CANVAS_PADDING,
  isCanvasMarkerEvent,
  layerPointToCanvasPoint,
  markCanvasMarkerEvent,
  pointHitsCanvasIcon,
  rectsOverlap,
  sortCanvasMarkersByZ,
  uniqueCanvasIconUrls,
  type TarkovCanvasIconHit,
  type TarkovCanvasMarker,
} from "./tarkovMapCanvasMarkers";

function hit(
  id: string,
  rect: { left: number; top: number; right: number; bottom: number },
  zIndex = 0,
): TarkovCanvasIconHit {
  const marker: TarkovCanvasMarker = {
    id,
    x: 0,
    z: 0,
    iconUrl: "/icon.png",
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    tooltipHtml: id,
    zIndex,
  };
  return { id, zIndex, marker, ...rect };
}

describe("tarkov map canvas markers", () => {
  it("pads the viewport so a drag can reuse the last paint", () => {
    const view = canvasIconViewSize({ x: 800, y: 600 }, ICON_CANVAS_PADDING);
    expect(view.padX).toBe(360);
    expect(view.padY).toBe(270);
    expect(view.width).toBe(1520);
    expect(view.height).toBe(1140);
  });

  it("projects layer points into canvas space and icon boxes", () => {
    expect(layerPointToCanvasPoint({ x: 140, y: 80 }, { x: 40, y: 20 })).toEqual({
      x: 100,
      y: 60,
    });
    expect(canvasIconScreenRect({ x: 100, y: 50 }, [24, 24], [12, 12])).toEqual({
      left: 88,
      top: 38,
      right: 112,
      bottom: 62,
    });
    expect(canvasIconScreenRect({ x: 100, y: 50 }, [24, 24], [12, 24])).toEqual({
      left: 88,
      top: 26,
      right: 112,
      bottom: 50,
    });
  });

  it("picks the topmost icon under a point", () => {
    const rect = { left: 10, top: 10, right: 34, bottom: 34 };
    expect(pointHitsCanvasIcon({ x: 10, y: 10 }, rect)).toBe(true);
    expect(pointHitsCanvasIcon({ x: 34, y: 20 }, rect)).toBe(false);
    expect(
      hitTestCanvasIcons(
        [hit("loot", rect, 10), hit("lock", rect, 50), hit("spawn", rect, 40)],
        { x: 20, y: 20 },
      )?.id,
    ).toBe("lock");
    expect(
      hitTestCanvasIcons([hit("loot", rect, 10)], { x: 0, y: 0 }),
    ).toBeNull();
  });

  it("sorts paint order and dedupes icon urls", () => {
    expect(
      sortCanvasMarkersByZ([
        { id: "a", zIndex: 20 },
        { id: "b" },
        { id: "c", zIndex: 20 },
        { id: "d", zIndex: 5 },
      ]).map((row) => row.id),
    ).toEqual(["b", "d", "a", "c"]);
    expect(
      uniqueCanvasIconUrls([
        { iconUrl: "/lock.png" },
        { iconUrl: " /lock.png " },
        { iconUrl: "/jacket.png" },
        { iconUrl: "" },
      ]),
    ).toEqual(["/lock.png", "/jacket.png"]);
  });

  it("marks a DOM event so pin/line clicks can ignore icon hits", () => {
    const event = new Event("click");
    expect(isCanvasMarkerEvent(event)).toBe(false);
    expect(isCanvasMarkerEvent(undefined)).toBe(false);
    markCanvasMarkerEvent(event);
    expect(isCanvasMarkerEvent(event)).toBe(true);
    expect((event as unknown as Record<string, boolean>)[CANVAS_MARKER_EVENT]).toBe(
      true,
    );
  });

  it("rejects icons fully outside the padded view", () => {
    const view = { left: 0, top: 0, right: 100, bottom: 80 };
    expect(rectsOverlap({ left: 90, top: 70, right: 110, bottom: 90 }, view)).toBe(
      true,
    );
    expect(rectsOverlap({ left: 100, top: 0, right: 120, bottom: 20 }, view)).toBe(
      false,
    );
  });
});
