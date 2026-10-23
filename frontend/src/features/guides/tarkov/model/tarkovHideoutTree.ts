/** 藏身处升级前置树：每座设施一列、每级一个节点，连线来自 station_requirements。 */

import type {
  HideoutStationSpec,
  HideoutTraderReq,
} from "./tarkovHideoutProgress";

export const HIDEOUT_TREE_NODE_W = 128;
export const HIDEOUT_TREE_NODE_H = 54;
export const HIDEOUT_TREE_COL_GAP = 20;
export const HIDEOUT_TREE_ROW_GAP = 44;
export const HIDEOUT_TREE_PAD_X = 20;
export const HIDEOUT_TREE_PAD_Y = 20;

/**
 * 左→右参考 Wiki 模块图。未列入的设施（新 dump）按名称追加。
 * 同一列里 Y 不重叠的设施会叠放，省宽度。
 */
export const HIDEOUT_TREE_STATION_ORDER: string[] = [
  "defective-wall",
  "gym",
  "hall-of-fame",
  "gear-rack",
  "medstation",
  "lavatory",
  "water-collector",
  "nutrition-unit",
  "intelligence-center",
  "cultist-circle",
  "christmas-tree",
  "booze-generator",
  "scav-case",
  "security",
  "generator",
  "bitcoin-farm",
  "vents",
  "solar-power",
  "rest-space",
  "air-filtering-unit",
  "heating",
  "library",
  "stash",
  "workbench",
  "illumination",
  "shooting-range",
  "weapon-rack",
];

const ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"];

export type HideoutTreeNodeKind = "built" | "ready" | "locked";

export type HideoutTreeNode = {
  key: string;
  stationId: string;
  stationSlug: string;
  stationName: string;
  imageLink: string;
  level: number;
  roman: string;
  layer: number;
  col: number;
  x: number;
  y: number;
  traders: HideoutTraderReq[];
};

export type HideoutTreeEdge = {
  key: string;
  from: string;
  to: string;
  kind: "self" | "station";
  path: string;
};

export type HideoutTreeWire = {
  key: string;
  path: string;
  edgeKeys: string[];
};

export type HideoutTreeLegendItem = {
  slug: string;
  name: string;
};

export type HideoutTreeLayout = {
  nodes: HideoutTreeNode[];
  edges: HideoutTreeEdge[];
  wires: HideoutTreeWire[];
  legend: HideoutTreeLegendItem[];
  width: number;
  height: number;
};

export function hideoutTreeNodeKey(stationId: string, level: number): string {
  return `${stationId.trim()}:${Math.trunc(level)}`;
}

export function hideoutRoman(level: number): string {
  const n = Math.trunc(Number(level));
  if (n >= 1 && n < ROMAN.length) return ROMAN[n];
  if (!Number.isFinite(n) || n <= 0) return "";
  return String(n);
}

export function hideoutTreeNodeKind(opts: {
  current: number;
  level: number;
  ready: boolean;
}): HideoutTreeNodeKind {
  if (opts.current >= opts.level) return "built";
  if (opts.ready) return "ready";
  return "locked";
}

export function hideoutTreeBusY(
  fromY: number,
  nodeH = HIDEOUT_TREE_NODE_H,
): number {
  return fromY + nodeH + Math.round(HIDEOUT_TREE_ROW_GAP / 2);
}

export function hideoutTreeEdgePath(
  from: { x: number; y: number; col: number },
  to: { x: number; y: number; col: number },
  nodeW = HIDEOUT_TREE_NODE_W,
  nodeH = HIDEOUT_TREE_NODE_H,
): string {
  return segsToPath(edgeSegs(from, to, nodeW, nodeH));
}

type RawSeg = {
  axis: "h" | "v";
  at: number;
  start: number;
  end: number;
  edgeKey: string;
};

