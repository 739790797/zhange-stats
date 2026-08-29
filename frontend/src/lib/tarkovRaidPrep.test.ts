import { describe, expect, it } from "vitest";
import {
  buildRaidPrepOverlays,
  resolveRaidPrepLocatePoint,
  buildRaidPrepSummary,
  clusterRaidPrepOverlayLabels,
  colorForTaskIndex,
  collectRaidPrepTaskItems,
  collectRaidPrepTaskKeys,
  collectRaidPrepSummaryTypeColumns,
  collectRaidPrepTaskShootSlots,
  raidPrepObjectiveCount,
  expandRaidPrepSummaryItemLines,
  raidPrepSummaryHasBringTypes,
  raidPrepSummaryHasShootTypes,
  collectRaidPrepTaskObjectiveLines,
  collectRaidPrepTaskObjectives,
  formatRaidPrepKeyNeedLine,
  parseRaidPrepObjectiveDone,
  serializeRaidPrepObjectiveDone,
  toggleRaidPrepObjectiveDone,
  filterRaidPrepRows,
  isGarbledTarkovName,
  isTarkovHexId,
  mapLayerFloorBands,
  mapSlugKeys,
  locationHitsMap,
  neededKeyNamesForMap,
  normalizeRaidPrepMapId,
  objectiveAppliesToMap,
  objectiveZoneNames,
  overlayFloorNames,
  overlayFloorForSpan,
  overlayFloorForPoint,
  overlayVisibleOnFloor,
  parseCsvParam,
  partitionRaidPrepRows,
  pinSelectedRaidPrepRows,
  raidPrepMapOptions,
  collectRaidPrepQuestFilterPeople,
  raidPrepParticipants,
  raidPrepPersonKey,
  raidPrepQuestOverlayVisible,
  resolveRaidPrepLocatePoints,
  selectedTasksFromCatalog,
  serializeSelectedIds,
  sortRaidPrepSummaryByParticipants,
  displayRaidPrepTaskName,
  formatRaidPrepParticipantLine,
  raidPrepParticipantNames,
  tarkovReadableName,
  traderFilterLabel,
  type RaidPrepTaskLike,
  type TarkovRaidPrepOverlay,
  RAID_PREP_TASK_COLORS,
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
    expect(normalizeRaidPrepMapId("bigmap")).toBe("customs");
    expect([...mapSlugKeys("customs")].sort()).toEqual(["bigmap", "customs"]);
    expect(normalizeRaidPrepMapId("nope")).toBe("");
  });

  it("inserts night factory after factory", () => {
    const ids = raidPrepMapOptions().map((item) => item.id);
    expect(ids).toContain("customs");
    expect(ids.indexOf("night-factory")).toBe(ids.indexOf("factory") + 1);
  });

  it("treats customs aliases and 海关 names as the same map", () => {
    expect(locationHitsMap({ map_slug: "bigmap" }, "customs")).toBe(true);
    expect(locationHitsMap({ map_name: "海关" }, "customs")).toBe(true);
    expect(locationHitsMap({ map_slug: "woods" }, "customs")).toBe(false);
  });
});

describe("raid prep participant line", () => {
  it("joins unique names with 顿号", () => {
    expect(
      formatRaidPrepParticipantLine(raidPrepParticipantNames([
        { name: "甲" },
        { name: " 乙 " },
        { name: "甲" },
        { name: "" },
      ])),
    ).toBe("有哪些用户参与该任务：甲、乙");
  });

  it("shows 暂无 when nobody claimed the task", () => {
    expect(formatRaidPrepParticipantLine([])).toBe(
      "有哪些用户参与该任务：暂无",
    );
    expect(raidPrepParticipantNames(undefined)).toEqual([]);
  });

  it("keeps userId for map chips and dedupes by person", () => {
    expect(
      raidPrepParticipants([
        { name: "Ra1nY", userId: 7 },
        { name: "Ra1nY", userId: 7 },
        { name: "乙", userId: 8 },
        { name: "" },
      ]),
    ).toEqual([
      { name: "Ra1nY", userId: 7 },
      { name: "乙", userId: 8 },
    ]);
  });

  it("filters quest overlays by selected people", () => {
    const byTask = new Map([
      ["t1", [{ name: "甲", userId: 1 }, { name: "乙", userId: 2 }]],
      ["t2", [{ name: "乙", userId: 2 }]],
    ]);
    const people = collectRaidPrepQuestFilterPeople(byTask);
    expect(people.map((row) => raidPrepPersonKey(row))).toEqual(["id:1", "id:2"]);
    const onlyJia = new Set(["id:1"]);
    expect(
      raidPrepQuestOverlayVisible(raidPrepParticipants(byTask.get("t1")), onlyJia),
    ).toBe(true);
    expect(
      raidPrepQuestOverlayVisible(raidPrepParticipants(byTask.get("t2")), onlyJia),
    ).toBe(false);
    expect(raidPrepQuestOverlayVisible([], onlyJia)).toBe(true);
    expect(raidPrepQuestOverlayVisible(people, new Set())).toBe(false);
    expect(raidPrepQuestOverlayVisible(people, null)).toBe(true);
  });
});

