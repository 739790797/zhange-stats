import { describe, expect, it } from "vitest";
import {
  flattenBossHubRows,
  selectIndependentOtherBosses,
} from "./tarkovBossHubRows";
import type { BossSpawnGroupApi } from "./tarkovBossSpawnGroups";

function icebreakerGroup(
  escorts: BossSpawnGroupApi["escorts"],
): BossSpawnGroupApi {
  return {
    maps: [{ slug: "icebreaker", name: "破冰船", spawn_chance: "100%" }],
    shared_spawn_chance: "100%",
    land_label: "与战局时间无关",
    locations: [
      { map: "破冰船", map_slug: "icebreaker", name: "BotZoneEngineHide", chance: 1 },
    ],
    escorts,
    show_location_chance: false,
  };
}

describe("flattenBossHubRows", () => {
  it("merges map / chance / land when the same boss repeats one map", () => {
    const rows = flattenBossHubRows([
      {
        id: "bossBullyBlackDiv",
        slug: "bully-black-div",
        spawn_groups: [
          icebreakerGroup([{ slug: "follower", name: "护卫", count: 3, chance: 1 }]),
          icebreakerGroup([{ slug: "follower", name: "护卫", count: 2, chance: 1 }]),
          icebreakerGroup([{ slug: "follower", name: "护卫", count: 4, chance: 1 }]),
        ],
      },
    ]);
    expect(rows).toHaveLength(3);
    expect(rows.map((row) => row.nameSpan)).toEqual([3, 0, 0]);
    expect(rows.map((row) => row.mapSpan)).toEqual([3, 0, 0]);
    expect(rows.map((row) => row.landSpan)).toEqual([3, 0, 0]);
    expect(rows.map((row) => row.group?.escorts[0].count)).toEqual([3, 2, 4]);
  });

  it("does not merge the same map across different bosses", () => {
    const rows = flattenBossHubRows([
      {
        id: "bossBullyBlackDiv",
        slug: "bully-black-div",
        spawn_groups: [
          icebreakerGroup([{ slug: "follower", name: "护卫", count: 3, chance: 1 }]),
        ],
      },
      {
        id: "bossKaban",
        slug: "kaban",
        spawn_groups: [
          icebreakerGroup([{ slug: "follower", name: "护卫", count: 3, chance: 1 }]),
        ],
      },
    ]);
    expect(rows.map((row) => row.mapSpan)).toEqual([1, 1]);
    expect(rows.map((row) => row.nameSpan)).toEqual([1, 1]);
  });

  it("does not merge the same map when spawn chance differs", () => {
    const rows = flattenBossHubRows([
      {
        id: "bossKnight",
        slug: "knight",
        spawn_groups: [
          {
            maps: [{ slug: "lighthouse", name: "灯塔", spawn_chance: "20%" }],
            shared_spawn_chance: "20%",
            land_label: "开局",
            locations: [],
            escorts: [{ slug: "followerBigPipe", name: "Big Pipe", count: 1, chance: 1 }],
          },
          {
            maps: [{ slug: "lighthouse", name: "灯塔", spawn_chance: "100%" }],
            shared_spawn_chance: "100%",
            land_label: "开局",
            locations: [],
            escorts: [{ slug: "followerBirdEye", name: "Bird Eye", count: 1, chance: 1 }],
          },
        ],
      },
    ]);
    expect(rows.map((row) => row.mapSpan)).toEqual([1, 1]);
    expect(rows.map((row) => row.landSpan)).toEqual([2, 0]);
  });

  it("does not merge maps that differ on the same boss", () => {
    const rows = flattenBossHubRows([
      {
        id: "bossKilla",
        slug: "killa",
        spawn_groups: [
          {
            maps: [{ slug: "interchange", name: "立交桥", spawn_chance: "75%" }],
            shared_spawn_chance: "75%",
            land_label: "开局",
            locations: [],
            escorts: [],
          },
          {
            maps: [{ slug: "terminal", name: "码头", spawn_chance: "20%" }],
            shared_spawn_chance: "20%",
            land_label: "与战局时间无关",
            locations: [],
            escorts: [],
          },
        ],
      },
    ]);
    expect(rows.map((row) => row.nameSpan)).toEqual([2, 0]);
    expect(rows.map((row) => row.mapSpan)).toEqual([1, 1]);
    expect(rows.map((row) => row.landSpan)).toEqual([1, 1]);
  });
});

describe("selectIndependentOtherBosses", () => {
  it("hides escort-only followers copied onto the boss spawn", () => {
    const rows = selectIndependentOtherBosses([
      {
        id: "followerBigPipe",
        slug: "big-pipe",
        parent_ids: ["bossKnight"],
        spawn_groups: [
          {
            maps: [{ slug: "factory", name: "工厂", spawn_chance: "30%" }],
            shared_spawn_chance: "30%",
            land_label: "开局",
            locations: [],
            escorts: [],
          },
        ],
      },
      {
        id: "PmcBot",
        slug: "raider",
        parent_ids: [],
        spawn_groups: [
          {
            maps: [{ slug: "lab", name: "实验室", spawn_chance: "100%" }],
            shared_spawn_chance: "100%",
            land_label: "开局",
            locations: [{ map: "实验室", map_slug: "lab", name: "BotZone", chance: 1 }],
            escorts: [],
          },
        ],
      },
    ]);
    expect(rows.map((row) => row.id)).toEqual(["PmcBot"]);
  });

  it("keeps independent waves when the same mob also escorts a boss", () => {
    const rows = selectIndependentOtherBosses([
      {
        id: "ExUsec",
        slug: "rogue",
        parent_ids: ["bossKnight"],
        spawn_groups: [
          {
            maps: [{ slug: "lighthouse", name: "灯塔", spawn_chance: "30%" }],
            shared_spawn_chance: "30%",
            land_label: "开局",
            locations: [],
            escorts: [],
          },
          {
            maps: [{ slug: "lighthouse", name: "灯塔", spawn_chance: "50%" }],
            shared_spawn_chance: "50%",
            land_label: "开局",
            locations: [
              { map: "灯塔", map_slug: "lighthouse", name: "WaterTreatment", chance: 1 },
            ],
            escorts: [],
          },
        ],
      },
    ]);
    expect(rows).toHaveLength(1);
    expect(rows[0].spawn_groups).toHaveLength(1);
    expect(rows[0].spawn_groups?.[0].maps?.[0].spawn_chance).toBe("50%");
  });

  it("skips top-level named bosses", () => {
    expect(
      selectIndependentOtherBosses([
        {
          id: "bossKilla",
          slug: "killa",
          parent_ids: [],
          spawn_groups: [],
        },
      ]),
    ).toEqual([]);
  });

  it("hides named-id escorts that only copy the parent spawn", () => {
    const rows = selectIndependentOtherBosses([
      {
        id: "bossBoarSniper",
        slug: "kaban-guard-sniper",
        parent_ids: ["bossBoar"],
        spawn_groups: [
          {
            maps: [{ slug: "streets-of-tarkov", name: "街区", spawn_chance: "60%" }],
            shared_spawn_chance: "60%",
            land_label: "开局",
            locations: [],
            escorts: [],
          },
        ],
      },
    ]);
    expect(rows).toEqual([]);
  });
});
