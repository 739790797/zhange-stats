/** 个人中心任务进度：按前置关系做分层 DAG，一张卡只出现一次。 */

import type { TaskForestItem } from "@/lib/tarkovTaskForest";
import { taskChoiceLabel } from "@/lib/tarkovTaskForest";

export const FLOW_NODE_WIDTH = 196;
export const FLOW_NODE_HEIGHT = 86;
export const FLOW_COL_GAP = 32;
export const FLOW_RANK_GAP = 64;
export const FLOW_PAD_X = 16;
export const FLOW_PAD_Y = 28;

const LAYOUT_PASSES = 8;
const MUTEX_PAD_X = 10;
const MUTEX_PAD_TOP = 22;
const MUTEX_PAD_BOTTOM = 8;

export type TaskGraphNode<T extends TaskForestItem = TaskForestItem> = {
  id: string;
  task: T;
  stub: boolean;
  matched: boolean;
  rank: number;
  column: number;
  x: number;
  y: number;
};

export type TaskGraphEdge = {
  from: string;
  to: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

export type TaskGraphMutexGroup = {
  ids: string[];
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
};

export type TaskGraphMesh<T extends TaskForestItem = TaskForestItem> = {
  nodes: TaskGraphNode<T>[];
  edges: TaskGraphEdge[];
  mutexGroups: TaskGraphMutexGroup[];
  width: number;
  height: number;
};

export type TaskGraphLayout<T extends TaskForestItem = TaskForestItem> = {
  meshes: TaskGraphMesh<T>[];
  isolates: TaskGraphNode<T>[];
};

function asIds(value: readonly string[] | null | undefined): string[] {
  if (!value?.length) return [];
  const out: string[] = [];
  const seen = new Set<string>();
  for (const raw of value) {
    const ident = String(raw || "").trim();
    if (!ident || seen.has(ident)) continue;
    seen.add(ident);
    out.push(ident);
  }
  return out;
}

function nameKey<T extends TaskForestItem>(task: T): string {
  return `${task.name || task.id}\0${task.id}`;
}

function compareName<T extends TaskForestItem>(left: T, right: T): number {
  return nameKey(left).localeCompare(nameKey(right), "zh-CN");
}

function indexById<T extends TaskForestItem>(
  items: readonly T[],
): Map<string, T> {
  const byId = new Map<string, T>();
  for (const item of items) {
    const ident = String(item.id || "").trim();
    if (!ident || byId.has(ident)) continue;
    byId.set(ident, item);
  }
  return byId;
}

function mutexPair<T extends TaskForestItem>(left: T, right: T): boolean {
  if (left.id === right.id) return false;
  const a = new Set(asIds(left.mutex_ids));
  const b = new Set(asIds(right.mutex_ids));
  return a.has(right.id) && b.has(left.id);
}

function mutexCliques<T extends TaskForestItem>(
  byId: ReadonlyMap<string, T>,
): string[][] {
  const remaining = [...byId.values()].sort(compareName);
  const out: string[][] = [];
  while (remaining.length) {
    const head = remaining.shift();
    if (!head) break;
    const clique = [head];
    let grew = true;
    while (grew) {
      grew = false;
      for (let i = remaining.length - 1; i >= 0; i -= 1) {
        const cand = remaining[i];
        if (clique.every((row) => mutexPair(row, cand))) {
          clique.push(cand);
          remaining.splice(i, 1);
          grew = true;
        }
      }
    }
    if (clique.length >= 2) {
      out.push(clique.sort(compareName).map((row) => row.id));
    }
  }
  return out;
}

type Adj = Map<string, string[]>;

function pushAdj(map: Adj, from: string, to: string) {
  const list = map.get(from);
  if (list) list.push(to);
  else map.set(from, [to]);
}

function uniqueSorted(ids: string[]): string[] {
  return [...new Set(ids)].sort();
}

/** 去掉成环边，保留 DAG。 */
export function acyclicPrereqEdges<T extends TaskForestItem>(
  items: readonly T[],
): Array<[string, string]> {
  const byId = indexById(items);
  const raw: Array<[string, string]> = [];
  for (const task of byId.values()) {
    for (const parent of asIds(task.prereq_ids)) {
      if (!byId.has(parent) || parent === task.id) continue;
      raw.push([parent, task.id]);
    }
  }
  const outs: Adj = new Map();
  for (const [from, to] of raw) pushAdj(outs, from, to);

  const visiting = new Set<string>();
  const done = new Set<string>();
  const cyclic = new Set<string>();
  const walk = (ident: string) => {
    if (done.has(ident) || visiting.has(ident)) return;
    visiting.add(ident);
    for (const next of outs.get(ident) || []) {
      if (visiting.has(next)) {
        cyclic.add(`${ident}\0${next}`);
        continue;
      }
      if (!done.has(next)) walk(next);
    }
    visiting.delete(ident);
    done.add(ident);
  };
  for (const ident of byId.keys()) walk(ident);
  return raw.filter(([from, to]) => !cyclic.has(`${from}\0${to}`));
}

function longestPathRanks(
  ids: readonly string[],
  preds: Adj,
): Map<string, number> {
  const rank = new Map<string, number>();
  const visiting = new Set<string>();
  const walk = (ident: string): number => {
    const hit = rank.get(ident);
    if (hit !== undefined) return hit;
    if (visiting.has(ident)) {
      rank.set(ident, 0);
      return 0;
    }
    visiting.add(ident);
    let best = 0;
    let hasPred = false;
    for (const parent of preds.get(ident) || []) {
      hasPred = true;
      best = Math.max(best, walk(parent) + 1);
    }
    visiting.delete(ident);
    const value = hasPred ? best : 0;
    rank.set(ident, value);
    return value;
  };
  for (const ident of ids) walk(ident);
  return rank;
}

function median(values: number[]): number {
  if (!values.length) return Number.NaN;
  const sorted = [...values].sort((left, right) => left - right);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2) return sorted[mid]!;
  return (sorted[mid - 1]! + sorted[mid]!) / 2;
}

