import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ANY_TASK_MAP,
  applyTaskDoneToggle,
  setTaskStatus,
  collectTaskMapChips,
  describeTaskMap,
  groupTasksByTrader,
  loadTaskCursorAt,
  loadTaskDoneIds,
  loadTaskObjectivePairs,
  loadTaskStartedIds,
  loadTaskSyncAt,
  parseTaskDonesState,
  planAccountTaskHydrate,
  keepCatalogTaskProgress,
  mergeObjectivesForTask,
  displayTaskProgressName,
  isWritableTaskStatus,
  resolveAccountTaskProgress,
  resolveTaskMapId,
  resolveTaskStatus,
  saveTaskDoneIds,
  saveTaskProgress,
  saveTaskSyncMark,
  setTaskObjective,
  summarizeTaskProgress,
  taskHitsMap,
  taskLoyaltyLevel,
  taskPlayerLevelLabel,
} from "./tarkovTaskTree";
import type { TaskListItem } from "./tarkovTaskTree";

function task(
  id: string,
  name: string,
  extra: Partial<TaskListItem> = {},
): TaskListItem {
  return { id, name, trader_slug: "prapor", ...extra };
}

describe("task progress", () => {
  const items = [
    task("p1", "惩罚者 - 1"),
    task("p2", "惩罚者 - 2"),
    task("side", "支线"),
  ];

  it("summarizes incomplete / active / completed", () => {
    expect(summarizeTaskProgress(items, new Set(["p1"]), new Set(["p2"]))).toEqual({
      total: 3,
      incomplete: 1,
      active: 1,
      completed: 1,
      failed: 0,
      unreachable: 0,
    });
  });

  it("toggles a single task", () => {
    expect(applyTaskDoneToggle([], "p2", true)).toEqual(["p2"]);
    expect(applyTaskDoneToggle(["p1", "p2"], "p1", false)).toEqual(["p2"]);
  });

  it("resolves done over started", () => {
    expect(resolveTaskStatus("p1", new Set(["p1"]), new Set(["p1"]))).toBe("done");
    expect(resolveTaskStatus("p1", new Set(), new Set(["p1"]))).toBe("active");
    expect(resolveTaskStatus("p1", new Set(), new Set())).toBe("todo");
  });

  it("derives failed and unreachable from line index", () => {
    const mutex = { mutex_ids: ["choose"], blocked_by: [] };
    const fork = { mutex_ids: ["choose"], blocked_by: ["bat1"] };
    expect(
      resolveTaskStatus("price1", new Set(["price1"]), new Set(), mutex),
    ).toBe("done");
    expect(
      resolveTaskStatus("price1", new Set(["choose"]), new Set(), mutex),
    ).toBe("failed");
    expect(
      resolveTaskStatus("price2", new Set(["bat1"]), new Set(), fork),
    ).toBe("unreachable");
    expect(
      resolveTaskStatus("price2", new Set(), new Set(["bat1"]), fork),
    ).toBe("unreachable");
    expect(
      resolveTaskStatus("choose", new Set(), new Set(["choose"]), mutex),
    ).toBe("active");
    expect(isWritableTaskStatus("failed")).toBe(false);
    expect(isWritableTaskStatus("todo")).toBe(true);
  });

  it("counts failed and unreachable outside incomplete", () => {
    const rows = [
      task("price1", "独立的代价", { mutex_ids: ["choose"], blocked_by: ["bat2"] }),
      task("price2", "独立的代价", { mutex_ids: ["choose"], blocked_by: ["bat1"] }),
      task("side", "支线"),
    ];
    expect(
      summarizeTaskProgress(rows, new Set(["choose", "bat1"]), new Set()),
    ).toEqual({
      total: 3,
      incomplete: 1,
      active: 0,
      completed: 0,
      failed: 2,
      unreachable: 0,
    });
    expect(summarizeTaskProgress(rows, new Set(["bat1"]), new Set())).toEqual({
      total: 3,
      incomplete: 2,
      active: 0,
      completed: 0,
      failed: 0,
      unreachable: 1,
    });
  });

  it("appends line hint without duplicating faction", () => {
    expect(
      displayTaskProgressName({
        id: "p1",
        name: "独立的代价",
        line_hint: "经「横插一杠」",
      }),
    ).toBe("独立的代价（经「横插一杠」）");
    expect(
      displayTaskProgressName({
        id: "u",
        name: "湿活",
        faction_name: "USEC",
        line_hint: "USEC",
      }),
    ).toBe("湿活 (USEC)");
  });

  it("hides ids missing from the live catalog", () => {
    expect(
      keepCatalogTaskProgress(
        ["keep", "gone"],
        ["live", "gone-start"],
        ["keep", "live"],
      ),
    ).toEqual({ done: ["keep"], started: ["live"] });
    expect(
      keepCatalogTaskProgress(["gone"], ["gone-start"], null),
    ).toEqual({ done: ["gone"], started: ["gone-start"] });
  });

  it("sets a specific status", () => {
    expect(setTaskStatus([], [], "p1", "active")).toEqual({
      done: [],
      started: ["p1"],
    });
    expect(setTaskStatus([], ["p1"], "p1", "done")).toEqual({
      done: ["p1"],
      started: [],
    });
    expect(setTaskStatus(["p1"], [], "p1", "todo")).toEqual({
      done: [],
      started: [],
    });
    expect(setTaskStatus(["p1"], ["p2"], "p2", "done")).toEqual({
      done: ["p1", "p2"],
      started: [],
    });
  });
});

