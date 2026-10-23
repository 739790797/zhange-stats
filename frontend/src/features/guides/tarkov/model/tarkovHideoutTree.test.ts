import { describe, expect, it } from "vitest";
import type { HideoutStationSpec } from "./tarkovHideoutProgress";
import {
  HIDEOUT_TREE_NODE_H,
  HIDEOUT_TREE_ROW_GAP,
  buildHideoutTreeLayout,
  hideoutRoman,
  hideoutTreeEdgePath,
  hideoutTreeFocus,
  hideoutTreeActiveKey,
  hideoutTreeClickedKey,
  hideoutTreeNodeKey,
  hideoutTreeNodeKind,
} from "./tarkovHideoutTree";

function catalog(): HideoutStationSpec[] {
  return [
    {
      id: "sec",
      slug: "security",
      name: "安保",
      levels: [
        { level: 1, station_requirements: [] },
        { level: 2, station_requirements: [{ station_id: "sec", level: 1 }] },
      ],
    },
    {
      id: "gen",
      slug: "generator",
      name: "发电机",
      levels: [
        {
          level: 1,
          station_requirements: [{ station_id: "sec", level: 1 }],
          trader_requirements: [{ slug: "mechanic", name: "Mechanic", level: 1 }],
        },
        {
          level: 2,
          station_requirements: [
            { station_id: "gen", level: 1 },
            { station_id: "sec", level: 2 },
          ],
        },
      ],
    },
    {
      id: "solar",
      slug: "solar-power",
      name: "太阳能",
      levels: [
        { level: 1, station_requirements: [{ station_id: "gen", level: 2 }] },
      ],
    },
  ];
}

