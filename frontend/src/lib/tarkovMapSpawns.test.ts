import { describe, expect, it } from "vitest";
import {
  allPresentSpawnKindsOn,
  anyPresentSpawnKindOn,
  defaultSpawnKindFlags,
  spawnKindsPresent,
  tarkovSpawnIconAnchor,
  tarkovSpawnIconUrl,
  withSpawnKindsForPresent,
} from "./tarkovMapSpawns";

describe("tarkov map spawn styles", () => {
  it("uses tarkov.dev spawn icon paths and pmc bottom anchor", () => {
    expect(tarkovSpawnIconUrl("boss")).toBe("/tarkov/map-icons/spawn_boss.png");
    expect(tarkovSpawnIconUrl("pmc")).toBe("/tarkov/map-icons/spawn_pmc.png");
    expect(tarkovSpawnIconAnchor("pmc")).toEqual([12, 24]);
    expect(tarkovSpawnIconAnchor("scav")).toEqual([12, 12]);
  });

  it("lists present spawn kinds from spawns + bosses", () => {
    expect(
      spawnKindsPresent({
        spawns: [{ kind: "pmc" }, { kind: "scav" }, { kind: "pmc" }],
        bosses: [{ id: "tagilla" }],
      }),
    ).toEqual(["pmc", "scav", "boss"]);
    expect(spawnKindsPresent({ spawns: [], bosses: [] })).toEqual([]);
    expect(spawnKindsPresent({ spawns: [{ kind: "pmc" }] })).toEqual(["pmc"]);
  });

  it("toggles spawn kinds like tarkov.dev layer groups", () => {
    const present = spawnKindsPresent({
      spawns: [{ kind: "pmc" }, { kind: "scav" }],
      bosses: [1],
    });
    const flags = defaultSpawnKindFlags(true);
    expect(allPresentSpawnKindsOn(flags, present)).toBe(true);
    const offBoss = { ...flags, boss: false };
    expect(allPresentSpawnKindsOn(offBoss, present)).toBe(false);
    expect(anyPresentSpawnKindOn(offBoss, present)).toBe(true);
    expect(withSpawnKindsForPresent(flags, present, false)).toEqual({
      pmc: false,
      scav: false,
      boss: false,
    });
  });
});
