/** 个人中心任务进度：按前置链建树，互斥兄弟收成 N 选 1。 */

import type { TaskListItem } from "@/lib/tarkovTaskTree";

export const TARKOV_TASK_PROGRESS_VIEW_KEY =
  "zhange.guides.tarkov.taskProgressView.v1";

export type TaskProgressView = "list" | "tree";

export type TaskForestItem = Pick<
  TaskListItem,
  "id" | "name" | "prereq_ids" | "mutex_ids" | "trader_slug" | "trader_name"
>;

export type TaskForestNode<T extends TaskForestItem = TaskForestItem> = {
  task: T;
  extraPrereqIds: string[];
  matched: boolean;
  children: TaskForestChild<T>[];
};

export type TaskForestChoice<T extends TaskForestItem = TaskForestItem> = {
  kind: "choice";
  options: TaskForestNode<T>[];
};

export type TaskForestChild<T extends TaskForestItem = TaskForestItem> =
  | { kind: "task"; node: TaskForestNode<T> }
  | TaskForestChoice<T>;

const MAX_ANCESTOR_WALK = 32;

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

function inGroupPrereqs<T extends TaskForestItem>(
  task: T,
  byId: ReadonlyMap<string, T>,
): string[] {
  return asIds(task.prereq_ids).filter((ident) => byId.has(ident));
}

function ancestorSet<T extends TaskForestItem>(
  taskId: string,
  byId: ReadonlyMap<string, T>,
): Set<string> {
  const out = new Set<string>();
  const row = byId.get(taskId);
  const stack = row ? inGroupPrereqs(row, byId) : [];
  let guard = 0;
  while (stack.length && guard < MAX_ANCESTOR_WALK * 16) {
    guard += 1;
    const cur = stack.pop();
    if (!cur || out.has(cur)) continue;
    out.add(cur);
    const next = byId.get(cur);
    if (next) stack.push(...inGroupPrereqs(next, byId));
  }
  return out;
}

function primaryParentId<T extends TaskForestItem>(
  task: T,
  byId: ReadonlyMap<string, T>,
): string | null {
  const ids = inGroupPrereqs(task, byId);
  if (!ids.length) return null;
  const latest = ids.filter(
    (left) => !ids.some((right) => right !== left && ancestorSet(right, byId).has(left)),
  );
  latest.sort();
  return latest[0] || ids[0] || null;
}

function dropParentCycles(parentOf: Map<string, string>) {
  const visiting = new Set<string>();
  const done = new Set<string>();
  const walk = (ident: string) => {
    if (done.has(ident)) return;
    if (visiting.has(ident)) {
      parentOf.delete(ident);
      return;
    }
    visiting.add(ident);
    const parent = parentOf.get(ident);
    if (parent) walk(parent);
    visiting.delete(ident);
    done.add(ident);
  };
  for (const ident of [...parentOf.keys()]) walk(ident);
}

function mutexPair<T extends TaskForestItem>(left: T, right: T): boolean {
  if (left.id === right.id) return false;
  const a = new Set(asIds(left.mutex_ids));
  const b = new Set(asIds(right.mutex_ids));
  return a.has(right.id) && b.has(left.id);
}

function sortNodes<T extends TaskForestItem>(
  nodes: TaskForestNode<T>[],
): TaskForestNode<T>[] {
  return [...nodes].sort((left, right) =>
    (left.task.name || left.task.id).localeCompare(
      right.task.name || right.task.id,
      "zh-CN",
    ),
  );
}

function groupMutexSiblings<T extends TaskForestItem>(
  nodes: TaskForestNode<T>[],
): TaskForestChild<T>[] {
  const remaining = sortNodes(nodes);
  const out: TaskForestChild<T>[] = [];
  while (remaining.length) {
    const head = remaining.shift();
    if (!head) break;
    const clique = [head];
    let grew = true;
    while (grew) {
      grew = false;
      for (let i = remaining.length - 1; i >= 0; i -= 1) {
        const cand = remaining[i];
        if (clique.every((row) => mutexPair(row.task, cand.task))) {
          clique.push(cand);
          remaining.splice(i, 1);
          grew = true;
        }
      }
    }
    if (clique.length >= 2) {
      out.push({ kind: "choice", options: sortNodes(clique) });
    } else {
      out.push({ kind: "task", node: head });
    }
  }
  return out;
}

