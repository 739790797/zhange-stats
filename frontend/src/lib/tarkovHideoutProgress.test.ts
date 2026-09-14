import { describe, expect, it } from "vitest";
import {
  aggregateHideoutUpgradeRanges,
  aggregateReadyHideoutUpgradeItems,
  applyHideoutLevel,
  buildHideoutBonusTable,
  canSetHideoutLevel,
  clampHideoutUpgradeRange,
  defaultHideoutCalcRange,
  filledHideoutLevels,
  formatHideoutBonusCell,
  formatHideoutBonusValue,
  formatHideoutUpgradeStation,
  hideoutBonusLabel,
  hideoutCatalogMinLevel,
  hideoutDefaultLevel,
  hideoutItemNeedsFleaBuy,
  hideoutLevelChoices,
  hideoutUpgradeFleaCost,
  hideoutUpgradeMaterialItems,
  indexHideoutStations,
  isHideoutMoneyItem,
  partitionHideoutStations,
  skillReqMet,
  traderReqMet,
  TARKOV_ROUBLE_ITEM_ID,
  type HideoutStationSpec,
} from "./tarkovHideoutProgress";

function catalog(): HideoutStationSpec[] {
  return [
    {
      id: "stash",
      slug: "stash",
      levels: [
        { level: 1, station_requirements: [] },
        { level: 2, station_requirements: [{ station_id: "gen", level: 1 }] },
      ],
    },
    {
      id: "gen",
      slug: "generator",
      levels: [
        { level: 1, station_requirements: [] },
        { level: 2, station_requirements: [{ station_id: "stash", level: 2 }] },
      ],
    },
    {
      id: "bench",
      slug: "workbench",
      levels: [
        { level: 1, station_requirements: [{ station_id: "gen", level: 1 }] },
        { level: 2, station_requirements: [{ station_id: "gen", level: 2 }] },
      ],
    },
  ];
}

