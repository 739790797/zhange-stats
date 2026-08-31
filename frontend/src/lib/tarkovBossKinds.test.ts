import { describe, expect, it } from "vitest";
import {
  filterCatalogBosses,
  groupBossesByKind,
  isCatalogBossKind,
  normalizeBossKind,
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
});
