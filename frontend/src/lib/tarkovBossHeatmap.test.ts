import { describe, expect, it } from "vitest";
import {
  buildBossHeatmap,
  buildBossPortraitIndex,
  formatHoverAria,
  formatHoverSquadSizes,
  heatmapCellHoverBlocks,
  heatmapMapParentSlug,
  heatmapSpawnLocationOptions,
  hoverEscortSchemes,
  hoverSquadCountForLocation,
  parseChancePct,
} from "./tarkovBossHeatmap";
import type { BossSpawnGroupApi } from "./tarkovBossSpawnGroups";

function group(partial: BossSpawnGroupApi): BossSpawnGroupApi {
  return {
    maps: [],
    shared_spawn_chance: "",
    land_label: "开局",
    locations: [],
    escorts: [],
    show_location_chance: false,
    ...partial,
  };
}

function terminal(bossId: string, escorts: BossSpawnGroupApi["escorts"] = []) {
  return {
    id: bossId,
    slug: bossId,
    name: bossId,
    spawn_groups: [
      group({
        maps: [{ slug: "terminal", name: "码头", spawn_chance: "20%" }],
        shared_spawn_chance: "20%",
        land_label: "与战局时间无关",
        locations: [
          { map: "码头", map_slug: "terminal", name: "Zone2ScavPort29", chance: 1 },
        ],
        escorts,
      }),
    ],
  };
}

describe("parseChancePct", () => {
  it("reads the largest number in a label", () => {
    expect(parseChancePct("75%")).toBe(75);
    expect(parseChancePct("25–30%")).toBe(30);
    expect(parseChancePct("100%/70%")).toBe(100);
  });
});