describe("selected ids", () => {
  it("parses and caps selected task ids", () => {
    expect(parseCsvParam("a, b,,a")).toEqual(["a", "b"]);
    expect(serializeSelectedIds(["x", "x", "y"])).toBe("x,y");
  });

  it("pins checked tasks to the top without shuffling groups", () => {
    const rows = [{ id: "a" }, { id: "b" }, { id: "c" }, { id: "d" }];
    expect(pinSelectedRaidPrepRows(rows, new Set()).map((row) => row.id)).toEqual(
      ["a", "b", "c", "d"],
    );
    expect(
      pinSelectedRaidPrepRows(rows, new Set(["c", "b"])).map((row) => row.id),
    ).toEqual(["b", "c", "a", "d"]);
    expect(
      pinSelectedRaidPrepRows(rows, new Set(["missing"])).map((row) => row.id),
    ).toEqual(["a", "b", "c", "d"]);
  });

  it("keeps selected tasks outside the current filter", () => {
    const filtered = [{ id: "a" }, { id: "b" }];
    const picked = selectedTasksFromCatalog(
      [{ id: "a" }, { id: "b" }, { id: "c" }],
      ["c", "a", "missing"],
    );
    expect(picked.map((row) => row.id)).toEqual(["c", "a"]);
    expect(
      partitionRaidPrepRows(filtered, picked).rest.map((row) => row.id),
    ).toEqual(["b"]);
    expect(partitionRaidPrepRows(filtered, []).picked).toEqual([]);
  });
});

describe("buildRaidPrepOverlays", () => {
  const task: RaidPrepTaskLike = {
    id: "t1",
    name: "Debut",
    trader_slug: "prapor",
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
      title: "Debut 1",
      traderSlug: "prapor",
      keyNames: [],
      showNoKey: false,
      optional: false,
      outline: [
        { x: 0, z: 0 },
        { x: 4, z: 0 },
        { x: 4, z: 4 },
      ],
      points: [{ x: 1, z: 2 }],
    });
    expect(overlays[1]).toMatchObject({
      kind: "spawn",
      title: "Debut 2",
      keyNames: [],
      showNoKey: false,
      optional: false,
      points: [{ x: 10, z: 20 }],
    });
    expect(overlays[0].color).toBe(colorForTaskIndex(0));
    expect(objectiveZoneNames(task)).toEqual(["Dorms"]);
    expect(neededKeyNamesForMap(task, "customs")).toEqual(["Dorm 114"]);
    expect(neededKeyNamesForMap(task, "streets")).toEqual([]);
  });

  it("does not hang task-level keys on a point whose objective has none", () => {
    const mixed: RaidPrepTaskLike = {
      id: "t-mix",
      name: "逃跑",
      needed_keys: [
        {
          map: { slug: "customs" },
          keys: [{ name: "Dorm 114" }],
        },
      ],
      objectives: [
        {
          id: "o-open",
          type: "visit",
          description: "open 114",
          required_keys: [[{ name: "Dorm 114" }]],
          zones: [{ id: "z-114", map_slug: "customs", x: 1, z: 1 }],
        },
        {
          id: "o-visit",
          type: "visit",
          description: "reach the yard",
          zones: [{ id: "z-yard", map_slug: "customs", x: 40, z: 40 }],
        },
      ],
    };
    const overlays = buildRaidPrepOverlays([mixed], "customs");
    expect(overlays.map((row) => row.title)).toEqual(["逃跑 1", "逃跑 2"]);
    expect(overlays[0]).toMatchObject({
      keyNames: ["Dorm 114"],
      showNoKey: false,
    });
    expect(overlays[1]).toMatchObject({
      keyNames: [],
      showNoKey: true,
    });
  });

  it("formats a needed-key line without doubling 钥匙", () => {
    expect(formatRaidPrepKeyNeedLine(["Dorm 114"])).toBe("需要Dorm 114钥匙");
    expect(formatRaidPrepKeyNeedLine(["TerraGroup 会议室钥匙"])).toBe(
      "需要TerraGroup 会议室钥匙",
    );
    expect(formatRaidPrepKeyNeedLine(["宿舍114", "RB-OB钥匙"])).toBe(
      "需要宿舍114钥匙、RB-OB钥匙",
    );
    expect(formatRaidPrepKeyNeedLine([])).toBe("");
  });

  it("leaves a single-point task unnumbered", () => {
    const overlays = buildRaidPrepOverlays(
      [
        {
          id: "t-one",
          name: "Debut",
          objectives: [
            {
              id: "o-visit",
              type: "visit",
              zones: [{ id: "z1", map_slug: "customs", x: 1, z: 2 }],
            },
          ],
        },
      ],
      "customs",
    );
    expect(overlays).toHaveLength(1);
    expect(overlays[0].title).toBe("Debut");
  });

  it("marks optional objectives and prefers their required_keys", () => {
    const optionalTask: RaidPrepTaskLike = {
      id: "t-opt",
      name: "Shortage",
      trader_slug: "therapist",
      needed_keys: [
        {
          map: { slug: "customs" },
          keys: [{ name: "Task-level key" }],
        },
      ],
      objectives: [
        {
          id: "o-opt",
          type: "visit",
          description: "find ambulance",
          optional: true,
          required_keys: [[{ name: "Dorm 114" }]],
          zones: [
            {
              id: "z-amb",
              map_slug: "customs",
              x: 5,
              z: 5,
            },
          ],
        },
      ],
    };
    const overlays = buildRaidPrepOverlays([optionalTask], "customs");
    expect(overlays).toHaveLength(1);
    expect(overlays[0]).toMatchObject({
      optional: true,
      keyNames: ["Dorm 114"],
      subtitle: expect.stringContaining("find ambulance"),
    });
  });

  it("drops skipped objectives from the map and remaining keys", () => {
    const mixed: RaidPrepTaskLike = {
      id: "t-storage",
      name: "备储专家",
      needed_keys: [
        {
          map: { slug: "customs" },
          keys: [{ id: "rb-ob", name: "RB-OB钥匙" }],
        },
      ],
      objectives: [
        {
          id: "o-key",
          type: "visit",
          description: "检查兵营东楼黑",
          required_keys: [[{ id: "rb-ob", name: "RB-OB钥匙" }]],
          zones: [{ id: "z-east", map_slug: "customs", x: 1, z: 1 }],
        },
        {
          id: "o-free",
          type: "visit",
          description: "检查兵营南楼白",
          zones: [{ id: "z-south", map_slug: "customs", x: 40, z: 40 }],
        },
      ],
    };
    const skipped = new Map([["t-storage", new Set(["o-key"])]]);
    const overlays = buildRaidPrepOverlays([mixed], "customs", skipped);
    expect(overlays).toHaveLength(1);
    expect(overlays[0]).toMatchObject({
      title: "备储专家",
      keyNames: [],
      showNoKey: false,
      subtitle: expect.stringContaining("检查兵营南楼白"),
    });
    expect(collectRaidPrepTaskKeys(mixed, "customs", new Set(["o-key"]))).toEqual(
      [],
    );
    expect(
      collectRaidPrepTaskKeys(mixed, "customs", new Set(["o-free"])).map(
        (item) => item.name,
      ),
    ).toEqual(["RB-OB钥匙"]);
    expect(resolveRaidPrepLocatePoints(mixed, "customs", new Set(["o-key"]))).toEqual(
      [{ x: 40, z: 40 }],
    );
  });
});

