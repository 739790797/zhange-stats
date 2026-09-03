import { describe, expect, it } from "vitest";
import rawMaps from "@/data/tarkov-dev-maps.json";
import { findInteractiveMap, type TarkovDevMapGroup } from "./tarkovMapImages";
import { mapLayerFloorBands } from "./tarkovRaidPrep";
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
  type ResolvedMapPlace,
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
    const onAny = { floor: "", top: 0, bottom: 0, x: 0, z: 0, position: [0, 0, 0] };
    const onSecond = { ...onAny, floor: "2nd Floor" };
    expect(placeVisibleOnFloor(onAny, "2nd Floor")).toBe(true);
    expect(placeVisibleOnFloor(onSecond, "2nd Floor")).toBe(true);
    expect(placeVisibleOnFloor(onSecond, "")).toBe(false);
  });

  it("filters interchange store labels by height so mall floors do not stack", () => {
    const layer = findInteractiveMap("interchange");
    expect(layer).toBeTruthy();
    const bands = mapLayerFloorBands(layer);
    const byText = new Map(
      resolveMapPlaceLabels(layer!).map((row) => [row.text, row]),
    );
    const idea = byText.get("IDEA");
    const goshan = byText.get("好圣");
    const garage = byText.get("车库 A");
    const third = byText.get("父与子");
    expect(idea && goshan && garage && third).toBeTruthy();
    expect(placeVisibleOnFloor(idea!, "", bands)).toBe(false);
    expect(placeVisibleOnFloor(idea!, "2nd Floor", bands)).toBe(true);
    expect(placeVisibleOnFloor(idea!, "3rd Floor", bands)).toBe(false);
    expect(placeVisibleOnFloor(goshan!, "2nd Floor", bands)).toBe(true);
    expect(placeVisibleOnFloor(goshan!, "", bands)).toBe(false);
    expect(placeVisibleOnFloor(garage!, "", bands)).toBe(true);
    expect(placeVisibleOnFloor(garage!, "2nd Floor", bands)).toBe(false);
    expect(placeVisibleOnFloor(third!, "3rd Floor", bands)).toBe(true);
    expect(placeVisibleOnFloor(third!, "2nd Floor", bands)).toBe(false);
    expect(placeVisibleOnFloor(third!, "", bands)).toBe(false);
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

function placeXZ(row: ResolvedMapPlace): { x: number; z: number } {
  return {
    x: row.x ?? row.position[0],
    z: row.z ?? row.position[1],
  };
}

function placeHasHeight(row: ResolvedMapPlace): boolean {
  return Number.isFinite(row.top) || Number.isFinite(row.bottom);
}

function selectableFloors(layer: NonNullable<ReturnType<typeof findInteractiveMap>>): string[] {
  const named = (layer.layers || [])
    .filter((floor) => floor.svgLayer || floor.tilePath)
    .map((floor) => floor.name);
  return ["", ...named];
}

describe("place labels on every interactive map", () => {
  const groups = rawMaps as TarkovDevMapGroup[];

  it("splits same-spot labels that have disjoint height onto different floors", () => {
    const stacks: string[] = [];
    for (const group of groups) {
      const layer = findInteractiveMap(group.normalizedName);
      if (!layer) continue;
      const bands = mapLayerFloorBands(layer);
      const places = resolveMapPlaceLabels(layer);
      const floors = selectableFloors(layer);
      for (const floor of floors) {
        const visible = places.filter((row) =>
          placeVisibleOnFloor(row, floor, bands),
        );
        for (let i = 0; i < visible.length; i += 1) {
          const a = visible[i]!;
          if (!placeHasHeight(a)) continue;
          const aAt = placeXZ(a);
          for (let j = i + 1; j < visible.length; j += 1) {
            const b = visible[j]!;
            if (!placeHasHeight(b)) continue;
            const bAt = placeXZ(b);
            const dx = aAt.x - bAt.x;
            const dz = aAt.z - bAt.z;
            if (dx * dx + dz * dz > 18 * 18) continue;
            const aLo = Math.min(a.bottom ?? a.top ?? 0, a.top ?? a.bottom ?? 0);
            const aHi = Math.max(a.bottom ?? a.top ?? 0, a.top ?? a.bottom ?? 0);
            const bLo = Math.min(b.bottom ?? b.top ?? 0, b.top ?? b.bottom ?? 0);
            const bHi = Math.max(b.bottom ?? b.top ?? 0, b.top ?? b.bottom ?? 0);
            if (aHi < bLo || bHi < aLo) {
              stacks.push(
                `${group.normalizedName} ${floor || "ground"}: ${a.text} × ${b.text}`,
              );
            }
          }
        }
      }
    }
    expect(stacks).toEqual([]);
  });

  it("keeps factory office/tunnel names on the floors their height belongs to", () => {
    const layer = findInteractiveMap("factory");
    expect(layer).toBeTruthy();
    const bands = mapLayerFloorBands(layer);
    const byText = new Map(
      resolveMapPlaceLabels(layer!).map((row) => [row.text, row]),
    );
    const lockers = byText.get("更衣室");
    const mainOffice = byText.get("主办公区");
    const stash = byText.get("地下藏匿点");
    expect(lockers && mainOffice && stash).toBeTruthy();
    expect(placeVisibleOnFloor(lockers!, "", bands)).toBe(false);
    expect(placeVisibleOnFloor(lockers!, "2nd Floor", bands)).toBe(true);
    expect(placeVisibleOnFloor(lockers!, "3rd Floor", bands)).toBe(false);
    expect(placeVisibleOnFloor(mainOffice!, "", bands)).toBe(false);
    expect(placeVisibleOnFloor(mainOffice!, "2nd Floor", bands)).toBe(false);
    expect(placeVisibleOnFloor(mainOffice!, "3rd Floor", bands)).toBe(true);
    expect(placeVisibleOnFloor(stash!, "Tunnels", bands)).toBe(true);
    expect(placeVisibleOnFloor(stash!, "3rd Floor", bands)).toBe(false);
  });

  it("keeps labs level-1 and level-2 names from stacking at the same spot", () => {
    const layer = findInteractiveMap("the-lab");
    expect(layer).toBeTruthy();
    const bands = mapLayerFloorBands(layer);
    const byText = new Map(
      resolveMapPlaceLabels(layer!).map((row) => [row.text, row]),
    );
    const vestibule = byText.get("门厅 1");
    const security = byText.get("安保 1");
    const infirmary1 = byText.get("医务室 1 层");
    const infirmary2 = byText.get("医务室 2 层");
    expect(vestibule && security && infirmary1 && infirmary2).toBeTruthy();
    expect(placeVisibleOnFloor(vestibule!, "", bands)).toBe(true);
    expect(placeVisibleOnFloor(vestibule!, "Second Level", bands)).toBe(false);
    expect(placeVisibleOnFloor(security!, "", bands)).toBe(false);
    expect(placeVisibleOnFloor(security!, "Second Level", bands)).toBe(true);
    expect(placeVisibleOnFloor(infirmary1!, "", bands)).toBe(true);
    expect(placeVisibleOnFloor(infirmary1!, "Second Level", bands)).toBe(false);
    expect(placeVisibleOnFloor(infirmary2!, "", bands)).toBe(false);
    expect(placeVisibleOnFloor(infirmary2!, "Second Level", bands)).toBe(true);
  });

  it("keeps ground zero office/winery names on the floors their height belongs to", () => {
    const layer = findInteractiveMap("ground-zero");
    expect(layer).toBeTruthy();
    const bands = mapLayerFloorBands(layer);
    const byText = new Map(
      resolveMapPlaceLabels(layer!).map((row) => [row.text, row]),
    );
    const office = byText.get("科学办公室");
    const winery = byText.get("ASAP 酒庄");
    expect(office && winery).toBeTruthy();
    expect(placeVisibleOnFloor(office!, "", bands)).toBe(false);
    expect(placeVisibleOnFloor(office!, "2nd Floor", bands)).toBe(true);
    expect(placeVisibleOnFloor(winery!, "", bands)).toBe(true);
    expect(placeVisibleOnFloor(winery!, "2nd Floor", bands)).toBe(false);
    expect(placeVisibleOnFloor(winery!, "3rd Floor", bands)).toBe(false);
  });

  it("keeps height on every map whose upstream labels actually use top/bottom", () => {
    const lost: string[] = [];
    for (const group of groups) {
      const layer = findInteractiveMap(group.normalizedName);
      if (!layer) continue;
      const raw = (layer.labels || []).filter(
        (row) => Number.isFinite(row.top) || Number.isFinite(row.bottom),
      );
      if (!raw.length) continue;
      if (hasCustomMapPlaceLabels(group.normalizedName)) continue;
      const resolved = resolveMapPlaceLabels(layer).filter(placeHasHeight);
      if (!resolved.length) lost.push(group.normalizedName);
    }
    expect(lost).toEqual([]);
  });
});
