import { describe, expect, it } from "vitest";
import {
  ROR2_HOME_TILES,
  ROR2_SIDE_LINKS,
  ROR2_UNRELEASED_GROUPS,
  filterRor2Items,
  filterRor2Survivors,
  groupRor2ItemsByRarity,
  ror2ActiveExpansion,
  ror2ActiveRarity,
  ror2ArtifactIconUrl,
  ror2CatalogItems,
  ror2Crumbs,
  ror2DirectoryGroups,
  ror2ItemSections,
  ror2ItemsHref,
  ror2PageTitle,
  ror2SectionRows,
  ror2SurvivorSections,
  ror2SurvivorStatLine,
  ror2SurvivorsHref,
  ror2UnlockIcon,
  ror2UnreleasedRows,
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
  it("links every content tile", () => {
    expect(ROR2_HOME_TILES.map((tile) => tile.label)).toEqual([
      "幸存者",
      "物品",
      "怪物",
      "环境",
      "成就",
      "可交互物",
      "无人机",
      "神器",
      "纽特祭坛",
    ]);
    expect(ROR2_HOME_TILES.every((tile) => tile.href)).toBe(true);
    expect(ROR2_HOME_TILES[0]?.href).toBe("/guides/ror2/survivors");
    expect(ROR2_HOME_TILES[1]?.href).toBe("/guides/ror2/items");
    expect(ROR2_HOME_TILES.map((tile) => tile.href)).toEqual([
      "/guides/ror2/survivors",
      "/guides/ror2/items",
      "/guides/ror2/monsters",
      "/guides/ror2/environments",
      "/guides/ror2/challenges",
      "/guides/ror2/interactables",
      "/guides/ror2/drones",
      "/guides/ror2/artifacts",
      "/guides/ror2/newt-altars",
    ]);
  });

  it("splits survivors into base game and each expansion", () => {
    const sections = ror2SurvivorSections([
      { name: "Heretic", expansion: "" },
      { name: "Newbie", expansion: "" },
      { name: "Railgunner", expansion: "SotV" },
      { name: "Commando" },
      { name: "Seeker", expansion: "SotS" },
      { name: "Void Fiend", expansion: "SotV" },
      { name: "Operator", expansion: "AC" },
      { name: "Enforcer", expansion: "HC" },
      { name: "Guest", expansion: "ZZ" },
      { name: "Huntress", expansion: "  " },
    ]);
    expect(sections.map((section) => `${section.id}:${section.label}`)).toEqual([
      "base:本体",
      "SotV:虚空幸存者",
      "SotS:风暴探寻者",
      "AC:合金意念",
      "HC:万象归衡",
      "ZZ:ZZ",
    ]);
    expect(sections[0]?.survivors.map((row) => row.name)).toEqual([
      "Commando",
      "Huntress",
      "Heretic",
      "Newbie",
    ]);
    expect(sections[1]?.survivors.map((row) => row.name)).toEqual(["Railgunner", "Void Fiend"]);
  });

  it("keeps misc tiles as labels without routes", () => {
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
    expect(ror2PageTitle("/guides/ror2/survivors")).toBe("雨中冒险2 · 幸存者");
    expect(ror2PageTitle("/guides/ror2/monsters")).toBe("雨中冒险2 · 怪物");
    expect(ror2Crumbs("/guides/ror2/monsters")).toEqual([{ label: "怪物" }]);
    expect(ror2PageTitle("/guides/ror2/unreleased")).toBe("雨中冒险2 · Unreleased Items");
    expect(ror2Crumbs("/guides/ror2/unreleased")).toEqual([{ label: "Unreleased Items" }]);
  });

  it("drops the home crumb because the brand mark stands in for it", () => {
    expect(ror2Crumbs("/guides/ror2")).toEqual([]);
    expect(ror2Crumbs("/guides/ror2/")).toEqual([]);
    expect(ror2Crumbs("/guides/ror2/survivors")).toEqual([{ label: "幸存者" }]);
    expect(ror2Crumbs("/guides/ror2/survivors/")).toEqual([{ label: "幸存者" }]);
    expect(ror2Crumbs("/guides/ror2/items")).toEqual([{ label: "物品" }]);
  });
});

