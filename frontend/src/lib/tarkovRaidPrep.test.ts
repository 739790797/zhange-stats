import { describe, expect, it } from "vitest";
import {
  buildRaidPrepOverlays,
  buildRaidPrepSummary,
  clusterRaidPrepOverlayLabels,
  colorForTaskId,
  collectRaidPrepTaskItems,
  collectRaidPrepTaskKeys,
  isTarkovHexId,
  mapSlugKeys,
  neededKeyNamesForMap,
  normalizeRaidPrepMapId,
  objectiveAppliesToMap,
  objectiveZoneNames,
  parseCsvParam,
  partitionRaidPrepRows,
  pinSelectedRaidPrepRows,
  raidPrepMapOptions,
  selectedTasksFromCatalog,
  serializeSelectedIds,
  sortRaidPrepSummaryByParticipants,
  tarkovReadableName,
  traderFilterLabel,
  type RaidPrepTaskLike,
  type TarkovRaidPrepOverlay,
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
      title: "Debut",
      traderSlug: "prapor",
      keyNames: ["Dorm 114"],
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
      keyNames: ["Dorm 114"],
      optional: false,
      points: [{ x: 10, z: 20 }],
    });
    expect(overlays[0].color).toBe(colorForTaskId("t1"));
    expect(objectiveZoneNames(task)).toEqual(["Dorms"]);
    expect(neededKeyNamesForMap(task, "customs")).toEqual(["Dorm 114"]);
    expect(neededKeyNamesForMap(task, "streets")).toEqual([]);
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
    expect(items.map((item) => `${item.role}:${item.name}×${item.count}`)).toEqual([
      "上交:金项链×7",
      "捡取:硬盘×1",
      "上交:金项链×2",
    ]);
    expect(items[2].found_in_raid).toBe(true);
    expect(items.some((item) => item.id === "ms2000")).toBe(false);
    expect(keys.some((item) => item.id === "k-other")).toBe(false);
  });

  it("treats objectives without a map as this raid", () => {
    expect(objectiveAppliesToMap({ type: "giveItem" }, "customs")).toBe(true);
    expect(
      objectiveAppliesToMap({ type: "plantItem", maps: [{ slug: "woods" }] }, "customs"),
    ).toBe(false);
    expect(
      objectiveAppliesToMap({ type: "plantItem", maps: [{ slug: "customs" }] }, "customs"),
    ).toBe(true);
  });

  it("lists selected tasks with their items", () => {
    const rows = buildRaidPrepSummary([task], "customs");
    expect(rows).toHaveLength(1);
    expect(rows[0].taskName).toBe("Debut");
    expect(rows[0].items).toHaveLength(3);
    expect(rows[0].keys.map((item) => item.name)).toEqual(["Dorm 114"]);
    expect(rows[0].types).toEqual(["findQuestItem", "giveItem"]);
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
    return {
      key: title,
      kind: "spawn",
      color: pink,
      title,
      subtitle: "",
      traderSlug: "",
      keyNames: [],
      optional: false,
      outline: [],
      points,
      ...extras,
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
      { title: "半路杀人", color: pink, traderSlug: "", count: 4, optional: false },
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
        overlay("半路杀人", [{ x: 10, z: 10 }]),
        overlay(" Debut ", [{ x: 12, z: 11 }], { color: blue, key: "debut" }),
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
        kind: "zone",
        color: blue,
        title: "Debut",
        subtitle: "",
        traderSlug: "",
        keyNames: [],
        optional: false,
        outline: [
          { x: 0, z: 0 },
          { x: 40, z: 0 },
          { x: 40, z: 40 },
        ],
        points: [{ x: 12, z: 8 }],
      },
    ]);
    expect(labels).toHaveLength(1);
    expect(labels[0]).toMatchObject({ x: 12, z: 8 });
    expect(labels[0].items).toEqual([
      { title: "Debut", color: blue, traderSlug: "", count: 1, optional: false },
    ]);
  });

  it("keeps optional labels separate from required ones of the same task", () => {
    const labels = clusterRaidPrepOverlayLabels([
      overlay("Shortage", [{ x: 1, z: 1 }]),
      overlay("Shortage", [{ x: 2, z: 2 }], {
        key: "opt",
        optional: true,
      }),
    ]);
    expect(labels).toHaveLength(1);
    expect(labels[0].items).toEqual([
      { title: "Shortage", color: pink, traderSlug: "", count: 1, optional: false },
      { title: "Shortage", color: pink, traderSlug: "", count: 1, optional: true },
    ]);
  });

  it("keeps the trader slug on clustered labels", () => {
    const labels = clusterRaidPrepOverlayLabels([
      overlay("半路杀人", [{ x: 1, z: 1 }], { traderSlug: "prapor" }),
      overlay("Debut", [{ x: 2, z: 2 }], {
        color: blue,
        key: "debut",
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
