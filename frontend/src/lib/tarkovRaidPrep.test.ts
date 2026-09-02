import { describe, expect, it } from "vitest";
import { findInteractiveMap } from "@/lib/tarkovMapImages";
import {
  buildRaidPrepOverlays,
  filterRaidPrepOverlaysForViewer,
  raidPrepObjectiveStepText,
  collectRaidPrepOverlaySteps,
  resolveRaidPrepLocatePoint,
  buildRaidPrepSummary,
  clusterRaidPrepOverlayLabels,
  hydrateRaidPrepCatalogRows,
  mergeRaidPrepGeometryItems,
  missingRaidPrepGeometryIds,
  raidPrepVirtualWindow,
  colorForTaskIndex,
  collectRaidPrepTaskItems,
  collectRaidPrepTaskKeys,
  collectRaidPrepBringKit,
  collectRaidPrepSummaryTypeColumns,
  raidPrepTaskIdsForParticipant,
  collectRaidPrepTaskShootSlots,
  raidPrepObjectiveCount,
  expandRaidPrepSummaryItemLines,
  raidPrepSummaryHasBringTypes,
  raidPrepSummaryHasShootTypes,
  collectRaidPrepTaskObjectiveLines,
  placeRaidPrepListHint,
  collectRaidPrepTaskObjectives,
  matchRaidPrepOverlayAtPoint,
  formatRaidPrepKeyNeedLine,
  parseRaidPrepObjectiveDone,
  mergeRaidPrepSkipMaps,
  raidPrepObjectiveDoneScope,
  raidPrepObjectiveDoneLegacyScopes,
  raidPrepSkipMapsEqual,
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
  raidPrepAutoSwitchMapId,
  raidPrepMapsEquivalent,
  objectiveAppliesToMap,
  objectiveZoneNames,
  overlayFloorNames,
  overlayFloorForSpan,
  overlayFloorForPoint,
  overlayVisibleOnFloor,
  parseCsvParam,
  partitionRaidPrepRows,
  planRaidPrepTaskProgressSync,
  raidPrepIdsFromTaskProgress,
  describeRaidPrepTaskProgressSync,
  hideCompletedRaidPrepRows,
  raidPrepTaskProgressStatus,
  raidPrepTaskProgressLabel,
  raidPrepObjectiveCheckedForViewer,
  sortRaidPrepRowsByProgress,
  groupRaidPrepRowsByProgress,
  filterRaidPrepRowsByScope,
  countRaidPrepRowsByScope,
  mergeRaidPrepNeededItems,
  raidPrepKeyIsMissing,
  raidPrepTaskKeysUnavailable,
  RAID_PREP_UNAVAILABLE_KEY_HINT,
  collectUnavailableRaidPrepTaskIds,
  mergeRaidPrepAvailableKeyIds,
  settleRaidPrepSelection,
  formatRaidPrepOverlayKeyLabel,
  pinSelectedRaidPrepRows,
  raidPrepMapOptions,
  collectRaidPrepQuestFilterPeople,
  defaultQuestPersonOffKeys,
  nextQuestPeopleParentSelection,
  nextQuestPersonSelection,
  raidPrepParticipants,
  raidPrepPersonKey,
  raidPrepQuestOverlayVisible,
  resolveRaidPrepLocatePoints,
  resolveRaidPrepLocateTargets,
  selectedTasksFromCatalog,
  serializeSelectedIds,
  sortRaidPrepSummaryByParticipants,
  displayRaidPrepTaskName,
  collectRaidPrepCompletedUsers,
  collectRaidPrepPartyKeySkipMap,
  collectRaidPrepOtherMapGroups,
  formatRaidPrepOtherMapsLead,
  raidPrepMapObjectivesComplete,
  raidPrepTaskCanLocate,
  formatRaidPrepOverlayPointTitle,
  formatRaidPrepParticipantLine,
  objectiveDonesToSkipMap,
  raidPrepMapObjectiveIds,
  roomObjectiveMarksForCompletedTasks,
  skipMapToObjectiveDones,
  raidPrepParticipantNames,
  tarkovReadableName,
  traderFilterLabel,
  type RaidPrepNeededItem,
  type RaidPrepTaskLike,
  type TarkovRaidPrepOverlay,
  RAID_PREP_MAX_SELECTED,
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

  it("auto-switches only on live raid phases or empty current map", () => {
    expect(raidPrepMapsEquivalent("streets-of-tarkov", "streets")).toBe(true);
    expect(raidPrepMapsEquivalent("factory", "night-factory")).toBe(false);
    expect(
      raidPrepAutoSwitchMapId({
        currentMapId: "woods",
        logMapId: "customs",
        phaseKind: "raid_started",
      }),
    ).toBe("customs");
    expect(
      raidPrepAutoSwitchMapId({
        currentMapId: "customs",
        logMapId: "bigmap",
        phaseKind: "raid_started",
      }),
    ).toBe("");
    expect(
      raidPrepAutoSwitchMapId({
        currentMapId: "woods",
        logMapId: "customs",
        phaseKind: "raid_exited",
        fillEmpty: true,
      }),
    ).toBe("");
    expect(
      raidPrepAutoSwitchMapId({
        currentMapId: "",
        logMapId: "night-factory",
        phaseKind: "raid_exited",
        fillEmpty: true,
      }),
    ).toBe("night-factory");
    expect(
      raidPrepAutoSwitchMapId({
        currentMapId: "",
        logMapId: "customs",
        phaseKind: "raid_exited",
        fillEmpty: false,
      }),
    ).toBe("");
    expect(
      raidPrepAutoSwitchMapId({
        currentMapId: "woods",
        logMapId: "customs",
        phaseKind: "map_loading",
      }),
    ).toBe("");
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

  it("selects only the clicked person after the parent was turned off", () => {
    const keys = ["id:1", "id:2", "id:3"];
    expect(nextQuestPeopleParentSelection(keys, true)).toEqual({
      showQuests: false,
      offKeys: keys,
    });
    expect(nextQuestPeopleParentSelection(keys, false)).toEqual({
      showQuests: true,
      offKeys: [],
    });
    expect(
      nextQuestPersonSelection(keys, new Set(), false, "id:2"),
    ).toEqual({
      showQuests: true,
      offKeys: ["id:1", "id:3"],
    });
    expect(
      nextQuestPersonSelection(keys, new Set(keys), true, "id:2"),
    ).toEqual({
      showQuests: true,
      offKeys: ["id:1", "id:3"],
    });
    expect(
      nextQuestPersonSelection(keys, new Set(["id:2"]), true, "id:2"),
    ).toEqual({
      showQuests: true,
      offKeys: [],
    });
  });

  it("defaults the quest filter to only the current user", () => {
    const people = [
      { name: "甲", userId: 1 },
      { name: "乙", userId: 2 },
      { name: "丙", userId: 3 },
    ];
    expect(defaultQuestPersonOffKeys(people, 2)).toEqual(["id:1", "id:3"]);
    expect(defaultQuestPersonOffKeys(people, 0)).toBeNull();
    expect(defaultQuestPersonOffKeys(people.slice(0, 1), 1)).toBeNull();
    expect(defaultQuestPersonOffKeys(people, 9)).toBeNull();
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
      title: "Debut（第1处）",
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
      title: "Debut（第2处）",
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
    expect(overlays.map((row) => row.title)).toEqual([
      "逃跑（第1处）",
      "逃跑（第2处）",
    ]);
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

  it("uses the objective description without a type prefix", () => {
    expect(
      raidPrepObjectiveStepText({
        type: "mark",
        description: "在海岸线找到第二处交易现场，并使用MS2000指示器标记",
      }),
    ).toBe("在海岸线找到第二处交易现场，并使用MS2000指示器标记");
    expect(raidPrepObjectiveStepText({ type: "mark" })).toBe("标记");
    expect(
      raidPrepObjectiveStepText({
        type: "visit",
        description: "探路",
        optional: true,
      }),
    ).toBe("探路（可选）");
  });

  it("places a task-list hint left of the sidebar and keeps it in the viewport", () => {
    const box = placeRaidPrepListHint({
      viewW: 1200,
      viewH: 800,
      boxW: 320,
      boxH: 180,
      edgeRight: 900,
      triggerTop: 120,
    });
    expect(box.left + 320).toBeLessThanOrEqual(900 - 8);
    expect(box.left).toBeGreaterThanOrEqual(8);
    expect(box.top).toBeGreaterThanOrEqual(8);
    expect(box.top + 180).toBeLessThanOrEqual(800 - 8);
    expect(box.maxWidth).toBeLessThanOrEqual(1200 - 16);
    expect(box.maxHeight).toBeLessThanOrEqual(800 - 16);
  });

  it("shifts a tall task-list hint up so it does not leave the viewport", () => {
    const box = placeRaidPrepListHint({
      viewW: 800,
      viewH: 600,
      boxW: 240,
      boxH: 420,
      edgeRight: 620,
      triggerTop: 480,
    });
    expect(box.top).toBeGreaterThanOrEqual(8);
    expect(box.top + 420).toBeLessThanOrEqual(600 - 8);
    expect(box.left + 240).toBeLessThanOrEqual(620 - 8);
  });

  it("clamps a huge task-list hint so it never creates overflow", () => {
    const box = placeRaidPrepListHint({
      viewW: 400,
      viewH: 300,
      boxW: 900,
      boxH: 800,
      edgeRight: 80,
      triggerTop: 20,
    });
    expect(box.left).toBeGreaterThanOrEqual(8);
    expect(box.top).toBeGreaterThanOrEqual(8);
    expect(box.left + box.maxWidth).toBeLessThanOrEqual(400);
    expect(box.top + box.maxHeight).toBeLessThanOrEqual(300);
  });

  it("highlights the hovered location among all map steps", () => {
    const task: RaidPrepTaskLike = {
      id: "anesthesia",
      name: "麻醉",
      objectives: [
        {
          id: "o-1",
          type: "mark",
          description: "在海岸线找到第一处交易现场，并使用MS2000指示器标记",
          zones: [{ id: "z1", map_slug: "shoreline", x: 1, z: 1 }],
        },
        {
          id: "o-2",
          type: "mark",
          description: "在海岸线找到第二处交易现场，并使用MS2000指示器标记",
          zones: [{ id: "z2", map_slug: "shoreline", x: 80, z: 90 }],
        },
      ],
    };
    const overlays = buildRaidPrepOverlays([task], "shoreline");
    expect(overlays.map((row) => row.subtitle)).toEqual([
      "在海岸线找到第一处交易现场，并使用MS2000指示器标记",
      "在海岸线找到第二处交易现场，并使用MS2000指示器标记",
    ]);
    expect(collectRaidPrepOverlaySteps(task, "shoreline", "o-2")).toEqual([
      {
        id: "o-1",
        text: "在海岸线找到第一处交易现场，并使用MS2000指示器标记",
        optional: false,
        active: false,
      },
      {
        id: "o-2",
        text: "在海岸线找到第二处交易现场，并使用MS2000指示器标记",
        optional: false,
        active: true,
      },
    ]);
    expect(overlays[1]!.steps.filter((step) => step.active).map((step) => step.text)).toEqual([
      "在海岸线找到第二处交易现场，并使用MS2000指示器标记",
    ]);
    expect(matchRaidPrepOverlayAtPoint(overlays, "anesthesia", { x: 80, z: 90 })?.title).toBe(
      "麻醉（第2处）",
    );
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

  it("does not glue a point index onto a name that already ends with -2", () => {
    const overlays = buildRaidPrepOverlays(
      [
        {
          id: "wet-2",
          name: "湿活-2",
          objectives: [
            {
              id: "o-visit",
              type: "visit",
              zones: [
                { id: "z1", map_slug: "customs", x: 1, z: 1 },
                { id: "z2", map_slug: "customs", x: 2, z: 2 },
                { id: "z3", map_slug: "customs", x: 3, z: 3 },
                { id: "z4", map_slug: "customs", x: 4, z: 4 },
              ],
            },
          ],
        },
      ],
      "customs",
    );
    expect(overlays.map((row) => row.title)).toEqual([
      "湿活-2（第1处）",
      "湿活-2（第2处）",
      "湿活-2（第3处）",
      "湿活-2（第4处）",
    ]);
  });

  it("drops duplicate copies of the same zone so steps are not repeated", () => {
    const truck1 = {
      id: "place_n1",
      map_slug: "shoreline",
      x: -234.49,
      z: -164.42,
    };
    const truck2 = {
      id: "place_n2",
      map_slug: "shoreline",
      x: -596.26,
      z: 475.53,
    };
    const task: RaidPrepTaskLike = {
      id: "humanitarian-supplies",
      name: "人道主义援助",
      objectives: [
        {
          id: "o-mark-1",
          type: "mark",
          description: "使用MS2000指示器标记第一辆UN卡车",
          zones: [truck1, truck1],
        },
        {
          id: "o-visit-1",
          type: "visit",
          description: "在海岸线找到第一辆装有UN失货货物的卡车",
          optional: true,
          zones: [truck1, truck1],
        },
        {
          id: "o-mark-2",
          type: "mark",
          description: "使用MS2000指示器标记第二辆UN卡车",
          zones: [truck2, truck2],
        },
        {
          id: "o-visit-2",
          type: "visit",
          description: "在海岸线找到第二辆装有UN失货货物的卡车",
          optional: true,
          zones: [truck2, truck2],
        },
      ],
    };
    const overlays = buildRaidPrepOverlays([task], "shoreline");
    expect(overlays).toHaveLength(4);
    expect(overlays.map((row) => [row.title, row.optional, row.subtitle])).toEqual([
      [
        "人道主义援助（第1处）",
        false,
        "使用MS2000指示器标记第一辆UN卡车",
      ],
      [
        "人道主义援助（第2处）",
        true,
        "在海岸线找到第一辆装有UN失货货物的卡车（可选）",
      ],
      [
        "人道主义援助（第3处）",
        false,
        "使用MS2000指示器标记第二辆UN卡车",
      ],
      [
        "人道主义援助（第4处）",
        true,
        "在海岸线找到第二辆装有UN失货货物的卡车（可选）",
      ],
    ]);
    expect(overlays[2]!.steps.map((step) => [step.active, step.text])).toEqual([
      [false, "使用MS2000指示器标记第一辆UN卡车"],
      [false, "在海岸线找到第一辆装有UN失货货物的卡车（可选）"],
      [true, "使用MS2000指示器标记第二辆UN卡车"],
      [false, "在海岸线找到第二辆装有UN失货货物的卡车（可选）"],
    ]);
    const labels = clusterRaidPrepOverlayLabels(overlays);
    const atFirst = labels.find((row) => Math.round(row.x) === -234);
    expect(atFirst?.items.map((item) => item.subtitle)).toEqual([
      expect.stringContaining("第一辆UN卡车"),
      expect.stringContaining("第一辆装有UN"),
    ]);
    expect(resolveRaidPrepLocatePoints(task, "shoreline")).toEqual([
      { x: -234.49, z: -164.42 },
      { x: -596.26, z: 475.53 },
    ]);
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

  it("hides skipped objectives on the viewer's map and drops them from remaining keys", () => {
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
    const overlays = buildRaidPrepOverlays([mixed], "customs");
    expect(overlays).toHaveLength(2);
    expect(overlays.map((row) => row.subtitle)).toEqual([
      "检查兵营东楼黑",
      "检查兵营南楼白",
    ]);
    expect(overlays.map((row) => row.objectiveId)).toEqual(["o-key", "o-free"]);
    expect(
      filterRaidPrepOverlaysForViewer(
        overlays,
        new Map([["t-storage", new Set(["o-key"])]]),
      ).map((row) => row.subtitle),
    ).toEqual(["检查兵营南楼白"]);
    expect(
      filterRaidPrepOverlaysForViewer(
        overlays,
        new Map([["t-storage", new Set(["o-free"])]]),
      ).map((row) => row.subtitle),
    ).toEqual(["检查兵营东楼黑"]);
    expect(filterRaidPrepOverlaysForViewer(overlays, new Map())).toHaveLength(2);
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
    expect(raidPrepTaskCanLocate(mixed, "customs")).toBe(true);
    expect(raidPrepTaskCanLocate(mixed, "customs", new Set(["o-key"]))).toBe(
      true,
    );
    expect(
      raidPrepTaskCanLocate(mixed, "customs", new Set(["o-key", "o-free"])),
    ).toBe(false);
    expect(
      raidPrepTaskCanLocate(mixed, "customs", undefined, { taskDone: true }),
    ).toBe(false);
    expect(raidPrepTaskCanLocate(mixed, "woods")).toBe(false);
  });

  it("keeps locate before geometry hydrates, hides after this-map steps are done", () => {
    const stub: RaidPrepTaskLike = {
      id: "t-stub",
      name: "Stub",
      objectives: [
        {
          id: "o1",
          type: "visit",
          description: "去检查",
          maps: [{ slug: "customs", name: "海关" }],
        },
      ],
    };
    expect(
      raidPrepTaskCanLocate(stub, "customs", undefined, {
        hasMapMarkers: true,
      }),
    ).toBe(true);
    expect(
      raidPrepTaskCanLocate(stub, "customs", new Set(["o1"]), {
        hasMapMarkers: true,
      }),
    ).toBe(false);
    expect(
      raidPrepTaskCanLocate(stub, "customs", undefined, {
        hasMapMarkers: false,
      }),
    ).toBe(false);
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

  it("numbers overlay points without gluing onto a trailing -2", () => {
    expect(formatRaidPrepOverlayPointTitle("湿活-2", 0, 1)).toBe("湿活-2");
    expect(formatRaidPrepOverlayPointTitle("湿活-2", 0, 4)).toBe("湿活-2（第1处）");
    expect(formatRaidPrepOverlayPointTitle("湿活-2", 3, 4)).toBe("湿活-2（第4处）");
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
    const kit = collectRaidPrepBringKit(rows);
    expect(kit.map((item) => item.name)).toEqual([
      "WIFI 摄像头",
      "MS2000",
      "信号弹",
    ]);
  });

  it("merges the current user's plant/mark/use kit across tasks", () => {
    const rows = buildRaidPrepSummary(
      [
        {
          id: "t-a",
          name: "A",
          objectives: [
            { type: "plantItem", items: [{ id: "cam", name: "摄像头" }] },
            { type: "mark", items: [{ id: "ms", name: "MS2000" }] },
          ],
        },
        {
          id: "t-b",
          name: "B",
          objectives: [
            { type: "useItem", items: [{ id: "cam", name: "摄像头" }] },
            { type: "findItem", items: [{ id: "bolt", name: "螺栓" }] },
          ],
        },
      ],
      "customs",
    );
    const byTask = new Map([
      ["t-a", [{ name: "甲", userId: 1 }]],
      ["t-b", [{ name: "乙", userId: 2 }, { name: "甲", userId: 1 }]],
    ]);
    expect(raidPrepTaskIdsForParticipant(byTask, 1)).toEqual(
      new Set(["t-a", "t-b"]),
    );
    expect(raidPrepTaskIdsForParticipant(byTask, 2)).toEqual(new Set(["t-b"]));
    expect(raidPrepTaskIdsForParticipant(byTask, 0)).toBeNull();
    expect(raidPrepTaskIdsForParticipant(byTask, 9)).toEqual(new Set());
    expect(collectRaidPrepBringKit(rows, new Set())).toEqual([]);
    const mine = collectRaidPrepBringKit(rows, new Set(["t-a", "t-b"]));
    expect(mine.map((item) => `${item.name}×${item.count}`)).toEqual([
      "摄像头×2",
      "MS2000×1",
    ]);
    expect(
      collectRaidPrepBringKit(rows, new Set(["t-b"])).map((item) => item.name),
    ).toEqual(["摄像头"]);
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
    expect(rows[0].hasMapKeys).toBe(true);
  });

  it("keeps party keys when the viewer finished but a teammate has not", () => {
    const wealth: RaidPrepTaskLike = {
      id: "wealth",
      name: "财不外露",
      objectives: [
        { id: "o-find", type: "visit", description: "找到不动产管理处" },
        {
          id: "o-key",
          type: "visit",
          description: "进入办公室",
          required_keys: [
            [{ id: "re-office", name: "不动产管理处办公室钥匙" }],
          ],
        },
        { id: "o-upload", type: "visit", description: "上传找到的信息" },
      ],
    };
    const viewerSkip = new Map([
      ["wealth", new Set(["o-find", "o-key", "o-upload"])],
    ]);
    const people = new Map([
      ["wealth", [{ userId: 1, name: "我" }, { userId: 2, name: "队友" }]],
    ]);
    const keySkipped = collectRaidPrepPartyKeySkipMap(
      [wealth],
      "streets",
      people,
      [
        { task_id: "wealth", objective_id: "o-find", user_id: 1 },
        { task_id: "wealth", objective_id: "o-key", user_id: 1 },
        { task_id: "wealth", objective_id: "o-upload", user_id: 1 },
      ],
      viewerSkip,
    );
    expect(keySkipped.get("wealth")?.size ?? 0).toBe(0);
    const rows = buildRaidPrepSummary(
      [wealth],
      "streets",
      viewerSkip,
      keySkipped,
    );
    expect(rows[0].keys.map((item) => item.name)).toEqual([
      "不动产管理处办公室钥匙",
    ]);
    expect(rows[0].hasMapKeys).toBe(true);
  });

  it("hides party keys only after every participant finished the key step", () => {
    const wealth: RaidPrepTaskLike = {
      id: "wealth",
      name: "财不外露",
      objectives: [
        {
          id: "o-key",
          type: "visit",
          description: "进入办公室",
          required_keys: [
            [{ id: "re-office", name: "不动产管理处办公室钥匙" }],
          ],
        },
        { id: "o-upload", type: "visit", description: "上传找到的信息" },
      ],
    };
    const people = new Map([
      ["wealth", [{ userId: 1 }, { userId: 2 }]],
    ]);
    const keySkipped = collectRaidPrepPartyKeySkipMap(
      [wealth],
      "streets",
      people,
      [
        { task_id: "wealth", objective_id: "o-key", user_id: 1 },
        { task_id: "wealth", objective_id: "o-upload", user_id: 1 },
        { task_id: "wealth", objective_id: "o-key", user_id: 2 },
        { task_id: "wealth", objective_id: "o-upload", user_id: 2 },
      ],
    );
    expect([...keySkipped.get("wealth")!].sort()).toEqual([
      "o-key",
      "o-upload",
    ]);
    const rows = buildRaidPrepSummary(
      [wealth],
      "streets",
      new Map([["wealth", new Set(["o-key", "o-upload"])]]),
      keySkipped,
    );
    expect(rows[0].keys).toEqual([]);
    expect(rows[0].hasMapKeys).toBe(true);
  });

  it("drops a key after every participant finished that key step", () => {
    const wealth: RaidPrepTaskLike = {
      id: "wealth",
      name: "财不外露",
      objectives: [
        {
          id: "o-key",
          type: "visit",
          description: "进入办公室",
          required_keys: [
            [{ id: "re-office", name: "不动产管理处办公室钥匙" }],
          ],
        },
        { id: "o-upload", type: "visit", description: "上传找到的信息" },
      ],
    };
    const keySkipped = collectRaidPrepPartyKeySkipMap(
      [wealth],
      "streets",
      new Map([["wealth", [{ userId: 1 }, { userId: 2 }]]]),
      [
        { task_id: "wealth", objective_id: "o-key", user_id: 1 },
        { task_id: "wealth", objective_id: "o-key", user_id: 2 },
      ],
    );
    expect([...keySkipped.get("wealth")!]).toEqual(["o-key"]);
    const rows = buildRaidPrepSummary([wealth], "streets", undefined, keySkipped);
    expect(rows[0].keys).toEqual([]);
    expect(rows[0].hasMapKeys).toBe(true);
  });

  it("falls back to viewer skip when a task has no participants", () => {
    const wealth: RaidPrepTaskLike = {
      id: "wealth",
      name: "财不外露",
      objectives: [
        {
          id: "o-key",
          type: "visit",
          description: "进入办公室",
          required_keys: [
            [{ id: "re-office", name: "不动产管理处办公室钥匙" }],
          ],
        },
      ],
    };
    const viewerSkip = new Map([["wealth", new Set(["o-key"])]]);
    const keySkipped = collectRaidPrepPartyKeySkipMap(
      [wealth],
      "streets",
      undefined,
      [],
      viewerSkip,
    );
    expect([...keySkipped.get("wealth")!]).toEqual(["o-key"]);
    const rows = buildRaidPrepSummary(
      [wealth],
      "streets",
      viewerSkip,
      keySkipped,
    );
    expect(rows[0].keys).toEqual([]);
    expect(rows[0].hasMapKeys).toBe(true);
  });

  it("marks hasMapKeys false when the task has no keys on this map", () => {
    const rows = buildRaidPrepSummary(
      [
        {
          id: "visit-only",
          name: "探路",
          objectives: [{ id: "o1", type: "visit", description: "去看看" }],
        },
      ],
      "customs",
    );
    expect(rows[0].keys).toEqual([]);
    expect(rows[0].hasMapKeys).toBe(false);
  });

  it("lists users who finished every required map objective", () => {
    const tasks: RaidPrepTaskLike[] = [
      {
        id: "wet-2",
        name: "湿活-2",
        objectives: [
          { id: "o-1", type: "visit", description: "点1" },
          { id: "o-2", type: "visit", description: "点2" },
          { id: "o-opt", type: "visit", description: "可选", optional: true },
        ],
      },
    ];
    const dones = [
      { task_id: "wet-2", objective_id: "o-1", user_id: 1, display_name: "甲" },
      { task_id: "wet-2", objective_id: "o-2", user_id: 1, display_name: "甲" },
      { task_id: "wet-2", objective_id: "o-1", user_id: 2, display_name: "乙" },
    ];
    const completed = collectRaidPrepCompletedUsers(tasks, "customs", dones);
    expect(completed.get("wet-2")?.map((row) => row.name)).toEqual(["甲"]);
    const mine = objectiveDonesToSkipMap(dones, 2);
    expect([...mine.get("wet-2")!]).toEqual(["o-1"]);
    const wet: RaidPrepTaskLike = {
      ...tasks[0]!,
      objectives: [
        {
          id: "o-1",
          type: "visit",
          description: "在海岸线找到渔民的住所",
          zones: [{ id: "z1", map_slug: "shoreline", x: 1, z: 1 }],
        },
        {
          id: "o-2",
          type: "visit",
          description: "使用MS2000指示器标记钓鱼点",
          zones: [{ id: "z2", map_slug: "shoreline", x: 80, z: 90 }],
        },
      ],
    };
    expect(
      buildRaidPrepOverlays([wet], "shoreline").map((row) => row.subtitle),
    ).toEqual([
      "在海岸线找到渔民的住所",
      "使用MS2000指示器标记钓鱼点",
    ]);
    expect(raidPrepMapObjectiveIds(tasks[0]!, "customs")).toEqual([
      "o-1",
      "o-2",
      "o-opt",
    ]);
    expect(
      roomObjectiveMarksForCompletedTasks(
        ["wet-2", "other"],
        tasks,
        "customs",
        dones,
        2,
      ),
    ).toEqual([
      { taskId: "wet-2", objectiveId: "o-2" },
      { taskId: "wet-2", objectiveId: "o-opt" },
    ]);
    expect(
      skipMapToObjectiveDones(mine, { userId: 2, name: "乙" }),
    ).toEqual([
      {
        task_id: "wet-2",
        objective_id: "o-1",
        user_id: 2,
        display_name: "乙",
      },
    ]);
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
    expect(raidPrepObjectiveDoneScope("streets", "pve", 7)).toBe(
      "user:7:pve:streets",
    );
    expect(raidPrepObjectiveDoneLegacyScopes("streets", "ab12")).toEqual([
      "solo:streets",
      "room:ab12",
    ]);
    const merged = mergeRaidPrepSkipMaps(
      new Map([["t1", new Set(["a"])]]),
      new Map([["t1", new Set(["b"])], ["t2", new Set(["c"])]]),
    );
    expect([...merged.get("t1")!].sort()).toEqual(["a", "b"]);
    expect([...merged.get("t2")!]).toEqual(["c"]);
    expect(
      raidPrepSkipMapsEqual(merged, mergeRaidPrepSkipMaps(merged)),
    ).toBe(true);
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

describe("multi-map raid prep progress", () => {
  const meme: RaidPrepTaskLike = {
    id: "meme",
    name: "这是什么梗？",
    objectives: [
      {
        id: "s1",
        type: "mark",
        description: "在塔科夫街区被铁丝网缠绕的尸体处安装Wi-Fi摄像头",
        maps: [{ slug: "streets", name: "塔科夫街区" }],
      },
      {
        id: "s2",
        type: "mark",
        description: "在塔科夫街区的烧伤女孩病房处安装Wi-Fi摄像头",
        maps: [{ slug: "streets", name: "塔科夫街区" }],
      },
      {
        id: "c1",
        type: "mark",
        description: "在海关的旧加油站安装Wi-Fi摄像头",
        maps: [{ slug: "customs", name: "海关" }],
      },
      {
        id: "w1",
        type: "mark",
        description: "在森林的木屋处安装Wi-Fi摄像头",
        maps: [{ slug: "woods", name: "森林" }],
      },
    ],
  };

  it("only lists this-map steps for checkboxes", () => {
    expect(
      collectRaidPrepTaskObjectives(meme, "streets").map((row) => row.id),
    ).toEqual(["s1", "s2"]);
    expect(
      collectRaidPrepTaskObjectives(meme, "customs").map((row) => row.id),
    ).toEqual(["c1"]);
  });

  it("treats this-map steps complete without requiring other maps", () => {
    expect(raidPrepMapObjectivesComplete(meme, "streets")).toBe(false);
    expect(
      raidPrepMapObjectivesComplete(meme, "streets", new Set(["s1"])),
    ).toBe(false);
    expect(
      raidPrepMapObjectivesComplete(meme, "streets", new Set(["s1", "s2"])),
    ).toBe(true);
    expect(
      raidPrepMapObjectivesComplete(meme, "customs", new Set(["s1", "s2"])),
    ).toBe(false);
    expect(
      raidPrepMapObjectivesComplete(meme, "customs", new Set(["c1"])),
    ).toBe(true);
    expect(raidPrepMapObjectivesComplete(meme, "streets", new Set())).toBe(
      false,
    );
    expect(
      raidPrepMapObjectivesComplete({ id: "empty" }, "streets", new Set(["x"])),
    ).toBe(false);
  });

  it("groups remaining maps for the prep popup", () => {
    const groups = collectRaidPrepOtherMapGroups(meme, "streets");
    expect(formatRaidPrepOtherMapsLead(groups)).toBe(
      "此任务还需在海关、森林完成",
    );
    expect(groups.map((row) => row.mapLabel)).toEqual(["海关", "森林"]);
    expect(groups[0]?.lines).toEqual(["在海关的旧加油站安装Wi-Fi摄像头"]);
    expect(groups[1]?.lines).toEqual(["在森林的木屋处安装Wi-Fi摄像头"]);
    const summary = buildRaidPrepSummary(
      [meme],
      "streets",
      new Map([["meme", new Set(["s1", "s2"])]]),
    );
    expect(summary[0]?.mapComplete).toBe(true);
    expect(summary[0]?.otherMapGroups.map((row) => row.mapLabel)).toEqual([
      "海关",
      "森林",
    ]);
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
      steps: [],
      traderSlug: "",
      keyNames: [],
      showNoKey: false,
      optional: false,
      objectiveId: "",
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
        steps: [],
        traderSlug: "",
        keyNames: [],
        showNoKey: false,
        optional: false,
        objectiveId: "o-visit",
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
        overlay("逃跑（第1处）", [{ x: 10, z: 10 }], {
          taskId: "t-run",
          keyNames: ["Dorm 114"],
        }),
        overlay("逃跑（第2处）", [{ x: 12, z: 11 }], {
          taskId: "t-run",
          key: "run-2",
          showNoKey: true,
        }),
      ],
      36,
    );
    expect(labels).toHaveLength(1);
    expect(labels[0].items.map((item) => item.title)).toEqual([
      "逃跑（第1处）",
      "逃跑（第2处）",
    ]);
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

  it("keeps many far-apart seeds as separate labels", () => {
    const overlays = Array.from({ length: 40 }, (_, index) =>
      overlay(`Task-${index}`, [{ x: index * 400, z: index * 400 }], {
        taskId: `t${index}`,
      }),
    );
    expect(clusterRaidPrepOverlayLabels(overlays, 36)).toHaveLength(40);
  });
});

describe("raidPrepVirtualWindow", () => {
  it("returns empty for zero rows", () => {
    expect(
      raidPrepVirtualWindow({
        scrollTop: 0,
        viewportHeight: 400,
        count: 0,
        rowHeight: 56,
      }),
    ).toEqual({ start: 0, end: 0, padTop: 0, padBottom: 0 });
  });

  it("windows a long list with overscan", () => {
    const win = raidPrepVirtualWindow({
      scrollTop: 560,
      viewportHeight: 280,
      count: 80,
      rowHeight: 56,
      overscan: 2,
    });
    expect(win.start).toBe(8);
    expect(win.end).toBe(17);
    expect(win.padTop).toBe(448);
    expect(win.padBottom).toBe((80 - 17) * 56);
  });
});

describe("raid prep geometry cache", () => {
  it("lists missing ids and merges fetched items", () => {
    const cached = { a: { id: "a", name: "A" } };
    expect(missingRaidPrepGeometryIds(cached, ["a", "b", "b", ""])).toEqual([
      "b",
    ]);
    expect(
      mergeRaidPrepGeometryItems(cached, [{ id: "b", name: "B" }]),
    ).toEqual({
      a: { id: "a", name: "A" },
      b: { id: "b", name: "B" },
    });
    expect(
      hydrateRaidPrepCatalogRows(
        [{ id: "a", name: "lean" }, { id: "b", name: "lean-b" }],
        { a: { id: "a", name: "rich" } },
      ),
    ).toEqual([{ id: "a", name: "rich" }, { id: "b", name: "lean-b" }]);
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
  it("filters by trader and query", () => {
    const rows = [
      {
        id: "a",
        name: "Alpha",
        trader_slug: "prapor",
        trader_name: "Prapor",
      },
      {
        id: "b",
        name: "Beta",
        trader_slug: "therapist",
        trader_name: "Therapist",
      },
    ];
    expect(filterRaidPrepRows(rows, { trader: "prapor" }).map((r) => r.id)).toEqual([
      "a",
    ]);
    expect(filterRaidPrepRows(rows, { q: "beta" }).map((r) => r.id)).toEqual(["b"]);
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

  it("does not treat shoreline outdoor lows as underground", () => {
    const bands = mapLayerFloorBands({
      heightRange: [-1000, -1],
      layers: [
        { name: "2nd Floor", extents: [{ height: [-1, 2] }] },
        { name: "3rd Floor", extents: [{ height: [2, 1000] }] },
        {
          name: "Underground",
          extents: [
            {
              height: [-1000, -5],
              bounds: [
                [
                  [-137, -68],
                  [-237, -104],
                  "west wing",
                ],
                [
                  [-234, -134],
                  [-268, -163],
                  "admin",
                ],
              ],
            },
          ],
        },
      ],
    });
    const road = { x: -355, z: 188 };
    const westWing = { x: -180, z: -80 };
    expect(overlayFloorForPoint(-6, bands, road)).toBe("");
    expect(overlayFloorForPoint(-6, bands)).toBe("");
    expect(overlayFloorForPoint(-6, bands, westWing)).toBe("Underground");
    expect(overlayVisibleOnFloor({ min: -6, max: -6 }, "", bands, road)).toBe(
      true,
    );
    expect(
      overlayVisibleOnFloor({ min: -6, max: -6 }, "Underground", bands, road),
    ).toBe(false);
    expect(
      overlayVisibleOnFloor({ min: -6, max: -6 }, "", bands, westWing),
    ).toBe(false);
    expect(
      overlayVisibleOnFloor(
        { min: -6, max: -6 },
        "Underground",
        bands,
        westWing,
      ),
    ).toBe(true);
  });

  it("matches a later bounded extent, not only the first", () => {
    const bands = mapLayerFloorBands({
      heightRange: [-1000, 2],
      layers: [
        {
          name: "2nd Floor",
          extents: [
            {
              height: [2.7, 6.5],
              bounds: [[[10, 10], [20, 20], "dorms"]],
            },
            {
              height: [14, 15],
              bounds: [[[400, -40], [450, -90], "sniper"]],
            },
          ],
        },
      ],
    });
    expect(overlayFloorForPoint(14.5, bands, { x: 420, z: -60 })).toBe(
      "2nd Floor",
    );
    expect(overlayFloorForPoint(4, bands, { x: 420, z: -60 })).toBe("");
    expect(overlayFloorForPoint(4, bands, { x: 15, z: 15 })).toBe("2nd Floor");
    expect(
      overlayVisibleOnFloor(
        { min: 14.5, max: 14.5 },
        "2nd Floor",
        bands,
        { x: 15, z: 15 },
      ),
    ).toBe(false);
  });

  it("keeps shoreline maps.json outdoor points on ground", () => {
    const layer = findInteractiveMap("shoreline");
    const bands = mapLayerFloorBands(layer);
    const underground = bands.find((band) => band.name === "Underground");
    expect(underground?.extents?.some((extent) => extent.bounds?.length)).toBe(
      true,
    );
    expect(overlayFloorForPoint(-6, bands, { x: -355, z: 188 })).toBe("");
    expect(overlayFloorForPoint(-6, bands, { x: -180, z: -80 })).toBe(
      "Underground",
    );
  });

  it("keeps a tall streets courtyard playground on ground", () => {
    const layer = findInteractiveMap("streets-of-tarkov");
    const bands = mapLayerFloorBands(layer);
    const playground = { min: 2.28, max: 11.58 };
    const at = { x: 215.64, z: 360.7 };
    expect(overlayFloorForSpan(playground, bands, at)).toBe("");
    expect(overlayFloorForPoint(8.23, bands, at)).toBe("");
    expect(overlayVisibleOnFloor(playground, "", bands, at)).toBe(true);
    expect(overlayVisibleOnFloor(playground, "2nd Floor", bands, at)).toBe(
      true,
    );
  });

  it("does not promote a ground zone just because the trigger box clips 2nd", () => {
    const bands = mapLayerFloorBands({
      heightRange: [-6, 10],
      layers: [{ name: "2nd Floor", extents: [{ height: [10, 15] }] }],
    });
    const span = { min: 2, max: 11.5 };
    expect(overlayFloorForSpan(span, bands)).toBe("");
    expect(overlayVisibleOnFloor(span, "", bands)).toBe(true);
    expect(overlayVisibleOnFloor(span, "2nd Floor", bands)).toBe(true);
    expect(overlayFloorForSpan({ min: 11, max: 14 }, bands)).toBe("2nd Floor");
    expect(overlayVisibleOnFloor({ min: 11, max: 14 }, "", bands)).toBe(false);
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
    expect(resolveRaidPrepLocateTargets(task, "customs")).toEqual([
      { x: 9, z: 8, objectiveId: "o-main" },
      { x: 1, z: 1, objectiveId: "o-opt" },
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

  it("does not cycle the same truck twice when zone copies repeat", () => {
    const task: RaidPrepTaskLike = {
      id: "t-truck",
      objectives: [
        {
          id: "o-mark",
          zones: [
            { id: "z1", map_slug: "customs", x: 3, z: 4 },
            { id: "z1", map_slug: "customs", x: 3, z: 4 },
          ],
        },
        {
          id: "o-visit",
          optional: true,
          zones: [{ id: "z1", map_slug: "customs", x: 3, z: 4 }],
        },
      ],
    };
    expect(resolveRaidPrepLocatePoints(task, "customs")).toEqual([{ x: 3, z: 4 }]);
  });
});

describe("raidPrepIdsFromTaskProgress", () => {
  it("keeps catalog order and drops done or unknown ids", () => {
    expect(
      raidPrepIdsFromTaskProgress(
        ["woods-a", "woods-b", "woods-c"],
        ["woods-c", "other", "woods-a", "woods-b"],
        ["woods-b"],
      ),
    ).toEqual(["woods-a", "woods-c"]);
  });

  it("ignores blanks and repeats", () => {
    expect(
      raidPrepIdsFromTaskProgress(
        [" a ", "a", "b"],
        ["a", " a ", "", "b"],
        [" b "],
      ),
    ).toEqual(["a"]);
  });
});

describe("planRaidPrepTaskProgressSync", () => {
  it("merges in-progress map tasks onto the current selection", () => {
    const plan = planRaidPrepTaskProgressSync({
      catalogIds: ["a", "b", "c"],
      selectedIds: ["c"],
      startedIds: ["a", "x"],
      doneIds: ["b"],
    });
    expect(plan.matchedIds).toEqual(["a"]);
    expect(plan.addedIds).toEqual(["a"]);
    expect(plan.nextIds).toEqual(["c", "a"]);
    expect(plan.hint).toBe("已勾选 1 个进行中任务");
  });

  it("does not uncheck existing picks when nothing new matches", () => {
    const plan = planRaidPrepTaskProgressSync({
      catalogIds: ["a", "b"],
      selectedIds: ["a"],
      startedIds: ["a"],
    });
    expect(plan.addedIds).toEqual([]);
    expect(plan.nextIds).toEqual(["a"]);
    expect(plan.hint).toBe("进行中的本图任务已全部勾选");
  });

  it("caps new unique tasks against occupied room ids", () => {
    const occupied = Array.from({ length: RAID_PREP_MAX_SELECTED }, (_, i) => `r${i}`);
    const plan = planRaidPrepTaskProgressSync({
      catalogIds: ["new", occupied[0]!],
      selectedIds: [],
      startedIds: ["new", occupied[0]!],
      occupiedIds: occupied,
    });
    expect(plan.addedIds).toEqual([occupied[0]]);
    expect(plan.nextIds).toEqual([occupied[0]]);
    expect(plan.hint).toBe(
      `已勾选 1 个进行中任务（已达 ${RAID_PREP_MAX_SELECTED} 个上限）`,
    );
  });

  it("explains an empty personal-center started list", () => {
    expect(
      describeRaidPrepTaskProgressSync({
        startedCount: 0,
        matchedCount: 0,
        addedCount: 0,
      }),
    ).toBe("个人中心没有进行中的任务");
    expect(
      describeRaidPrepTaskProgressSync({
        startedCount: 2,
        matchedCount: 0,
        addedCount: 0,
      }),
    ).toBe("没有进行中且属于本图的任务");
  });
});

describe("raid prep packing and settle", () => {
  it("hides completed catalog rows", () => {
    expect(
      hideCompletedRaidPrepRows(
        [{ id: "a" }, { id: "b" }, { id: "c" }],
        ["b", ""],
      ),
    ).toEqual([{ id: "a" }, { id: "c" }]);
  });

  it("reads task progress status and filters list scopes", () => {
    expect(raidPrepTaskProgressStatus("a", ["a"], ["a"])).toBe("done");
    expect(raidPrepTaskProgressStatus("b", ["a"], ["b"])).toBe("active");
    expect(raidPrepTaskProgressStatus("c", ["a"], ["b"])).toBe("todo");
    expect(raidPrepTaskProgressLabel("active")).toBe("进行中");
    expect(raidPrepTaskProgressLabel("todo")).toBe("未完成");
    expect(raidPrepTaskProgressLabel("done")).toBe("已完成");
    expect(raidPrepObjectiveCheckedForViewer("s1", new Set(), true)).toBe(true);
    expect(raidPrepObjectiveCheckedForViewer("s1", new Set(["s1"]), false)).toBe(
      true,
    );
    expect(raidPrepObjectiveCheckedForViewer("s1", new Set(), false)).toBe(
      false,
    );
    const rows = [{ id: "a" }, { id: "b" }, { id: "c" }];
    expect(
      filterRaidPrepRowsByScope(rows, "all", {
        doneIds: ["a"],
        startedIds: ["b"],
      }).map((row) => row.id),
    ).toEqual(["a", "b", "c"]);
    expect(
      filterRaidPrepRowsByScope(rows, "picked", { selectedIds: ["b"] }).map(
        (row) => row.id,
      ),
    ).toEqual(["b"]);
    expect(
      filterRaidPrepRowsByScope(rows, "active", {
        doneIds: ["a"],
        startedIds: ["b"],
      }).map((row) => row.id),
    ).toEqual(["b"]);
    expect(
      filterRaidPrepRowsByScope(rows, "todo", {
        doneIds: ["a"],
        startedIds: ["b"],
      }).map((row) => row.id),
    ).toEqual(["c"]);
    expect(
      filterRaidPrepRowsByScope(rows, "done", {
        doneIds: ["a"],
        startedIds: ["b"],
      }).map((row) => row.id),
    ).toEqual(["a"]);
    expect(
      countRaidPrepRowsByScope(rows, {
        selectedIds: ["a", "c"],
        doneIds: ["a"],
        startedIds: ["b"],
      }),
    ).toEqual({ all: 3, picked: 2, active: 1, todo: 1, done: 1 });
    expect(
      sortRaidPrepRowsByProgress(rows, ["a"], ["b"]).map((row) => row.id),
    ).toEqual(["b", "c", "a"]);
    expect(groupRaidPrepRowsByProgress(rows, ["a"], ["b"])).toEqual({
      active: [{ id: "b" }],
      todo: [{ id: "c" }],
      done: [{ id: "a" }],
    });
  });

  it("merges the same needed item across tasks", () => {
    const merged = mergeRaidPrepNeededItems([
      {
        id: "bolt",
        name: "螺栓",
        icon_link: "",
        types: [],
        count: 3,
        found_in_raid: false,
        optional: false,
        kind: "item",
        role: "find",
        objectiveType: "findItem",
      },
      {
        id: "bolt",
        name: "螺栓",
        icon_link: "",
        types: [],
        count: 2,
        found_in_raid: false,
        optional: false,
        kind: "item",
        role: "find",
        objectiveType: "findItem",
      },
    ]);
    expect(merged).toHaveLength(1);
    expect(merged[0]?.count).toBe(5);
  });

  it("treats a key as missing only when nobody owns or brings it", () => {
    expect(raidPrepKeyIsMissing(["甲"], [])).toBe(false);
    expect(raidPrepKeyIsMissing([], ["乙"])).toBe(false);
    expect(raidPrepKeyIsMissing([], [])).toBe(true);
  });

  it("blocks a task only when every required key is missing", () => {
    const key = (
      id: string,
      optional = false,
    ): RaidPrepNeededItem => ({
      id,
      name: id,
      icon_link: "",
      types: [],
      count: 1,
      found_in_raid: false,
      optional,
      kind: "key",
      role: "钥匙",
      objectiveType: "key",
    });
    expect(raidPrepTaskKeysUnavailable([], new Set())).toBe(false);
    expect(raidPrepTaskKeysUnavailable([key("k1", true)], new Set())).toBe(false);
    expect(raidPrepTaskKeysUnavailable([key("k1"), key("k2", true)], new Set())).toBe(
      true,
    );
    expect(
      raidPrepTaskKeysUnavailable([key("k1"), key("k2")], new Set(["k2"])),
    ).toBe(false);
    expect(raidPrepTaskKeysUnavailable([key("k1")], new Set(["k1"]))).toBe(false);
    expect(RAID_PREP_UNAVAILABLE_KEY_HINT).not.toMatch(/隐藏|做不了/);
    expect(
      raidPrepTaskKeysUnavailable(
        [{ ...key("any"), anyOf: [key("a"), key("b")] }],
        new Set(["b"]),
      ),
    ).toBe(false);
    expect(mergeRaidPrepAvailableKeyIds([{ item_id: "k1" }], [{ item_id: "k2" }])).toEqual(
      new Set(["k1", "k2"]),
    );
  });

  it("lists tasks whose required keys nobody owns, without hiding overlays", () => {
    const task: RaidPrepTaskLike = {
      id: "wet-2",
      name: "带血的水",
      needed_keys: [
        {
          map: { slug: "customs" },
          keys: [{ id: "office", name: "公司主管办公室钥匙" }],
        },
      ],
      objectives: [
        {
          id: "o-1",
          type: "visit",
          description: "检查办公室",
          required_keys: [[{ id: "office", name: "公司主管办公室钥匙" }]],
          zones: [{ id: "z-1", map_slug: "customs", x: 1, z: 1 }],
        },
      ],
    };
    expect(
      collectUnavailableRaidPrepTaskIds([task], "customs", undefined, new Set()),
    ).toEqual(new Set(["wet-2"]));
    expect(
      collectUnavailableRaidPrepTaskIds(
        [task],
        "customs",
        undefined,
        new Set(["office"]),
      ),
    ).toEqual(new Set());
    expect(buildRaidPrepOverlays([task], "customs")).toHaveLength(1);
  });

  it("drops completed tasks after a successful raid", () => {
    expect(
      settleRaidPrepSelection({
        selectedIds: ["a", "b", "c"],
        completedIds: ["b"],
      }),
    ).toEqual({ nextIds: ["a", "c"], removedIds: ["b"] });
    expect(
      settleRaidPrepSelection({
        selectedIds: ["a", "b"],
        completedIds: ["b"],
        aborted: true,
      }).nextIds,
    ).toEqual(["a", "b"]);
  });

  it("shows overlay key names on the map label", () => {
    expect(formatRaidPrepOverlayKeyLabel(["宿舍 114", "Dorm 105"])).toBe(
      "宿舍 114、Dorm 105",
    );
    expect(formatRaidPrepOverlayKeyLabel([], true)).toBe("不需要钥匙");
  });
});
