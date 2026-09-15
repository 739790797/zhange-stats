/** 任务线账：手改完成时补前置、互斥收口，并把被挡住 / 子孙从完成·进行中拿掉。 */

import { applyMutexLedger, mutexIndexFromTasks } from "@/lib/tarkovTaskMutex";

const PREREQ_WALK_MAX = 32;
const DESCENDANT_WALK_MAX = 256;

export type TaskLineSpec = {
  id?: string | null;
  mutex_ids?: readonly string[] | null;
  prereq_ids?: readonly string[] | null;
  blocked_by?: readonly string[] | null;
};

export type TaskLineIndex = {
  mutexById: Map<string, string[]>;
  prereqById: Map<string, string[]>;
  childrenById: Map<string, string[]>;
  blockedById: Map<string, string[]>;
};

export type TaskWritableStatus = "todo" | "active" | "done" | "failed";

function asId(raw: string | null | undefined): string {
  return String(raw || "").trim().toLowerCase();
}

function asIdList(ids: Iterable<string>): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of ids) {
    const id = asId(raw);
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(id);
  }
  return out;
}

function pushEdge(
  map: Map<string, string[]>,
  from: string,
  to: string,
): void {
  if (!from || !to || from === to) return;
  const row = map.get(from) || [];
  if (!row.includes(to)) row.push(to);
  map.set(from, row);
}

export function taskLineIndexFromTasks(
  items: ReadonlyArray<TaskLineSpec>,
): TaskLineIndex {
  const prereqById = new Map<string, string[]>();
  const childrenById = new Map<string, string[]>();
  const blockedById = new Map<string, string[]>();
  for (const item of items) {
    const id = asId(item.id);
    if (!id) continue;
    for (const raw of item.prereq_ids || []) {
      const prereq = asId(String(raw || ""));
      if (!prereq) continue;
      pushEdge(prereqById, id, prereq);
      pushEdge(childrenById, prereq, id);
    }
    for (const raw of item.blocked_by || []) {
      const blocker = asId(String(raw || ""));
      if (!blocker) continue;
      pushEdge(blockedById, id, blocker);
    }
  }
  return {
    mutexById: mutexIndexFromTasks(items),
    prereqById,
    childrenById,
    blockedById,
  };
}

export function collectDescendantIds(
  taskId: string,
  childrenById: ReadonlyMap<string, readonly string[]>,
): string[] {
  const root = asId(taskId);
  if (!root) return [];
  const out: string[] = [];
  const seen = new Set<string>([root]);
  const stack = [...(childrenById.get(root) || [])];
  while (stack.length) {
    const cur = asId(String(stack.pop() || ""));
    if (!cur || seen.has(cur)) continue;
    seen.add(cur);
    out.push(cur);
    if (seen.size > DESCENDANT_WALK_MAX) break;
    stack.push(...(childrenById.get(cur) || []));
  }
  return out;
}

/** 被已完成 / 进行中任务挡住的后续，不留在三本账上（展示成无法完成）。 */
export function dropBlockedProgress(
  doneIds: Iterable<string>,
  startedIds: Iterable<string>,
  failedIds: Iterable<string>,
  blockedById: ReadonlyMap<string, readonly string[]>,
): { done: string[]; started: string[]; failed: string[] } {
  const done = asIdList(doneIds);
  const started = asIdList(startedIds);
  const failed = asIdList(failedIds);
  if (!blockedById.size) {
    return { done, started, failed };
  }
  const doneSet = new Set(done);
  const startedSet = new Set(started);
  const drop = new Set<string>();
  for (const [id, blockers] of blockedById) {
    if (!id) continue;
    if (blockers.some((raw) => {
      const blocker = asId(String(raw || ""));
      return Boolean(blocker && (doneSet.has(blocker) || startedSet.has(blocker)));
    })) {
      drop.add(id);
    }
  }
  if (!drop.size) return { done, started, failed };
  return {
    done: done.filter((id) => !drop.has(id)),
    started: started.filter((id) => !drop.has(id)),
    failed: failed.filter((id) => !drop.has(id)),
  };
}

export function applyTaskLineLedger(
  doneIds: Iterable<string>,
  startedIds: Iterable<string>,
  failedIds: Iterable<string>,
  index: TaskLineIndex,
  prefer?: Iterable<string>,
): { done: string[]; started: string[]; failed: string[] } {
  const mutexed = applyMutexLedger(
    doneIds,
    startedIds,
    failedIds,
    index.mutexById,
    prefer,
  );
  return dropBlockedProgress(
    mutexed.done,
    mutexed.started,
    mutexed.failed,
    index.blockedById,
  );
}

function walkComplete(
  startId: string,
  done: Set<string>,
  started: Set<string>,
  failed: Set<string>,
  prereqById: ReadonlyMap<string, readonly string[]>,
  skipRoot = false,
): void {
  const walking = new Set<string>();
  if (skipRoot) walking.add(startId);
  const visit = (id: string) => {
    if (!id || walking.has(id)) return;
    walking.add(id);
    done.add(id);
    started.delete(id);
    failed.delete(id);
    if (walking.size > PREREQ_WALK_MAX) return;
    for (const raw of prereqById.get(id) || []) {
      visit(asId(String(raw || "")));
    }
  };
  if (skipRoot) {
    for (const raw of prereqById.get(startId) || []) {
      visit(asId(String(raw || "")));
    }
    return;
  }
  visit(startId);
}

export function setTaskLineStatus(
  doneIds: readonly string[],
  startedIds: readonly string[],
  taskId: string,
  status: TaskWritableStatus,
  failedIds: readonly string[] = [],
  index?: TaskLineIndex | null,
): { done: string[]; started: string[]; failed: string[] } {
  const ident = asId(taskId);
  const done = new Set(asIdList(doneIds));
  const failed = new Set(asIdList(failedIds).filter((id) => !done.has(id)));
  const started = new Set(
    asIdList(startedIds).filter((id) => !done.has(id) && !failed.has(id)),
  );
  if (!ident) {
    return { done: [...done], started: [...started], failed: [...failed] };
  }

  const dropSelf = () => {
    done.delete(ident);
    started.delete(ident);
    failed.delete(ident);
  };

  const dropDescendantProgress = () => {
    if (!index) return;
    for (const child of collectDescendantIds(ident, index.childrenById)) {
      done.delete(child);
      started.delete(child);
    }
  };

  if (status === "done") {
    if (index) {
      walkComplete(ident, done, started, failed, index.prereqById);
    } else {
      dropSelf();
      done.add(ident);
    }
  } else if (status === "active") {
    if (index) {
      walkComplete(ident, done, started, failed, index.prereqById, true);
    }
    dropSelf();
    dropDescendantProgress();
    started.add(ident);
  } else if (status === "failed") {
    dropSelf();
    failed.add(ident);
    dropDescendantProgress();
  } else {
    dropSelf();
    dropDescendantProgress();
  }

  if (!index) {
    return { done: [...done], started: [...started], failed: [...failed] };
  }
  return applyTaskLineLedger(
    [...done],
    [...started],
    [...failed],
    index,
    status === "done" ? [ident] : [],
  );
}