export function taskChoiceLabel(count: number): string {
  if (count <= 1) return "";
  if (count === 2) return "二选一";
  if (count === 3) return "三选一";
  return `${count} 选 1`;
}

export type FlowRibbonKind = "prereq" | "blocked" | "conflict";

export const FLOW_RIBBON_COLORS: Record<FlowRibbonKind, string> = {
  prereq: "#7a7c70",
  blocked: "#c8932a",
  conflict: "#c45c4a",
};

/** 色条按「触及其他任务」的关系种类等分：前置灰、阻断黄、冲突红。 */
export function flowCardRibbonKinds(opts: {
  prereq?: boolean;
  blocked?: boolean;
  conflict?: boolean;
}): FlowRibbonKind[] {
  const out: FlowRibbonKind[] = [];
  if (opts.prereq) out.push("prereq");
  if (opts.blocked) out.push("blocked");
  if (opts.conflict) out.push("conflict");
  return out;
}

export function flowCardRibbonGradient(
  kinds: readonly FlowRibbonKind[],
): string {
  if (!kinds.length) return "transparent";
  if (kinds.length === 1) return FLOW_RIBBON_COLORS[kinds[0]!];
  const slice = 100 / kinds.length;
  return `linear-gradient(to bottom, ${kinds
    .map((kind, index) => {
      const color = FLOW_RIBBON_COLORS[kind];
      const start = index * slice;
      const end = (index + 1) * slice;
      return `${color} ${start}% ${end}%`;
    })
    .join(", ")})`;
}

export function countForestTasks<T extends TaskForestItem>(
  children: readonly TaskForestChild<T>[],
): number {
  let total = 0;
  for (const child of children) {
    if (child.kind === "choice") {
      for (const option of child.options) {
        total += 1 + countForestTasks(option.children);
      }
    } else {
      total += 1 + countForestTasks(child.node.children);
    }
  }
  return total;
}

export function forestNodeDepth<T extends TaskForestItem>(
  node: TaskForestNode<T>,
): number {
  let deepest = 0;
  for (const child of node.children) {
    deepest = Math.max(deepest, forestChildDepth(child));
  }
  return 1 + deepest;
}

export function forestChildDepth<T extends TaskForestItem>(
  child: TaskForestChild<T>,
): number {
  if (child.kind === "choice") {
    return Math.max(0, ...child.options.map(forestNodeDepth));
  }
  return forestNodeDepth(child.node);
}

function childSortKey<T extends TaskForestItem>(
  child: TaskForestChild<T>,
): string {
  if (child.kind === "choice") {
    return child.options.map((row) => row.task.name || row.task.id).join(",");
  }
  return child.node.task.name || child.node.task.id;
}

export type SplitFlowForest<T extends TaskForestItem = TaskForestItem> = {
  chains: TaskForestChild<T>[];
  isolates: TaskForestChild<T>[];
};

/** 有后续（或互斥分叉）的根与无前后续的独立卡拆开；任务线按深度从长到短。 */
export function splitFlowForest<T extends TaskForestItem>(
  forest: readonly TaskForestChild<T>[],
): SplitFlowForest<T> {
  const chains: TaskForestChild<T>[] = [];
  const isolates: TaskForestChild<T>[] = [];
  for (const child of forest) {
    if (child.kind === "choice" || child.node.children.length) {
      chains.push(child);
    } else {
      isolates.push(child);
    }
  }
  chains.sort((left, right) => {
    const byDepth = forestChildDepth(right) - forestChildDepth(left);
    if (byDepth) return byDepth;
    return childSortKey(left).localeCompare(childSortKey(right), "zh-CN");
  });
  isolates.sort((left, right) =>
    childSortKey(left).localeCompare(childSortKey(right), "zh-CN"),
  );
  return { chains, isolates };
}

export function tarkovFlowTraderAnchor(slug: string): string {
  return `tarkov-flow-trader-${slug || "none"}`;
}

