import { describe, expect, it } from "vitest";
import { findInteractiveMap } from "./tarkovMapImages";
import { mapLayerFloorBands } from "./tarkovRaidPrep";
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
  tarkovLockKeyBadge,
  tarkovLockKeyStatusLines,
  tarkovLockLabel,
  tarkovLockThumbUrl,
  tarkovLockTooltipHtml,
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

  it("uses x/z so customs dorm locks sit on 2nd, not the whole map", () => {
    const bands = mapLayerFloorBands(findInteractiveMap("customs"));
    const dorm = { x: 200, z: 160, y: 4 };
    const yard = { x: 400, z: 0, y: 4 };
    expect(tarkovMarkerVisibleOnFloor(dorm, "2nd Floor", bands)).toBe(true);
    expect(tarkovMarkerVisibleOnFloor(dorm, "", bands)).toBe(false);
    expect(tarkovMarkerVisibleOnFloor(yard, "2nd Floor", bands)).toBe(false);
    expect(tarkovMarkerVisibleOnFloor(yard, "", bands)).toBe(true);
  });

  it("keeps shoreline resort basement off the outdoor ground layer", () => {
    const bands = mapLayerFloorBands(findInteractiveMap("shoreline"));
    const westWing = { x: -180, z: -80, y: -6 };
    const road = { x: -355, z: 188, y: -6 };
    expect(tarkovMarkerVisibleOnFloor(westWing, "Underground", bands)).toBe(
      true,
    );
    expect(tarkovMarkerVisibleOnFloor(westWing, "", bands)).toBe(false);
    expect(tarkovMarkerVisibleOnFloor(road, "Underground", bands)).toBe(false);
    expect(tarkovMarkerVisibleOnFloor(road, "", bands)).toBe(true);
  });
});

describe("tarkov lock key badge", () => {
  const me = { item_id: "k1", user_id: 1, display_name: "甲" };
  const mate = { item_id: "k1", user_id: 2, display_name: "乙" };

  it("stays unset without a key or in encyclopedia mode", () => {
    expect(tarkovLockKeyBadge("", { mode: "solo", viewerId: 1 })).toBeUndefined();
    expect(
      tarkovLockKeyBadge("k1", { mode: "neutral", viewerId: 1, owns: [me] }),
    ).toBeUndefined();
    expect(tarkovLockKeyBadge("k1")).toBeUndefined();
  });

  it("marks solo own vs missing and ignores teammates", () => {
    expect(
      tarkovLockKeyBadge("k1", { mode: "solo", viewerId: 1, owns: [me] }),
    ).toBe("own");
    expect(
      tarkovLockKeyBadge("k1", { mode: "solo", viewerId: 1, brings: [me] }),
    ).toBe("own");
    expect(
      tarkovLockKeyBadge("k1", { mode: "solo", viewerId: 1, owns: [mate] }),
    ).toBe("missing");
    expect(tarkovLockKeyBadge("k1", { mode: "solo", viewerId: 1 })).toBe(
      "missing",
    );
  });

  it("prefers self in a party, then teammate own or bring", () => {
    expect(
      tarkovLockKeyBadge("k1", {
        mode: "party",
        viewerId: 1,
        owns: [me, mate],
        brings: [mate],
      }),
    ).toBe("own");
    expect(
      tarkovLockKeyBadge("k1", {
        mode: "party",
        viewerId: 1,
        owns: [mate],
      }),
    ).toBe("teammate");
    expect(
      tarkovLockKeyBadge("k1", {
        mode: "party",
        viewerId: 1,
        brings: [mate],
      }),
    ).toBe("teammate");
    expect(tarkovLockKeyBadge("k1", { mode: "party", viewerId: 1 })).toBe(
      "missing",
    );
  });
});

describe("tarkov lock tooltip html", () => {
  const classes = {
    tip: "lockTip",
    icon: "lockTipIcon",
    text: "lockTipText",
    status: "lockTipStatus",
  };

  it("keeps encyclopedia bubbles to icon, name and power, without lock type", () => {
    const html = tarkovLockTooltipHtml(
      {
        key_id: "k1",
        key_name: "宿舍 114",
        key_icon: "https://assets.tarkov.dev/k1-icon.webp",
        lock_type: "door",
        needs_power: true,
      },
      classes,
    );
    expect(html).toContain("宿舍 114");
    expect(html).toContain("lockTipIcon");
    expect(html).toContain("https://assets.tarkov.dev/k1-icon.webp");
    expect(html).toContain("需供电");
    expect(html).not.toContain(">门<");
    expect(html).not.toContain("拥有");
    expect(html).not.toContain("带了");
    expect(tarkovLockKeyStatusLines("k1")).toEqual([]);
  });

  it("adds who owns and who brought for raid maps", () => {
    expect(
      tarkovLockKeyStatusLines("k1", {
        mode: "party",
        viewerId: 1,
        owns: [{ item_id: "k1", user_id: 1, display_name: "甲" }],
        brings: [{ item_id: "k1", user_id: 2, display_name: "乙" }],
      }),
    ).toEqual(["甲拥有这把钥匙。", "乙带了这把钥匙。"]);
    expect(
      tarkovLockKeyStatusLines("k1", { mode: "solo", viewerId: 1 }),
    ).toEqual(["没人拥有这把钥匙", "还没人声明带这把钥匙"]);
    const html = tarkovLockTooltipHtml(
      { key_id: "k1", key_name: "工厂钥匙", lock_type: "door" },
      classes,
      { mode: "solo", viewerId: 1 },
    );
    expect(html).toContain("没人拥有这把钥匙");
    expect(html).toContain("还没人声明带这把钥匙");
    expect(html).not.toContain("没人拥有这把钥匙 还没人声明带这把钥匙");
    expect(html).toContain("lockTipStatus");
    expect(html).not.toContain(">门<");
  });
});