function orderRanks(
  ranks: Map<string, number>,
  preds: Adj,
  succs: Adj,
  byId: ReadonlyMap<string, TaskForestItem>,
): Map<number, string[]> {
  const maxRank = Math.max(0, ...ranks.values());
  const byRank = new Map<number, string[]>();
  for (let rank = 0; rank <= maxRank; rank += 1) byRank.set(rank, []);
  const ids = [...ranks.keys()].sort((left, right) => {
    const byRankDiff = (ranks.get(left) || 0) - (ranks.get(right) || 0);
    if (byRankDiff) return byRankDiff;
    const a = byId.get(left);
    const b = byId.get(right);
    if (a && b) return compareName(a, b);
    return left.localeCompare(right);
  });
  for (const ident of ids) {
    const rank = ranks.get(ident) || 0;
    byRank.get(rank)!.push(ident);
  }

  const columnOf = new Map<string, number>();
  const assignColumns = (row: string[]) => {
    row.forEach((ident, index) => columnOf.set(ident, index));
  };
  for (const row of byRank.values()) assignColumns(row);

  const sortRow = (rank: number, toward: "pred" | "succ") => {
    const row = byRank.get(rank);
    if (!row || row.length < 2) return;
    const adj = toward === "pred" ? preds : succs;
    row.sort((left, right) => {
      const leftBar = median(
        (adj.get(left) || [])
          .map((ident) => columnOf.get(ident))
          .filter((value): value is number => value !== undefined),
      );
      const rightBar = median(
        (adj.get(right) || [])
          .map((ident) => columnOf.get(ident))
          .filter((value): value is number => value !== undefined),
      );
      const leftHas = Number.isFinite(leftBar);
      const rightHas = Number.isFinite(rightBar);
      if (leftHas && rightHas && leftBar !== rightBar) return leftBar - rightBar;
      if (leftHas !== rightHas) return leftHas ? -1 : 1;
      return (columnOf.get(left) || 0) - (columnOf.get(right) || 0);
    });
    assignColumns(row);
  };

  for (let pass = 0; pass < LAYOUT_PASSES; pass += 1) {
    if (pass % 2 === 0) {
      for (let rank = 1; rank <= maxRank; rank += 1) sortRow(rank, "pred");
    } else {
      for (let rank = maxRank - 1; rank >= 0; rank -= 1) sortRow(rank, "succ");
    }
  }
  return byRank;
}

function rankWidth(count: number): number {
  if (count <= 0) return 0;
  return count * FLOW_NODE_WIDTH + (count - 1) * FLOW_COL_GAP;
}

