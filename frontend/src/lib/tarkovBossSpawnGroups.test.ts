import { describe, expect, it } from "vitest";
import {
  escortChipLabel,
  formatEscortComposition,
  groupBossSpawnWaves,
  isSameMobCountVariants,
  locationChipLabel,
  spawnGroupComboNumbers,
  spawnGroupFromApi,
} from "./tarkovBossSpawnGroups";

const pipe = {
  slug: "big-pipe",
  name: "Big Pipe",
  count: 1,
  chance: 1,
};

const bird = {
  slug: "birdeye",
  name: "Birdeye",
  count: 1,
  chance: 1,
};

describe("groupBossSpawnWaves", () => {
  it("merges maps that share the same escort recipe", () => {
    const groups = groupBossSpawnWaves({
      maps: [
        { slug: "customs", name: "海关", spawn_chance: "20%" },
        { slug: "woods", name: "森林", spawn_chance: "20%" },
        { slug: "lighthouse", name: "灯塔", spawn_chance: "20%" },
        { slug: "shoreline", name: "海岸线", spawn_chance: "20%" },
        { slug: "icebreaker", name: "破冰船", spawn_chance: "100%" },
      ],
      spawn_locations: [
        { map: "海关", map_slug: "customs", name: "Dorms", chance: 0.2 },
        { map: "森林", map_slug: "woods", name: "Sawmill", chance: 0.2 },
        { map: "破冰船", map_slug: "icebreaker", name: "Deck", chance: 1 },
      ],
      escorts: [
        { ...pipe, map: "海关", map_slug: "customs" },
        { ...bird, map: "海关", map_slug: "customs" },
        { ...pipe, map: "森林", map_slug: "woods" },
        { ...bird, map: "森林", map_slug: "woods" },
        { ...pipe, map: "灯塔", map_slug: "lighthouse" },
        { ...bird, map: "灯塔", map_slug: "lighthouse" },
        { ...pipe, map: "海岸线", map_slug: "shoreline" },
        { ...bird, map: "海岸线", map_slug: "shoreline" },
        {
          slug: "rogue",
          name: "游荡者",
          count: 2,
          chance: 1,
          map: "破冰船",
          map_slug: "icebreaker",
        },
      ],
    });
    expect(groups).toHaveLength(2);
    expect(groups[0].maps.map((row) => row.slug)).toEqual([
      "customs",
      "woods",
      "lighthouse",
      "shoreline",
    ]);
    expect(groups[0].sharedSpawnChance).toBe("20%");
    expect(groups[0].escorts.map((row) => row.slug)).toEqual(["big-pipe", "birdeye"]);
    expect(groups[0].locations.map((row) => row.name)).toEqual(["Dorms", "Sawmill"]);
    expect(groups[0].showLocationChance).toBe(false);
    expect(groups[1].maps.map((row) => row.slug)).toEqual(["icebreaker"]);
    expect(groups[1].sharedSpawnChance).toBe("100%");
    expect(groups[1].escorts).toEqual([
      { slug: "rogue", name: "游荡者", count: 2, chance: 1 },
    ]);
  });

  it("keeps maps on one row when combo matches but spawn chance differs", () => {
    const groups = groupBossSpawnWaves({
      maps: [
        { slug: "interchange", name: "立交桥", spawn_chance: "45%" },
        { slug: "terminal", name: "码头", spawn_chance: "20%" },
      ],
      spawn_locations: [
        { map: "立交桥", map_slug: "interchange", name: "Mall", chance: 0.45 },
        { map: "码头", map_slug: "terminal", name: "Pier", chance: 0.2 },
      ],
      escorts: [],
    });
    expect(groups).toHaveLength(1);
    expect(groups[0].sharedSpawnChance).toBeNull();
    expect(groups[0].maps.map((row) => row.spawnChance)).toEqual(["45%", "20%"]);
    expect(groups[0].escorts).toEqual([]);
    expect(groups[0].showLocationChance).toBe(true);
  });

  it("keeps amount rolls of the same combo on one group", () => {
    const groups = groupBossSpawnWaves({
      maps: [{ slug: "woods", name: "森林", spawn_chance: "30%" }],
      escorts: [
        {
          slug: "follower-kojaniy",
          name: "Shturman guard",
          count: 2,
          chance: 0.5,
          map: "森林",
          map_slug: "woods",
        },
        {
          slug: "follower-kojaniy",
          name: "Shturman guard",
          count: 3,
          chance: 0.5,
          map: "森林",
          map_slug: "woods",
        },
      ],
    });
    expect(groups).toHaveLength(1);
    expect(groups[0].escorts.map((row) => row.count)).toEqual([2, 3]);
    expect(escortChipLabel(groups[0].escorts[0])).toBe("Shturman guard ×2（50%）");
    expect(escortChipLabel(groups[0].escorts[1])).toBe("Shturman guard ×3（50%）");
  });

  it("prefixes location names that collide across maps", () => {
    const group = groupBossSpawnWaves({
      maps: [
        { slug: "customs", name: "海关", spawn_chance: "20%" },
        { slug: "woods", name: "森林", spawn_chance: "20%" },
      ],
      spawn_locations: [
        { map: "海关", map_slug: "customs", name: "Sawmill", chance: 0.2 },
        { map: "森林", map_slug: "woods", name: "Sawmill", chance: 0.2 },
      ],
    })[0];
    expect(locationChipLabel(group.locations[0], group)).toBe("海关 Sawmill");
    expect(locationChipLabel(group.locations[1], group)).toBe("森林 Sawmill");
  });

  it("maps API spawn groups including land label", () => {
    const group = spawnGroupFromApi({
      maps: [{ slug: "lighthouse", name: "灯塔", spawn_chance: "30%" }],
      shared_spawn_chance: "30%",
      land_label: "开局",
      locations: [
        { map: "灯塔", map_slug: "lighthouse", name: "Zone_Chalet", chance: 0.5 },
      ],
      escorts: [{ slug: "big-pipe", name: "Big Pipe", count: 1, chance: 1 }],
      show_location_chance: false,
    });
    expect(group.landLabel).toBe("开局");
    expect(group.sharedSpawnChance).toBe("30%");
    expect(group.escorts[0].name).toBe("Big Pipe");
    expect(group.locations[0].positions).toEqual([]);
  });

  it("keeps spawn coordinates from the API", () => {
    const group = spawnGroupFromApi({
      maps: [{ slug: "customs", name: "海关", spawn_chance: "20%" }],
      locations: [
        {
          map: "海关",
          map_slug: "customs",
          name: "Dorms",
          chance: 1,
          positions: [{ x: 10, y: 2, z: 30 }],
        },
      ],
    });
    expect(group.locations[0].positions).toEqual([{ x: 10, y: 2, z: 30 }]);
  });
});

describe("escort combo labels", () => {
  it("treats one follower with several counts as variants", () => {
    expect(
      isSameMobCountVariants([
        { slug: "g", name: "保镖" },
        { slug: "g", name: "保镖" },
      ]),
    ).toBe(true);
    expect(isSameMobCountVariants([pipe, bird])).toBe(false);
    expect(formatEscortComposition([pipe, bird])).toBe("Big Pipe ×1、Birdeye ×1");
  });

  it("numbers spawn groups that share a map", () => {
    const ice = { slug: "icebreaker", name: "破冰船", spawnChance: "100%" };
    expect(
      spawnGroupComboNumbers([
        { maps: [ice] },
        { maps: [ice] },
        { maps: [ice] },
      ]),
    ).toEqual([1, 2, 3]);
    expect(
      spawnGroupComboNumbers([
        { maps: [{ slug: "customs", name: "海关", spawnChance: "20%" }] },
        { maps: [{ slug: "icebreaker", name: "破冰船", spawnChance: "100%" }] },
      ]),
    ).toEqual([null, null]);
  });
});
