import { describe, expect, it } from "vitest";
import type { TaskForestItem } from "./tarkovTaskForest";
import {
  FLOW_NODE_HEIGHT,
  FLOW_NODE_WIDTH,
  acyclicPrereqEdges,
  countGraphLayout,
  keepGraphAncestors,
  layoutTaskGraph,
  meshEdgePath,
  outsidePrereqIds,
} from "./tarkovTaskGraph";

function task(
  id: string,
  name: string,
  extra: Partial<TaskForestItem> = {},
): TaskForestItem {
  return { id, name, ...extra };
}

function nodeIds<T extends TaskForestItem>(
  layout: ReturnType<typeof layoutTaskGraph<T>>,
): string[] {
  return [
    ...layout.meshes.flatMap((mesh) => mesh.nodes.map((row) => row.id)),
    ...layout.isolates.map((row) => row.id),
  ].sort();
}

describe("layoutTaskGraph", () => {
  it("keeps a diamond as one node with two inbound edges", () => {
    const layout = layoutTaskGraph([
      task("a", "熟人"),
      task("b", "生存者之路", { prereq_ids: ["a"] }),
      task("c", "神射手-1", { prereq_ids: ["a"] }),
      task("d", "硬汉", { prereq_ids: ["b"] }),
      task("e", "神射手-2", { prereq_ids: ["c"] }),
      task("f", "隐士", { prereq_ids: ["d"] }),
      task("g", "冷血", { prereq_ids: ["d"] }),
    ]);
    expect(layout.meshes).toHaveLength(1);
    expect(layout.isolates).toHaveLength(0);
    const mesh = layout.meshes[0]!;
    expect(mesh.nodes.map((row) => row.id).sort()).toEqual([
      "a",
      "b",
      "c",
      "d",
      "e",
      "f",
      "g",
    ]);
    expect(mesh.nodes.filter((row) => row.id === "d")).toHaveLength(1);
    const fromA = mesh.edges.filter((row) => row.from === "a").map((row) => row.to).sort();
    expect(fromA).toEqual(["b", "c"]);
    const fromD = mesh.edges.filter((row) => row.from === "d").map((row) => row.to).sort();
    expect(fromD).toEqual(["f", "g"]);
    const rank = Object.fromEntries(mesh.nodes.map((row) => [row.id, row.rank]));
    expect(rank.a).toBe(0);
    expect(rank.b).toBe(1);
    expect(rank.c).toBe(1);
    expect(rank.d).toBe(2);
    expect(rank.e).toBe(2);
    expect(rank.f).toBe(3);
    expect(rank.g).toBe(3);
    for (const edge of mesh.edges) {
      const parent = mesh.nodes.find((row) => row.id === edge.from)!;
      const child = mesh.nodes.find((row) => row.id === edge.to)!;
      expect(child.y).toBeGreaterThan(parent.y);
    }
  });

  it("does not duplicate a task that has two parents", () => {
    const layout = layoutTaskGraph([
      task("p1", "前置甲"),
      task("p2", "前置乙"),
      task("kid", "后续", { prereq_ids: ["p1", "p2"] }),
    ]);
    const mesh = layout.meshes[0]!;
    expect(mesh.nodes.filter((row) => row.id === "kid")).toHaveLength(1);
    expect(mesh.edges).toHaveLength(2);
    expect(mesh.edges.map((row) => row.from).sort()).toEqual(["p1", "p2"]);
    expect(mesh.edges.every((row) => row.to === "kid")).toBe(true);
    const kid = mesh.nodes.find((row) => row.id === "kid")!;
    expect(kid.rank).toBe(1);
  });

  it("splits true isolates from the mesh", () => {
    const layout = layoutTaskGraph([
      task("root", "惩罚者-第1部分"),
      task("next", "惩罚者-第2部分", { prereq_ids: ["root"] }),
      task("solo", "首秀"),
    ]);
    expect(nodeIds(layout)).toEqual(["next", "root", "solo"]);
    expect(layout.isolates.map((row) => row.id)).toEqual(["solo"]);
    expect(layout.meshes).toHaveLength(1);
    expect(countGraphLayout(layout)).toBe(3);
  });

  it("keeps mutex siblings in one mesh with a hull when they share a rank", () => {
    const layout = layoutTaskGraph([
      task("root", "起点"),
      task("a", "线A", { prereq_ids: ["root"], mutex_ids: ["b"] }),
      task("b", "线B", { prereq_ids: ["root"], mutex_ids: ["a"] }),
    ]);
    const mesh = layout.meshes[0]!;
    expect(mesh.mutexGroups).toHaveLength(1);
    expect(mesh.mutexGroups[0]!.ids.sort()).toEqual(["a", "b"]);
    expect(mesh.mutexGroups[0]!.label).toBe("二选一");
    const a = mesh.nodes.find((row) => row.id === "a")!;
    const b = mesh.nodes.find((row) => row.id === "b")!;
    expect(a.rank).toBe(b.rank);
    expect(a.y).toBe(b.y);
    expect(Math.abs(a.x - b.x)).toBeGreaterThanOrEqual(FLOW_NODE_WIDTH);
  });

  it("puts a root-level mutex pair in the mesh instead of isolates", () => {
    const layout = layoutTaskGraph([
      task("chem", "化学-第4部分", { mutex_ids: ["curio"] }),
      task("curio", "好奇心", { mutex_ids: ["chem"] }),
      task("solo", "首秀"),
    ]);
    expect(layout.isolates.map((row) => row.id)).toEqual(["solo"]);
    expect(layout.meshes).toHaveLength(1);
    expect(layout.meshes[0]!.nodes.map((row) => row.id).sort()).toEqual([
      "chem",
      "curio",
    ]);
    expect(layout.meshes[0]!.mutexGroups[0]!.label).toBe("二选一");
  });

  it("breaks directed cycles without dropping either task", () => {
    const edges = acyclicPrereqEdges([
      task("a", "A", { prereq_ids: ["b"] }),
      task("b", "B", { prereq_ids: ["a"] }),
    ]);
    expect(edges).toHaveLength(1);
    const layout = layoutTaskGraph([
      task("a", "A", { prereq_ids: ["b"] }),
      task("b", "B", { prereq_ids: ["a"] }),
    ]);
    expect(nodeIds(layout)).toEqual(["a", "b"]);
    expect(countGraphLayout(layout)).toBe(2);
  });

  it("does not overlap cards on the same rank", () => {
    const layout = layoutTaskGraph([
      task("r", "根"),
      task("a", "甲", { prereq_ids: ["r"] }),
      task("b", "乙", { prereq_ids: ["r"] }),
      task("c", "丙", { prereq_ids: ["r"] }),
    ]);
    const mesh = layout.meshes[0]!;
    const rank1 = mesh.nodes.filter((row) => row.rank === 1);
    expect(rank1).toHaveLength(3);
    const xs = rank1.map((row) => row.x).sort((left, right) => left - right);
    for (let i = 1; i < xs.length; i += 1) {
      expect(xs[i]! - xs[i - 1]!).toBeGreaterThanOrEqual(FLOW_NODE_WIDTH);
    }
    expect(mesh.nodes.every((row) => row.y >= 0)).toBe(true);
    expect(mesh.height).toBeGreaterThan(FLOW_NODE_HEIGHT);
  });

  it("leaves foreign extra prereqs off the mesh", () => {
    const layout = layoutTaskGraph(
      [
        task("a", "本商前置", { trader_slug: "therapist" }),
        task("c", "后续", {
          trader_slug: "therapist",
          prereq_ids: ["a", "p"],
        }),
      ],
      { stubIds: [] },
    );
    const mesh = layout.meshes[0]!;
    expect(mesh.edges).toEqual([
      expect.objectContaining({ from: "a", to: "c" }),
    ]);
    const inGraph = new Set(mesh.nodes.map((row) => row.id));
    expect(outsidePrereqIds(mesh.nodes.find((row) => row.id === "c")!.task, inGraph)).toEqual(
      ["p"],
    );
  });

  it("marks stubs and unmatched ancestors", () => {
    const layout = layoutTaskGraph(
      [
        task("p", "首秀", { trader_slug: "prapor" }),
        task("t", "后续", { trader_slug: "therapist", prereq_ids: ["p"] }),
      ],
      { stubIds: ["p"], matched: new Set(["t"]) },
    );
    const mesh = layout.meshes[0]!;
    expect(mesh.nodes.find((row) => row.id === "p")).toMatchObject({
      stub: true,
      matched: false,
    });
    expect(mesh.nodes.find((row) => row.id === "t")).toMatchObject({
      stub: false,
      matched: true,
    });
  });
});

describe("keepGraphAncestors", () => {
  it("keeps the path to a match and drops unrelated tasks", () => {
    const { items, matched } = keepGraphAncestors(
      [
        task("stick", "横插一杠"),
        task("bat1", "电池换新", { prereq_ids: ["stick"] }),
        task("price1", "独立的代价", { prereq_ids: ["bat1"] }),
        task("chem", "化学-第4部分"),
      ],
      (row) => row.id === "price1",
    );
    expect(items.map((row) => row.id).sort()).toEqual(["bat1", "price1", "stick"]);
    expect([...matched]).toEqual(["price1"]);
  });
});

describe("meshEdgePath", () => {
  it("draws a vertical cubic between stacked nodes", () => {
    const path = meshEdgePath(10, 0, 10, FLOW_NODE_HEIGHT + 40);
    expect(path.startsWith("M 10 0 C")).toBe(true);
    expect(path.endsWith("10 126")).toBe(true);
  });
});