function layoutComponent<T extends TaskForestItem>(
  ids: readonly string[],
  byId: ReadonlyMap<string, T>,
  preds: Adj,
  succs: Adj,
  edges: Array<[string, string]>,
  cliques: string[][],
  stubIds: ReadonlySet<string>,
  matched: ReadonlySet<string> | null,
): TaskGraphMesh<T> {
  const local = new Set(ids);
  const ranks = longestPathRanks(ids, preds);
  const byRank = orderRanks(ranks, preds, succs, byId);
  const maxRank = Math.max(0, ...ranks.values());
  const widest = Math.max(
    FLOW_NODE_WIDTH,
    ...[...byRank.values()].map((row) => rankWidth(row.length)),
  );

  const nodes: TaskGraphNode<T>[] = [];
  const at = new Map<string, TaskGraphNode<T>>();
  for (let rank = 0; rank <= maxRank; rank += 1) {
    const row = byRank.get(rank) || [];
    const offsetX = FLOW_PAD_X + (widest - rankWidth(row.length)) / 2;
    row.forEach((ident, column) => {
      const task = byId.get(ident);
      if (!task) return;
      const node: TaskGraphNode<T> = {
        id: ident,
        task,
        stub: stubIds.has(ident),
        matched: matched ? matched.has(ident) : true,
        rank,
        column,
        x: offsetX + column * (FLOW_NODE_WIDTH + FLOW_COL_GAP),
        y: FLOW_PAD_Y + rank * (FLOW_NODE_HEIGHT + FLOW_RANK_GAP),
      };
      nodes.push(node);
      at.set(ident, node);
    });
  }

  const drawn: TaskGraphEdge[] = [];
  for (const [from, to] of edges) {
    if (!local.has(from) || !local.has(to)) continue;
    const parent = at.get(from);
    const child = at.get(to);
    if (!parent || !child) continue;
    drawn.push({
      from,
      to,
      x1: parent.x + FLOW_NODE_WIDTH / 2,
      y1: parent.y + FLOW_NODE_HEIGHT,
      x2: child.x + FLOW_NODE_WIDTH / 2,
      y2: child.y,
    });
  }

  const mutexGroups: TaskGraphMutexGroup[] = [];
  for (const clique of cliques) {
    const members = clique.map((ident) => at.get(ident)).filter(Boolean) as TaskGraphNode<T>[];
    if (members.length < 2) continue;
    const rank = members[0]!.rank;
    if (members.some((row) => row.rank !== rank)) continue;
    const columns = members.map((row) => row.column).sort((a, b) => a - b);
    const span = columns[columns.length - 1]! - columns[0]! + 1;
    if (span !== members.length) continue;
    const xs = members.map((row) => row.x);
    const ys = members.map((row) => row.y);
    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    mutexGroups.push({
      ids: members.map((row) => row.id),
      label: taskChoiceLabel(members.length),
      x: minX - MUTEX_PAD_X,
      y: minY - MUTEX_PAD_TOP,
      width: Math.max(...xs) + FLOW_NODE_WIDTH - minX + MUTEX_PAD_X * 2,
      height: FLOW_NODE_HEIGHT + MUTEX_PAD_TOP + MUTEX_PAD_BOTTOM,
    });
  }

  const right = Math.max(
    FLOW_PAD_X + widest,
    ...nodes.map((row) => row.x + FLOW_NODE_WIDTH),
    ...mutexGroups.map((row) => row.x + row.width),
    0,
  );
  const bottom = Math.max(
    FLOW_PAD_Y + FLOW_NODE_HEIGHT,
    ...nodes.map((row) => row.y + FLOW_NODE_HEIGHT),
    ...mutexGroups.map((row) => row.y + row.height),
    0,
  );

  return {
    nodes,
    edges: drawn,
    mutexGroups,
    width: right + FLOW_PAD_X,
    height: bottom + FLOW_PAD_Y,
  };
}

function unionFind(ids: readonly string[]) {
  const parent = new Map<string, string>();
  for (const ident of ids) parent.set(ident, ident);
  const find = (ident: string): string => {
    const now = parent.get(ident) || ident;
    if (now !== ident) {
      const root = find(now);
      parent.set(ident, root);
      return root;
    }
    return now;
  };
  const union = (left: string, right: string) => {
    const a = find(left);
    const b = find(right);
    if (a !== b) parent.set(a, b);
  };
  return { find, union };
}