describe("resolveRaidPrepLocatePoint", () => {
  it("prefers the first non-optional marker on the current map", () => {
    const task: RaidPrepTaskLike = {
      id: "t-locate",
      name: "Locate me",
      objectives: [
        {
          id: "o-opt",
          optional: true,
          zones: [
            {
              id: "z-opt",
              map_slug: "customs",
              x: 1,
              z: 1,
            },
          ],
        },
        {
          id: "o-main",
          optional: false,
          possible_locations: [
            {
              map_slug: "customs",
              positions: [{ x: 9, z: 8 }],
            },
          ],
        },
      ],
    };
    expect(resolveRaidPrepLocatePoint(task, "customs")).toEqual({
      x: 9,
      z: 8,
    });
  });

  it("falls back to optional markers when no required point exists", () => {
    const task: RaidPrepTaskLike = {
      id: "t-opt-only",
      name: "Optional only",
      objectives: [
        {
          id: "o-opt",
          optional: true,
          zones: [
            {
              id: "z-opt",
              map_slug: "customs",
              x: 3,
              z: 4,
            },
          ],
        },
      ],
    };
    expect(resolveRaidPrepLocatePoint(task, "customs")).toEqual({
      x: 3,
      z: 4,
    });
  });

  it("ignores markers on other maps", () => {
    const task: RaidPrepTaskLike = {
      id: "t-other",
      name: "Other map",
      objectives: [
        {
          id: "o-main",
          zones: [
            {
              id: "z-other",
              map_slug: "streets",
              x: 5,
              z: 5,
            },
          ],
        },
      ],
    };
    expect(resolveRaidPrepLocatePoint(task, "customs")).toBeNull();
  });
});

describe("readable item names", () => {
  it("hides hex ids that leaked through as names", () => {
    expect(isTarkovHexId("5a9f913a86f77472bf74a592")).toBe(true);
    expect(tarkovReadableName("5a9f913a86f77472bf74a592")).toBe("");
    expect(
      tarkovReadableName("5a9f913a86f77472bf74a592", "5a9f913a86f77472bf74a592"),
    ).toBe("");
    expect(tarkovReadableName("宿舍 114 钥匙", "5a9f913a86f77472bf74a592")).toBe(
      "宿舍 114 钥匙",
    );
    expect(isGarbledTarkovName("????")).toBe(true);
    expect(isGarbledTarkovName("？？？？")).toBe(true);
    expect(tarkovReadableName("????", "abc")).toBe("");
    expect(tarkovReadableName("首秀", "abc")).toBe("首秀");
    expect(
      displayRaidPrepTaskName({
        id: "t1",
        name: "????",
        normalized_name: "debut",
      }),
    ).toBe("debut");
  });

  it("skips unresolved key ids on the task card", () => {
    const task: RaidPrepTaskLike = {
      id: "t-keys",
      needed_keys: [
        {
          map: { slug: "customs" },
          keys: [
            { id: "5a9f913a86f77472bf74a592", name: "5a9f913a86f77472bf74a592" },
            { id: "k114", name: "Dorm 114" },
          ],
        },
      ],
    };
    expect(neededKeyNamesForMap(task, "customs")).toEqual(["Dorm 114"]);
  });
});

