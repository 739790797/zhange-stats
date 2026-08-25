/** 按商人把任务收成可缩进的任务线；详情邻域按 hop 分层布局。 */

export type TaskRequirementRef = {
  id: string;
  name?: string;
  met?: boolean | null;
};

export type GraphTask = {
  id: string;
  name: string;
  trader_slug?: string;
  trader_name?: string;
  min_player_level?: number;
  experience?: number;
  kappa_required?: boolean;
  lightkeeper_required?: boolean;
  faction_name?: string;
  progress_status?: string | null;
  task_requirements?: TaskRequirementRef[];
};

export type ChainExtraParent = {
  id: string;
  name: string;
  met?: boolean | null;
};

export type ChainRow = {
  task: GraphTask;
  depth: number;
  extraParents: ChainExtraParent[];
};

export type TaskChain = {
  id: string;
  title: string;
  rows: ChainRow[];
  singleton: boolean;
};

export type TraderChainGroup = {
  traderSlug: string;
  traderName: string;
  chains: TaskChain[];
};

const SERIES_RE = /^(.*?)\s*[-–—]\s*\d+\s*$/;

function seriesPrefix(name: string): string | null {
  const match = name.trim().match(SERIES_RE);
  const prefix = match?.[1]?.trim() || "";
  return prefix || null;
}

function reqsOf(task: GraphTask): TaskRequirementRef[] {
  return (task.task_requirements || []).filter((row) => row.id);
}

function extraParent(
  row: TaskRequirementRef,
  primaryId: string | null,
): ChainExtraParent | null {
  if (!row.id || row.id === primaryId) return null;
  return {
    id: row.id,
    name: row.name || row.id,
    met: row.met,
  };
}

function chainTitle(rows: ChainRow[]): string {
  const names = rows.map((row) => row.task.name);
  const prefixes = names
    .map(seriesPrefix)
    .filter((value): value is string => Boolean(value));
  if (prefixes.length >= 2 && prefixes.every((item) => item === prefixes[0])) {
    return prefixes[0];
  }
  const roots = rows.filter((row) => row.depth === 0);
  if (roots.length === 1) return roots[0].task.name;
  if (roots.length > 1) {
    return roots.map((row) => row.task.name).join(" / ");
  }
  return names[0] || rows[0]?.task.id || "";
}

function orderChain(
  compIds: string[],
  byId: Map<string, GraphTask>,
  parentsIn: Map<string, string[]>,
): TaskChain {
  const set = new Set(compIds);
  const depth = new Map<string, number>();
  const walk = (id: string, stack: Set<string>): number => {
    const cached = depth.get(id);
    if (cached !== undefined) return cached;
    if (stack.has(id)) return 0;
    stack.add(id);
    const prefs = (parentsIn.get(id) || []).filter((pid) => set.has(pid));
    const value = prefs.length
      ? 1 + Math.max(...prefs.map((pid) => walk(pid, stack)))
      : 0;
    stack.delete(id);
    depth.set(id, value);
    return value;
  };
  for (const id of compIds) walk(id, new Set());

  const remaining = new Set(compIds);
  const emitted = new Set<string>();
  const rows: ChainRow[] = [];
  while (remaining.size) {
    const ready = [...remaining].filter((id) =>
      (parentsIn.get(id) || []).every((pid) => !set.has(pid) || emitted.has(pid)),
    );
    const pool = ready.length ? ready : [...remaining];
    pool.sort((a, b) => {
      const delta = (depth.get(a) || 0) - (depth.get(b) || 0);
      if (delta) return delta;
      const left = byId.get(a)?.name || a;
      const right = byId.get(b)?.name || b;
      return left.localeCompare(right, "zh-CN");
    });
    const pick = pool[0];
    remaining.delete(pick);
    emitted.add(pick);
    const task = byId.get(pick);
    if (!task) continue;
    const inParents = (parentsIn.get(pick) || []).filter((pid) => set.has(pid));
    let primary: string | null = null;
    if (inParents.length) {
      const ranked = [...inParents].sort((a, b) => {
        const delta = (depth.get(b) || 0) - (depth.get(a) || 0);
        if (delta) return delta;
        return (byId.get(a)?.name || a).localeCompare(byId.get(b)?.name || b, "zh-CN");
      });
      primary = ranked[0];
    }
    rows.push({
      task,
      depth: depth.get(pick) || 0,
      extraParents: reqsOf(task)
        .map((row) => extraParent(row, primary))
        .filter((row): row is ChainExtraParent => Boolean(row)),
    });
  }

  return {
    id: rows[0]?.task.id || compIds[0] || "",
    title: chainTitle(rows),
    rows,
    singleton: rows.length <= 1,
  };
}