describe("tarkovHideoutTree", () => {
  it("formats roman numerals and node keys", () => {
    expect(hideoutRoman(1)).toBe("I");
    expect(hideoutRoman(4)).toBe("IV");
    expect(hideoutRoman(6)).toBe("VI");
    expect(hideoutRoman(12)).toBe("12");
    expect(hideoutTreeNodeKey(" abc ", 2)).toBe("abc:2");
  });

  it("marks built / ready / locked from current level", () => {
    expect(hideoutTreeNodeKind({ current: 2, level: 1, ready: false })).toBe(
      "built",
    );
    expect(hideoutTreeNodeKind({ current: 1, level: 2, ready: true })).toBe(
      "ready",
    );
    expect(hideoutTreeNodeKind({ current: 0, level: 2, ready: false })).toBe(
      "locked",
    );
  });

  it("layers nodes by longest station-requirement path", () => {
    const layout = buildHideoutTreeLayout(catalog());
    const byKey = new Map(layout.nodes.map((node) => [node.key, node]));
    expect(byKey.get("sec:1")?.layer).toBe(0);
    expect(byKey.get("sec:2")?.layer).toBe(1);
    expect(byKey.get("gen:1")?.layer).toBe(1);
    expect(byKey.get("gen:2")?.layer).toBe(2);
    expect(byKey.get("solar:1")?.layer).toBe(3);
    expect(byKey.get("gen:1")?.traders.map((row) => row.slug)).toEqual([
      "mechanic",
    ]);
  });

  it("keeps same-station edges and cross-station edges without duplicates", () => {
    const layout = buildHideoutTreeLayout(catalog());
    const keys = layout.edges.map((edge) => `${edge.kind}:${edge.key}`).sort();
    expect(keys).toEqual(
      [
        "self:gen:1>gen:2",
        "self:sec:1>sec:2",
        "station:gen:2>solar:1",
        "station:sec:1>gen:1",
        "station:sec:2>gen:2",
      ].sort(),
    );
  });

  it("packs a later station under an earlier one when layers do not overlap", () => {
    const layout = buildHideoutTreeLayout(catalog());
    const gen = layout.nodes.find((node) => node.stationSlug === "generator");
    const solar = layout.nodes.find((node) => node.stationSlug === "solar-power");
    expect(gen?.col).toBe(solar?.col);
    expect(layout.legend.map((row) => row.slug)).toEqual([
      "security",
      "generator",
      "solar-power",
    ]);
  });

  it("skips missing station ids and empty catalogs", () => {
    expect(buildHideoutTreeLayout([]).nodes).toEqual([]);
    expect(buildHideoutTreeLayout([]).wires).toEqual([]);
    const layout = buildHideoutTreeLayout([
      {
        id: "bench",
        slug: "workbench",
        name: "工作台",
        levels: [
          { level: 1, station_requirements: [{ station_id: "missing", level: 3 }] },
        ],
      },
    ]);
    expect(layout.nodes).toHaveLength(1);
    expect(layout.edges).toEqual([]);
    expect(layout.wires).toEqual([]);
    expect(layout.nodes[0].layer).toBe(0);
  });

  it("routes same-column edges vertically and others onto a shared bus", () => {
    const vertical = hideoutTreeEdgePath(
      { x: 10, y: 10, col: 1 },
      { x: 10, y: 80, col: 1 },
    );
    expect(vertical).toBe("M 74 64 L 74 80");
    const midY = 0 + HIDEOUT_TREE_NODE_H + Math.round(HIDEOUT_TREE_ROW_GAP / 2);
    const bent = hideoutTreeEdgePath(
      { x: 0, y: 0, col: 0 },
      { x: 200, y: 100, col: 2 },
    );
    expect(bent).toBe(`M 64 54 L 64 ${midY} L 264 ${midY} L 264 100`);
  });

  it("merges overlapping horizontals from the same layer", () => {
    const layout = buildHideoutTreeLayout([
      {
        id: "hub",
        slug: "security",
        name: "安保",
        levels: [
          { level: 1, station_requirements: [] },
          { level: 2, station_requirements: [{ station_id: "hub", level: 1 }] },
        ],
      },
      {
        id: "left",
        slug: "generator",
        name: "发电机",
        levels: [
          { level: 1, station_requirements: [{ station_id: "hub", level: 1 }] },
        ],
      },
      {
        id: "right",
        slug: "workbench",
        name: "工作台",
        levels: [
          { level: 1, station_requirements: [{ station_id: "hub", level: 1 }] },
        ],
      },
    ]);
    const bus = layout.wires.find(
      (wire) =>
        wire.edgeKeys.includes("hub:1>left:1") &&
        wire.edgeKeys.includes("hub:1>right:1"),
    );
    expect(bus?.path).toMatch(/^M \d+ \d+ L \d+ \d+$/);
    const [fromX, busY, toX] = (bus?.path.match(/\d+/g) || []).map(Number);
    expect(fromX).not.toBe(toX);
    expect(busY).toBe(
      layout.nodes.find((node) => node.key === "hub:1")!.y +
        HIDEOUT_TREE_NODE_H +
        Math.round(HIDEOUT_TREE_ROW_GAP / 2),
    );
  });

  it("focuses the selected node and its direct prerequisites", () => {
    const layout = buildHideoutTreeLayout(catalog());
    const focus = hideoutTreeFocus("gen:2", layout.edges);
    expect([...focus.nodes].sort()).toEqual(["gen:1", "gen:2", "sec:2"]);
    expect([...focus.edges].sort()).toEqual(["gen:1>gen:2", "sec:2>gen:2"]);
    expect(hideoutTreeFocus("", layout.edges).nodes.size).toBe(0);
  });

  it("uses hover only when nothing is selected, and click toggles the same node off", () => {
    expect(hideoutTreeActiveKey("gen:2", "sec:1")).toBe("gen:2");
    expect(hideoutTreeActiveKey("", "sec:1")).toBe("sec:1");
    expect(hideoutTreeActiveKey("", "")).toBe("");
    expect(hideoutTreeClickedKey("gen:2", "gen:2")).toBe("");
    expect(hideoutTreeClickedKey("gen:2", "sec:1")).toBe("sec:1");
    expect(hideoutTreeClickedKey("", "sec:1")).toBe("sec:1");
    expect(hideoutTreeClickedKey("gen:2", "")).toBe("");
  });

  it("does not leave collinear overlapping wires", () => {
    const layout = buildHideoutTreeLayout(catalog());
    const collinear = new Map<string, { start: number; end: number }[]>();
    for (const wire of layout.wires) {
      const nums = (wire.path.match(/-?\d+/g) || []).map(Number);
      if (nums.length !== 4) continue;
      const [x1, y1, x2, y2] = nums;
      const key = y1 === y2 ? `h:${y1}` : `v:${x1}`;
      const range =
        y1 === y2
          ? { start: Math.min(x1, x2), end: Math.max(x1, x2) }
          : { start: Math.min(y1, y2), end: Math.max(y1, y2) };
      const bag = collinear.get(key);
      if (bag) bag.push(range);
      else collinear.set(key, [range]);
    }
    for (const bag of collinear.values()) {
      bag.sort((a, b) => a.start - b.start);
      for (let i = 1; i < bag.length; i += 1) {
        expect(bag[i].start).toBeGreaterThan(bag[i - 1].end);
      }
    }
  });
});