describe("buildBossHeatmap", () => {
  it("marks terminal as a 5-pick-1 pool and customs as independent", () => {
    const model = buildBossHeatmap([
      terminal("bossGluhar", [{ slug: "g", name: "突击", count: 2, chance: 1 }]),
      terminal("bossKilla"),
      {
        id: "bossBully",
        slug: "reshala",
        name: "Reshala",
        spawn_groups: [
          group({
            maps: [{ slug: "customs", name: "海关", spawn_chance: "75%" }],
            shared_spawn_chance: "75%",
            land_label: "开局",
            escorts: [{ slug: "b", name: "卫兵", count: 4, chance: 1 }],
          }),
          group({
            maps: [{ slug: "terminal", name: "码头", spawn_chance: "20%" }],
            shared_spawn_chance: "20%",
            land_label: "与战局时间无关",
            locations: [
              { map: "码头", map_slug: "terminal", name: "Zone2ScavPort29", chance: 1 },
            ],
            escorts: [{ slug: "b", name: "卫兵", count: 4, chance: 1 }],
          }),
        ],
      },
      terminal("bossSanitar", [{ slug: "s", name: "卫兵", count: 3, chance: 1 }]),
      terminal("bossTagilla"),
    ]);
    const terminalCol = model.maps.find((col) => col.slug === "terminal");
    const customsCol = model.maps.find((col) => col.slug === "customs");
    expect(terminalCol?.pool).toBe(true);
    expect(customsCol?.pool).toBe(false);
    const killa = model.bosses.findIndex((row) => row.id === "bossKilla");
    const termIdx = model.maps.findIndex((col) => col.slug === "terminal");
    expect(model.cells[killa][termIdx]).toMatchObject({
      label: "20%",
      pool: true,
      recipeCount: 1,
    });
    expect(heatmapCellHoverBlocks(model.cells[killa][termIdx].recipes)).toEqual([
      {
        chance: "20%",
        showChance: false,
        land: "与战局时间无关",
        escorts: [],
        squadSizes: [],
      },
    ]);
    const glukhar = model.bosses.findIndex((row) => row.id === "bossGluhar");
    expect(heatmapCellHoverBlocks(model.cells[glukhar][termIdx].recipes)).toEqual([
      {
        chance: "20%",
        showChance: false,
        land: "与战局时间无关",
        escorts: [{ slug: "g", name: "突击", count: 2, chance: 1 }],
        squadSizes: [],
      },
    ]);
    expect(model.drilldowns.terminal.pool).toBe(true);
    expect(model.drilldowns.terminal.entries).toHaveLength(5);
  });

  it("collapses icebreaker recipes into ×N and does not treat 100% waves as a pool", () => {
    const model = buildBossHeatmap([
      {
        id: "bossBullyBlackDiv",
        slug: "black-div-boss",
        name: "Black Div. Boss",
        spawn_groups: [2, 3, 4].map((count) =>
          group({
            maps: [{ slug: "icebreaker", name: "破冰船", spawn_chance: "100%" }],
            shared_spawn_chance: "100%",
            land_label: "与战局时间无关",
            escorts: [{ slug: "g", name: "保镖", count, chance: 1 }],
          }),
        ),
      },
    ]);
    expect(model.maps[0]?.pool).toBe(false);
    expect(model.cells[0][0]).toMatchObject({
      label: "100%",
      recipeCount: 3,
      locationCount: 0,
      pool: false,
    });
    expect(model.drilldowns.icebreaker.entries[0].recipes).toHaveLength(3);
    expect(model.drilldowns.icebreaker.entries[0].recipes.map((row) => row.escortLabel)).toEqual([
      "保镖 ×2",
      "保镖 ×3",
      "保镖 ×4",
    ]);
    expect(heatmapCellHoverBlocks(model.cells[0][0].recipes)).toEqual([
      {
        chance: "100%",
        showChance: false,
        land: "与战局时间无关",
        escorts: [{ slug: "g", name: "保镖", count: 2, chance: 1 }],
        squadSizes: [],
      },
      {
        chance: "100%",
        showChance: false,
        land: "与战局时间无关",
        escorts: [{ slug: "g", name: "保镖", count: 3, chance: 1 }],
        squadSizes: [],
      },
      {
        chance: "100%",
        showChance: false,
        land: "与战局时间无关",
        escorts: [{ slug: "g", name: "保镖", count: 4, chance: 1 }],
        squadSizes: [],
      },
    ]);
  });

  it("includes independent non-boss rows when they are passed in", () => {
    const model = buildBossHeatmap([
      {
        id: "PmcBot",
        slug: "raider",
        name: "Raider",
        spawn_groups: [
          group({
            maps: [{ slug: "the-lab", name: "实验室", spawn_chance: "60%" }],
            shared_spawn_chance: "60%",
            land_label: "15分钟",
            escorts: [{ slug: "PmcBot", name: "Raider", count: 2, chance: 1 }],
          }),
        ],
      },
    ]);
    expect(model.bosses.map((row) => row.id)).toEqual(["PmcBot"]);
    expect(model.maps.map((col) => col.short)).toEqual(["实验室"]);
    expect(model.cells[0][0]).toMatchObject({ label: "60%", recipeCount: 1, pool: false });
    expect(model.maps[0]?.pool).toBe(false);
    expect(
      heatmapCellHoverBlocks(model.cells[0][0].recipes, model.bosses[0]),
    ).toEqual([
      {
        chance: "60%",
        showChance: false,
        land: "15分钟",
        escorts: [],
        squadSizes: [{ size: 3, chance: "60%" }],
      },
    ]);
  });

  it("does not treat non-boss chance sums as a 5-pick-1 pool", () => {
    const loc = { map: "实验室", map_slug: "the-lab", name: "BotZone", chance: 1 };
    const model = buildBossHeatmap([
      {
        id: "PmcBot",
        slug: "raider",
        name: "Raider",
        spawn_groups: [
          group({
            maps: [{ slug: "the-lab", name: "实验室", spawn_chance: "60%" }],
            shared_spawn_chance: "60%",
            locations: [loc],
          }),
        ],
      },
      {
        id: "ExUsec",
        slug: "rogue",
        name: "游荡者",
        spawn_groups: [
          group({
            maps: [{ slug: "the-lab", name: "实验室", spawn_chance: "40%" }],
            shared_spawn_chance: "40%",
            locations: [loc],
          }),
        ],
      },
    ]);
    expect(model.maps[0]?.pool).toBe(false);
    expect(model.cells[0][0].pool).toBe(false);
  });

  it("prefixes chance when one cell has mixed spawn rates", () => {
    const model = buildBossHeatmap([
      {
        id: "bossKnight",
        slug: "knight",
        name: "Knight",
        spawn_groups: [
          group({
            maps: [{ slug: "woods", name: "森林", spawn_chance: "25%" }],
            escorts: [{ slug: "p", name: "Pipe", count: 1, chance: 1 }],
          }),
          group({
            maps: [{ slug: "woods", name: "森林", spawn_chance: "30%" }],
            escorts: [
              { slug: "p", name: "Pipe", count: 1, chance: 1 },
              { slug: "b", name: "Birdeye", count: 1, chance: 1 },
            ],
          }),
        ],
      },
    ]);
    expect(heatmapCellHoverBlocks(model.cells[0][0].recipes)).toEqual([
      {
        chance: "25%",
        showChance: true,
        land: "开局",
        escorts: [{ slug: "p", name: "Pipe", count: 1, chance: 1 }],
        squadSizes: [],
      },
      {
        chance: "30%",
        showChance: true,
        land: "开局",
        escorts: [
          { slug: "p", name: "Pipe", count: 1, chance: 1 },
          { slug: "b", name: "Birdeye", count: 1, chance: 1 },
        ],
        squadSizes: [],
      },
    ]);
  });

  it("folds self-escorts of a non-boss into unique squad sizes", () => {
    const model = buildBossHeatmap([
      {
        id: "pmcBEAR",
        slug: "bear",
        name: "BEAR",
        spawn_groups: [0, 1, 2, 3, 0, 1].map((count) =>
          group({
            maps: [{ slug: "lighthouse", name: "灯塔", spawn_chance: "50%" }],
            shared_spawn_chance: "50%",
            land_label: "开局",
            escorts: [{ slug: "bear", name: "BEAR", count, chance: 1 }],
          }),
        ),
      },
    ]);
    expect(
      heatmapCellHoverBlocks(model.cells[0][0].recipes, model.bosses[0]),
    ).toEqual([
      {
        chance: "50%",
        showChance: false,
        land: "开局",
        escorts: [],
        squadSizes: [
          { size: 1, chance: "50%" },
          { size: 2, chance: "50%" },
          { size: 3, chance: "50%" },
          { size: 4, chance: "50%" },
        ],
      },
    ]);
    expect(
      formatHoverSquadSizes(
        heatmapCellHoverBlocks(model.cells[0][0].recipes, model.bosses[0])[0]!
          .squadSizes,
        false,
      ),
    ).toBe("1–4");
  });

  it("does not sum exclusive self-escort counts into one squad size", () => {
    const model = buildBossHeatmap([
      {
        id: "pmcBEAR",
        slug: "bear",
        name: "BEAR",
        spawn_groups: [
          group({
            maps: [{ slug: "lighthouse", name: "灯塔", spawn_chance: "50%" }],
            shared_spawn_chance: "50%",
            land_label: "开局",
            escorts: [0, 1, 2].map((count) => ({
              slug: "bear",
              name: "BEAR",
              count,
              chance: 1,
            })),
          }),
        ],
      },
    ]);
    expect(
      heatmapCellHoverBlocks(model.cells[0][0].recipes, model.bosses[0])[0]?.squadSizes,
    ).toEqual([
      { size: 1, chance: "50%" },
      { size: 2, chance: "50%" },
      { size: 3, chance: "50%" },
    ]);
  });

  it("counts unique spawn locations instead of recipe repeats", () => {
    const model = buildBossHeatmap([
      {
        id: "PmcBot",
        slug: "raider",
        name: "Raider",
        spawn_groups: [
          group({
            maps: [{ slug: "the-lab", name: "实验室", spawn_chance: "50%" }],
            shared_spawn_chance: "50%",
            locations: [
              {
                map: "实验室",
                map_slug: "the-lab",
                name: "BotZoneA",
                chance: 1,
                positions: [{ x: 1, y: 4, z: 2 }],
              },
              { map: "实验室", map_slug: "the-lab", name: "BotZoneB", chance: 1 },
              { map: "实验室", map_slug: "the-lab", name: "BotZoneC", chance: 1 },
            ],
          }),
        ],
      },
    ]);
    expect(model.cells[0][0]).toMatchObject({
      label: "50%",
      recipeCount: 1,
      locationCount: 3,
    });
    expect(model.cells[0][0].spawnPoints).toEqual([
      { name: "BotZoneA", chance: 1, x: 1, y: 4, z: 2 },
    ]);
  });
});