describe("raid prep needed items", () => {
  const task: RaidPrepTaskLike = {
    id: "t1",
    name: "Debut",
    trader_slug: "prapor",
    trader_name: "Prapor（俄商）",
    needed_keys: [
      {
        map: { slug: "customs" },
        keys: [{ id: "k114", name: "Dorm 114", icon_link: "k.png", types: ["keys"] }],
      },
      {
        map: { slug: "streets" },
        keys: [{ id: "k-other", name: "LexOs" }],
      },
    ],
    objectives: [
      {
        type: "giveItem",
        count: 7,
        items: [{ id: "gold", name: "金项链", icon_link: "g.png" }],
      },
      {
        type: "findQuestItem",
        maps: [{ slug: "customs" }],
        items: [{ id: "hdd", name: "硬盘" }],
      },
      {
        type: "plantItem",
        maps: [{ slug: "woods" }],
        items: [{ id: "ms2000", name: "MS2000" }],
      },
      {
        type: "giveItem",
        count: 2,
        found_in_raid: true,
        items: [{ id: "gold", name: "金项链" }],
      },
    ],
  };

  it("keeps current-map keys and unmapped handover items", () => {
    const items = collectRaidPrepTaskItems(task, "customs");
    const keys = collectRaidPrepTaskKeys(task, "customs");
    expect(keys.map((item) => item.name)).toEqual(["Dorm 114"]);
    expect(keys[0]?.count).toBe(1);
    expect(items.map((item) => `${item.role}:${item.name}×${item.count}`)).toEqual([
      "上交:金项链×7",
      "捡取:硬盘×1",
      "上交:金项链×2",
    ]);
    expect(items[2].found_in_raid).toBe(true);
    expect(items.some((item) => item.id === "ms2000")).toBe(false);
    expect(keys.some((item) => item.id === "k-other")).toBe(false);
  });

  it("keeps a single key when several objectives share the same lock", () => {
    const guitar: RaidPrepTaskLike = {
      id: "t-guitar",
      name: "高保真",
      objectives: [
        {
          id: "o-spot",
          type: "visit",
          description: "找到音乐人集会点",
          required_keys: [[{ id: "prim", name: "Primorsky 46-48号天桥钥匙" }]],
          zones: [{ map_slug: "streets", x: 1, z: 1 }],
        },
        {
          id: "o-pick",
          type: "findQuestItem",
          description: "找到吉他拨片",
          required_keys: [[{ id: "prim", name: "Primorsky 46-48号天桥钥匙" }]],
          maps: [{ slug: "streets" }],
        },
      ],
    };
    const keys = collectRaidPrepTaskKeys(guitar, "streets");
    expect(keys).toHaveLength(1);
    expect(keys[0]).toMatchObject({
      id: "prim",
      count: 1,
    });
  });

  it("collapses any-of category hand-ins using the objective description", () => {
    const meds: RaidPrepTaskLike = {
      id: "t-meds",
      name: "Veterinary",
      objectives: [
        {
          id: "o-med",
          type: "giveItem",
          description: "上交任意在战局中找到的医疗物品",
          count: 5,
          found_in_raid: true,
          items: [
            { id: "m1", name: "AI-2" },
            { id: "m2", name: "IFAK" },
            { id: "m3", name: "Salewa" },
            { id: "m4", name: "Grizzly" },
          ],
        },
      ],
    };
    const items = collectRaidPrepTaskItems(meds, "customs");
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({
      name: "上交任意在战局中找到的医疗物品",
      count: 5,
      found_in_raid: true,
    });
    expect(items[0].anyOf?.map((item) => item.name)).toEqual([
      "AI-2",
      "IFAK",
      "Salewa",
      "Grizzly",
    ]);
  });

  it("does not collapse long item lists unless the description says 任意", () => {
    const tags: RaidPrepTaskLike = {
      id: "t-tags",
      name: "Punisher",
      objectives: [
        {
          id: "o-tags",
          type: "giveItem",
          description: "上交战局中找到物品：BEAR 或 USEC 狗牌",
          count: 10,
          items: [
            { id: "t1", name: "BEAR dogtag" },
            { id: "t2", name: "USEC dogtag" },
            { id: "t3", name: "BEAR dogtag 2" },
            { id: "t4", name: "USEC dogtag 2" },
          ],
        },
        {
          id: "o-sell",
          type: "sellItem",
          description: "卖任何物品给Ragman",
          count: 50,
          items: [
            { id: "a", name: "A" },
            { id: "b", name: "B" },
            { id: "c", name: "C" },
            { id: "d", name: "D" },
          ],
        },
      ],
    };
    const items = collectRaidPrepTaskItems(tags, "customs");
    expect(items.map((item) => item.name)).toEqual([
      "BEAR dogtag",
      "USEC dogtag",
      "BEAR dogtag 2",
      "USEC dogtag 2",
      "A",
      "B",
      "C",
      "D",
    ]);
    expect(items.every((item) => !item.anyOf)).toBe(true);
  });

  it("treats objectives without a map as this raid", () => {
    expect(objectiveAppliesToMap({ type: "giveItem" }, "customs")).toBe(true);
    expect(
      objectiveAppliesToMap({ type: "plantItem", maps: [{ slug: "woods" }] }, "customs"),
    ).toBe(false);
    expect(
      objectiveAppliesToMap({ type: "plantItem", maps: [{ slug: "customs" }] }, "customs"),
    ).toBe(true);
    expect(
      objectiveAppliesToMap({ type: "plantItem", maps: [{ slug: "bigmap" }] }, "customs"),
    ).toBe(true);
  });

  it("lists selected tasks with items grouped by objective type", () => {
    const rows = buildRaidPrepSummary([task], "customs");
    expect(rows).toHaveLength(1);
    expect(rows[0].taskName).toBe("Debut");
    expect(rows[0].itemsByType.findItem?.map((item) => item.name)).toEqual([
      "硬盘",
    ]);
    expect(
      rows[0].itemsByType.giveItem?.map(
        (item) => `${item.name}×${item.count}`,
      ),
    ).toEqual(["金项链×7", "金项链×2"]);
    expect(rows[0].keys.map((item) => item.name)).toEqual(["Dorm 114"]);
    expect(rows[0].types).toEqual(["findQuestItem", "giveItem"]);
    expect(rows[0].objectiveLines).toEqual(["上交", "捡取"]);
    expect(collectRaidPrepSummaryTypeColumns(rows)).toEqual([
      "findItem",
      "giveItem",
    ]);
  });

  it("merges item and quest-item types into one summary column", () => {
    const rows = buildRaidPrepSummary(
      [
        {
          id: "t-merge",
          name: "Merge",
          objectives: [
            {
              type: "findItem",
              items: [{ id: "bolts", name: "螺栓" }],
            },
            {
              type: "findQuestItem",
              items: [{ id: "hdd", name: "硬盘" }],
            },
            {
              type: "giveQuestItem",
              items: [{ id: "note", name: "纸条" }],
            },
            {
              type: "plantItem",
              items: [{ id: "ms2000", name: "MS2000" }],
            },
            {
              type: "plantQuestItem",
              items: [{ id: "blood", name: "血样" }],
            },
          ],
        },
      ],
      "customs",
    );
    expect(collectRaidPrepSummaryTypeColumns(rows)).toEqual([
      "plantItem",
      "findItem",
      "giveItem",
    ]);
    expect(rows[0].itemsByType.findItem?.map((item) => item.name)).toEqual([
      "螺栓",
      "硬盘",
    ]);
    expect(rows[0].itemsByType.giveItem?.map((item) => item.name)).toEqual([
      "纸条",
    ]);
    expect(rows[0].itemsByType.plantItem?.map((item) => item.name)).toEqual([
      "MS2000",
      "血样",
    ]);
  });

  it("only opens summary columns for types that carry items", () => {
    const rows = buildRaidPrepSummary(
      [
        {
          id: "t-mix",
          name: "Mix",
          objectives: [
            { type: "shoot", description: "杀十人" },
            {
              type: "giveItem",
              items: [{ id: "gold", name: "金项链" }],
            },
            { type: "visit", maps: [{ slug: "customs" }] },
          ],
        },
      ],
      "customs",
    );
    expect(rows[0].types).toEqual(["shoot", "giveItem", "visit"]);
    expect(collectRaidPrepSummaryTypeColumns(rows)).toEqual(["giveItem"]);
    expect(raidPrepSummaryHasShootTypes(rows)).toBe(true);
    expect(rows[0].shootSlots.map((slot) => slot.text)).toEqual(["杀十人"]);
  });

  it("puts kill descriptions in a dedicated summary column", () => {
    const rows = buildRaidPrepSummary(
      [
        {
          id: "t-shoot",
          name: "Shoot",
          objectives: [
            {
              type: "shoot",
              description: "在海关使用 HS2000 击杀 4 名 PMC",
              items: [{ id: "hs2000", name: "HS2000" }],
              count: 4,
            },
            {
              type: "shoot",
              description: "找到并消灭Kollontay",
            },
            {
              type: "giveItem",
              items: [{ id: "gold", name: "金项链" }],
            },
            {
              type: "shoot",
              maps: [{ slug: "woods" }],
              description: "别的图不要出现",
            },
          ],
        },
      ],
      "customs",
    );
    expect(collectRaidPrepSummaryTypeColumns(rows)).toEqual(["giveItem"]);
    expect(raidPrepSummaryHasShootTypes(rows)).toBe(true);
    expect(rows[0].shootSlots.map((slot) => slot.text)).toEqual([
      "在海关使用 HS2000 击杀 4 名 PMC",
      "找到并消灭Kollontay",
    ]);
    expect(rows[0].shootSlots[0]?.items.map((item) => item.name)).toEqual([
      "HS2000",
    ]);
    expect(rows[0].shootSlots[0]?.items[0]?.count).toBe(1);
    expect(rows[0].shootSlots.map((slot) => slot.count)).toEqual([4, 1]);
    const grid = expandRaidPrepSummaryItemLines(
      rows[0]!,
      ["giveItem"],
      false,
      true,
    );
    expect(grid.lines).toHaveLength(2);
    expect(grid.lines.map((line) => line.shoot?.text)).toEqual([
      "在海关使用 HS2000 击杀 4 名 PMC",
      "找到并消灭Kollontay",
    ]);
    expect(grid.lines.map((line) => line.rest.giveItem?.name)).toEqual([
      "金项链",
      undefined,
    ]);
  });

  it("omits skipped kill objectives from the summary shoot column", () => {
    const slots = collectRaidPrepTaskShootSlots(
      {
        id: "t-skip-shoot",
        objectives: [
          { id: "o-scav", type: "shoot", description: "击杀 10 名 Scav" },
          { id: "o-pmc", type: "shoot", description: "击杀 5 名 PMC" },
        ],
      },
      "customs",
      new Set(["o-scav"]),
    );
    expect(slots.map((slot) => slot.text)).toEqual(["击杀 5 名 PMC"]);
  });

  it("keeps kill count on the shoot slot, not on the weapon chip", () => {
    expect(raidPrepObjectiveCount({ count: 15 })).toBe(15);
    expect(raidPrepObjectiveCount({ count: 0 })).toBe(1);
    expect(raidPrepObjectiveCount({})).toBe(1);
    const slots = collectRaidPrepTaskShootSlots(
      {
        id: "t-count",
        objectives: [
          {
            type: "shoot",
            description: "击杀 Scav",
            count: 12,
            items: [{ id: "m4", name: "M4A1" }],
          },
        ],
      },
      "customs",
    );
    expect(slots[0]?.count).toBe(12);
    expect(slots[0]?.items[0]?.count).toBe(1);
  });

  it("puts plant, mark, and use columns with keys, ahead of find/give", () => {
    const rows = buildRaidPrepSummary(
      [
        {
          id: "t-bring",
          name: "Bring",
          objectives: [
            {
              type: "findItem",
              items: [{ id: "bolts", name: "螺栓" }],
            },
            {
              type: "mark",
              items: [{ id: "ms2000", name: "MS2000" }],
            },
            {
              type: "plantItem",
              items: [{ id: "wifi", name: "WIFI 摄像头" }],
            },
            {
              type: "useItem",
              items: [{ id: "flare", name: "信号弹" }],
            },
            {
              type: "giveItem",
              items: [{ id: "gold", name: "金项链" }],
            },
          ],
        },
      ],
      "customs",
    );
    expect(collectRaidPrepSummaryTypeColumns(rows)).toEqual([
      "plantItem",
      "mark",
      "useItem",
      "findItem",
      "giveItem",
    ]);
    expect(raidPrepSummaryHasBringTypes(rows)).toBe(true);
  });

  it("treats a mark-only task as having the merged bring column", () => {
    const rows = buildRaidPrepSummary(
      [
        {
          id: "t-mark",
          name: "Mark",
          objectives: [{ type: "mark" }],
        },
      ],
      "customs",
    );
    expect(collectRaidPrepSummaryTypeColumns(rows)).toEqual([]);
    expect(raidPrepSummaryHasBringTypes(rows, [])).toBe(true);
  });

  it("expands a summary task to one item per line", () => {
    const rows = buildRaidPrepSummary(
      [
        {
          id: "t-lines",
          name: "Lines",
          needed_keys: [
            {
              map: { slug: "customs" },
              keys: [
                { id: "k1", name: "宿舍 114" },
                { id: "k2", name: "宿舍 105" },
              ],
            },
          ],
          objectives: [
            {
              type: "plantItem",
              items: [
                { id: "wifi", name: "WIFI 摄像头" },
                { id: "blood", name: "血样" },
              ],
            },
            {
              type: "findItem",
              items: [{ id: "bolts", name: "螺栓" }],
            },
          ],
        },
      ],
      "customs",
    );
    const grid = expandRaidPrepSummaryItemLines(rows[0]!, ["findItem"], true);
    expect(grid.lines).toHaveLength(2);
    expect(grid.spanKey).toBe(false);
    expect(grid.spanBring).toBe(false);
    expect(grid.spanRest.findItem).toBe(true);
    expect(grid.lines.map((line) => line.key?.name)).toEqual([
      "宿舍 114",
      "宿舍 105",
    ]);
    expect(grid.lines.map((line) => line.bring?.item?.name)).toEqual([
      "WIFI 摄像头",
      "血样",
    ]);
    expect(grid.lines.map((line) => line.rest.findItem?.name)).toEqual([
      "螺栓",
      undefined,
    ]);
  });

  it("uses objective descriptions for the summary hover", () => {
    const lines = collectRaidPrepTaskObjectiveLines(
      {
        id: "kollontay",
        name: "人之路·庇护者",
        objectives: [
          { type: "shoot", description: "找到并消灭Kollontay" },
          {
            type: "giveQuestItem",
            description: "上交在战局中找到的Kollontay的警棍",
          },
          {
            type: "plantItem",
            maps: [{ slug: "woods" }],
            description: "别的图不要出现",
          },
          { type: "visit", description: "可选探路", optional: true },
        ],
      },
      "streets",
    );
    expect(lines).toEqual([
      "找到并消灭Kollontay",
      "上交在战局中找到的Kollontay的警棍",
      "可选探路（可选）",
    ]);
  });

  it("lists every map objective with per-point keys for checkboxes", () => {
    const objectives = collectRaidPrepTaskObjectives(
      {
        id: "t-storage",
        objectives: [
          {
            id: "o-key",
            type: "visit",
            description: "检查兵营东楼黑",
            required_keys: [[{ name: "RB-OB钥匙" }]],
          },
          {
            id: "o-free",
            type: "visit",
            description: "检查兵营南楼白",
          },
        ],
      },
      "customs",
    );
    expect(objectives).toEqual([
      {
        id: "o-key",
        text: "检查兵营东楼黑",
        optional: false,
        keyNames: ["RB-OB钥匙"],
      },
      {
        id: "o-free",
        text: "检查兵营南楼白",
        optional: false,
        keyNames: [],
      },
    ]);
  });

  it("omits skipped handover items from the summary", () => {
    const rows = buildRaidPrepSummary(
      [task],
      "customs",
      new Map([["t1", new Set(["i:0"])]]),
    );
    expect(rows[0].itemsByType.giveItem?.map((item) => item.name)).toEqual([
      "金项链",
    ]);
    expect(rows[0].itemsByType.giveItem?.[0]?.count).toBe(2);
    expect(rows[0].keys.map((item) => item.name)).toEqual(["Dorm 114"]);
  });

  it("round-trips personal objective-done maps", () => {
    const skipped = toggleRaidPrepObjectiveDone(new Map(), "t1", "o-key");
    expect([...skipped.get("t1")!]).toEqual(["o-key"]);
    const cleared = toggleRaidPrepObjectiveDone(skipped, "t1", "o-key");
    expect(cleared.size).toBe(0);
    expect(
      serializeRaidPrepObjectiveDone(
        parseRaidPrepObjectiveDone({ t1: ["o-key", ""], t2: [] }),
      ),
    ).toEqual({ t1: ["o-key"] });
  });

  it("sorts summary rows by participant count descending", () => {
    const rows = [
      { taskId: "a", taskName: "Alpha" },
      { taskId: "b", taskName: "Bravo" },
      { taskId: "c", taskName: "Charlie" },
    ];
    const people = new Map<string, string[]>([
      ["a", ["u1"]],
      ["b", ["u1", "u2", "u3"]],
      ["c", ["u1", "u2"]],
    ]);
    expect(
      sortRaidPrepSummaryByParticipants(rows, people).map((row) => row.taskId),
    ).toEqual(["b", "c", "a"]);
  });
});

