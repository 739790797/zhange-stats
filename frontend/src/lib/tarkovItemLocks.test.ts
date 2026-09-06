import { describe, expect, it } from "vitest";
import type { TarkovItemDetail } from "@/api/guidesApi";
import { findInteractiveMap } from "./tarkovMapImages";
import { mapLayerFloorBands } from "./tarkovRaidPrep";
import {
  itemKeyLockMaps,
  itemKeyLocksAsMapLocks,
  lockFocusPoint,
  lockOverlayFloor,
  lockPointLabel,
  lockTypeSummary,
  type TarkovItemKeyLock,
  type TarkovItemKeyLockMap,
} from "./tarkovItemLocks";

const factoryDoor: TarkovItemKeyLock = {
  id: "gate-m",
  lock_type: "door",
  needs_power: false,
  x: 10,
  y: 1,
  z: 20,
};

const customsDoor: TarkovItemKeyLock = {
  id: "customs-door",
  lock_type: "door",
  needs_power: false,
  x: 1,
  z: 2,
};

const truck: TarkovItemKeyLock = {
  id: "truck",
  lock_type: "trunk",
  needs_power: true,
  x: 3,
  z: 4,
};

const factoryMap: TarkovItemKeyLockMap = {
  slug: "factory",
  name: "工厂",
  english: "Factory",
  parent_slug: "",
  locks: [factoryDoor],
};

const customsMap: TarkovItemKeyLockMap = {
  slug: "customs",
  name: "海关",
  english: "Customs",
  parent_slug: "",
  locks: [customsDoor, truck],
};

function detail(locks: TarkovItemKeyLockMap[]): TarkovItemDetail {
  return {
    id: "factory-exit",
    name: "工厂紧急出口钥匙",
    short_name: "",
    description: "",
    locks,
  };
}

describe("itemKeyLockMaps", () => {
  it("keeps maps that have a plottable lock and drops the rest", () => {
    expect(
      itemKeyLockMaps(
        detail([
          factoryMap,
          {
            slug: "lighthouse",
            name: "灯塔",
            english: "Lighthouse",
            parent_slug: "",
            locks: [{ id: "fake", lock_type: "trunk", needs_power: false }],
          },
          { slug: "", name: "空", english: "", parent_slug: "", locks: [factoryDoor] },
        ]),
      ),
    ).toEqual([factoryMap]);
    expect(itemKeyLockMaps(null)).toEqual([]);
  });
});

describe("lockTypeSummary", () => {
  it("counts lock types in Chinese", () => {
    expect(lockTypeSummary([factoryDoor, customsDoor, truck])).toBe(
      "2 处门 · 1 处后备箱",
    );
  });
});

describe("lockPointLabel", () => {
  it("numbers repeated types and marks power", () => {
    const locks = [customsDoor, truck];
    expect(lockPointLabel(customsDoor, 0, locks)).toBe("门");
    expect(lockPointLabel(truck, 1, locks)).toBe("后备箱 · 需供电");
    expect(lockPointLabel(factoryDoor, 0, [factoryDoor, customsDoor])).toBe("门 1");
    expect(lockPointLabel(factoryDoor, 0, [factoryDoor], "2 层")).toBe("2 层 · 门");
  });
});

describe("lockOverlayFloor", () => {
  it("puts a reserve barracks lock on 2nd floor, not the ground overview", () => {
    const bands = mapLayerFloorBands(findInteractiveMap("reserve"));
    const pawn = { id: "rb-ak", lock_type: "door", needs_power: false, x: -120, z: 60, y: -2 };
    expect(lockOverlayFloor(pawn, bands)).toBe("2nd Floor");
    expect(lockFocusPoint(pawn)).toEqual({ x: -120, z: 60, y: -2 });
  });

  it("uses the height span midpoint when focusing", () => {
    expect(
      lockFocusPoint({
        id: "span",
        lock_type: "door",
        needs_power: false,
        x: 1,
        z: 2,
        top: 14,
        bottom: 10,
      }),
    ).toEqual({ x: 1, z: 2, y: 12 });
    expect(
      lockFocusPoint({ id: "none", lock_type: "door", needs_power: false }),
    ).toBeNull();
  });
});

describe("itemKeyLocksAsMapLocks", () => {
  it("fills map-lock fields for the viewer", () => {
    expect(itemKeyLocksAsMapLocks(customsMap, "factory-exit", "工厂紧急出口钥匙")).toEqual([
      {
        id: "customs-door",
        lock_type: "door",
        needs_power: false,
        key_id: "factory-exit",
        key_name: "工厂紧急出口钥匙",
        key_short_name: "",
        key_icon: "",
        x: 1,
        y: undefined,
        z: 2,
        top: undefined,
        bottom: undefined,
      },
      {
        id: "truck",
        lock_type: "trunk",
        needs_power: true,
        key_id: "factory-exit",
        key_name: "工厂紧急出口钥匙",
        key_short_name: "",
        key_icon: "",
        x: 3,
        y: undefined,
        z: 4,
        top: undefined,
        bottom: undefined,
      },
    ]);
  });
});