describe("heatmap spawn map helpers", () => {
  it("uses factory tiles for night factory", () => {
    expect(heatmapMapParentSlug("night-factory")).toBe("factory");
    expect(heatmapMapParentSlug("customs")).toBe("");
  });

  it("keeps one area chip per spawn zone name", () => {
    expect(
      heatmapSpawnLocationOptions([
        { name: "Dorms", chance: 1, x: 1, y: 2, z: 3 },
        { name: "Dorms", chance: 1, x: 4, y: 2, z: 6 },
        { name: "Gas", chance: 0.5, x: 8, y: 0, z: 9 },
      ]),
    ).toEqual([
      { name: "Dorms", chance: 1, x: 2.5, y: 2, z: 4.5 },
      { name: "Gas", chance: 0.5, x: 8, y: 0, z: 9 },
    ]);
  });

  it("does not collapse spawn slots when a zone has several coordinates", () => {
    const points = ["ZoneGateTowerRight", "ZoneGateTowerLeft"].flatMap((name) =>
      [0, 1, 2].map((n) => ({
        name,
        chance: 1,
        x: n,
        y: 0,
        z: n,
      })),
    );
    expect(heatmapSpawnLocationOptions(points)).toHaveLength(2);
    expect(points).toHaveLength(6);
  });
});