describe("clusterRaidPrepOverlayLabels", () => {
  const pink = "#f0a3c2";
  const blue = "#6cb6ff";

  function overlay(
    title: string,
    points: Array<{ x: number; z: number }>,
    extras: Partial<TarkovRaidPrepOverlay> = {},
  ): TarkovRaidPrepOverlay {
    const { height, ...rest } = extras;
    return {
      key: title,
      taskId: rest.taskId || rest.key || title,
      kind: "spawn",
      color: pink,
      title,
      subtitle: "",
      traderSlug: "",
      keyNames: [],
      showNoKey: false,
      optional: false,
      outline: [],
      points,
      ...rest,
      height: height ?? null,
    };
  }

  it("merges nearby points of the same task into one label at the centroid", () => {
    const labels = clusterRaidPrepOverlayLabels(
      [
        overlay("半路杀人", [
          { x: 100, z: 200 },
          { x: 104, z: 201 },
          { x: 102, z: 197 },
          { x: 98, z: 199 },
        ]),
      ],
      36,
    );
    expect(labels).toHaveLength(1);
    expect(labels[0].items).toEqual([
      {
        taskId: "半路杀人",
        title: "半路杀人",
        color: pink,
        traderSlug: "",
        subtitle: "",
        keyNames: [],
        showNoKey: false,
        count: 4,
        optional: false,
        height: null,
      },
    ]);
    expect(labels[0].x).toBe(100);
    expect(labels[0].z).toBe(200);
  });

  it("keeps far-apart locations of the same task as separate labels", () => {
    const labels = clusterRaidPrepOverlayLabels(
      [
        overlay("Debut", [
          { x: 0, z: 0 },
          { x: 200, z: 0 },
        ]),
      ],
      36,
    );
    expect(labels).toHaveLength(2);
    expect(labels.map((row) => row.x).sort((a, b) => a - b)).toEqual([0, 200]);
  });

  it("stacks different task names that sit on the same cluster", () => {
    const labels = clusterRaidPrepOverlayLabels(
      [
        overlay("半路杀人", [{ x: 10, z: 10 }], { taskId: "t-ambush" }),
        overlay(" Debut ", [{ x: 12, z: 11 }], {
          color: blue,
          key: "debut",
          taskId: "t-debut",
        }),
      ],
      36,
    );
    expect(labels).toHaveLength(1);
    expect(labels[0].items.map((item) => item.title)).toEqual([
      "半路杀人",
      "Debut",
    ]);
    expect(labels[0].items[1].color).toBe(blue);
  });

  it("places a zone label on the zone center, not every outline vertex", () => {
    const labels = clusterRaidPrepOverlayLabels([
      {
        key: "zone",
        taskId: "t-debut",
        kind: "zone",
        color: blue,
        title: "Debut",
        subtitle: "",
        traderSlug: "",
        keyNames: [],
        showNoKey: false,
        optional: false,
        outline: [
          { x: 0, z: 0 },
          { x: 40, z: 0 },
          { x: 40, z: 40 },
        ],
        points: [{ x: 12, z: 8 }],
        height: null,
      },
    ]);
    expect(labels).toHaveLength(1);
    expect(labels[0]).toMatchObject({ x: 12, z: 8 });
    expect(labels[0].items).toEqual([
      {
        taskId: "t-debut",
        title: "Debut",
        color: blue,
        traderSlug: "",
        subtitle: "",
        keyNames: [],
        showNoKey: false,
        count: 1,
        optional: false,
        height: null,
      },
    ]);
  });

  it("keeps optional labels separate from required ones of the same task", () => {
    const labels = clusterRaidPrepOverlayLabels([
      overlay("Shortage", [{ x: 1, z: 1 }], { taskId: "t-shortage" }),
      overlay("Shortage", [{ x: 2, z: 2 }], {
        key: "opt",
        taskId: "t-shortage",
        optional: true,
      }),
    ]);
    expect(labels).toHaveLength(1);
    expect(labels[0].items).toEqual([
      {
        taskId: "t-shortage",
        title: "Shortage",
        color: pink,
        traderSlug: "",
        subtitle: "",
        keyNames: [],
        showNoKey: false,
        count: 1,
        optional: false,
        height: null,
      },
      {
        taskId: "t-shortage",
        title: "Shortage",
        color: pink,
        traderSlug: "",
        subtitle: "",
        keyNames: [],
        showNoKey: false,
        count: 1,
        optional: true,
        height: null,
      },
    ]);
  });

  it("stacks numbered points of the same task instead of merging them", () => {
    const labels = clusterRaidPrepOverlayLabels(
      [
        overlay("逃跑 1", [{ x: 10, z: 10 }], {
          taskId: "t-run",
          keyNames: ["Dorm 114"],
        }),
        overlay("逃跑 2", [{ x: 12, z: 11 }], {
          taskId: "t-run",
          key: "run-2",
          showNoKey: true,
        }),
      ],
      36,
    );
    expect(labels).toHaveLength(1);
    expect(labels[0].items.map((item) => item.title)).toEqual(["逃跑 1", "逃跑 2"]);
    expect(labels[0].items[0]).toMatchObject({
      keyNames: ["Dorm 114"],
      showNoKey: false,
    });
    expect(labels[0].items[1]).toMatchObject({
      keyNames: [],
      showNoKey: true,
    });
  });

  it("keeps the trader slug on clustered labels", () => {
    const labels = clusterRaidPrepOverlayLabels([
      overlay("半路杀人", [{ x: 1, z: 1 }], {
        taskId: "t-ambush",
        traderSlug: "prapor",
      }),
      overlay("Debut", [{ x: 2, z: 2 }], {
        color: blue,
        key: "debut",
        taskId: "t-debut",
        traderSlug: "therapist",
      }),
    ]);
    expect(labels).toHaveLength(1);
    expect(labels[0].items.map((item) => item.traderSlug)).toEqual([
      "prapor",
      "therapist",
    ]);
  });

  it("clusters in projected space so zoomed-out far points can still share a label", () => {
    const labels = clusterRaidPrepOverlayLabels(
      [
        overlay("Debut", [
          { x: 0, z: 0 },
          { x: 200, z: 0 },
        ]),
      ],
      {
        gap: 40,
        project: (point) => ({ x: point.x / 10, z: point.z / 10 }),
      },
    );
    expect(labels).toHaveLength(1);
    expect(labels[0].x).toBe(0);
    expect(labels[0].z).toBe(0);
  });

  it("keeps projected-far points as separate labels", () => {
    const labels = clusterRaidPrepOverlayLabels(
      [
        overlay("Debut", [
          { x: 0, z: 0 },
          { x: 20, z: 0 },
        ]),
      ],
      {
        gap: 40,
        project: (point) => ({ x: point.x * 10, z: point.z * 10 }),
      },
    );
    expect(labels).toHaveLength(2);
  });

  it("skips hex ids that leaked through as task titles", () => {
    expect(
      clusterRaidPrepOverlayLabels([
        overlay("5a9f913a86f77472bf74a592", [{ x: 1, z: 1 }]),
      ]),
    ).toEqual([]);
  });
});