describe("ror2 survivor list", () => {
  const rows = [
    { name: "Commando", expansion: "", description: "jack", umbra: "Gunslinger", health: 110, health_per_level: 33, damage: 12, damage_per_level: 2.4, speed: 7, armor: 0 },
    { name: "Railgunner", expansion: "SotV", description: "shot", umbra: "Nomad", health: 110, damage: 12, regen: -6, regen_per_level: -1.2, armor: 20 },
  ];

  it("filters by expansion and builds the list href", () => {
    expect(ror2ActiveExpansion("SotV", rows)).toBe("SotV");
    expect(ror2ActiveExpansion("missing", rows)).toBe("all");
    expect(ror2ActiveExpansion("base", rows)).toBe("base");
    expect(filterRor2Survivors(rows, "", "SotV").map((row) => row.name)).toEqual(["Railgunner"]);
    expect(filterRor2Survivors(rows, "slinger", "all").map((row) => row.name)).toEqual(["Commando"]);
    expect(ror2SurvivorsHref()).toBe("/guides/ror2/survivors");
    expect(ror2SurvivorsHref("all", "  ")).toBe("/guides/ror2/survivors");
    expect(ror2SurvivorsHref("base", "a b")).toBe("/guides/ror2/survivors?cat=base&q=a+b");
  });

  it("formats growth stats and skips zero armor", () => {
    expect(ror2SurvivorStatLine(rows[0]!)).toBe("生命 110 (+33) · 伤害 12 (+2.4) · 移速 7");
    expect(ror2SurvivorStatLine(rows[1]!)).toBe("生命 110 · 伤害 12 · 回复 -6 (-1.2) · 护甲 20");
  });
});

describe("ror2 unreleased directory", () => {
  it("keeps the wiki's five sections and does not pull the released item that shares a code", () => {
    const rows = ror2UnreleasedRows({
      items: [
        { name: "DrizzlePlayerHelper", code: "DrizzlePlayerHelper", description: "armor" },
        { name: "BurnNearby", code: "BurnNearby", description: "fire" },
        { name: "Helfire Tincture", code: "BurnNearby", rarity: "Lunar Equipment" },
        { name: "Ancestral Incubator", code: "Incubator", description: "pod" },
      ],
      equipment: [
        { name: "Overloading Excavator", code: "IrradiatingLaser", description: "laser" },
        { name: "Jar of Souls", code: "SoulJar" },
      ],
    });
    const groups = ror2DirectoryGroups(
      rows,
      ROR2_UNRELEASED_GROUPS.map((group) => group.id),
    );
    expect(groups.map((group) => group.label)).toEqual([
      "Internal Items",
      "Unfinished Items",
      "Lore",
      "Internal Equipment",
      "Unfinished Equipment",
    ]);
    expect(groups[0]?.rows.map((row) => row.name)).toContain("DrizzlePlayerHelper");
    expect(groups[1]?.rows.map((row) => row.name)).toContain("BurnNearby");
    expect(groups[1]?.rows.map((row) => row.name)).not.toContain("Helfire Tincture");
    expect(groups[2]?.rows.map((row) => row.name)).toEqual([
      "Ancestral Incubator",
      "Strange Scrap, White",
      "Strange Scrap, Green",
      "Strange Scrap, Red",
      "Blessings of Terafirmae",
      "Overloading Excavator",
      "Elegy of Extinction",
      "Faulty Conductor (Equipment)",
      "G-Force Accelerator",
    ]);
    expect(groups[4]?.rows.map((row) => row.name)).toContain("Jar of Souls");
    expect(groups.reduce((sum, group) => sum + group.rows.length, 0)).toBe(rows.length);
  });
});

