import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  TARKOV_TASK_PROGRESS_VIEW_KEY,
  buildTaskForest,
  collectPrereqClosure,
  countForestTasks,
  filterTaskForest,
  flowCardRibbonGradient,
  flowCardRibbonKinds,
  forestChildDepth,
  loadTaskProgressView,
  parseTaskProgressView,
  saveTaskProgressView,
  splitFlowForest,
  tarkovFlowTaskAnchor,
  tarkovFlowTraderAnchor,
  taskChoiceLabel,
  type TaskForestChild,
  type TaskForestItem,
  type TaskForestNode,
} from "./tarkovTaskForest";

function task(
  id: string,
  name: string,
  extra: Partial<TaskForestItem> = {},
): TaskForestItem {
  return { id, name, ...extra };
}

function findNode<T extends TaskForestItem>(
  children: readonly TaskForestChild<T>[],
  id: string,
): TaskForestNode<T> | undefined {
  for (const child of children) {
    if (child.kind === "choice") {
      for (const option of child.options) {
        if (option.task.id === id) return option;
        const nested = findNode(option.children, id);
        if (nested) return nested;
      }
      continue;
    }
    if (child.node.task.id === id) return child.node;
    const nested = findNode(child.node.children, id);
    if (nested) return nested;
  }
  return undefined;
}

function collectIds<T extends TaskForestItem>(
  children: readonly TaskForestChild<T>[],
): string[] {
  const out: string[] = [];
  for (const child of children) {
    if (child.kind === "choice") {
      for (const option of child.options) {
        out.push(option.task.id);
        out.push(...collectIds(option.children));
      }
    } else {
      out.push(child.node.task.id);
      out.push(...collectIds(child.node.children));
    }
  }
  return out;
}