describe("traderFilterLabel", () => {
  it("reads known trader nicknames", () => {
    expect(traderFilterLabel("prapor", "Prapor")).toEqual({
      english: "Prapor",
      chinese: "俄商",
    });
    expect(traderFilterLabel("unknown", "Skier（滑雪）")).toEqual({
      english: "Skier",
      chinese: "滑雪",
    });
  });
});

describe("filterRaidPrepRows", () => {
  it("filters by trader, query, and progress status", () => {
    const rows = [
      {
        id: "a",
        name: "Alpha",
        trader_slug: "prapor",
        trader_name: "Prapor",
        progress_status: "active",
      },
      {
        id: "b",
        name: "Beta",
        trader_slug: "therapist",
        trader_name: "Therapist",
        progress_status: "complete",
      },
    ];
    expect(filterRaidPrepRows(rows, { trader: "prapor" }).map((r) => r.id)).toEqual([
      "a",
    ]);
    expect(filterRaidPrepRows(rows, { q: "beta" }).map((r) => r.id)).toEqual(["b"]);
    expect(
      filterRaidPrepRows(rows, { progressStatus: "complete" }).map((r) => r.id),
    ).toEqual(["b"]);
    expect(filterRaidPrepRows(rows, { progressStatus: "all" })).toHaveLength(2);
  });
});

