import { describe, expect, it } from "vitest";
import {
  MAP_SLUG_EQUIV_GROUPS,
  RAID_PREP_AUTO_MAP_KINDS,
  isRaidPrepAutoMapKind,
  mapSlugKeys,
  normalizeRaidPrepMapId,
  raidPrepMapOptions,
} from "./tarkovMapSlugs";

describe("mapSlugKeys", () => {
  it("expands equivalence groups and ignores unknown slugs", () => {
    expect([...mapSlugKeys("streets")].sort()).toEqual([
      "streets",
      "streets-of-tarkov",
    ]);
    expect([...mapSlugKeys("bigmap")].sort()).toEqual(["bigmap", "customs"]);
    expect([...mapSlugKeys("unknown-map")]).toEqual(["unknown-map"]);
    expect([...mapSlugKeys("")]).toEqual([]);
  });

  it("normalizes case and trims", () => {
    expect([...mapSlugKeys(" CUSTOMS ")].sort()).toEqual(["bigmap", "customs"]);
  });
});

describe("normalizeRaidPrepMapId", () => {
  it("maps aliases onto catalog ids", () => {
    expect(normalizeRaidPrepMapId("streets-of-tarkov")).toBe("streets");
    expect(normalizeRaidPrepMapId("lab")).toBe("lab");
    expect(normalizeRaidPrepMapId("the-lab")).toBe("lab");
    expect(normalizeRaidPrepMapId("factory-night")).toBe("night-factory");
    expect(normalizeRaidPrepMapId("bigmap")).toBe("customs");
    expect(normalizeRaidPrepMapId("nope-not-a-map")).toBe("");
    expect(normalizeRaidPrepMapId("")).toBe("");
  });
});

describe("raidPrepMapOptions", () => {
  it("lists ready maps plus the night factory variant", () => {
    const ids = raidPrepMapOptions().map((row) => row.id);
    expect(ids).toContain("customs");
    expect(ids).toContain("night-factory");
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("isRaidPrepAutoMapKind", () => {
  it("accepts only the loading / matching / starting phases", () => {
    for (const kind of RAID_PREP_AUTO_MAP_KINDS) {
      expect(isRaidPrepAutoMapKind(kind)).toBe(true);
    }
    expect(isRaidPrepAutoMapKind(" raid_started ")).toBe(true);
    expect(isRaidPrepAutoMapKind("raid_exited")).toBe(false);
    expect(isRaidPrepAutoMapKind("")).toBe(false);
    expect(isRaidPrepAutoMapKind(null)).toBe(false);
  });
});

describe("MAP_SLUG_EQUIV_GROUPS", () => {
  it("keeps each alias in a single group", () => {
    const seen = new Set<string>();
    for (const group of MAP_SLUG_EQUIV_GROUPS) {
      for (const slug of group) {
        expect(seen.has(slug)).toBe(false);
        seen.add(slug);
      }
    }
  });
});
