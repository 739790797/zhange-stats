import { describe, expect, it } from "vitest";
import {
  filterCatalogBosses,
  groupBossCatalogTree,
  groupBossesByKind,
  isCatalogBossKind,
  isFollowerMobId,
  isHangableUnderNamedBoss,
  isNamedBossId,
  isTopLevelNamedBoss,
  namedBossParentId,
  normalizeBossKind,
  selectTopLevelNamedBosses,
  TARKOV_BOSS_HUB_SECTION_LABELS,
  TARKOV_BOSS_KIND_LABELS,
} from "./tarkovBossKinds";

describe("tarkovBossKinds", () => {
  it("treats missing kind as named boss", () => {
    expect(normalizeBossKind(undefined)).toBe("boss");
    expect(normalizeBossKind("")).toBe("boss");
    expect(normalizeBossKind("ELITE")).toBe("elite");
    expect(TARKOV_BOSS_KIND_LABELS).toEqual({
      boss: "Boss",
      elite: "Elite",
      soldier: "Soldier",
    });
    expect(TARKOV_BOSS_HUB_SECTION_LABELS).toEqual({
      boss: "Boss",
      other: "非 Boss",
    });
  });

  it("groups the catalog into Boss / Elite / Soldier", () => {
    const rows = [
      { id: "killa", kind: "boss" },
      { id: "raider", kind: "elite" },
      { id: "vsRF", kind: "soldier" },
      { id: "usec", kind: "soldier" },
    ];
    expect(groupBossesByKind(rows)).toEqual({
      boss: [{ id: "killa", kind: "boss" }],
      elite: [{ id: "raider", kind: "elite" }],
      soldier: [
        { id: "vsRF", kind: "soldier" },
        { id: "usec", kind: "soldier" },
      ],
    });
    expect(filterCatalogBosses(rows).map((row) => row.id)).toEqual([
      "killa",
      "raider",
    ]);
    expect(isCatalogBossKind("soldier")).toBe(false);
  });

  it("keeps follower ids out of the home catalog", () => {
    expect(isNamedBossId("bossGluhar")).toBe(true);
    expect(isNamedBossId("bossBoarSniper")).toBe(true);
    expect(isNamedBossId("blackDivision")).toBe(false);
    expect(namedBossParentId(["bossBoar"])).toBe("bossBoar");
    expect(namedBossParentId(["followerBoar", "bossBoar"])).toBe("bossBoar");
    expect(isTopLevelNamedBoss("bossBoar", [])).toBe(true);
    expect(isTopLevelNamedBoss("bossBoarSniper", ["bossBoar"])).toBe(false);
    expect(isHangableUnderNamedBoss("bossBoarSniper", ["bossBoar"])).toBe(true);
    expect(isHangableUnderNamedBoss("followerGluharAssault", ["bossGluhar"])).toBe(
      true,
    );
    expect(isHangableUnderNamedBoss("ExUsec", ["bossKnight"])).toBe(false);
    expect(isFollowerMobId("followerGluharAssault")).toBe(true);
    expect(
      filterCatalogBosses([
        { id: "bossKilla", kind: "boss" },
        { id: "followerBigPipe", kind: "boss" },
        { id: "PmcBot", kind: "elite" },
      ]).map((row) => row.id),
    ).toEqual(["bossKilla", "PmcBot"]);
  });

  it("nests follower* and named-id escorts under their named boss parent", () => {
    const rows = [
      { id: "bossGluhar", parent_ids: [] },
      { id: "bossKnight", parent_ids: [] },
      { id: "bossBoar", parent_ids: [] },
      {
        id: "followerGluharAssault",
        parent_ids: ["bossGluhar"],
      },
      { id: "followerBigPipe", parent_ids: ["bossKnight"] },
      { id: "ExUsec", parent_ids: ["bossKnight"] },
      { id: "blackDivision", parent_ids: [] },
      { id: "PmcBot", parent_ids: [] },
      { id: "bossBoarSniper", parent_ids: ["bossBoar"] },
    ];
    const tree = groupBossCatalogTree(rows);
    expect(tree.bosses.map((row) => row.id)).toEqual([
      "bossGluhar",
      "bossKnight",
      "bossBoar",
    ]);
    expect(selectTopLevelNamedBosses(rows).map((row) => row.id)).toEqual([
      "bossGluhar",
      "bossKnight",
      "bossBoar",
    ]);
    expect(tree.bosses[0].children?.map((row) => row.id)).toEqual([
      "followerGluharAssault",
    ]);
    expect(tree.bosses[1].children?.map((row) => row.id)).toEqual([
      "followerBigPipe",
    ]);
    expect(tree.bosses[2].children?.map((row) => row.id)).toEqual([
      "bossBoarSniper",
    ]);
    expect(tree.others.map((row) => row.id)).toEqual([
      "ExUsec",
      "blackDivision",
      "PmcBot",
    ]);
  });
});