describe("overlay floors", () => {
  it("shows ground-only overlays on the unnamed band", () => {
    const bands = mapLayerFloorBands({
      heightRange: [-6, 10],
      layers: [{ name: "2nd", extents: [{ height: [12, 20] }] }],
    });
    expect(overlayVisibleOnFloor(null, "", bands)).toBe(true);
    expect(overlayVisibleOnFloor({ min: 14, max: 16 }, "", bands)).toBe(false);
    expect(overlayVisibleOnFloor({ min: 14, max: 16 }, "2nd", bands)).toBe(true);
    expect(overlayFloorNames({ min: 14, max: 16 }, bands)).toEqual(["2nd"]);
    expect(overlayFloorForSpan({ min: 14, max: 16 }, bands)).toBe("2nd");
    expect(overlayFloorForSpan(null, bands)).toBe("");
    expect(overlayFloorForPoint(15, bands)).toBe("2nd");
    expect(overlayFloorForPoint(0, bands)).toBe("");
  });
});

describe("colorForTaskIndex", () => {
  it("cycles the palette by selection order", () => {
    expect(colorForTaskIndex(0)).toBe(RAID_PREP_TASK_COLORS[0]);
    expect(colorForTaskIndex(RAID_PREP_TASK_COLORS.length)).toBe(
      RAID_PREP_TASK_COLORS[0],
    );
  });
});

describe("resolveRaidPrepLocatePoints", () => {
  it("lists required points before optional ones", () => {
    const task: RaidPrepTaskLike = {
      id: "t-locate",
      objectives: [
        {
          id: "o-opt",
          optional: true,
          zones: [{ id: "z-opt", map_slug: "customs", x: 1, z: 1 }],
        },
        {
          id: "o-main",
          possible_locations: [
            { map_slug: "customs", positions: [{ x: 9, z: 8 }] },
          ],
        },
      ],
    };
    expect(resolveRaidPrepLocatePoints(task, "customs")).toEqual([
      { x: 9, z: 8 },
      { x: 1, z: 1 },
    ]);
  });

  it("keeps zone height on locate points", () => {
    const task: RaidPrepTaskLike = {
      id: "t-floor",
      objectives: [
        {
          zones: [
            { map_slug: "customs", x: 4, z: 5, top: 14, bottom: 16 },
          ],
        },
      ],
    };
    expect(resolveRaidPrepLocatePoints(task, "customs")).toEqual([
      { x: 4, z: 5, y: 15 },
    ]);
  });
});