function edgeSegs(
  from: { x: number; y: number; col: number },
  to: { x: number; y: number; col: number },
  nodeW: number,
  nodeH: number,
): Array<{ x1: number; y1: number; x2: number; y2: number }> {
  const x1 = from.x + nodeW / 2;
  const y1 = from.y + nodeH;
  const x2 = to.x + nodeW / 2;
  const y2 = to.y;
  if (from.col === to.col || x1 === x2) {
    return [{ x1, y1, x2, y2 }];
  }
  const midY = hideoutTreeBusY(from.y, nodeH);
  return [
    { x1, y1, x2: x1, y2: midY },
    { x1, y1: midY, x2, y2: midY },
    { x1: x2, y1: midY, x2, y2 },
  ];
}

function segsToPath(segs: Array<{ x1: number; y1: number; x2: number; y2: number }>): string {
  if (!segs.length) return "";
  const first = segs[0];
  let d = `M ${first.x1} ${first.y1} L ${first.x2} ${first.y2}`;
  for (let i = 1; i < segs.length; i += 1) {
    d += ` L ${segs[i].x2} ${segs[i].y2}`;
  }
  return d;
}

function toRawSeg(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  edgeKey: string,
): RawSeg | null {
  const ax = Math.round(x1);
  const ay = Math.round(y1);
  const bx = Math.round(x2);
  const by = Math.round(y2);
  if (ax === bx && ay === by) return null;
  if (ay === by) {
    return {
      axis: "h",
      at: ay,
      start: Math.min(ax, bx),
      end: Math.max(ax, bx),
      edgeKey,
    };
  }
  if (ax === bx) {
    return {
      axis: "v",
      at: ax,
      start: Math.min(ay, by),
      end: Math.max(ay, by),
      edgeKey,
    };
  }
  return {
    axis: "h",
    at: ay,
    start: Math.min(ax, bx),
    end: Math.max(ax, bx),
    edgeKey,
  };
}

function mergeRawSegs(raw: RawSeg[]): HideoutTreeWire[] {
  const groups = new Map<string, RawSeg[]>();
  for (const seg of raw) {
    const key = `${seg.axis}:${seg.at}`;
    const bag = groups.get(key);
    if (bag) bag.push(seg);
    else groups.set(key, [seg]);
  }
  const wires: HideoutTreeWire[] = [];
  for (const [groupKey, bag] of groups) {
    const items = bag
      .map((seg) => ({
        start: seg.start,
        end: seg.end,
        keys: new Set([seg.edgeKey]),
      }))
      .sort((a, b) => a.start - b.start || a.end - b.end);
    const merged: { start: number; end: number; keys: Set<string> }[] = [];
    for (const item of items) {
      const last = merged[merged.length - 1];
      if (last && item.start <= last.end) {
        last.end = Math.max(last.end, item.end);
        item.keys.forEach((key) => last.keys.add(key));
      } else {
        merged.push({
          start: item.start,
          end: item.end,
          keys: new Set(item.keys),
        });
      }
    }
    const axis = bag[0].axis;
    const at = bag[0].at;
    merged.forEach((item, index) => {
      const path =
        axis === "h"
          ? `M ${item.start} ${at} L ${item.end} ${at}`
          : `M ${at} ${item.start} L ${at} ${item.end}`;
      wires.push({
        key: `${groupKey}:${index}:${item.start}:${item.end}`,
        path,
        edgeKeys: [...item.keys].sort(),
      });
    });
  }
  wires.sort((a, b) => a.key.localeCompare(b.key));
  return wires;
}

export function hideoutTreeWires(
  nodes: HideoutTreeNode[],
  edges: HideoutTreeEdge[],
  only?: ReadonlySet<string>,
): HideoutTreeWire[] {
  const byKey = new Map(nodes.map((node) => [node.key, node]));
  const raw: RawSeg[] = [];
  for (const edge of edges) {
    if (only && !only.has(edge.key)) continue;
    const from = byKey.get(edge.from);
    const to = byKey.get(edge.to);
    if (!from || !to) continue;
    for (const seg of edgeSegs(from, to, HIDEOUT_TREE_NODE_W, HIDEOUT_TREE_NODE_H)) {
      const row = toRawSeg(seg.x1, seg.y1, seg.x2, seg.y2, edge.key);
      if (row) raw.push(row);
    }
  }
  return mergeRawSegs(raw);
}