describe("groupTasksByTrader", () => {
  it("keeps completed tasks in the group", () => {
    const items = [
      task("p1", "惩罚者 - 1"),
      task("p2", "惩罚者 - 2"),
      task("solo", "单独"),
    ];
    const groups = groupTasksByTrader(
      items,
      [{ slug: "prapor", name: "Prapor" }],
      ["solo"],
    );
    expect(groups[0]?.items.map((row) => row.id)).toEqual(["p1", "p2", "solo"]);
    expect(groups[0]?.done).toBe(1);
    expect(groups[0]?.total).toBe(3);
  });

  it("filters by name", () => {
    const items = [
      task("p1", "惩罚者 - 1"),
      task("side", "支线"),
    ];
    const groups = groupTasksByTrader(
      items,
      [{ slug: "prapor", name: "Prapor" }],
      [],
      { q: "支线" },
    );
    expect(groups[0]?.items.map((row) => row.id)).toEqual(["side"]);
  });

  it("filters by map aliases", () => {
    const items = [
      task("c1", "海关", { map_slug: "bigmap", map_name: "Customs" }),
      task("w1", "森林", { map_slug: "woods", map_name: "森林" }),
      task("any", "任意", { map_slug: "", map_name: "" }),
    ];
    const groups = groupTasksByTrader(
      items,
      [{ slug: "prapor", name: "Prapor" }],
      [],
      { map: "customs" },
    );
    expect(groups[0]?.items.map((row) => row.id)).toEqual(["c1"]);
  });
});

describe("task map chips", () => {
  it("canonicalizes slugs and names", () => {
    expect(resolveTaskMapId({ map_slug: "bigmap" })).toBe("customs");
    expect(resolveTaskMapId({ map_name: "海关" })).toBe("customs");
    expect(resolveTaskMapId({})).toBe("");
    expect(taskHitsMap({ map_slug: "the-lab" }, "lab")).toBe(true);
    expect(taskHitsMap({ map_name: "森林" }, "woods")).toBe(true);
    expect(taskHitsMap({}, ANY_TASK_MAP)).toBe(true);
    expect(taskHitsMap({ map_slug: "woods" }, ANY_TASK_MAP)).toBe(false);
  });

  it("lists maps present on the board", () => {
    const chips = collectTaskMapChips([
      task("c1", "海关", { map_slug: "customs" }),
      task("c2", "海关二", { map_slug: "bigmap" }),
      task("w1", "森林", { map_slug: "woods" }),
      task("any", "任意"),
    ]);
    expect(chips.map((row) => ({ id: row.id, count: row.count }))).toEqual([
      { id: "customs", count: 2 },
      { id: "woods", count: 1 },
      { id: ANY_TASK_MAP, count: 1 },
    ]);
    expect(chips[0]?.icon).toBeTruthy();
    expect(describeTaskMap({ map_slug: "bigmap" })).toMatchObject({
      id: "customs",
      label: "海关",
    });
    expect(describeTaskMap({})).toBeNull();
  });
});

