import { describe, expect, it } from "vitest";
import {
  ROR2_HOME_TILES,
  ROR2_SIDE_LINKS,
  filterRor2Items,
  groupRor2ItemsByRarity,
  ror2ActiveRarity,
  ror2ItemSections,
  ror2ItemsHref,
  ror2PageTitle,
} from "./ror2Home";
import { ror2ItemStackLabel, ror2RarityAccent } from "./ror2Catalog";

const ROWS = [
  { name: "Syringe", rarity: "Common", description: "speed <style=cIsDamage>15%</style>" },
  { name: "Behemoth", rarity: "Legendary", description: "boom" },
  { name: "Radar", rarity: "Equipment", description: "scan" },
  { name: "Mystery", rarity: "Foo", description: "x" },
  { name: "Blank", rarity: "", description: "y" },
];

describe("ror2 home directory", () => {
  it("lays content tiles out as two rows of five, with only items linked", () => {
    expect(ROR2_HOME_TILES.map((tile) => tile.label)).toEqual([
      "幸存者",
      "物品",
      "怪物",
      "环境",
      "成就",
      "可交互物",
      "无人机",
      "神龛",
      "神器",
      "纽特祭坛",
    ]);
    expect(ROR2_HOME_TILES.filter((tile) => tile.href).map((tile) => tile.id)).toEqual(["items"]);
    expect(ROR2_HOME_TILES[1]?.href).toBe("/guides/ror2/items");
  });

  it("keeps the side rail as labels without routes", () => {
    expect(ROR2_SIDE_LINKS.map((item) => item.label)).toEqual([
      "游戏机制",
      "物品堆叠",
      "状态效果",
      "伤害计算",
      "游戏模式",
      "日志总览",
      "模组说明",
    ]);
    expect(ROR2_SIDE_LINKS).toHaveLength(7);
  });

  it("names the items page in the document title", () => {
    expect(ror2PageTitle("/guides/ror2")).toBe("雨中冒险2");
    expect(ror2PageTitle("/guides/ror2/")).toBe("雨中冒险2");
    expect(ror2PageTitle("/guides/ror2/items")).toBe("雨中冒险2 · 物品");
  });
});

describe("ror2 item list", () => {
  it("groups wiki rarities into passive, active, and the rest", () => {
    const sections = ror2ItemSections(ROWS);
    expect(sections.map((section) => section.id)).toEqual(["passive", "active", "other"]);
    expect(sections[0]?.rarities.map((chip) => `${chip.id}:${chip.count}`)).toEqual([
      "Common:1",
      "Legendary:1",
      "Untiered:1",
    ]);
    expect(sections[1]?.rarities.map((chip) => chip.id)).toEqual(["Equipment"]);
    expect(sections[2]?.rarities.map((chip) => chip.id)).toEqual(["Foo"]);
  });

  it("drops an unknown category back to all", () => {
    expect(ror2ActiveRarity(null, ROWS)).toBe("all");
    expect(ror2ActiveRarity("Common", ROWS)).toBe("Common");
    expect(ror2ActiveRarity("Nope", ROWS)).toBe("all");
    expect(ror2ActiveRarity("Untiered", ROWS)).toBe("Untiered");
  });

  it("filters by rarity, then by visible text", () => {
    expect(filterRor2Items(ROWS, "", "Equipment").map((row) => row.name)).toEqual(["Radar"]);
    expect(filterRor2Items(ROWS, "15%", "all").map((row) => row.name)).toEqual(["Syringe"]);
    expect(filterRor2Items(ROWS, "cIsDamage", "Common")).toEqual([]);
    expect(groupRor2ItemsByRarity(ROWS).map((group) => group.rarity)).toEqual([
      "Common",
      "Legendary",
      "Untiered",
      "Equipment",
      "Foo",
    ]);
  });

  it("builds the items url from category and query", () => {
    expect(ror2ItemsHref()).toBe("/guides/ror2/items");
    expect(ror2ItemsHref("all", "  ")).toBe("/guides/ror2/items");
    expect(ror2ItemsHref("Lunar Equipment", "A B")).toBe(
      "/guides/ror2/items?cat=Lunar+Equipment&q=A+B",
    );
  });

  it("keeps a rarity accent and a single stack label", () => {
    expect(ror2RarityAccent("Lunar")).toBe("#307fff");
    expect(ror2RarityAccent("")).toBe("#9aa4b2");
    expect(ror2ItemStackLabel([{ stack: "Linear" }, { stack: "Linear" }, { stack: "None" }])).toBe(
      "Linear / None",
    );
  });
});