export function hideoutTreeFocus(
  selectedKey: string | undefined,
  edges: HideoutTreeEdge[],
): { nodes: Set<string>; edges: Set<string> } {
  const nodes = new Set<string>();
  const focusEdges = new Set<string>();
  const key = (selectedKey || "").trim();
  if (!key) return { nodes, edges: focusEdges };
  nodes.add(key);
  for (const edge of edges) {
    if (edge.to !== key) continue;
    focusEdges.add(edge.key);
    nodes.add(edge.from);
  }
  return { nodes, edges: focusEdges };
}

export function hideoutTreeActiveKey(
  selectedKey?: string,
  hoverKey?: string,
): string {
  const selected = (selectedKey || "").trim();
  if (selected) return selected;
  return (hoverKey || "").trim();
}

export function hideoutTreeClickedKey(
  selectedKey: string | undefined,
  clickedKey: string,
): string {
  const selected = (selectedKey || "").trim();
  const clicked = (clickedKey || "").trim();
  if (!clicked) return "";
  return selected === clicked ? "" : clicked;
}

type StationLevels = {
  station: HideoutStationSpec;
  ident: string;
  slug: string;
  name: string;
  levels: number[];
};

function stationLevels(station: HideoutStationSpec): number[] {
  const seen = new Set<number>();
  const out: number[] = [];
  for (const row of station.levels || []) {
    const level = Math.trunc(Number(row.level || 0));
    if (level < 1 || seen.has(level)) continue;
    seen.add(level);
    out.push(level);
  }
  out.sort((a, b) => a - b);
  return out;
}

function collectStations(stations: HideoutStationSpec[] | undefined): StationLevels[] {
  const out: StationLevels[] = [];
  for (const station of stations || []) {
    const ident = (station.id || "").trim();
    if (!ident) continue;
    const levels = stationLevels(station);
    if (!levels.length) continue;
    out.push({
      station,
      ident,
      slug: (station.slug || "").trim().toLowerCase(),
      name: (station.name || station.slug || ident).trim(),
      levels,
    });
  }
  return out;
}

function addEdge(
  incoming: Map<string, Set<string>>,
  from: string,
  to: string,
) {
  if (!from || !to || from === to) return;
  let bag = incoming.get(to);
  if (!bag) {
    bag = new Set();
    incoming.set(to, bag);
  }
  bag.add(from);
}

function longestLayer(
  key: string,
  incoming: Map<string, Set<string>>,
  memo: Map<string, number>,
  visiting: Set<string>,
): number {
  const cached = memo.get(key);
  if (cached != null) return cached;
  if (visiting.has(key)) return 0;
  visiting.add(key);
  let best = 0;
  const preds = incoming.get(key);
  if (preds) {
    for (const pred of preds) {
      best = Math.max(best, longestLayer(pred, incoming, memo, visiting) + 1);
    }
  }
  visiting.delete(key);
  memo.set(key, best);
  return best;
}

function packColumns(
  ranges: Map<string, { min: number; max: number }>,
  ordered: string[],
  preferredParent: Map<string, string>,
): string[][] {
  const columns: { slug: string; min: number; max: number }[][] = [];
  const colOf = new Map<string, number>();
  for (const slug of ordered) {
    const range = ranges.get(slug);
    if (!range) continue;
    const parent = preferredParent.get(slug);
    const tryCols: number[] = [];
    const parentCol = parent != null ? colOf.get(parent) : undefined;
    if (parentCol != null) tryCols.push(parentCol);
    for (let i = 0; i < columns.length; i += 1) {
      if (!tryCols.includes(i)) tryCols.push(i);
    }
    let placed = false;
    for (const index of tryCols) {
      const col = columns[index];
      const clash = col.some(
        (item) => !(range.min > item.max || range.max < item.min),
      );
      if (clash) continue;
      col.push({ slug, ...range });
      colOf.set(slug, index);
      placed = true;
      break;
    }
    if (!placed) {
      colOf.set(slug, columns.length);
      columns.push([{ slug, ...range }]);
    }
  }
  return columns.map((col) => col.map((item) => item.slug));
}

