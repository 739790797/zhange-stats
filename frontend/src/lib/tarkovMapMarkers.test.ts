import { describe, expect, it } from "vitest";
import {
  allPresentKindsOn,
  hazardKindsPresent,
  isHazardKindOn,
  isLootContainerKindOn,
  lootContainerKindLabel,
  lootContainerKindsPresent,
  tarkovBtrIconUrl,
  tarkovBtrStopLabel,
  tarkovContainerIconUrl,
  tarkovHazardIconUrl,
  tarkovHazardKindLabel,
  tarkovLockHref,
  tarkovLockIconUrl,
  tarkovLockLabel,
  tarkovLockThumbUrl,
  tarkovStationaryLabel,
  tarkovMarkerHeightSpan,
  tarkovMarkerVisibleOnFloor,
  withKindsForPresent,
} from "./tarkovMapMarkers";

describe("tarkov map marker helpers", () => {
  it("defaults hazards on and loot containers off", () => {
    expect(isHazardKindOn({}, "minefield")).toBe(true);
    expect(isLootContainerKindOn({}, "jacket")).toBe(false);
    expect(allPresentKindsOn({}, ["minefield", "sniper"], true)).toBe(true);
    expect(allPresentKindsOn({}, ["jacket"], false)).toBe(false);
    expect(withKindsForPresent({}, ["jacket", "safe"], true)).toEqual({
      jacket: true,
      safe: true,
    });
  });

  it("lists hazard and container kinds with known order", () => {
    expect(
      hazardKindsPresent([
        { hazard_type: "sniper" },
        { hazard_type: "mortar" },
        { hazard_type: "minefield" },
        { hazard_type: "sniper" },
      ]),
    ).toEqual(["minefield", "sniper", "mortar"]);
    expect(
      lootContainerKindsPresent([
        { normalized_name: "jacket", name: "夹克" },
        { normalized_name: "safe", name: "保险箱" },
        { normalized_name: "jacket" },
      ]),
    ).toEqual(["jacket", "safe"]);
    expect(lootContainerKindLabel("jacket", [{ normalized_name: "jacket", name: "夹克" }])).toBe(
      "夹克",
    );
    expect(
      lootContainerKindsPresent([
        { normalized_name: "578f87a3245977356274f2cb", name: "578f87a3245977356274f2cb" },
        { normalized_name: "jacket", name: "夹克" },
      ]),
    ).toEqual(["jacket", "other"]);
    expect(
      lootContainerKindLabel("other", [
        { normalized_name: "578f87a3245977356274f2cb", name: "578f87a3245977356274f2cb" },
      ]),
    ).toBe("其他容器");
  });

  it("uses tarkov.dev icon files and key encyclopedia href", () => {
    expect(tarkovLockIconUrl()).toBe("/tarkov/map-icons/lock.png");
    expect(tarkovHazardIconUrl("mortar")).toBe("/tarkov/map-icons/hazard_mortar.png");
    expect(tarkovHazardIconUrl("minefield")).toBe("/tarkov/map-icons/hazard.png");
    expect(tarkovBtrIconUrl()).toBe("/tarkov/map-icons/btr_stop.png");
    expect(tarkovContainerIconUrl("jacket")).toBe("/tarkov/map-icons/container_jacket.png");
    expect(tarkovContainerIconUrl("medical-supply-crate")).toBe(
      "/tarkov/map-icons/container_crate.png",
    );
    expect(tarkovContainerIconUrl("unknown-box")).toBe(
      "/tarkov/map-icons/container_crate.png",
    );
    expect(tarkovLockHref("dorm-114")).toBe("/guides/tarkov/items/keys/dorm-114");
    expect(tarkovLockLabel({ key_name: "宿舍 114" })).toBe("宿舍 114");
    expect(
      tarkovLockLabel({ key_name: "5448ba0b4bdc2d02308b456c Name" }),
    ).toBe("门锁");
    expect(
      tarkovLockThumbUrl({
        key_id: "5448ba0b4bdc2d02308b456c",
        key_icon: "",
      }),
    ).toBe("https://assets.tarkov.dev/5448ba0b4bdc2d02308b456c-icon.webp");
    expect(tarkovStationaryLabel({ name: "AGS 30x29毫米自动榴弹发射器" })).toBe(
      "AGS 30x29毫米自动榴弹发射器",
    );
    expect(tarkovStationaryLabel({ name: "5d52cc5ba4b9367408500062" })).toBe("固定武器");
    expect(
      tarkovBtrStopLabel({
        name: "Trading/Dialog/PlayerTaxi/TarkovStreets/p3/Name",
      }),
    ).toBe("BTR");
    expect(tarkovBtrStopLabel({ name: "市中心" })).toBe("市中心");
    expect(tarkovHazardKindLabel("minefield")).toBe("雷区");
    expect(tarkovHazardKindLabel("custom", "自定义")).toBe("自定义");
  });

  it("keeps markers without height on every floor", () => {
    const bands = [
      { name: "", min: -2, max: 4 },
      { name: "2nd", min: 10, max: 16 },
    ];
    expect(tarkovMarkerHeightSpan({ x: 1, z: 2 })).toBeNull();
    expect(tarkovMarkerVisibleOnFloor({ x: 1, z: 2 }, "", bands)).toBe(true);
    expect(tarkovMarkerVisibleOnFloor({ x: 1, z: 2 }, "2nd", bands)).toBe(true);
    expect(
      tarkovMarkerVisibleOnFloor({ x: 1, z: 2, top: 14, bottom: 12 }, "", bands),
    ).toBe(false);
    expect(
      tarkovMarkerVisibleOnFloor({ x: 1, z: 2, top: 14, bottom: 12 }, "2nd", bands),
    ).toBe(true);
  });
});