describe("tarkovHideoutProgress", () => {
  it("defaults stash to 1 and other stations to 0", () => {
    const levels = filledHideoutLevels(catalog(), {});
    expect(levels.stash).toBe(1);
    expect(levels.gen).toBe(0);
    expect(levels.bench).toBe(0);
    expect(hideoutDefaultLevel({ slug: "stash" })).toBe(1);
  });

  it("does not gate upgrades on item requirements", () => {
    const stations: HideoutStationSpec[] = [
      {
        id: "gen",
        slug: "generator",
        levels: [
          { level: 1, item_requirements: [{ id: "screw", count: 10 }] },
        ],
      },
    ];
    const levels = filledHideoutLevels(stations, {});
    const byId = indexHideoutStations(stations);
    expect(canSetHideoutLevel(byId.get("gen"), 1, levels, byId)).toBe(true);
  });

  it("partitions by whether the next station level is ready", () => {
    const stations = catalog();
    const byId = indexHideoutStations(stations);
    const start = filledHideoutLevels(stations, {});
    expect(partitionHideoutStations(stations, start, byId)).toEqual({
      ready: [stations[1]],
      blocked: [stations[0], stations[2]],
      maxed: [],
    });
    const afterGen = applyHideoutLevel(stations, start, "gen", 1);
    expect(partitionHideoutStations(stations, afterGen, byId)).toEqual({
      ready: [stations[0], stations[2]],
      blocked: [stations[1]],
      maxed: [],
    });
    const maxed = filledHideoutLevels(stations, {
      stash: 2,
      gen: 2,
      bench: 2,
    });
    expect(partitionHideoutStations(stations, maxed, byId)).toEqual({
      ready: [],
      blocked: [],
      maxed: stations,
    });
  });

  it("blocks upgrade until station prereqs hold", () => {
    const stations = catalog();
    const levels = filledHideoutLevels(stations, {});
    const byId = indexHideoutStations(stations);
    expect(canSetHideoutLevel(byId.get("bench"), 1, levels, byId)).toBe(false);
    expect(() => applyHideoutLevel(stations, levels, "bench", 1)).toThrow(
      /前置/,
    );
    const next = applyHideoutLevel(stations, levels, "gen", 1);
    expect(next.gen).toBe(1);
    expect(applyHideoutLevel(stations, next, "bench", 1).bench).toBe(1);
  });

  it("cascades dependents on downgrade", () => {
    const stations = catalog();
    const start = filledHideoutLevels(stations, {
      stash: 2,
      gen: 2,
      bench: 2,
    });
    const mid = applyHideoutLevel(stations, start, "gen", 1);
    expect(mid).toEqual({ stash: 2, gen: 1, bench: 1 });
    expect(applyHideoutLevel(stations, mid, "gen", 0)).toEqual({
      stash: 1,
      gen: 0,
      bench: 0,
    });
  });

  it("clamps stash to at least 1", () => {
    const stations = catalog();
    expect(applyHideoutLevel(stations, { stash: 1 }, "stash", 0).stash).toBe(1);
  });

  it("keeps trader/skill unset until user data exists", () => {
    expect(traderReqMet({ slug: "prapor", level: 2 }, undefined)).toBeNull();
    expect(skillReqMet({ skill_id: "HideoutManagement", level: 5 }, undefined)).toBeNull();
    expect(traderReqMet({ slug: "prapor", level: 2 }, { prapor: 2 })).toBe(true);
    expect(traderReqMet({ slug: "prapor", level: 2 }, { prapor: 1 })).toBe(false);
    expect(traderReqMet({ slug: "prapor", level: 2 }, { mechanic: 4 })).toBeNull();
  });

  it("gives EOD stash floor 4 without station prereqs", () => {
    const stations: HideoutStationSpec[] = [
      {
        id: "stash",
        slug: "stash",
        levels: [
          { level: 1, station_requirements: [] },
          { level: 2, station_requirements: [{ station_id: "gen", level: 1 }] },
          { level: 3, station_requirements: [{ station_id: "gen", level: 2 }] },
          { level: 4, station_requirements: [{ station_id: "gen", level: 3 }] },
        ],
      },
      {
        id: "gen",
        slug: "generator",
        levels: [{ level: 1, station_requirements: [] }],
      },
    ];
    const levels = filledHideoutLevels(stations, {}, 4);
    expect(levels.stash).toBe(4);
    expect(hideoutDefaultLevel(stations[0], 4)).toBe(4);
    expect(applyHideoutLevel(stations, levels, "stash", 3, 4).stash).toBe(4);
    const byId = indexHideoutStations(stations);
    expect(canSetHideoutLevel(byId.get("stash"), 3, levels, byId, 4)).toBe(false);
  });

  it("formats bonus values", () => {
    expect(formatHideoutBonusValue("ExperienceRate", 0.15)).toBe("+15%");
    expect(formatHideoutBonusValue("FuelConsumption", -0.5)).toBe("-50%");
    expect(formatHideoutBonusValue("StashSize", 300)).toBe("+300");
    expect(formatHideoutBonusValue("UnlockArmorRepair", 1)).toBe("解锁");
    expect(formatHideoutBonusCell("EnergyRegeneration", null)).toBe("—");
    expect(formatHideoutBonusCell("EnergyRegeneration", 0.08)).toBe("+8%");
  });

  it("builds a per-level bonus table and carries undeclared bonuses forward", () => {
    const station: HideoutStationSpec = {
      id: "intel",
      slug: "intelligence-center",
      levels: [
        {
          level: 1,
          bonuses: [
            { type: "ScavCooldownTimer", name: "Scav冷却时间", value: -0.15 },
            { type: "QuestMoneyReward", name: "任务金钱奖励", value: 0.05 },
          ],
        },
        {
          level: 2,
          bonuses: [
            { type: "QuestMoneyReward", name: "任务金钱奖励", value: 0.1 },
            { type: "InsuranceReturnTime", name: "保险返还时间", value: -0.2 },
          ],
        },
        {
          level: 3,
          bonuses: [
            { type: "ScavCooldownTimer", name: "Scav冷却时间", value: -0.2 },
            { type: "RagfairCommission", name: "跳蚤市场税率", value: -0.3 },
          ],
        },
      ],
    };
    const table = buildHideoutBonusTable(station);
    expect(table.levels).toEqual([1, 2, 3]);
    expect(table.rows.map((row) => row.type)).toEqual([
      "ScavCooldownTimer",
      "QuestMoneyReward",
      "InsuranceReturnTime",
      "RagfairCommission",
    ]);
    expect(table.rows[0].values).toEqual([-0.15, -0.15, -0.2]);
    expect(table.rows[1].values).toEqual([0.05, 0.1, 0.1]);
    expect(table.rows[2].values).toEqual([null, -0.2, -0.2]);
    expect(table.rows[3].values).toEqual([null, null, -0.3]);
  });

  it("splits skill-group bonuses and restates heating-style values", () => {
    const station: HideoutStationSpec = {
      id: "heat",
      slug: "heating",
      levels: [
        {
          level: 1,
          bonuses: [{ type: "EnergyRegeneration", name: "能量恢复速率", value: 0.04 }],
        },
        {
          level: 2,
          bonuses: [{ type: "EnergyRegeneration", name: "能量恢复速率", value: 0.08 }],
        },
        {
          level: 3,
          bonuses: [
            { type: "EnergyRegeneration", name: "能量恢复速率", value: 0.12 },
            { type: "DebuffEndDelay", name: "负面效果消退", value: -0.5 },
          ],
        },
      ],
    };
    const heating = buildHideoutBonusTable(station);
    expect(heating.rows).toHaveLength(2);
    expect(heating.rows[0].values).toEqual([0.04, 0.08, 0.12]);
    expect(heating.rows[1].values).toEqual([null, null, -0.5]);
    const air: HideoutStationSpec = {
      id: "air",
      levels: [
        {
          level: 1,
          bonuses: [
            {
              type: "SkillGroupLevelingBoost",
              name: "技能组升级加速",
              skill: "Physical",
              value: 0.4,
            },
            {
              type: "SkillGroupLevelingBoost",
              name: "技能组升级加速",
              skill: "Combat",
              value: 0.1,
            },
          ],
        },
      ],
    };
    const rows = buildHideoutBonusTable(air).rows;
    expect(rows).toHaveLength(2);
    expect(hideoutBonusLabel(rows[0])).toBe("技能组升级加速（Physical）");
    expect(buildHideoutBonusTable({ id: "gym", levels: [{ level: 1 }] }).rows).toEqual(
      [],
    );
  });

  it("aggregates next-level items of ready stations", () => {
    const stations: HideoutStationSpec[] = [
      {
        id: "med",
        slug: "medstation",
        name: "医疗站",
        levels: [
          {
            level: 1,
            item_requirements: [
              { id: "screw", name: "螺丝", count: 2, flea_price: 100 },
              { id: "ai2", name: "AI-2", count: 1, found_in_raid: true },
            ],
          },
        ],
      },
      {
        id: "wc",
        slug: "lavatory",
        name: "卫生间",
        levels: [
          {
            level: 1,
            item_requirements: [
              { id: "screw", name: "螺丝", count: 3, flea_price: 120 },
              { id: "ai2", name: "AI-2", count: 2 },
            ],
          },
        ],
      },
      {
        id: "intel",
        slug: "intelligence-center",
        name: "情报中心",
        levels: [
          {
            level: 1,
            station_requirements: [{ station_id: "med", level: 1 }],
            item_requirements: [{ id: "gpu", name: "显卡", count: 1 }],
          },
        ],
      },
    ];
    const levels = filledHideoutLevels(stations, {});
    const byId = indexHideoutStations(stations);
    const { ready, blocked } = partitionHideoutStations(stations, levels, byId);
    expect(ready.map((row) => row.id)).toEqual(["med", "wc"]);
    expect(blocked.map((row) => row.id)).toEqual(["intel"]);
    const needs = aggregateReadyHideoutUpgradeItems(ready, levels);
    expect(needs).toHaveLength(3);
    const screw = needs.find((row) => row.id === "screw" && !row.found_in_raid);
    const ai2 = needs.find((row) => row.id === "ai2" && !row.found_in_raid);
    const ai2Fir = needs.find((row) => row.id === "ai2" && row.found_in_raid);
    expect(ai2).toEqual(
      expect.objectContaining({
        id: "ai2",
        found_in_raid: false,
        count: 2,
        stations: [expect.objectContaining({ id: "wc", level: 1, slug: "lavatory" })],
      }),
    );
    expect(ai2Fir).toEqual(
      expect.objectContaining({
        id: "ai2",
        found_in_raid: true,
        count: 1,
        stations: [expect.objectContaining({ id: "med", level: 1 })],
      }),
    );
    expect(screw).toEqual(
      expect.objectContaining({
        id: "screw",
        count: 5,
        flea_price: 100,
        stations: [
          expect.objectContaining({ id: "med", name: "医疗站" }),
          expect.objectContaining({ id: "wc", name: "卫生间" }),
        ],
      }),
    );
    expect(aggregateReadyHideoutUpgradeItems([], levels)).toEqual([]);
    expect(
      aggregateReadyHideoutUpgradeItems(
        [
          {
            id: "empty",
            name: "空",
            levels: [{ level: 1, item_requirements: [{ name: "无 id", count: 3 }] }],
          },
        ],
        { empty: 0 },
      ),
    ).toEqual([]);
  });

  it("only includes the next ready level, not later ones", () => {
    const stations: HideoutStationSpec[] = [
      {
        id: "gen",
        slug: "generator",
        name: "发电机",
        levels: [
          { level: 1, item_requirements: [{ id: "a", name: "A", count: 1 }] },
          { level: 2, item_requirements: [{ id: "b", name: "B", count: 4 }] },
          { level: 3, item_requirements: [{ id: "c", name: "C", count: 9 }] },
        ],
      },
    ];
    const levels = filledHideoutLevels(stations, { gen: 1 });
    const needs = aggregateReadyHideoutUpgradeItems(stations, levels);
    expect(needs).toEqual([
      expect.objectContaining({
        id: "b",
        count: 4,
        stations: [expect.objectContaining({ id: "gen", level: 2 })],
      }),
    ]);
  });

  it("sums a custom N to M range across stations", () => {
    const stations: HideoutStationSpec[] = [
      {
        id: "med",
        slug: "medstation",
        name: "医疗站",
        levels: [
          { level: 1, item_requirements: [{ id: "bandage", name: "绷带", count: 1 }] },
          { level: 2, item_requirements: [{ id: "bandage", name: "绷带", count: 2 }] },
          { level: 3, item_requirements: [{ id: "saline", name: "生理盐水", count: 4 }] },
        ],
      },
      {
        id: "wc",
        slug: "lavatory",
        name: "卫生间",
        levels: [
          { level: 1, item_requirements: [{ id: "soap", name: "肥皂", count: 1 }] },
        ],
      },
    ];
    expect(aggregateHideoutUpgradeRanges(stations, [{ stationId: "med", from: 0, to: 1 }])).toEqual([
      expect.objectContaining({
        id: "bandage",
        count: 1,
        stations: [expect.objectContaining({ id: "med", from: 0, to: 1 })],
      }),
    ]);
    const spanned = aggregateHideoutUpgradeRanges(stations, [
      { stationId: "med", from: 0, to: 3 },
      { stationId: "wc", from: 0, to: 1 },
    ]);
    expect(spanned.find((row) => row.id === "bandage")).toEqual(
      expect.objectContaining({
        count: 3,
        stations: [expect.objectContaining({ name: "医疗站", from: 0, to: 3 })],
      }),
    );
    expect(spanned.find((row) => row.id === "saline")?.count).toBe(4);
    expect(spanned.find((row) => row.id === "soap")?.count).toBe(1);
    expect(aggregateHideoutUpgradeRanges(stations, [{ stationId: "med", from: 2, to: 2 }])).toEqual([]);
    expect(
      formatHideoutUpgradeStation({
        id: "med",
        name: "医疗站",
        slug: "medstation",
        level: 3,
        from: 0,
        to: 3,
      }),
    ).toBe("医疗站 0→3");
  });

  it("lets the calculator pick any catalog range, ignoring current stash level", () => {
    const gen: HideoutStationSpec = {
      id: "gen",
      slug: "generator",
      levels: [{ level: 1 }, { level: 2 }, { level: 3 }],
    };
    expect(hideoutCatalogMinLevel(gen)).toBe(0);
    expect(hideoutLevelChoices(gen)).toEqual([0, 1, 2, 3]);
    expect(defaultHideoutCalcRange(gen)).toEqual({ from: 0, to: 1 });
    const stash: HideoutStationSpec = {
      id: "stash",
      slug: "stash",
      levels: [
        { level: 1, item_requirements: [{ id: "s1", name: "仓库1", count: 1 }] },
        { level: 2, item_requirements: [{ id: "s2", name: "仓库2", count: 2 }] },
        { level: 3, item_requirements: [{ id: "s3", name: "仓库3", count: 3 }] },
        { level: 4, item_requirements: [{ id: "s4", name: "仓库4", count: 4 }] },
      ],
    };
    expect(hideoutCatalogMinLevel(stash)).toBe(1);
    expect(hideoutLevelChoices(stash)).toEqual([1, 2, 3, 4]);
    expect(defaultHideoutCalcRange(stash)).toEqual({ from: 1, to: 2 });
    expect(clampHideoutUpgradeRange(stash, 1, 4)).toEqual({ from: 1, to: 4 });
    expect(
      aggregateHideoutUpgradeRanges([stash], [{ stationId: "stash", from: 1, to: 4 }]).map(
        (row) => ({ id: row.id, count: row.count }),
      ),
    ).toEqual([
      { id: "s2", count: 2 },
      { id: "s3", count: 3 },
      { id: "s4", count: 4 },
    ]);
  });

  it("treats dump money ids and money types as cash", () => {
    expect(isHideoutMoneyItem({ id: TARKOV_ROUBLE_ITEM_ID })).toBe(true);
    expect(isHideoutMoneyItem({ id: "5696686a4bdc2da3298b456a" })).toBe(true);
    expect(isHideoutMoneyItem({ id: "wire", types: ["money"] })).toBe(true);
    expect(isHideoutMoneyItem({ id: "wire" })).toBe(false);
  });

  it("puts dump construction cash first and does not add flea buyout", () => {
    const rows = hideoutUpgradeMaterialItems([
      { id: "wire", name: "电线", count: 10, flea_price: 24000 },
      {
        id: TARKOV_ROUBLE_ITEM_ID,
        name: "卢布",
        count: 50000,
        types: ["money"],
        flea_price: 1,
      },
    ]);
    expect(rows.map((row) => ({ id: row.id, count: row.count }))).toEqual([
      { id: TARKOV_ROUBLE_ITEM_ID, count: 50000 },
      { id: "wire", count: 10 },
    ]);
    expect(
      hideoutUpgradeMaterialItems([
        { id: "hose", name: "软管", count: 2, flea_price: 14000 },
      ]).map((row) => row.id),
    ).toEqual(["hose"]);
  });

  it("excludes construction cash and found-in-raid items from the flea shopping total", () => {
    expect(hideoutItemNeedsFleaBuy({ id: "wire" })).toBe(true);
    expect(
      hideoutItemNeedsFleaBuy({ id: "drill", found_in_raid: true }),
    ).toBe(false);
    expect(
      hideoutItemNeedsFleaBuy({
        id: TARKOV_ROUBLE_ITEM_ID,
        types: ["money"],
      }),
    ).toBe(false);
    expect(
      hideoutUpgradeFleaCost([
        { id: "wire", name: "电线", count: 10, flea_price: 24000 },
        {
          id: TARKOV_ROUBLE_ITEM_ID,
          name: "卢布",
          count: 50000,
          types: ["money"],
          flea_price: 1,
        },
        {
          id: "drill",
          name: "电钻",
          count: 1,
          found_in_raid: true,
          flea_price: 85420,
        },
      ]),
    ).toBe(240000);
    expect(
      hideoutUpgradeFleaCost([
        { id: "wire", name: "电线", count: 1, flea_price: 100 },
        { id: "ai2", name: "AI-2", count: 1, found_in_raid: true },
      ]),
    ).toBe(100);
  });

  it("keeps construction cash alone when there are no other items", () => {
    expect(
      hideoutUpgradeMaterialItems([
        { id: TARKOV_ROUBLE_ITEM_ID, name: "卢布", count: 25000, types: ["money"] },
      ]),
    ).toEqual([
      expect.objectContaining({ id: TARKOV_ROUBLE_ITEM_ID, count: 25000 }),
    ]);
  });
});