describe("buildBossPortraitIndex", () => {
  it("matches escort slug and catalog id", () => {
    const portraits = buildBossPortraitIndex([
      {
        id: "followerBigPipe",
        slug: "big-pipe",
        name: "Big Pipe",
        portrait_link: "https://img/pipe.png",
      },
    ]);
    expect(portraits.get("big-pipe")).toBe("https://img/pipe.png");
    expect(portraits.get("followerbigpipe")).toBe("https://img/pipe.png");
    expect(portraits.get("big pipe")).toBe("https://img/pipe.png");
  });
});

describe("hoverEscortSchemes", () => {
  it("labels icebreaker escort counts as exclusive combos", () => {
    const model = buildBossHeatmap([
      {
        id: "bossBullyBlackDiv",
        slug: "black-div-boss",
        name: "Black Div. Boss",
        spawn_groups: [2, 3, 4].map((count) =>
          group({
            maps: [{ slug: "icebreaker", name: "破冰船", spawn_chance: "100%" }],
            shared_spawn_chance: "100%",
            land_label: "与战局时间无关",
            escorts: [{ slug: "g", name: "保镖", count, chance: 1 }],
          }),
        ),
      },
    ]);
    const schemes = hoverEscortSchemes(
      heatmapCellHoverBlocks(model.cells[0][0].recipes),
    );
    expect(schemes?.map((row) => `组合${row.index}：${row.line}`)).toEqual([
      "组合1：保镖 ×2",
      "组合2：保镖 ×3",
      "组合3：保镖 ×4",
    ]);
    expect(formatHoverAria(heatmapCellHoverBlocks(model.cells[0][0].recipes))).toBe(
      "出生时间：与战局时间无关，出生伴随：组合1：保镖 ×2；组合2：保镖 ×3；组合3：保镖 ×4",
    );
  });

  it("keeps different followers in one wave as a single composition", () => {
    const model = buildBossHeatmap([
      {
        id: "bossKnight",
        slug: "knight",
        name: "Knight",
        spawn_groups: [
          group({
            maps: [{ slug: "customs", name: "海关", spawn_chance: "20%" }],
            escorts: [
              { slug: "p", name: "Pipe", count: 1, chance: 1 },
              { slug: "b", name: "Birdeye", count: 1, chance: 1 },
            ],
          }),
        ],
      },
    ]);
    expect(hoverEscortSchemes(heatmapCellHoverBlocks(model.cells[0][0].recipes))).toBeNull();
  });

  it("splits one wave of count variants into combos", () => {
    const blocks = heatmapCellHoverBlocks([
      {
        chance: "100%",
        chancePct: 100,
        land: "开局",
        escorts: [
          { slug: "g", name: "卫兵", count: 2, chance: 0.5 },
          { slug: "g", name: "卫兵", count: 3, chance: 0.5 },
        ],
        escortLabel: "",
      },
    ]);
    expect(hoverEscortSchemes(blocks)?.map((row) => row.line)).toEqual([
      "卫兵 ×2（50%）",
      "卫兵 ×3（50%）",
    ]);
  });
});