export function groupTaskChains(items: GraphTask[]): TaskChain[] {
  const byId = new Map(items.map((item) => [item.id, item]));
  const ids = new Set(byId.keys());
  const parentsIn = new Map<string, string[]>();
  const childrenIn = new Map<string, string[]>();
  for (const item of items) {
    const prefs = reqsOf(item)
      .map((row) => row.id)
      .filter((id) => ids.has(id) && id !== item.id);
    parentsIn.set(item.id, prefs);
    for (const parentId of prefs) {
      const list = childrenIn.get(parentId) || [];
      list.push(item.id);
      childrenIn.set(parentId, list);
    }
  }

  const seen = new Set<string>();
  const chains: TaskChain[] = [];
  for (const item of items) {
    if (seen.has(item.id)) continue;
    const stack = [item.id];
    const comp: string[] = [];
    while (stack.length) {
      const cur = stack.pop();
      if (!cur || seen.has(cur)) continue;
      seen.add(cur);
      comp.push(cur);
      for (const next of [
        ...(parentsIn.get(cur) || []),
        ...(childrenIn.get(cur) || []),
      ]) {
        if (!seen.has(next)) stack.push(next);
      }
    }
    chains.push(orderChain(comp, byId, parentsIn));
  }

  chains.sort((a, b) => {
    if (a.singleton !== b.singleton) return a.singleton ? 1 : -1;
    return a.title.localeCompare(b.title, "zh-CN");
  });
  return chains;
}

export function groupChainsByTrader(
  items: GraphTask[],
  traderOrder: Array<{ slug: string; name: string }>,
): TraderChainGroup[] {
  const byTrader = new Map<string, GraphTask[]>();
  for (const item of items) {
    const slug = item.trader_slug || "";
    const list = byTrader.get(slug) || [];
    list.push(item);
    byTrader.set(slug, list);
  }
  const ordered = traderOrder.map((row) => row.slug);
  const extra = [...byTrader.keys()].filter((slug) => !ordered.includes(slug));
  extra.sort((a, b) => {
    const left = byTrader.get(a)?.[0]?.trader_name || a;
    const right = byTrader.get(b)?.[0]?.trader_name || b;
    return left.localeCompare(right, "zh-CN");
  });
  return [...ordered, ...extra]
    .filter((slug) => byTrader.has(slug))
    .map((slug) => {
      const list = byTrader.get(slug) || [];
      const named = traderOrder.find((row) => row.slug === slug);
      return {
        traderSlug: slug,
        traderName: named?.name || list[0]?.trader_name || slug,
        chains: groupTaskChains(list),
      };
    });
}

export type NeighborhoodNode = {
  id: string;
  name: string;
  hop: number;
  trader_slug?: string;
  progress_status?: string | null;
};

export type NeighborhoodEdge = {
  source_id: string;
  target_id: string;
};

export type LaidOutNode = NeighborhoodNode & {
  x: number;
  y: number;
  width: number;
  height: number;
  current: boolean;
};

export type LaidOutEdge = {
  source_id: string;
  target_id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

const NODE_WIDTH = 148;
const NODE_HEIGHT = 40;
const RANK_GAP = 52;
const NODE_GAP = 12;
const PADDING = 8;

export function layoutTaskNeighborhood(
  nodes: NeighborhoodNode[],
  edges: NeighborhoodEdge[],
  currentId: string,
  opts?: {
    nodeWidth?: number;
    nodeHeight?: number;
    rankGap?: number;
    nodeGap?: number;
    padding?: number;
  },
): { nodes: LaidOutNode[]; edges: LaidOutEdge[]; width: number; height: number } {
  const nodeWidth = opts?.nodeWidth ?? NODE_WIDTH;
  const nodeHeight = opts?.nodeHeight ?? NODE_HEIGHT;
  const rankGap = opts?.rankGap ?? RANK_GAP;
  const nodeGap = opts?.nodeGap ?? NODE_GAP;
  const padding = opts?.padding ?? PADDING;
  if (!nodes.length) {
    return { nodes: [], edges: [], width: 0, height: 0 };
  }

  const columns = new Map<number, NeighborhoodNode[]>();
  for (const node of nodes) {
    const list = columns.get(node.hop) || [];
    list.push(node);
    columns.set(node.hop, list);
  }
  const hops = [...columns.keys()].sort((a, b) => a - b);
  for (const hop of hops) {
    const list = columns.get(hop) || [];
    list.sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
    columns.set(hop, list);
  }
  const maxCount = Math.max(...hops.map((hop) => columns.get(hop)?.length || 0), 1);
  const colHeight = maxCount * nodeHeight + (maxCount - 1) * nodeGap;
  const laid: LaidOutNode[] = [];
  const byId = new Map<string, LaidOutNode>();
  hops.forEach((hop, rank) => {
    const list = columns.get(hop) || [];
    const stackH = list.length * nodeHeight + Math.max(0, list.length - 1) * nodeGap;
    const top = padding + (colHeight - stackH) / 2;
    list.forEach((node, index) => {
      const placed: LaidOutNode = {
        ...node,
        x: padding + rank * (nodeWidth + rankGap),
        y: top + index * (nodeHeight + nodeGap),
        width: nodeWidth,
        height: nodeHeight,
        current: node.id === currentId,
      };
      laid.push(placed);
      byId.set(node.id, placed);
    });
  });

  const laidEdges: LaidOutEdge[] = [];
  for (const edge of edges) {
    const from = byId.get(edge.source_id);
    const to = byId.get(edge.target_id);
    if (!from || !to) continue;
    laidEdges.push({
      source_id: edge.source_id,
      target_id: edge.target_id,
      x1: from.x + from.width,
      y1: from.y + from.height / 2,
      x2: to.x,
      y2: to.y + to.height / 2,
    });
  }

  const width =
    padding * 2 + hops.length * nodeWidth + Math.max(0, hops.length - 1) * rankGap;
  const height = padding * 2 + colHeight;
  return { nodes: laid, edges: laidEdges, width, height };
}