function stationOrder(rows: StationLevels[]): string[] {
  const have = new Set(rows.map((row) => row.slug).filter(Boolean));
  const out: string[] = [];
  const seen = new Set<string>();
  for (const slug of HIDEOUT_TREE_STATION_ORDER) {
    if (!have.has(slug) || seen.has(slug)) continue;
    seen.add(slug);
    out.push(slug);
  }
  const rest = rows
    .filter((row) => row.slug && !seen.has(row.slug))
    .sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
  for (const row of rest) {
    seen.add(row.slug);
    out.push(row.slug);
  }
  for (const row of rows) {
    if (row.slug) continue;
    const key = row.ident;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(key);
  }
  return out;
}

export function buildHideoutTreeLayout(
  stations: HideoutStationSpec[] | undefined,
): HideoutTreeLayout {
  const rows = collectStations(stations);
  const byId = new Map(rows.map((row) => [row.ident, row]));
  const nodeSet = new Set<string>();
  for (const row of rows) {
    for (const level of row.levels) {
      nodeSet.add(hideoutTreeNodeKey(row.ident, level));
    }
  }

  const incoming = new Map<string, Set<string>>();
  const edgeKind = new Map<string, "self" | "station">();
  const mark = (from: string, to: string, kind: "self" | "station") => {
    if (!nodeSet.has(from) || !nodeSet.has(to)) return;
    addEdge(incoming, from, to);
    const key = `${from}>${to}`;
    if (!edgeKind.has(key) || kind === "self") edgeKind.set(key, kind);
  };

  for (const row of rows) {
    for (let i = 1; i < row.levels.length; i += 1) {
      mark(
        hideoutTreeNodeKey(row.ident, row.levels[i - 1]),
        hideoutTreeNodeKey(row.ident, row.levels[i]),
        "self",
      );
    }
    for (const spec of row.station.levels || []) {
      const level = Math.trunc(Number(spec.level || 0));
      if (level < 1) continue;
      const to = hideoutTreeNodeKey(row.ident, level);
      for (const req of spec.station_requirements || []) {
        const otherId = (req.station_id || "").trim();
        const need = Math.trunc(Number(req.level || 0));
        if (!otherId || need < 1) continue;
        const from = hideoutTreeNodeKey(otherId, need);
        const kind =
          otherId === row.ident &&
          row.levels.includes(need) &&
          row.levels.includes(level) &&
          row.levels[row.levels.indexOf(level) - 1] === need
            ? "self"
            : "station";
        mark(from, to, kind);
      }
    }
  }

  const layerMemo = new Map<string, number>();
  const visiting = new Set<string>();
  const layerOf = (key: string) =>
    longestLayer(key, incoming, layerMemo, visiting);

  const slugRanges = new Map<string, { min: number; max: number }>();
  const identColKey = new Map<string, string>();
  for (const row of rows) {
    const colKey = row.slug || row.ident;
    identColKey.set(row.ident, colKey);
    let min = Number.POSITIVE_INFINITY;
    let max = 0;
    for (const level of row.levels) {
      const layer = layerOf(hideoutTreeNodeKey(row.ident, level));
      min = Math.min(min, layer);
      max = Math.max(max, layer);
    }
    if (!Number.isFinite(min)) continue;
    const prev = slugRanges.get(colKey);
    if (!prev) slugRanges.set(colKey, { min, max });
    else slugRanges.set(colKey, { min: Math.min(prev.min, min), max: Math.max(prev.max, max) });
  }

  const preferredParent = new Map<string, string>();
  for (const row of rows) {
    const colKey = row.slug || row.ident;
    const first = row.levels[0];
    const spec = (row.station.levels || []).find(
      (item) => Math.trunc(Number(item.level || 0)) === first,
    );
    let bestLayer = -1;
    let best: string | null = null;
    for (const req of spec?.station_requirements || []) {
      const other = byId.get((req.station_id || "").trim());
      if (!other) continue;
      const need = Math.trunc(Number(req.level || 0));
      if (need < 1) continue;
      if (other.ident === row.ident) continue;
      const layer = layerOf(hideoutTreeNodeKey(other.ident, need));
      if (layer >= bestLayer) {
        bestLayer = layer;
        best = identColKey.get(other.ident) || other.slug || other.ident;
      }
    }
    if (best) preferredParent.set(colKey, best);
  }

  const columns = packColumns(slugRanges, stationOrder(rows), preferredParent);
  const colIndex = new Map<string, number>();
  columns.forEach((col, index) => {
    for (const slug of col) colIndex.set(slug, index);
  });

  let maxLayer = 0;
  const nodes: HideoutTreeNode[] = [];
  for (const row of rows) {
    const col = colIndex.get(row.slug || row.ident) ?? 0;
    const specByLevel = new Map(
      (row.station.levels || []).map((spec) => [
        Math.trunc(Number(spec.level || 0)),
        spec,
      ]),
    );
    for (const level of row.levels) {
      const key = hideoutTreeNodeKey(row.ident, level);
      const layer = layerOf(key);
      maxLayer = Math.max(maxLayer, layer);
      const spec = specByLevel.get(level);
      nodes.push({
        key,
        stationId: row.ident,
        stationSlug: row.slug,
        stationName: row.name,
        imageLink: (row.station.image_link || "").trim(),
        level,
        roman: hideoutRoman(level),
        layer,
        col,
        x: HIDEOUT_TREE_PAD_X + col * (HIDEOUT_TREE_NODE_W + HIDEOUT_TREE_COL_GAP),
        y: HIDEOUT_TREE_PAD_Y + layer * (HIDEOUT_TREE_NODE_H + HIDEOUT_TREE_ROW_GAP),
        traders: (spec?.trader_requirements || []).filter(
          (req) => (req.slug || req.id || "").trim(),
        ),
      });
    }
  }

  const byKey = new Map(nodes.map((node) => [node.key, node]));
  const edges: HideoutTreeEdge[] = [];
  for (const [to, preds] of incoming) {
    const dest = byKey.get(to);
    if (!dest) continue;
    for (const from of preds) {
      const src = byKey.get(from);
      if (!src) continue;
      const kind = edgeKind.get(`${from}>${to}`) || "station";
      edges.push({
        key: `${from}>${to}`,
        from,
        to,
        kind,
        path: hideoutTreeEdgePath(src, dest),
      });
    }
  }
  edges.sort((a, b) => a.key.localeCompare(b.key));
  nodes.sort((a, b) => a.col - b.col || a.layer - b.layer || a.level - b.level);
  const wires = hideoutTreeWires(nodes, edges);

  const legend: HideoutTreeLegendItem[] = [];
  const seenLegend = new Set<string>();
  for (const col of columns) {
    for (const slug of col) {
      if (seenLegend.has(slug)) continue;
      seenLegend.add(slug);
      const row = rows.find((item) => (item.slug || item.ident) === slug);
      if (!row) continue;
      legend.push({
        slug: row.slug || row.ident,
        name: row.name,
      });
    }
  }

  const colCount = Math.max(columns.length, 1);
  const width =
    HIDEOUT_TREE_PAD_X * 2 +
    colCount * HIDEOUT_TREE_NODE_W +
    Math.max(0, colCount - 1) * HIDEOUT_TREE_COL_GAP;
  const height =
    HIDEOUT_TREE_PAD_Y * 2 +
    (maxLayer + 1) * HIDEOUT_TREE_NODE_H +
    maxLayer * HIDEOUT_TREE_ROW_GAP;

  return { nodes, edges, wires, legend, width, height };
}