describe("task dones storage", () => {
  const mem = new Map<string, string>();

  beforeEach(() => {
    mem.clear();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => mem.get(key) ?? null,
      setItem: (key: string, value: string) => {
        mem.set(key, value);
      },
      removeItem: (key: string) => {
        mem.delete(key);
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps pvp and pve lists apart", () => {
    saveTaskDoneIds("pvp", ["a"]);
    saveTaskDoneIds("pve", ["b"]);
    expect(loadTaskDoneIds("pvp")).toEqual(["a"]);
    expect(loadTaskDoneIds("pve")).toEqual(["b"]);
    expect(parseTaskDonesState('["legacy"]', "pvp")).toEqual(["legacy"]);
    expect(parseTaskDonesState('["legacy"]', "pve")).toEqual([]);
    saveTaskProgress("pvp", ["a"], ["s"]);
    expect(loadTaskStartedIds("pvp")).toEqual(["s"]);
    expect(loadTaskStartedIds("pve")).toEqual([]);
    saveTaskSyncMark("pvp", "2026-08-31 00:40:00", "2026-08-30 20:11:02");
    expect(loadTaskSyncAt("pvp")).toBe("2026-08-31 00:40:00");
    expect(loadTaskCursorAt("pvp")).toBe("2026-08-30 20:11:02");
    expect(loadTaskSyncAt("pve")).toBe("");
    saveTaskSyncMark("pvp", "2026-08-31 00:41:00", "2026-08-30 19:00:00");
    expect(loadTaskCursorAt("pvp")).toBe("2026-08-30 20:11:02");
    saveTaskSyncMark("pvp", "2026-08-31 00:42:00");
    expect(loadTaskSyncAt("pvp")).toBe("2026-08-31 00:42:00");
    expect(loadTaskCursorAt("pvp")).toBe("2026-08-30 20:11:02");
    expect(loadTaskStartedIds("pvp")).toEqual(["s"]);
  });

  it("hydrates by union so a new PC cannot wipe the account", () => {
    saveTaskProgress("pvp", ["local-done"], ["local-start"]);
    expect(
      planAccountTaskHydrate({
        serverDone: [],
        serverStarted: [],
        localDone: ["local-done"],
        localStarted: ["local-start"],
      }),
    ).toEqual({
      done: ["local-done"],
      started: ["local-start"],
      objectives: [],
      upload: true,
    });
    expect(
      planAccountTaskHydrate({
        serverDone: ["account-done", "shared"],
        serverStarted: ["account-start"],
        localDone: ["shared", "raid-done"],
        localStarted: ["raid-start"],
      }),
    ).toEqual({
      done: ["account-done", "shared", "raid-done"],
      started: ["account-start", "raid-start"],
      objectives: [],
      upload: true,
    });
    expect(
      planAccountTaskHydrate({
        serverDone: ["account-done"],
        serverStarted: ["account-start"],
        localDone: [],
        localStarted: [],
      }),
    ).toEqual({
      done: ["account-done"],
      started: ["account-start"],
      objectives: [],
      upload: false,
    });
    saveTaskProgress("pvp", [], []);
    expect(
      resolveAccountTaskProgress(
        { task_ids: ["remote"], started_ids: ["live"] },
        "pvp",
      ),
    ).toEqual({ done: ["remote"], started: ["live"], objectives: [] });
  });

  it("unions objective pairs and keeps pvp/pve apart", () => {
    saveTaskProgress(
      "pvp",
      ["t1"],
      [],
      false,
      false,
      [{ task_id: "t1", objective_id: "cam-a" }],
    );
    expect(
      planAccountTaskHydrate({
        serverDone: ["t1"],
        serverStarted: [],
        serverObjectives: [{ task_id: "t1", objective_id: "cam-b" }],
        localDone: ["t1"],
        localStarted: [],
        localObjectives: [{ task_id: "t1", objective_id: "cam-a" }],
      }),
    ).toEqual({
      done: ["t1"],
      started: [],
      objectives: [
        { task_id: "t1", objective_id: "cam-b" },
        { task_id: "t1", objective_id: "cam-a" },
      ],
      upload: true,
    });
    expect(loadTaskObjectivePairs("pvp")).toEqual([
      { task_id: "t1", objective_id: "cam-a" },
    ]);
    expect(loadTaskObjectivePairs("pve")).toEqual([]);
    expect(
      setTaskObjective(
        [{ task_id: "t1", objective_id: "cam-a" }],
        "t1",
        "cam-a",
        false,
      ),
    ).toEqual([]);
    expect(mergeObjectivesForTask([], "t1", ["a", "b", "a"])).toEqual([
      { task_id: "t1", objective_id: "a" },
      { task_id: "t1", objective_id: "b" },
    ]);
  });
});

describe("task level and loyalty marks", () => {
  it("hides a missing player level and clamps loyalty to 1–4", () => {
    expect(taskPlayerLevelLabel(undefined)).toBe("—");
    expect(taskPlayerLevelLabel(0)).toBe("—");
    expect(taskPlayerLevelLabel(15)).toBe("15");
    expect(taskLoyaltyLevel(undefined)).toBe(1);
    expect(taskLoyaltyLevel(0)).toBe(1);
    expect(taskLoyaltyLevel(2)).toBe(2);
    expect(taskLoyaltyLevel(3)).toBe(3);
    expect(taskLoyaltyLevel(4)).toBe(4);
    expect(taskLoyaltyLevel(9)).toBe(4);
  });
});
