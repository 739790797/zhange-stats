import { describe, expect, it } from "vitest";
import { findInteractiveMap } from "./tarkovMapImages";
import {
  fallbackPlacesForImport,
  hasCustomMapPlaceLabels,
  normalizePlaceName,
  placeBoxCenter,
  placeLabelIconSize,
  placeLabelMovePatch,
  placeLabelPosition,
  placeNameLines,
  placeVisibleOnFloor,
  resolveMapPlaceLabels,
  translatePlaceByCenter,
} from "./tarkovMapPlaceLabels";

function overlayTexts(slug: string): string[] {
  const layer = findInteractiveMap(slug);
  expect(layer).toBeTruthy();
  return resolveMapPlaceLabels(layer!).map((row) => row.text);
}

describe("resolveMapPlaceLabels", () => {
  it("replaces shoreline tarkov.dev labels with the Chinese community overlay", () => {
    const texts = overlayTexts("shoreline");
    expect(hasCustomMapPlaceLabels("shoreline")).toBe(true);
    expect(texts).toEqual(
      expect.arrayContaining([
        "疗养院",
        "行政楼",
        "西楼",
        "东楼",
        "停车场",
        "真别墅",
        "假别墅",
        "蓝铁皮",
        "红白电塔",
        "雷达站",
        "村落",
      ]),
    );
    for (const banned of [
      "Resort",
      "Admin",
      "Cottages",
      "Construction",
      "Radio Tower",
      "北楼",
      "豪宅",
      "工地",
      "无线电塔",
    ]) {
      expect(texts).not.toContain(banned);
    }
    expect(texts.some((text) => /[A-Za-z]/.test(text))).toBe(false);
  });

  it("splits the two cottages west/east and keeps 蓝铁皮 toward the resort", () => {
    const layer = findInteractiveMap("shoreline");
    const byText = new Map(
      resolveMapPlaceLabels(layer!).map((row) => [row.text, row.position]),
    );
    const fake = byText.get("假别墅");
    const real = byText.get("真别墅");
    const blue = byText.get("蓝铁皮");
    expect(fake && real && blue).toBeTruthy();
    // 海岸线 +X 朝西：假别墅在西，真别墅在东，蓝铁皮更靠疗养院。
    expect(fake![0]).toBeGreaterThan(real![0]);
    expect(real![0]).toBeGreaterThan(blue![0]);
  });

  it("still translates other maps from tarkov.dev overlay text", () => {
    expect(hasCustomMapPlaceLabels("customs")).toBe(false);
    const texts = overlayTexts("customs");
    expect(texts).toContain("宿舍");
    expect(texts).toContain("大红房");
    expect(texts).not.toContain("Dorms");
  });

  it("prefers database places and drops upstream labels", () => {
    const layer = findInteractiveMap("customs");
    expect(layer).toBeTruthy();
    const places = resolveMapPlaceLabels(layer!, [
      {
        id: 3,
        kind: "box",
        name: "大红房西侧",
        x: 0,
        z: 0,
        x2: 10,
        z2: 4,
        label_x: 1,
        label_z: 3,
        size: 90,
      },
    ]);
    expect(hasCustomMapPlaceLabels("customs", [{ id: 3 }])).toBe(true);
    expect(places).toEqual([
      {
        id: 3,
        kind: "box",
        text: "大红房西侧",
        position: [1, 3],
        size: 90,
        floor: "",
        x: 0,
        z: 0,
        x2: 10,
        z2: 4,
        label_x: 1,
        label_z: 3,
      },
    ]);
    expect(places.some((row) => row.text === "宿舍")).toBe(false);
  });

  it("empty database list still uses the handwritten shoreline overlay", () => {
    const layer = findInteractiveMap("shoreline");
    const texts = resolveMapPlaceLabels(layer!, []).map((row) => row.text);
    expect(texts).toContain("疗养院");
  });

  it("computes box center and translates a box by new center", () => {
    expect(placeBoxCenter(-2, 0, 4, 6)).toEqual([1, 3]);
    const moved = translatePlaceByCenter(
      { kind: "box", name: "区", x: 0, z: 0, x2: 4, z2: 2 },
      { x: 10, z: 5 },
    );
    expect(moved).toEqual({ x: 8, z: 4, x2: 12, z2: 6 });
  });

  it("uses an explicit label offset and only patches text when dragging a box", () => {
    const boxed = {
      kind: "box" as const,
      name: "区",
      x: 0,
      z: 0,
      x2: 4,
      z2: 2,
      label_x: 9,
      label_z: -1,
    };
    expect(placeLabelPosition(boxed)).toEqual([9, -1]);
    expect(placeLabelPosition({ kind: "box", name: "区", x: 0, z: 0, x2: 4, z2: 2 })).toEqual([
      2, 1,
    ]);
    expect(placeLabelMovePatch(boxed, { x: 3, z: 4 })).toEqual({
      label_x: 3,
      label_z: 4,
    });
    expect(
      placeLabelMovePatch({ kind: "point", name: "点", x: 1, z: 2 }, { x: 8, z: 9 }),
    ).toEqual({ x: 8, z: 9 });
  });

  it("hides floor-scoped places on other levels", () => {
    expect(placeVisibleOnFloor("", "2nd Floor")).toBe(true);
    expect(placeVisibleOnFloor("2nd Floor", "2nd Floor")).toBe(true);
    expect(placeVisibleOnFloor("2nd Floor", "")).toBe(false);
  });

  it("splits and centers multi-line names", () => {
    expect(placeNameLines("  真别墅  \n\n  东侧  ")).toEqual(["真别墅", "东侧"]);
    expect(normalizePlaceName("  真别墅  \n\n  东侧  ")).toBe("真别墅\n东侧");
    const two = placeLabelIconSize("真别墅\n东侧");
    const one = placeLabelIconSize("真别墅");
    expect(two.h).toBeGreaterThan(one.h);
    expect(two.w).toBe(one.w);
  });

  it("exports fallback overlay as import rows", () => {
    const layer = findInteractiveMap("shoreline");
    const items = fallbackPlacesForImport(layer!);
    expect(items.some((row) => row.name === "真别墅")).toBe(true);
    expect(items.every((row) => row.kind === "point")).toBe(true);
  });
});