export function tarkovFlowTaskAnchor(taskId: string): string {
  return `tarkov-flow-task-${taskId}`;
}

export function collectPrereqClosure<T extends TaskForestItem>(
  items: readonly T[],
  catalog: ReadonlyMap<string, T>,
): T[] {
  const out = new Map<string, T>();
  for (const item of items) {
    const ident = String(item.id || "").trim();
    if (!ident) continue;
    out.set(ident, item);
  }
  const stack = [...out.values()];
  while (stack.length) {
    const cur = stack.pop();
    if (!cur) break;
    for (const ident of asIds(cur.prereq_ids)) {
      if (out.has(ident)) continue;
      const row = catalog.get(ident);
      if (!row) continue;
      out.set(ident, row);
      stack.push(row);
    }
  }
  return [...out.values()];
}

export function buildTaskForest<T extends TaskForestItem>(
  items: readonly T[],
): TaskForestChild<T>[] {
  const byId = new Map<string, T>();
  for (const item of items) {
    const ident = String(item.id || "").trim();
    if (!ident || byId.has(ident)) continue;
    byId.set(ident, item);
  }
  if (!byId.size) return [];

  const parentOf = new Map<string, string>();
  for (const task of byId.values()) {
    const parent = primaryParentId(task, byId);
    if (parent && parent !== task.id) parentOf.set(task.id, parent);
  }
  dropParentCycles(parentOf);

  const kids = new Map<string, T[]>();
  for (const [childId, parentId] of parentOf) {
    const child = byId.get(childId);
    if (!child) continue;
    const list = kids.get(parentId) || [];
    list.push(child);
    kids.set(parentId, list);
  }

  const visiting = new Set<string>();
  const toNode = (task: T): TaskForestNode<T> => {
    if (visiting.has(task.id)) {
      return { task, extraPrereqIds: [], matched: true, children: [] };
    }
    visiting.add(task.id);
    const primary = parentOf.get(task.id) || null;
    const extraPrereqIds = asIds(task.prereq_ids).filter(
      (ident) => ident !== primary && ident !== task.id,
    );
    const childNodes = (kids.get(task.id) || []).map(toNode);
    visiting.delete(task.id);
    return {
      task,
      extraPrereqIds,
      matched: true,
      children: groupMutexSiblings(childNodes),
    };
  };

  const roots: TaskForestNode<T>[] = [];
  for (const task of byId.values()) {
    if (!parentOf.has(task.id)) roots.push(toNode(task));
  }
  return groupMutexSiblings(roots);
}

function filterNode<T extends TaskForestItem>(
  node: TaskForestNode<T>,
  keep: (task: T) => boolean,
): TaskForestNode<T> | null {
  const children = filterTaskForest(node.children, keep);
  const matched = keep(node.task);
  if (!matched && !children.length) return null;
  return { ...node, matched, children };
}

export function filterTaskForest<T extends TaskForestItem>(
  children: readonly TaskForestChild<T>[],
  keep: (task: T) => boolean,
): TaskForestChild<T>[] {
  const out: TaskForestChild<T>[] = [];
  for (const child of children) {
    if (child.kind === "choice") {
      const options = child.options
        .map((option) => filterNode(option, keep))
        .filter((row): row is TaskForestNode<T> => Boolean(row));
      if (options.length >= 2) {
        out.push({ kind: "choice", options });
      } else if (options.length === 1) {
        out.push({ kind: "task", node: options[0] });
      }
      continue;
    }
    const node = filterNode(child.node, keep);
    if (node) out.push({ kind: "task", node });
  }
  return out;
}

export function parseTaskProgressView(raw: string | null | undefined): TaskProgressView {
  return raw === "tree" ? "tree" : "list";
}

export function loadTaskProgressView(): TaskProgressView {
  try {
    return parseTaskProgressView(localStorage.getItem(TARKOV_TASK_PROGRESS_VIEW_KEY));
  } catch {
    return "list";
  }
}

export function saveTaskProgressView(view: TaskProgressView) {
  try {
    localStorage.setItem(TARKOV_TASK_PROGRESS_VIEW_KEY, view);
  } catch {
    /* ignore quota / private mode */
  }
}