describe("buildTaskForest", () => {
  it("hangs BTR forks on their own trunks and keeps extra prereqs", () => {
    const forest = buildTaskForest([
      task("stick", "横插一杠"),
      task("business", "稳定业务"),
      task("bat1", "电池换新", { prereq_ids: ["stick"], mutex_ids: ["bat2"] }),
      task("bat2", "电池换新", { prereq_ids: ["business"], mutex_ids: ["bat1"] }),
      task("disco", "反将一军"),
      task("price1", "独立的代价", {
        prereq_ids: ["bat1", "disco"],
        mutex_ids: ["choose"],
      }),
      task("price2", "独立的代价", {
        prereq_ids: ["bat2", "disco"],
        mutex_ids: ["choose"],
      }),
      task("choose", "识时务者为俊杰", { mutex_ids: ["price1", "price2"] }),
    ]);
    const bat1 = findNode(forest, "bat1");
    const bat2 = findNode(forest, "bat2");
    const price1 = findNode(forest, "price1");
    const price2 = findNode(forest, "price2");
    expect(findNode(forest, "stick")?.children[0]?.kind).toBe("task");
    expect(bat1 && findNode(bat1.children, "price1")).toBeTruthy();
    expect(bat2 && findNode(bat2.children, "price2")).toBeTruthy();
    expect(price1?.extraPrereqIds).toEqual(["disco"]);
    expect(price2?.extraPrereqIds).toEqual(["disco"]);
    expect(findNode(forest, "choose")?.children).toEqual([]);
    expect(collectIds(forest).sort()).toEqual([
      "bat1",
      "bat2",
      "business",
      "choose",
      "disco",
      "price1",
      "price2",
      "stick",
    ]);
    expect(countForestTasks(forest)).toBe(8);
  });

  it("groups mutex siblings that share a parent", () => {
    const forest = buildTaskForest([
      task("root", "起点"),
      task("a", "线A", { prereq_ids: ["root"], mutex_ids: ["b"] }),
      task("b", "线B", { prereq_ids: ["root"], mutex_ids: ["a"] }),
    ]);
    const root = findNode(forest, "root");
    expect(root?.children).toHaveLength(1);
    expect(root?.children[0]?.kind).toBe("choice");
    if (root?.children[0]?.kind !== "choice") return;
    expect(root.children[0].options.map((row) => row.task.id).sort()).toEqual([
      "a",
      "b",
    ]);
    expect(taskChoiceLabel(2)).toBe("二选一");
  });

  it("groups a three-way mutex as one choice at the roots", () => {
    const forest = buildTaskForest([
      task("chem", "化学-第4部分", { mutex_ids: ["curio", "big"] }),
      task("curio", "好奇心", { mutex_ids: ["chem", "big"] }),
      task("big", "大客户", { mutex_ids: ["chem", "curio"] }),
      task("plain", "首秀"),
    ]);
    const choice = forest.find((row) => row.kind === "choice");
    expect(choice?.kind).toBe("choice");
    if (choice?.kind !== "choice") return;
    expect(choice.options.map((row) => row.task.id).sort()).toEqual([
      "big",
      "chem",
      "curio",
    ]);
    expect(taskChoiceLabel(choice.options.length)).toBe("三选一");
    expect(forest.some((row) => row.kind === "task" && row.node.task.id === "plain")).toBe(
      true,
    );
  });

  it("pulls missing prereqs into the closure so follow-ups can nest", () => {
    const child = task("c", "后续", { prereq_ids: ["p"] });
    const parent = task("p", "前置");
    const catalog = new Map([
      ["c", child],
      ["p", parent],
    ]);
    const closure = collectPrereqClosure([child], catalog);
    expect(closure.map((row) => row.id).sort()).toEqual(["c", "p"]);
    const forest = buildTaskForest(closure);
    expect(findNode(forest, "c")?.extraPrereqIds).toEqual([]);
    expect(
      findNode(forest, "p") && findNode(findNode(forest, "p")!.children, "c"),
    ).toBeTruthy();
  });

  it("keeps out-of-group prereqs as extras on a root", () => {
    const forest = buildTaskForest([
      task("a", "后续", { prereq_ids: ["b"] }),
    ]);
    const node = findNode(forest, "a");
    expect(node?.extraPrereqIds).toEqual(["b"]);
    expect(forest).toHaveLength(1);
  });

  it("attaches to the later in-group prereq when both are listed", () => {
    const forest = buildTaskForest([
      task("a", "A"),
      task("b", "B", { prereq_ids: ["a"] }),
      task("c", "C", { prereq_ids: ["a", "b"] }),
    ]);
    const aNode = findNode(forest, "a");
    const bNode = findNode(forest, "b");
    expect(bNode && findNode(bNode.children, "c")).toBeTruthy();
    expect(findNode(forest, "c")?.extraPrereqIds).toEqual(["a"]);
    expect(
      aNode?.children.some(
        (child) => child.kind === "task" && child.node.task.id === "c",
      ),
    ).toBe(false);
  });

  it("breaks parent cycles without duplicating nodes", () => {
    const forest = buildTaskForest([
      task("a", "A", { prereq_ids: ["b"] }),
      task("b", "B", { prereq_ids: ["a"] }),
    ]);
    expect(collectIds(forest).sort()).toEqual(["a", "b"]);
    expect(countForestTasks(forest)).toBe(2);
  });
});

describe("splitFlowForest", () => {
  it("keeps sequenced roots as chains and leftover cards as isolates", () => {
    const forest = buildTaskForest([
      task("root", "惩罚者-第1部分"),
      task("next", "惩罚者-第2部分", { prereq_ids: ["root"] }),
      task("solo", "首秀"),
      task("a", "线A", { mutex_ids: ["b"] }),
      task("b", "线B", { mutex_ids: ["a"] }),
    ]);
    const split = splitFlowForest(forest);
    expect(split.chains.map((row) => (row.kind === "choice" ? "choice" : row.node.task.id))).toEqual(
      ["root", "choice"],
    );
    expect(forestChildDepth(split.chains[0]!)).toBe(2);
    expect(
      split.isolates.map((row) => (row.kind === "task" ? row.node.task.id : "")),
    ).toEqual(["solo"]);
  });
});