describe("ror2 directory pages", () => {
  const catalog = {
    monsters: [
      { name: "Beetle", kind: "Normal", health: 80 },
      { name: "Watcher", kind: "DoNotInclude", health: 1 },
    ],
    drones: [{ name: "Gunner Drone", kind: "Drone", type2: "Interactable", quote: "Pew.", description: "Shoots.", cost: "40 Gold" }],
    environments: [{ name: "Distant Roost", stage: "1", subtitle: "Ground Zero", description: "Fog." }],
    challenges: [{ name: "Bookworm", kind: "Equipment", description: "Collect logs.", unlock: ["Radar Scanner"], coins: "2" }],
    interactables: [
      { name: "Gunner Drone", category: "Drones", effect: "Ally" },
      { name: "Shrine of Chance", category: "Shrines", effect: "Item" },
      { name: "Newt Altar", category: "Environment Specific", effect: "Portal", wiki_url: "https://riskofrain2.wiki.gg/wiki/Newt_Altars" },
    ],
    artifacts: [{ name: "Spite", description: "Bombs.", code: ["▲●▲"], expansion: "" }],
  };

  it("keeps interactables, including shrines, and lists newt altar stages", () => {
    expect(ror2SectionRows("monsters", catalog)).toHaveLength(1);
    expect(ror2SectionRows("drones", catalog).map((row) => row.group)).toEqual(["Interactable"]);
    expect(ror2SectionRows("challenges", {
      challenges: [{ name: "Warrior", kind: "Survivors", description: "Reach stage 3.", unlock: ["Bandit"], coins: "3" }],
      survivors: [{ name: "Bandit", image_url: "https://riskofrain2.wiki.gg/images/Bandit.png" }],
    })[0]).toMatchObject({
      unlocks: [{ name: "Bandit", imageUrl: "https://riskofrain2.wiki.gg/images/Bandit.png" }],
      coins: "3",
    });
    expect(ror2UnlockIcon("Paul's Goat Hoof", [])).toBe(
      "https://riskofrain2.wiki.gg/images/Paul's_Goat_Hoof.png",
    );
    expect(ror2SectionRows("artifacts", catalog)).toHaveLength(1);
    expect(ror2SectionRows("artifacts", catalog)[0]?.imageUrl).toBe(ror2ArtifactIconUrl("Spite"));
    expect(ror2ArtifactIconUrl("Chaos")).toBe("https://riskofrain2.wiki.gg/images/Artifact_of_Chaos.png");
    expect(ror2SectionRows("interactables", catalog).map((row) => row.name)).toEqual([
      "Gunner Drone",
      "Shrine of Chance",
      "Newt Altar",
    ]);
    expect(ror2SectionRows("newt-altars", catalog).map((row) => row.name)).toContain("Distant Roost");
    expect(ror2SectionRows("newt-altars", catalog)).toHaveLength(28);
    const monsters = ror2SectionRows("monsters", {
      monsters: [
        { name: "Beetle", kind: "Normal" },
        { name: "Watcher", kind: "DoNotInclude" },
        { name: "Scavenger", kind: "Special Boss", do_not_count: true },
      ],
    });
    expect(monsters.map((row) => row.name)).toEqual(["Beetle"]);
    const groups = ror2DirectoryGroups(monsters, ["Normal"]);
    expect(groups.map((group) => group.label)).toEqual(["Regular Monsters"]);
  });
});

describe("ror2 item list", () => {
  it("keeps every item and equipment row, including the same name", () => {
    const merged = ror2CatalogItems({
      items: [
        { name: "Scrap", rarity: "Common", wiki_url: "https://example/a" },
        { name: "Scrap", rarity: "Common", wiki_url: "https://example/b" },
      ],
      equipment: [{ name: "Scrap", rarity: "Common", wiki_url: "https://example/c" }],
    });
    expect(merged).toHaveLength(3);
    expect(merged.map((row) => row.wiki_url)).toEqual([
      "https://example/a",
      "https://example/b",
      "https://example/c",
    ]);
  });

  it("hides rows the wiki item page does not list", () => {
    const merged = ror2CatalogItems({
      items: [
        { name: "Syringe", rarity: "Common", categories: ["Damage"] },
        { name: "DrizzlePlayerHelper", rarity: "Untiered", categories: ["Hidden"] },
        { name: "Tonic Affliction", rarity: "Untiered" },
        { name: "BurnNearby", rarity: "Untiered" },
        { name: "Empty Bottle", rarity: "Untiered" },
        { name: "Ancestral Incubator", rarity: "Unused (Boss)" },
      ],
      equipment: [
        { name: "Radar", rarity: "Equipment" },
        { name: "Jar of Souls", rarity: "Unused" },
      ],
    });
    expect(merged.map((row) => row.name)).toEqual(["Syringe", "Tonic Affliction", "Empty Bottle", "Radar"]);
  });

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