describe("location-specific squad tables", () => {
  it("splits Wedge rooms that do not share a count table", () => {
    const model = buildBossHeatmap([
      {
        id: "bossWedge",
        slug: "the-wedge",
        name: "The Wedge",
        spawn_groups: [
          group({
            maps: [{ slug: "icebreaker", name: "破冰船", spawn_chance: "100%" }],
            shared_spawn_chance: "100%",
            land_label: "与战局时间无关",
            locations: [
              { map: "破冰船", map_slug: "icebreaker", name: "BotZoneRoomsFour", chance: 1 },
              { map: "破冰船", map_slug: "icebreaker", name: "BotZoneRoomsThirdKitchen", chance: 1 },
            ],
          }),
          group({
            maps: [{ slug: "icebreaker", name: "破冰船", spawn_chance: "100%" }],
            shared_spawn_chance: "100%",
            land_label: "与战局时间无关",
            locations: [
              { map: "破冰船", map_slug: "icebreaker", name: "BotZoneRoomsThird", chance: 1 },
              { map: "破冰船", map_slug: "icebreaker", name: "BotZoneRoomsThirdKitchen", chance: 1 },
              { map: "破冰船", map_slug: "icebreaker", name: "BotZoneRoomsFour", chance: 1 },
            ],
            escorts: [{ slug: "the-wedge", name: "The Wedge", count: 1, chance: 1 }],
          }),
          group({
            maps: [{ slug: "icebreaker", name: "破冰船", spawn_chance: "100%" }],
            shared_spawn_chance: "100%",
            land_label: "与战局时间无关",
            locations: [
              { map: "破冰船", map_slug: "icebreaker", name: "BotZoneRoomsThird", chance: 1 },
            ],
            escorts: [{ slug: "the-wedge", name: "The Wedge", count: 2, chance: 1 }],
          }),
        ],
      },
    ]);
    const blocks = heatmapCellHoverBlocks(
      model.cells[0][0].recipes,
      model.bosses[0],
    );
    expect(
      blocks.map((row) => ({
        locations: row.locations,
        sizes: row.squadSizes.map((item) => item.size),
      })),
    ).toEqual([
      {
        locations: ["BotZoneRoomsFour", "BotZoneRoomsThirdKitchen"],
        sizes: [1, 2],
      },
      {
        locations: ["BotZoneRoomsThird"],
        sizes: [2, 3],
      },
    ]);
    expect(formatHoverAria(blocks)).toBe(
      "出生时间：与战局时间无关，出生数量：1–2个，区域：BotZoneRoomsFour、BotZoneRoomsThirdKitchen，出生数量：2–3个，区域：BotZoneRoomsThird",
    );
    expect(hoverSquadCountForLocation(blocks, "BotZoneRoomsThird")).toBe("2–3个");
    expect(hoverSquadCountForLocation(blocks, "BotZoneRoomsFour")).toBe("1–2个");
  });

  it("keeps a shared count table without listing every location", () => {
    const loc = [
      { map: "破冰船", map_slug: "icebreaker", name: "BotZoneEngineHide", chance: 1 },
      { map: "破冰船", map_slug: "icebreaker", name: "BotZoneStern", chance: 1 },
    ];
    const model = buildBossHeatmap([
      {
        id: "bossBullyBlackDiv",
        slug: "black-div-boss",
        name: "Black Div. Boss",
        spawn_groups: [2, 3, 4].map((count) =>
          group({
            maps: [{ slug: "icebreaker", name: "破冰船", spawn_chance: "100%" }],
            shared_spawn_chance: "100%",
            land_label: "与战局时间无关",
            locations: loc,
            escorts: [{ slug: "g", name: "保镖", count, chance: 1 }],
          }),
        ),
      },
    ]);
    const blocks = heatmapCellHoverBlocks(model.cells[0][0].recipes, model.bosses[0]);
    expect(blocks.every((row) => !row.locations?.length)).toBe(true);
    expect(hoverEscortSchemes(blocks)?.map((row) => row.line)).toEqual([
      "保镖 ×2",
      "保镖 ×3",
      "保镖 ×4",
    ]);
  });

  it("lists Black Div raider rooms that only allow some squad sizes", () => {
    const model = buildBossHeatmap([
      {
        id: "pmcBotBlackDiv",
        slug: "black-div-raider",
        name: "Black Div. Raider",
        spawn_groups: [
          group({
            maps: [{ slug: "icebreaker", name: "破冰船", spawn_chance: "100%" }],
            locations: [
              { map: "破冰船", map_slug: "icebreaker", name: "BotZoneSternTop", chance: 1 },
              { map: "破冰船", map_slug: "icebreaker", name: "BotZoneStern", chance: 1 },
              { map: "破冰船", map_slug: "icebreaker", name: "BotZoneOutside_t3", chance: 1 },
            ],
            escorts: [{ slug: "black-div-raider", name: "Black Div. Raider", count: 2, chance: 1 }],
          }),
          group({
            maps: [{ slug: "icebreaker", name: "破冰船", spawn_chance: "100%" }],
            locations: [
              { map: "破冰船", map_slug: "icebreaker", name: "BotZoneSternTop", chance: 1 },
              { map: "破冰船", map_slug: "icebreaker", name: "BotZoneStern", chance: 1 },
            ],
            escorts: [{ slug: "black-div-raider", name: "Black Div. Raider", count: 3, chance: 1 }],
          }),
          group({
            maps: [{ slug: "icebreaker", name: "破冰船", spawn_chance: "100%" }],
            locations: [
              { map: "破冰船", map_slug: "icebreaker", name: "BotZoneSternTop", chance: 1 },
              { map: "破冰船", map_slug: "icebreaker", name: "BotZoneStern", chance: 1 },
              { map: "破冰船", map_slug: "icebreaker", name: "BotZoneInside_t4", chance: 1 },
            ],
            escorts: [{ slug: "black-div-raider", name: "Black Div. Raider", count: 4, chance: 1 }],
          }),
        ],
      },
    ]);
    const blocks = heatmapCellHoverBlocks(
      model.cells[0][0].recipes,
      model.bosses[0],
    );
    expect(
      blocks.map((row) => ({
        locations: row.locations,
        sizes: row.squadSizes.map((item) => item.size),
      })),
    ).toEqual([
      {
        locations: ["BotZoneSternTop", "BotZoneStern"],
        sizes: [3, 4, 5],
      },
      {
        locations: ["BotZoneOutside_t3"],
        sizes: [3],
      },
      {
        locations: ["BotZoneInside_t4"],
        sizes: [5],
      },
    ]);
    expect(hoverSquadCountForLocation(blocks, "BotZoneOutside_t3")).toBe("3个");
    expect(hoverSquadCountForLocation(blocks, "BotZoneInside_t4")).toBe("5个");
    expect(hoverSquadCountForLocation(blocks, "BotZoneStern")).toBe("3–5个");
  });
});
