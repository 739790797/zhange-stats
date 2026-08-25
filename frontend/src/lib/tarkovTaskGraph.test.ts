import { describe, expect, it } from "vitest";
import {
  groupChainsByTrader,
  groupTaskChains,
  layoutTaskNeighborhood,
  type GraphTask,
} from "./tarkovTaskGraph";

function task(
  id: string,
  name: string,
  extra: Partial<GraphTask> = {},
): GraphTask {
  return { id, name, trader_slug: "prapor", ...extra };
}

describe("groupTaskChains", () => {
  it("indents a linear chain and titles by series prefix", () => {
    const chains = groupTaskChains([
      task("p3", "惩罚者 - 3", { task_requirements: [{ id: "p2" }] }),
      task("p1", "惩罚者 - 1"),
      task("p2", "惩罚者 - 2", { task_requirements: [{ id: "p1" }] }),
    ]);
    expect(chains).toHaveLength(1);
    expect(chains[0].title).toBe("惩罚者");
    expect(chains[0].singleton).toBe(false);
    expect(chains[0].rows.map((row) => [row.task.id, row.depth])).toEqual([
      ["p1", 0],
      ["p2", 1],
      ["p3", 2],
    ]);
  });

  it("keeps merge nodes once and chips extra in-set parents", () => {
    const chains = groupTaskChains([
      task("a", "天神射手"),
      task("b", "邮递员派特 - 2"),
      task("c", "收藏家", {
        task_requirements: [
          { id: "a", name: "天神射手" },
          { id: "b", name: "邮递员派特 - 2" },
        ],
      }),
    ]);
    expect(chains).toHaveLength(1);
    const collector = chains[0].rows.find((row) => row.task.id === "c");
    expect(collector?.depth).toBe(1);
    expect(collector?.extraParents.map((row) => row.id)).toEqual(["b"]);
    expect(chains[0].rows.filter((row) => row.task.id === "c")).toHaveLength(1);
  });

  it("chips parents outside the current set", () => {
    const chains = groupTaskChains([
      task("p", "缔结友谊", {
        task_requirements: [{ id: "btr", name: "现世报" }],
      }),
    ]);
    expect(chains[0].singleton).toBe(true);
    expect(chains[0].rows[0].extraParents).toEqual([
      { id: "btr", name: "现世报", met: undefined },
    ]);
  });
});

describe("groupChainsByTrader", () => {
  it("splits by trader so cross-trader edges become chips", () => {
    const groups = groupChainsByTrader(
      [
        task("p1", "惩罚者 - 1"),
        task("col", "收藏家", {
          trader_slug: "fence",
          trader_name: "Fence（黑商）",
          task_requirements: [{ id: "p1", name: "惩罚者 - 1" }],
        }),
      ],
      [
        { slug: "prapor", name: "Prapor（俄商）" },
        { slug: "fence", name: "Fence（黑商）" },
      ],
    );
    expect(groups.map((row) => row.traderSlug)).toEqual(["prapor", "fence"]);
    expect(groups[0].chains[0].singleton).toBe(true);
    expect(groups[1].chains[0].rows[0].extraParents[0].id).toBe("p1");
  });
});

describe("layoutTaskNeighborhood", () => {
  it("places ancestors left and descendants right of current", () => {
    const layout = layoutTaskNeighborhood(
      [
        { id: "a", name: "A", hop: -1 },
        { id: "b", name: "B", hop: 0 },
        { id: "c", name: "C", hop: 1 },
        { id: "d", name: "D", hop: 1 },
      ],
      [
        { source_id: "a", target_id: "b" },
        { source_id: "b", target_id: "c" },
        { source_id: "b", target_id: "d" },
      ],
      "b",
    );
    const byId = Object.fromEntries(layout.nodes.map((node) => [node.id, node]));
    expect(byId.a.x).toBeLessThan(byId.b.x);
    expect(byId.b.x).toBeLessThan(byId.c.x);
    expect(byId.c.x).toBe(byId.d.x);
    expect(byId.b.current).toBe(true);
    expect(layout.edges).toHaveLength(3);
  });
});