describe("off-tree prereqs", () => {
  it("keeps a foreign primary parent as extra on the local root", () => {
    const forest = buildTaskForest([
      task("t", "后续", { trader_slug: "therapist", prereq_ids: ["p"] }),
    ]);
    expect(findNode(forest, "t")?.extraPrereqIds).toEqual(["p"]);
    expect(findNode(forest, "p")).toBeUndefined();
  });

  it("keeps a foreign extra when a native parent exists", () => {
    const forest = buildTaskForest([
      task("a", "本商前置", { trader_slug: "therapist" }),
      task("c", "后续", {
        trader_slug: "therapist",
        prereq_ids: ["a", "p"],
      }),
    ]);
    expect(findNode(forest, "c")?.extraPrereqIds).toEqual(["p"]);
    expect(findNode(forest, "p")).toBeUndefined();
  });

  it("builds stable anchors", () => {
    expect(tarkovFlowTraderAnchor("prapor")).toBe("tarkov-flow-trader-prapor");
    expect(tarkovFlowTaskAnchor("abc")).toBe("tarkov-flow-task-abc");
  });
});

describe("flowCardRibbonKinds", () => {
  it("splits equally by relation kinds instead of always splitting on mutex", () => {
    expect(flowCardRibbonKinds({})).toEqual([]);
    expect(flowCardRibbonKinds({ prereq: true })).toEqual(["prereq"]);
    expect(flowCardRibbonKinds({ conflict: true })).toEqual(["conflict"]);
    expect(flowCardRibbonKinds({ prereq: true, conflict: true })).toEqual([
      "prereq",
      "conflict",
    ]);
    expect(
      flowCardRibbonKinds({ prereq: true, blocked: true, conflict: true }),
    ).toEqual(["prereq", "blocked", "conflict"]);
    expect(flowCardRibbonGradient(["prereq"])).toBe("#7a7c70");
    expect(flowCardRibbonGradient(["conflict"])).toBe("#c45c4a");
    expect(flowCardRibbonGradient(["prereq", "conflict"])).toBe(
      "linear-gradient(to bottom, #7a7c70 0% 50%, #c45c4a 50% 100%)",
    );
    expect(flowCardRibbonGradient(["prereq", "blocked", "conflict"])).toMatch(
      /^linear-gradient\(to bottom, #7a7c70 0% [\d.]+%, #c8932a [\d.]+% [\d.]+%, #c45c4a [\d.]+% 100%\)$/,
    );
  });
});

describe("filterTaskForest", () => {
  it("keeps ancestors of a match and unwraps a lone choice option", () => {
    const forest = buildTaskForest([
      task("stick", "横插一杠"),
      task("bat1", "电池换新", { prereq_ids: ["stick"] }),
      task("price1", "独立的代价", { prereq_ids: ["bat1"] }),
      task("chem", "化学-第4部分", { mutex_ids: ["curio"] }),
      task("curio", "好奇心", { mutex_ids: ["chem"] }),
    ]);
    const filtered = filterTaskForest(forest, (row) => row.id === "price1");
    expect(findNode(filtered, "stick")).toBeTruthy();
    expect(findNode(filtered, "bat1")).toBeTruthy();
    expect(findNode(filtered, "price1")?.matched).toBe(true);
    expect(findNode(filtered, "stick")?.matched).toBe(false);
    expect(findNode(filtered, "chem")).toBeUndefined();
    expect(collectIds(filtered).sort()).toEqual(["bat1", "price1", "stick"]);

    const one = filterTaskForest(forest, (row) => row.id === "chem");
    expect(one).toHaveLength(1);
    expect(one[0]?.kind).toBe("task");
    if (one[0]?.kind === "task") {
      expect(one[0].node.task.id).toBe("chem");
      expect(one[0].node.matched).toBe(true);
    }
  });
});

describe("task progress view storage", () => {
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

  it("defaults to list and round-trips tree", () => {
    expect(parseTaskProgressView(null)).toBe("list");
    expect(parseTaskProgressView("nope")).toBe("list");
    expect(loadTaskProgressView()).toBe("list");
    saveTaskProgressView("tree");
    expect(mem.get(TARKOV_TASK_PROGRESS_VIEW_KEY)).toBe("tree");
    expect(loadTaskProgressView()).toBe("tree");
  });
});
