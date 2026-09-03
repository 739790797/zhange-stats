import { describe, expect, it } from "vitest";
import {
  filterGroupAllOn,
  filterGroupAnyOn,
  filterGroupPartial,
  TARKOV_MAP_FILTER_GROUP_LABELS,
  TARKOV_MAP_FILTER_GROUP_ORDER,
  TARKOV_MAP_FILTER_ITEM_LABELS,
  withFilterGroupOn,
} from "./tarkovMapFilterGroups";

describe("tarkov map filter groups", () => {
  it("uses tarkov.dev zh group titles", () => {
    expect(TARKOV_MAP_FILTER_GROUP_LABELS.levels).toBe("层级");
    expect(TARKOV_MAP_FILTER_GROUP_LABELS.extracts).toBe("撤离点");
    expect(TARKOV_MAP_FILTER_GROUP_LABELS.spawns).toBe("出生点");
    expect(TARKOV_MAP_FILTER_GROUP_LABELS.usable).toBe("可使用");
    expect(TARKOV_MAP_FILTER_GROUP_LABELS.lootable).toBe("可搜刮物品");
    expect(TARKOV_MAP_FILTER_GROUP_LABELS.tasks).toBe("任务");
    expect(TARKOV_MAP_FILTER_GROUP_LABELS.hazards).toBe("危险区");
    expect(TARKOV_MAP_FILTER_GROUP_LABELS.landmarks).toBe("地标");
    expect(TARKOV_MAP_FILTER_GROUP_LABELS.lootLoose).toBe("散落物");
    expect(TARKOV_MAP_FILTER_ITEM_LABELS.locks).toBe("锁");
    expect(TARKOV_MAP_FILTER_ITEM_LABELS.stationary).toBe("固定机枪");
    expect(TARKOV_MAP_FILTER_ITEM_LABELS.switches).toBe("开关");
    expect(TARKOV_MAP_FILTER_ITEM_LABELS.btrStop).toBe("BTR 停车点");
    expect(TARKOV_MAP_FILTER_ITEM_LABELS.placeNames).toBe("地名");
    expect(TARKOV_MAP_FILTER_ITEM_LABELS.lootLoose).toBe("散落物");
  });

  it("keeps tarkov.dev sidebar group order", () => {
    expect(TARKOV_MAP_FILTER_GROUP_ORDER).toEqual([
      "style",
      "levels",
      "extracts",
      "spawns",
      "usable",
      "lootable",
      "tasks",
      "hazards",
      "landmarks",
      "lootLoose",
    ]);
  });

  it("toggles a usable/landmarks parent without dropping missing children", () => {
    const items = [
      { key: "locks", on: true },
      { key: "switches", on: false },
    ];
    expect(filterGroupAllOn(items)).toBe(false);
    expect(filterGroupAnyOn(items)).toBe(true);
    expect(filterGroupPartial(items)).toBe(true);
    expect(filterGroupAllOn([])).toBe(false);
    expect(
      withFilterGroupOn(
        { showLocks: true, showSwitches: false, showStationary: true },
        ["showLocks", "showSwitches"],
        true,
      ),
    ).toEqual({
      showLocks: true,
      showSwitches: true,
      showStationary: true,
    });
  });
});