export function keepGraphAncestors<T extends TaskForestItem>(
  items: readonly T[],
  keep: (task: T) => boolean,
): { items: T[]; matched: Set<string> } {
  const byId = indexById(items);
  const matched = new Set<string>();
  for (const task of byId.values()) {
    if (keep(task)) matched.add(task.id);
  }
  if (!matched.size) return { items: [], matched };
  const preds: Adj = new Map();
  for (const [from, to] of acyclicPrereqEdges([...byId.values()])) {
    pushAdj(preds, to, from);
  }
  const keepIds = new Set(matched);
  const stack = [...matched];
  while (stack.length) {
    const ident = stack.pop();
    if (!ident) break;
    for (const parent of preds.get(ident) || []) {
      if (keepIds.has(parent)) continue;
      keepIds.add(parent);
      stack.push(parent);
    }
  }
  return {
    items: [...byId.values()].filter((row) => keepIds.has(row.id)),
    matched,
  };
}

export function outsidePrereqIds<T extends TaskForestItem>(
  task: T,
  inGraph: ReadonlySet<string>,
): string[] {
  return asIds(task.prereq_ids).filter(
    (ident) => ident !== task.id && !inGraph.has(ident),
  );
}

export function meshEdgePath(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
): string {
  const bend = Math.max(28, (y2 - y1) / 2);
  return `M ${x1} ${y1} C ${x1} ${y1 + bend}, ${x2} ${y2 - bend}, ${x2} ${y2}`;
}

export function countGraphLayout<T extends TaskForestItem>(
  layout: TaskGraphLayout<T>,
): number {
  return (
    layout.meshes.reduce((sum, mesh) => sum + mesh.nodes.length, 0) +
    layout.isolates.length
  );
}

export function layoutTaskGraph<T extends TaskForestItem>(
  items: readonly T[],
  opts: {
    stubIds?: readonly string[];
    matched?: ReadonlySet<string> | null;
  } = {},
): TaskGraphLayout<T> {
  const byId = indexById(items);
  const stubIds = new Set(
    (opts.stubIds || []).filter((ident) => byId.has(ident)),
  );
  const matched = opts.matched ?? null;
  if (!byId.size) return { meshes: [], isolates: [] };

  const edges = acyclicPrereqEdges([...byId.values()]);
  const preds: Adj = new Map();
  const succs: Adj = new Map();
  for (const [from, to] of edges) {
    pushAdj(succs, from, to);
    pushAdj(preds, to, from);
  }
  const cliques = mutexCliques(byId);
  const ids = [...byId.keys()];
  const { find, union } = unionFind(ids);
  for (const [from, to] of edges) union(from, to);
  for (const clique of cliques) {
    for (let i = 1; i < clique.length; i += 1) union(clique[0]!, clique[i]!);
  }

  const buckets = new Map<string, string[]>();
  for (const ident of ids) {
    const root = find(ident);
    const list = buckets.get(root) || [];
    list.push(ident);
    buckets.set(root, list);
  }

  const meshes: TaskGraphMesh<T>[] = [];
  const isolates: TaskGraphNode<T>[] = [];
  const groups = [...buckets.values()].map(uniqueSorted);
  groups.sort((left, right) => {
    if (right.length !== left.length) return right.length - left.length;
    const a = byId.get(left[0]!);
    const b = byId.get(right[0]!);
    if (a && b) return compareName(a, b);
    return (left[0] || "").localeCompare(right[0] || "");
  });

  for (const group of groups) {
    const linked = group.length > 1;
    if (!linked) {
      const ident = group[0]!;
      const task = byId.get(ident);
      if (!task) continue;
      isolates.push({
        id: ident,
        task,
        stub: stubIds.has(ident),
        matched: matched ? matched.has(ident) : true,
        rank: 0,
        column: 0,
        x: 0,
        y: 0,
      });
      continue;
    }
    meshes.push(
      layoutComponent(
        group,
        byId,
        preds,
        succs,
        edges,
        cliques,
        stubIds,
        matched,
      ),
    );
  }
  isolates.sort((left, right) => compareName(left.task, right.task));
  return { meshes, isolates };
}
