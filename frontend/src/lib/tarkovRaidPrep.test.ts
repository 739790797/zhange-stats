import { describe, expect, it } from "vitest";
import {
  buildRaidPrepOverlays,
  colorForTaskId,
  mapSlugKeys,
  neededKeyNamesForMap,
  normalizeRaidPrepMapId,
  objectiveZoneNames,
  parseCsvParam,
  raidPrepMapOptions,
  serializeSelectedIds,
  type RaidPrepTaskLike,
} from "./tarkovRaidPrep";

describe("raid prep map keys", () => {
  it("treats streets aliases as the same map", () => {
    expect([...mapSlugKeys("streets")].sort()).toEqual(
      ["streets", "streets-of-tarkov"].sort(),
    );
    expect(normalizeRaidPrepMapId("streets-of-tarkov")).toBe("streets");
    expect(normalizeRaidPrepMapId("lab")).toBe("lab");
    expect(normalizeRaidPrepMapId("the-lab")).toBe("lab");
    expect(normalizeRaidPrepMapId("factory-night")).toBe("night-factory");
    expect(normalizeRaidPrepMapId("nope")).toBe("");
  });

  it("inserts night factory after factory", () => {
    const ids = raidPrepMapOptions().map((item) => item.id);
    expect(ids).toContain("customs");
    expect(ids.indexOf("night-factory")).toBe(ids.indexOf("factory") + 1);
  });
});

describe("selected ids", () => {
  it("parses and caps selected task ids", () => {
    expect(parseCsvParam("a, b,,a")).toEqual(["a", "b"]);
    expect(serializeSelectedIds(["x", "x", "y"])).toBe("x,y");
  });
});

describe("buildRaidPrepOverlays", () => {
  const task: RaidPrepTaskLike = {
    id: "t1",
    name: "Debut",
    needed_keys: [
      {
        map: { slug: "customs" },
        keys: [{ name: "Dorm 114" }],
      },
    ],
    objectives: [
      {
        id: "o-visit",
        type: "visit",
        description: "go to dorms",
        zone_names: ["Dorms"],
        zones: [
          {
            id: "z1",
            map_slug: "customs",
            x: 1,
            z: 2,
            outline: [
              { x: 0, z: 0 },
              { x: 4, z: 0 },
              { x: 4, z: 4 },
            ],
          },
          {
            id: "z-other",
            map_slug: "streets",
            x: 9,
            z: 9,
          },
        ],
      },
      {
        id: "o-find",
        type: "findQuestItem",
        description: "hdd",
        possible_locations: [
          {
            map_slug: "customs",
            positions: [{ x: 10, z: 20 }],
          },
        ],
      },
    ],
  };

  it("keeps only the selected map markers", () => {
    const overlays = buildRaidPrepOverlays([task], "customs");
    expect(overlays).toHaveLength(2);
    expect(overlays[0]).toMatchObject({
      kind: "zone",
      title: "Debut",
      outline: [
        { x: 0, z: 0 },
        { x: 4, z: 0 },
        { x: 4, z: 4 },
      ],
      points: [{ x: 1, z: 2 }],
    });
    expect(overlays[1]).toMatchObject({
      kind: "spawn",
      points: [{ x: 10, z: 20 }],
    });
    expect(overlays[0].color).toBe(colorForTaskId("t1"));
    expect(objectiveZoneNames(task)).toEqual(["Dorms"]);
    expect(neededKeyNamesForMap(task, "customs")).toEqual(["Dorm 114"]);
    expect(neededKeyNamesForMap(task, "streets")).toEqual([]);
  });
});
