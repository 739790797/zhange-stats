/** 个人中心任务勾选：按商人分组；完成/进行中本机缓存 + 账号进度账。 */

import type { TarkovGameMode } from "@/lib/tarkovGameMode";
import { notifyTarkovTaskProgress, sameIdLists } from "@/lib/tarkovLiveWatch";
import { TARKOV_MAPS } from "@/lib/tarkovHomeNav";
import { compareBeijingClock, laterBeijingClock, nowBeijingStamp } from "@/lib/time";
import { applyMutexLedger, mutexIndexFromTasks } from "@/lib/tarkovTaskMutex";
import {
  setTaskLineStatus,
  taskLineIndexFromTasks,
  type TaskLineSpec,
} from "@/lib/tarkovTaskLineLedger";
import {
  mapSlugKeys,
  normalizeRaidPrepMapId,
  raidPrepMapOptions,
} from "@/lib/tarkovMapSlugs";

export const TARKOV_TASK_DONES_STORAGE_KEY = "zhange.guides.tarkov.taskDones.v1";
export const ANY_TASK_MAP = "any";

export type TaskListItem = {
  id: string;
  name: string;
  normalized_name?: string;
  trader_slug?: string;
  trader_name?: string;
  min_player_level?: number;
  min_trader_level?: number;
  map_slug?: string;
  map_name?: string;
  lightkeeper_required?: boolean;
  faction_name?: string;
  line_hint?: string;
  mutex_ids?: string[];
  blocked_by?: string[];
  prereq_ids?: string[];
  fail_prereq_ids?: string[];
  fail_or_complete_ids?: string[];
  restartable?: boolean;
};

export type TaskLineRef = {
  mutex_ids?: readonly string[] | null;
  blocked_by?: readonly string[] | null;
  prereq_ids?: readonly string[] | null;
  fail_prereq_ids?: readonly string[] | null;
  fail_or_complete_ids?: readonly string[] | null;
};

export type TaskListFilter = {
  q?: string;
  map?: string;
};

export type TaskMapChip = {
  id: string;
  label: string;
  english: string;
  icon: string;
  count: number;
};

export type TaskProgressSummary = {
  total: number;
  incomplete: number;
  active: number;
  completed: number;
  failed: number;
  unreachable: number;
};

export type TraderTaskGroup = {
  traderSlug: string;
  traderName: string;
  done: number;
  total: number;
  items: TaskListItem[];
};

export type TaskObjectivePair = {
  task_id: string;
  objective_id: string;
};

export type TarkovTaskDonesState = {
  v: 1;
  pvp?: string[];
  pve?: string[];
  started?: { pvp?: string[]; pve?: string[] };
  failed?: { pvp?: string[]; pve?: string[] };
  migrated?: { pvp?: boolean; pve?: boolean };
  startedMigrated?: { pvp?: boolean; pve?: boolean };
  syncedAt?: { pvp?: string; pve?: string };
  cursorAt?: { pvp?: string; pve?: string };
  objectives?: { pvp?: TaskObjectivePair[]; pve?: TaskObjectivePair[] };
  /** 用户从已完成改走的任务 id → 北京墙钟；日志回放不得用更早的完成事件粘回去。 */
  clearedDone?: { pvp?: Record<string, string>; pve?: Record<string, string> };
  /** 当前模式日志里选中的游戏 ProfileId。用来认出是哪个角色，不是转生标记。 */
  questProfileId?: { pvp?: string; pve?: string };
  /** 转生清空已写本机、账号整表替换还没成功。这段时间以本机账为准。 */
  questProfileResetPending?: { pvp?: boolean; pve?: boolean };
  /** 玩家清空进度后，下一次任务同步从当前模式最新 ProfileId 重放。 */
  questSyncFromLatest?: { pvp?: boolean; pve?: boolean };
  /** 本机点「清空进度」的时刻，还没被带日志的同步定成下限。登录时以账号的 pending_clear_at 为准。 */
  questClearedAt?: { pvp?: string; pve?: string };
  /**
   * 回放下限（北京墙钟）的本机缓存，只增不减。登录时以账号的 reset_at 为准，这里只是缓存与访客兜底。
   */
  questProgressFloor?: { pvp?: string; pve?: string };
  /**
   * 本机这份任务账基于账号的哪个 reset_epoch。和账号对不上说明别处清空 / 重置过，本机账作废、以账号为准；
   * 批量写入也带它，服务端对不上回 409。
   */
  questServerEpoch?: { pvp?: number; pve?: number };
};

let questLedgerEpoch = 0;

/** 转生清空后递增，丢掉还在飞的旧合并请求。 */
export function bumpQuestLedgerEpoch(): number {
  questLedgerEpoch += 1;
  return questLedgerEpoch;
}

export function questLedgerEpochNow(): number {
  return questLedgerEpoch;
}

export type AccountTaskProgress = {
  task_ids?: string[];
  started_ids?: string[];
  failed_ids?: string[];
  objective_dones?: TaskObjectivePair[];
};

export type AccountTaskHydratePlan = {
  done: string[];
  started: string[];
  failed: string[];
  objectives: TaskObjectivePair[];
  upload: boolean;
};

function asProfileId(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function asStampMap(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const out: Record<string, string> = {};
  for (const [rawId, rawAt] of Object.entries(
    value as Record<string, unknown>,
  )) {
    const ident = rawId.trim().toLowerCase();
    const at = typeof rawAt === "string" ? rawAt.trim() : "";
    if (!ident || !at) continue;
    out[ident] = at;
  }
  return out;
}

function asIdList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of value) {
    if (typeof raw !== "string") continue;
    const ident = raw.trim().toLowerCase();
    if (!ident || seen.has(ident)) continue;
    seen.add(ident);
    out.push(ident);
  }
  return out;
}

export function asObjectivePairs(value: unknown): TaskObjectivePair[] {
  const seen = new Set<string>();
  const out: TaskObjectivePair[] = [];
  const push = (taskId: string, objectiveId: string) => {
    const task = taskId.trim();
    const objective = objectiveId.trim();
    if (!task || !objective) return;
    const key = `${task}\0${objective}`;
    if (seen.has(key)) return;
    seen.add(key);
    out.push({ task_id: task, objective_id: objective });
  };
  if (Array.isArray(value)) {
    for (const raw of value) {
      if (!raw || typeof raw !== "object") continue;
      const row = raw as { task_id?: unknown; objective_id?: unknown };
      push(String(row.task_id ?? ""), String(row.objective_id ?? ""));
    }
    return out;
  }
  if (!value || typeof value !== "object") return out;
  for (const [taskId, ids] of Object.entries(value as Record<string, unknown>)) {
    if (!Array.isArray(ids)) continue;
    for (const id of ids) push(taskId, String(id ?? ""));
  }
  return out;
}

export function sameObjectiveLists(
  left: readonly TaskObjectivePair[],
  right: readonly TaskObjectivePair[],
): boolean {
  if (left.length !== right.length) return false;
  const keys = (rows: readonly TaskObjectivePair[]) =>
    [...rows]
      .map((row) => `${row.task_id}\0${row.objective_id}`)
      .sort();
  const a = keys(left);
  const b = keys(right);
  return a.every((key, index) => key === b[index]);
}

export function unionObjectivePairs(
  left: readonly TaskObjectivePair[],
  right: readonly TaskObjectivePair[],
): TaskObjectivePair[] {
  return asObjectivePairs([...left, ...right]);
}

export function setTaskObjective(
  pairs: readonly TaskObjectivePair[],
  taskId: string,
  objectiveId: string,
  checked: boolean,
): TaskObjectivePair[] {
  const task = taskId.trim();
  const objective = objectiveId.trim();
  if (!task || !objective) return asObjectivePairs(pairs);
  const next = asObjectivePairs(pairs).filter(
    (row) => !(row.task_id === task && row.objective_id === objective),
  );
  if (checked) next.push({ task_id: task, objective_id: objective });
  return next;
}

export function mergeObjectivesForTask(
  pairs: readonly TaskObjectivePair[],
  taskId: string,
  objectiveIds: readonly string[],
): TaskObjectivePair[] {
  const task = taskId.trim();
  if (!task) return asObjectivePairs(pairs);
  return unionObjectivePairs(
    pairs,
    objectiveIds.map((id) => ({ task_id: task, objective_id: id })),
  );
}

function asClock(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function asClockMap(
  value: unknown,
): { pvp?: string; pve?: string } | undefined {
  if (!value || typeof value !== "object") return undefined;
  const row = value as { pvp?: unknown; pve?: unknown };
  const pvp = asClock(row.pvp);
  const pve = asClock(row.pve);
  if (!pvp && !pve) return undefined;
  return {
    ...(pvp ? { pvp } : {}),
    ...(pve ? { pve } : {}),
  };
}

function asEpoch(value: unknown): number | undefined {
  return typeof value === "number" && Number.isInteger(value) && value >= 0
    ? value
    : undefined;
}

function asEpochMap(
  value: unknown,
): { pvp?: number; pve?: number } | undefined {
  if (!value || typeof value !== "object") return undefined;
  const row = value as { pvp?: unknown; pve?: unknown };
  const pvp = asEpoch(row.pvp);
  const pve = asEpoch(row.pve);
  if (pvp === undefined && pve === undefined) return undefined;
  return {
    ...(pvp !== undefined ? { pvp } : {}),
    ...(pve !== undefined ? { pve } : {}),
  };
}

export function taskMatchesQuery(task: TaskListItem, q: string): boolean {
  if (!q) return true;
  const hay = `${task.name} ${task.id} ${task.normalized_name || ""} ${task.line_hint || ""}`
    .toLowerCase()
    .replace(/[-_/]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const needle = q
    .toLowerCase()
    .replace(/[-_/]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!needle) return true;
  return hay.includes(needle) || hay.replace(/ /g, "").includes(needle.replace(/ /g, ""));
}

export function resolveTaskMapId(
  task: Pick<TaskListItem, "map_slug" | "map_name">,
): string {
  const slug = (task.map_slug || "").trim();
  const name = (task.map_name || "").trim();
  if (!slug && !name) return "";
  const fromSlug = normalizeRaidPrepMapId(slug);
  if (fromSlug) return fromSlug;
  if (name) {
    const needle = name.toLowerCase();
    const option = raidPrepMapOptions().find(
      (row) =>
        row.label === name ||
        row.english.toLowerCase() === needle ||
        row.id === needle,
    );
    if (option) return option.id;
    const home = TARKOV_MAPS.find(
      (row) => row.label === name || row.english.toLowerCase() === needle,
    );
    if (home) return home.id;
  }
  return slug.toLowerCase() || name.toLowerCase();
}

export function taskHitsMap(
  task: Pick<TaskListItem, "map_slug" | "map_name">,
  mapId: string,
): boolean {
  const want = (mapId || "").trim().toLowerCase();
  if (!want) return true;
  const got = resolveTaskMapId(task);
  if (want === ANY_TASK_MAP) return !got;
  if (!got) return false;
  if (got === want) return true;
  const keys = mapSlugKeys(want);
  return keys.has(got) || [...mapSlugKeys(got)].some((key) => keys.has(key));
}

export function describeTaskMap(
  task: Pick<TaskListItem, "map_slug" | "map_name">,
): TaskMapChip | null {
  const id = resolveTaskMapId(task);
  if (!id) return null;
  const option = raidPrepMapOptions().find((row) => row.id === id);
  if (option) {
    return {
      id: option.id,
      label: option.label,
      english: option.english,
      icon: option.icon,
      count: 1,
    };
  }
  return {
    id,
    label: (task.map_name || "").trim() || id,
    english: "",
    icon: "",
    count: 1,
  };
}

export function collectTaskMapChips(items: TaskListItem[]): TaskMapChip[] {
  const counts = new Map<string, number>();
  let anyCount = 0;
  for (const item of items) {
    const id = resolveTaskMapId(item);
    if (!id) {
      anyCount += 1;
      continue;
    }
    counts.set(id, (counts.get(id) || 0) + 1);
  }
  const chips: TaskMapChip[] = [];
  for (const option of raidPrepMapOptions()) {
    const count = counts.get(option.id) || 0;
    if (!count) continue;
    chips.push({
      id: option.id,
      label: option.label,
      english: option.english,
      icon: option.icon,
      count,
    });
    counts.delete(option.id);
  }
  for (const [id, count] of counts) {
    chips.push({ id, label: id, english: "", icon: "", count });
  }
  if (anyCount) {
    chips.push({
      id: ANY_TASK_MAP,
      label: "任意",
      english: "Any",
      icon: "",
      count: anyCount,
    });
  }
  return chips;
}

/** 前置已失败 / 无法完成的后续：展示成无法完成。 */
export function collectClosedTaskIds(
  items: ReadonlyArray<TaskListItem>,
  done: ReadonlySet<string>,
  started: ReadonlySet<string> = new Set(),
  failed: ReadonlySet<string> = new Set(),
): Set<string> {
  const byId = new Map<string, TaskListItem>();
  for (const item of items) {
    const id = String(item.id || "").trim().toLowerCase();
    if (id) byId.set(id, item);
  }
  const closed = new Set<string>();
  let grew = true;
  while (grew) {
    grew = false;
    for (const [id, item] of byId) {
      if (done.has(id) || closed.has(id)) continue;
      const status = resolveTaskStatus(id, done, started, item, failed);
      if (status === "failed" || status === "unreachable") {
        closed.add(id);
        grew = true;
        continue;
      }
      for (const raw of item.prereq_ids || []) {
        const pid = String(raw || "").trim().toLowerCase();
        if (pid && closed.has(pid)) {
          closed.add(id);
          grew = true;
          break;
        }
      }
      if (closed.has(id)) continue;
      let failLocked = false;
      for (const raw of item.fail_prereq_ids || []) {
        const pid = String(raw || "").trim().toLowerCase();
        if (!pid) continue;
        if (done.has(pid) || (closed.has(pid) && !failed.has(pid))) {
          failLocked = true;
          break;
        }
      }
      if (failLocked) {
        closed.add(id);
        grew = true;
        continue;
      }
      for (const raw of item.fail_or_complete_ids || []) {
        const pid = String(raw || "").trim().toLowerCase();
        if (!pid || done.has(pid) || failed.has(pid)) continue;
        if (closed.has(pid)) {
          closed.add(id);
          grew = true;
          break;
        }
      }
    }
  }
  return closed;
}

export function summarizeTaskProgress(
  items: TaskListItem[],
  done: ReadonlySet<string>,
  started: ReadonlySet<string> = new Set(),
  failed: ReadonlySet<string> = new Set(),
): TaskProgressSummary {
  const closed = collectClosedTaskIds(items, done, started, failed);
  let completed = 0;
  let active = 0;
  let failedCount = 0;
  let unreachable = 0;
  let incomplete = 0;
  for (const item of items) {
    const status = resolveTaskStatus(item.id, done, started, item, failed, closed);
    if (status === "done") completed += 1;
    else if (status === "active") active += 1;
    else if (status === "failed") failedCount += 1;
    else if (status === "unreachable") unreachable += 1;
    else incomplete += 1;
  }
  return {
    total: items.length,
    incomplete,
    active,
    completed,
    failed: failedCount,
    unreachable,
  };
}

export const TASK_WRITABLE_STATUS_KINDS = [
  "todo",
  "active",
  "done",
  "failed",
] as const;
export type TaskWritableStatus = (typeof TASK_WRITABLE_STATUS_KINDS)[number];

export const TASK_STATUS_KINDS = [
  "todo",
  "active",
  "done",
  "failed",
  "unreachable",
] as const;
export type TaskStatusKind = (typeof TASK_STATUS_KINDS)[number];

export const TASK_STATUS_LABELS: Record<TaskStatusKind, string> = {
  todo: "未完成",
  active: "进行中",
  done: "已完成",
  failed: "失败",
  unreachable: "无法完成",
};

export function isWritableTaskStatus(
  status: TaskStatusKind,
): status is TaskWritableStatus {
  return (
    status === "todo" ||
    status === "active" ||
    status === "done" ||
    status === "failed"
  );
}

/** 互斥失败 / 被挡住：由其它任务推出来，手改会立刻弹回。 */
export function isDerivedTaskStatus(
  taskId: string,
  done: ReadonlySet<string>,
  started: ReadonlySet<string>,
  line?: TaskLineRef | null,
  failed: ReadonlySet<string> = new Set(),
  closed?: ReadonlySet<string> | null,
): boolean {
  const status = resolveTaskStatus(taskId, done, started, line, failed, closed);
  if (status === "unreachable") return true;
  if (status !== "failed") return false;
  const ident = String(taskId || "").trim().toLowerCase();
  return Boolean(ident) && !failed.has(ident);
}

export function taskPlayerLevelLabel(level: number | null | undefined): string {
  const n = Math.trunc(Number(level) || 0);
  return n > 0 ? String(n) : "—";
}

export type TaskLoyaltyLevel = 1 | 2 | 3 | 4;

/** 商人好感 1–3 为罗马数字，4 及以上为皇冠（与游戏商人页一致）。 */
export function taskLoyaltyLevel(
  level: number | null | undefined,
): TaskLoyaltyLevel {
  const n = Math.trunc(Number(level) || 0);
  if (n <= 1) return 1;
  if (n >= 4) return 4;
  return n as 2 | 3;
}

function lineIdHits(
  ids: readonly string[] | null | undefined,
  ...pools: ReadonlySet<string>[]
): boolean {
  if (!ids?.length) return false;
  for (const raw of ids) {
    const ident = String(raw || "").trim().toLowerCase();
    if (!ident) continue;
    for (const pool of pools) {
      if (pool.has(ident)) return true;
    }
  }
  return false;
}

export function resolveTaskStatus(
  taskId: string,
  done: ReadonlySet<string>,
  started: ReadonlySet<string>,
  line?: TaskLineRef | null,
  failed: ReadonlySet<string> = new Set(),
  closed?: ReadonlySet<string> | null,
): TaskStatusKind {
  const ident = String(taskId || "").trim().toLowerCase();
  if (ident && done.has(ident)) return "done";
  if (ident && failed.has(ident)) return "failed";
  if (lineIdHits(line?.mutex_ids, done)) return "failed";
  if (lineIdHits(line?.blocked_by, done, started)) return "unreachable";
  if (ident && closed?.has(ident)) return "unreachable";
  if (lineIdHits(line?.fail_prereq_ids, done)) return "unreachable";
  if (ident && started.has(ident)) return "active";
  return "todo";
}

/** 完成前置已齐、失败前置已失败（或完成/失败二选一已满足）时才能接。 */
export function taskIsAvailable(
  task: TaskLineRef & { id?: string | null },
  done: ReadonlySet<string>,
  started: ReadonlySet<string> = new Set(),
  failed: ReadonlySet<string> = new Set(),
  closed?: ReadonlySet<string> | null,
): boolean {
  const status = resolveTaskStatus(task.id || "", done, started, task, failed, closed);
  if (status !== "todo") return false;
  for (const raw of task.prereq_ids || []) {
    const id = String(raw || "").trim().toLowerCase();
    if (id && !done.has(id)) return false;
  }
  for (const raw of task.fail_prereq_ids || []) {
    const id = String(raw || "").trim().toLowerCase();
    if (id && !failed.has(id)) return false;
  }
  for (const raw of task.fail_or_complete_ids || []) {
    const id = String(raw || "").trim().toLowerCase();
    if (id && !done.has(id) && !failed.has(id)) return false;
  }
  return true;
}

export function setTaskStatus(
  doneIds: readonly string[],
  startedIds: readonly string[],
  taskId: string,
  status: TaskWritableStatus,
  failedIds: readonly string[] = [],
  mutexIds?: readonly string[] | null,
  catalog?: readonly TaskLineSpec[] | null,
): { done: string[]; started: string[]; failed: string[] } {
  if (catalog?.length) {
    return setTaskLineStatus(
      doneIds,
      startedIds,
      taskId,
      status,
      failedIds,
      taskLineIndexFromTasks(catalog),
    );
  }
  const ident = taskId.trim().toLowerCase();
  const done = new Set(asIdList(doneIds));
  const failed = new Set(asIdList(failedIds).filter((id) => !done.has(id)));
  const started = new Set(
    asIdList(startedIds).filter((id) => !done.has(id) && !failed.has(id)),
  );
  if (!ident) return { done: [...done], started: [...started], failed: [...failed] };
  done.delete(ident);
  started.delete(ident);
  failed.delete(ident);
  if (status === "done") done.add(ident);
  else if (status === "active") started.add(ident);
  else if (status === "failed") failed.add(ident);
  const mutexById = mutexIndexFromTasks([
    { id: ident, mutex_ids: mutexIds || [] },
  ]);
  if (!mutexById.size) {
    return { done: [...done], started: [...started], failed: [...failed] };
  }
  return applyMutexLedger(
    [...done],
    [...started],
    [...failed],
    mutexById,
    status === "done" ? [ident] : [],
  );
}

/** 写下拉状态到本机进度，并通知联机大厅 / 个人中心刷新。 */
export function commitTaskStatus(
  mode: TarkovGameMode,
  taskId: string,
  status: TaskWritableStatus,
  fillObjectiveIds?: readonly string[],
  mutexIds?: readonly string[] | null,
  catalog?: readonly TaskLineSpec[] | null,
): {
  done: string[];
  started: string[];
  failed: string[];
  objectives: TaskObjectivePair[];
} {
  const next = setTaskStatus(
    loadTaskDoneIds(mode),
    loadTaskStartedIds(mode),
    taskId,
    status,
    loadTaskFailedIds(mode),
    mutexIds,
    catalog,
  );
  let objectives = loadTaskObjectivePairs(mode);
  if (status === "done" && fillObjectiveIds?.length) {
    objectives = mergeObjectivesForTask(objectives, taskId, fillObjectiveIds);
  }
  saveTaskProgress(
    mode,
    next.done,
    next.started,
    false,
    false,
    objectives,
    next.failed,
  );
  notifyTarkovTaskProgress({
    mode,
    done: next.done,
    started: next.started,
    failed: next.failed,
    objectives,
    changed: true,
    source: "user",
    completedIds: status === "done" ? [taskId.trim()].filter(Boolean) : [],
  });
  return { ...next, objectives };
}

export function commitTaskObjective(
  mode: TarkovGameMode,
  taskId: string,
  objectiveId: string,
  checked: boolean,
): TaskObjectivePair[] {
  const next = setTaskObjective(
    loadTaskObjectivePairs(mode),
    taskId,
    objectiveId,
    checked,
  );
  saveTaskObjectivePairs(mode, next);
  notifyTarkovTaskProgress({
    mode,
    done: loadTaskDoneIds(mode),
    started: loadTaskStartedIds(mode),
    objectives: next,
    changed: true,
    source: "user",
  });
  return next;
}

export function applyTaskDoneToggle(
  doneIds: readonly string[],
  taskId: string,
  complete: boolean,
): string[] {
  const ident = taskId.trim();
  if (!ident) return [...doneIds];
  const next = new Set(doneIds);
  if (complete) next.add(ident);
  else next.delete(ident);
  return [...next];
}

export function groupTasksByTrader(
  items: TaskListItem[],
  traders: Array<{ slug: string; name: string }>,
  doneIds: Iterable<string>,
  filter: TaskListFilter = {},
): TraderTaskGroup[] {
  const done = doneIds instanceof Set ? doneIds : new Set(doneIds);
  const q = (filter.q || "").trim().toLowerCase();
  const byTrader = new Map<string, TaskListItem[]>();
  for (const item of items) {
    const slug = item.trader_slug || "";
    const list = byTrader.get(slug) || [];
    list.push(item);
    byTrader.set(slug, list);
  }
  const ordered = traders.map((row) => row.slug);
  const extra = [...byTrader.keys()].filter((slug) => !ordered.includes(slug));
  extra.sort((a, b) => {
    const left = byTrader.get(a)?.[0]?.trader_name || a;
    const right = byTrader.get(b)?.[0]?.trader_name || b;
    return left.localeCompare(right, "zh-CN");
  });
  return [...ordered, ...extra]
    .filter((slug) => byTrader.has(slug))
    .map((slug) => {
      const all = byTrader.get(slug) || [];
      const named = traders.find((row) => row.slug === slug);
      const map = (filter.map || "").trim();
      const visible = all
        .filter((item) => taskMatchesQuery(item, q))
        .filter((item) => !map || taskHitsMap(item, map))
        .sort((a, b) =>
          (a.name || a.id).localeCompare(b.name || b.id, "zh-CN"),
        );
      const counts = summarizeTaskProgress(all, done);
      return {
        traderSlug: slug,
        traderName: named?.name || all[0]?.trader_name || slug,
        done: counts.completed,
        total: counts.total,
        items: visible,
      };
    })
    .filter((group) => group.items.length);
}

export function parseTaskDonesState(
  raw: string | null | undefined,
  mode: TarkovGameMode,
): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as Partial<TarkovTaskDonesState> | string[];
    if (Array.isArray(parsed)) return mode === "pvp" ? asIdList(parsed) : [];
    if (parsed && parsed.v === 1) return asIdList(parsed[mode]);
  } catch {
    /* ignore */
  }
  return [];
}

export function parseTaskStartedState(
  raw: string | null | undefined,
  mode: TarkovGameMode,
): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as Partial<TarkovTaskDonesState> | string[];
    if (Array.isArray(parsed) || !parsed || parsed.v !== 1) return [];
    return asIdList(parsed.started?.[mode]);
  } catch {
    /* ignore */
  }
  return [];
}

export function parseTaskFailedState(
  raw: string | null | undefined,
  mode: TarkovGameMode,
): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as Partial<TarkovTaskDonesState> | string[];
    if (Array.isArray(parsed) || !parsed || parsed.v !== 1) return [];
    return asIdList(parsed.failed?.[mode]);
  } catch {
    return [];
  }
}

export function loadTaskDoneIds(mode: TarkovGameMode): string[] {
  try {
    return parseTaskDonesState(
      localStorage.getItem(TARKOV_TASK_DONES_STORAGE_KEY),
      mode,
    );
  } catch {
    return [];
  }
}

export function loadTaskStartedIds(mode: TarkovGameMode): string[] {
  try {
    return parseTaskStartedState(
      localStorage.getItem(TARKOV_TASK_DONES_STORAGE_KEY),
      mode,
    );
  } catch {
    return [];
  }
}

export function loadTaskFailedIds(mode: TarkovGameMode): string[] {
  try {
    return parseTaskFailedState(
      localStorage.getItem(TARKOV_TASK_DONES_STORAGE_KEY),
      mode,
    );
  } catch {
    return [];
  }
}

function readState(): TarkovTaskDonesState {
  try {
    return parseTaskDonesStateRaw(
      localStorage.getItem(TARKOV_TASK_DONES_STORAGE_KEY),
    );
  } catch {
    return { v: 1 };
  }
}

export function parseTaskDonesStateRaw(
  raw: string | null | undefined,
): TarkovTaskDonesState {
  try {
    if (!raw) return { v: 1 };
    const parsed = JSON.parse(raw) as Partial<TarkovTaskDonesState> | string[];
    if (Array.isArray(parsed)) return { v: 1, pvp: asIdList(parsed) };
    if (parsed && parsed.v === 1) {
      return {
        v: 1,
        pvp: asIdList(parsed.pvp),
        pve: asIdList(parsed.pve),
        started: {
          pvp: asIdList(parsed.started?.pvp),
          pve: asIdList(parsed.started?.pve),
        },
        failed: {
          pvp: asIdList(parsed.failed?.pvp),
          pve: asIdList(parsed.failed?.pve),
        },
        migrated: parsed.migrated,
        startedMigrated: parsed.startedMigrated,
        syncedAt: asClockMap(parsed.syncedAt),
        cursorAt: asClockMap(parsed.cursorAt),
        objectives: {
          pvp: asObjectivePairs(parsed.objectives?.pvp),
          pve: asObjectivePairs(parsed.objectives?.pve),
        },
        clearedDone: {
          pvp: asStampMap(parsed.clearedDone?.pvp),
          pve: asStampMap(parsed.clearedDone?.pve),
        },
        questProfileId: {
          pvp: asProfileId(parsed.questProfileId?.pvp),
          pve: asProfileId(parsed.questProfileId?.pve),
        },
        questProfileResetPending: {
          pvp: Boolean(parsed.questProfileResetPending?.pvp),
          pve: Boolean(parsed.questProfileResetPending?.pve),
        },
        questSyncFromLatest: {
          pvp: Boolean(parsed.questSyncFromLatest?.pvp),
          pve: Boolean(parsed.questSyncFromLatest?.pve),
        },
        questClearedAt: asClockMap(parsed.questClearedAt),
        questProgressFloor: asClockMap(parsed.questProgressFloor),
        questServerEpoch: asEpochMap(parsed.questServerEpoch),
      };
    }
  } catch {
    /* ignore */
  }
  return { v: 1 };
}

function writeState(state: TarkovTaskDonesState): void {
  try {
    localStorage.setItem(TARKOV_TASK_DONES_STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* ignore quota / private mode */
  }
}

/**
 * 访客暂存的任务账并进当前账号的本机账：只取完成 / 进行中 / 失败 / 小步骤的并集。
 * 访客的「已清空」、转生待替换和日志游标不带过来，免得导入反过来删掉账号上的进度。
 */
export function mergeGuestTaskProgress(
  current: TarkovTaskDonesState,
  guest: TarkovTaskDonesState,
  skipModes: ReadonlySet<TarkovGameMode> = new Set(),
): TarkovTaskDonesState {
  const next: TarkovTaskDonesState = { ...current };
  for (const mode of ["pvp", "pve"] as const) {
    // 账号这个模式清空 / 转生重置过：访客账没有时间可比，并进来可能正是清空前的旧任务；交给下次日志同步按边界重放
    if (skipModes.has(mode)) continue;
    const merged = unionTaskProgress(
      {
        done: asIdList(current[mode]),
        started: asIdList(current.started?.[mode]),
        failed: asIdList(current.failed?.[mode]),
      },
      {
        done: asIdList(guest[mode]),
        started: asIdList(guest.started?.[mode]),
        failed: asIdList(guest.failed?.[mode]),
      },
    );
    next[mode] = merged.done;
    next.started = { ...next.started, [mode]: merged.started };
    next.failed = { ...next.failed, [mode]: merged.failed };
    next.objectives = {
      ...next.objectives,
      [mode]: unionObjectivePairs(
        asObjectivePairs(current.objectives?.[mode]),
        asObjectivePairs(guest.objectives?.[mode]),
      ),
    };
  }
  return next;
}

export function importGuestTaskProgress(
  raw: string | null | undefined,
  skipModes: ReadonlySet<TarkovGameMode> = new Set(),
): void {
  if (!raw) return;
  writeState(mergeGuestTaskProgress(readState(), parseTaskDonesStateRaw(raw), skipModes));
}

export function saveTaskDoneIds(
  mode: TarkovGameMode,
  ids: string[],
  migrated = false,
): void {
  const state = readState();
  state[mode] = asIdList(ids);
  if (migrated) {
    state.migrated = { ...state.migrated, [mode]: true };
  }
  writeState(state);
}

export function loadTaskObjectivePairs(mode: TarkovGameMode): TaskObjectivePair[] {
  return asObjectivePairs(readState().objectives?.[mode]);
}

export function saveTaskObjectivePairs(
  mode: TarkovGameMode,
  pairs: readonly TaskObjectivePair[],
): void {
  const state = readState();
  state.objectives = {
    ...state.objectives,
    [mode]: asObjectivePairs(pairs),
  };
  writeState(state);
}

export function saveTaskProgress(
  mode: TarkovGameMode,
  doneIds: string[],
  startedIds: string[],
  migrated = false,
  startedMigrated = false,
  objectives?: readonly TaskObjectivePair[],
  failedIds?: readonly string[],
): void {
  const state = readState();
  const cleaned = cleanTaskProgress(
    doneIds,
    startedIds,
    failedIds !== undefined ? failedIds : state.failed?.[mode] || [],
  );
  const prevDone = new Set(asIdList(state[mode]));
  const nextDone = new Set(cleaned.done);
  const modeCleared = { ...(state.clearedDone?.[mode] || {}) };
  const stamp = nowBeijingStamp();
  for (const id of prevDone) {
    if (!nextDone.has(id)) modeCleared[id] = stamp;
  }
  for (const id of nextDone) {
    delete modeCleared[id];
  }
  state[mode] = cleaned.done;
  state.started = { ...state.started, [mode]: cleaned.started };
  state.failed = { ...state.failed, [mode]: cleaned.failed };
  state.clearedDone = { ...state.clearedDone, [mode]: modeCleared };
  if (migrated) {
    state.migrated = { ...state.migrated, [mode]: true };
  }
  if (startedMigrated) {
    state.startedMigrated = { ...state.startedMigrated, [mode]: true };
  }
  if (objectives !== undefined) {
    state.objectives = {
      ...state.objectives,
      [mode]: asObjectivePairs(objectives),
    };
  }
  writeState(state);
}

export function cleanTaskProgress(
  doneIds: readonly string[],
  startedIds: readonly string[],
  failedIds: readonly string[] = [],
): { done: string[]; started: string[]; failed: string[] } {
  const done = asIdList(doneIds);
  const doneSet = new Set(done);
  const failed = asIdList(failedIds).filter((id) => !doneSet.has(id));
  const failedSet = new Set(failed);
  const started = asIdList(startedIds).filter(
    (id) => !doneSet.has(id) && !failedSet.has(id),
  );
  return { done, started, failed };
}

export function taskProgressQueryData(
  doneIds: readonly string[],
  startedIds: readonly string[],
  objectives?: readonly TaskObjectivePair[],
  failedIds: readonly string[] = [],
): {
  task_ids: string[];
  started_ids: string[];
  failed_ids: string[];
  objective_dones: TaskObjectivePair[];
} {
  const cleaned = cleanTaskProgress(doneIds, startedIds, failedIds);
  return {
    task_ids: cleaned.done,
    started_ids: cleaned.started,
    failed_ids: cleaned.failed,
    objective_dones: asObjectivePairs(objectives),
  };
}

type TaskDonesCacheFields = {
  cleared?: ReadonlyArray<{ task_id?: string | null; cleared_at?: string | null }> | null;
  reset_at?: string | null;
  pending_clear_at?: string | null;
  reset_profile_id?: string | null;
  reset_epoch?: number | null;
};

/**
 * 进度写回查询缓存时只盖完成 / 进行中 / 失败 / 小步骤。
 * 取消记录和回放边界留在原缓存上；账号回包带了 cleared 时用回包换掉。
 */
export function overlayTaskProgressCache<T>(
  prev: T,
  progress: {
    task_ids: string[];
    started_ids: string[];
    failed_ids: string[];
    objective_dones: TaskObjectivePair[];
  },
  server?: TaskDonesCacheFields | null,
): Record<string, unknown> {
  const base: Record<string, unknown> =
    prev && typeof prev === "object" ? { ...(prev as Record<string, unknown>) } : {};
  const next: Record<string, unknown> = { ...base, ...progress };
  if (server && Array.isArray(server.cleared)) {
    next.cleared = server.cleared;
    next.reset_at = server.reset_at ?? null;
    next.pending_clear_at = server.pending_clear_at ?? null;
    next.reset_profile_id = server.reset_profile_id ?? "";
    if (typeof server.reset_epoch === "number") next.reset_epoch = server.reset_epoch;
  }
  return next;
}

/** 进度账是冗余 id；目录里没有的（overlay disabled 等）只隐藏。catalog 空则原样。 */
export function keepCatalogTaskProgress(
  doneIds: readonly string[],
  startedIds: readonly string[],
  catalogIds?: ReadonlySet<string> | readonly string[] | null,
  failedIds: readonly string[] = [],
): { done: string[]; started: string[]; failed: string[] } {
  if (catalogIds == null) {
    return cleanTaskProgress(doneIds, startedIds, failedIds);
  }
  const catalog =
    catalogIds instanceof Set
      ? new Set([...catalogIds].map((id) => id.trim().toLowerCase()).filter(Boolean))
      : new Set(asIdList(catalogIds));
  if (!catalog.size) {
    return cleanTaskProgress(doneIds, startedIds, failedIds);
  }
  return cleanTaskProgress(
    asIdList(doneIds).filter((id) => catalog.has(id)),
    asIdList(startedIds).filter((id) => catalog.has(id)),
    asIdList(failedIds).filter((id) => catalog.has(id)),
  );
}

export function loadTaskClearedDone(mode: TarkovGameMode): Map<string, string> {
  return new Map(Object.entries(readState().clearedDone?.[mode] || {}));
}

/**
 * 按下限重放时仍要认的手动取消：晚于下限的取消挡住下限之后、取消之前的那次完成；
 * 不晚于下限的已被下限覆盖。下限为空（不重置）时原样全认。
 */
export function clearedDoneAfter(
  cleared: ReadonlyMap<string, string>,
  floor: string,
): Map<string, string> {
  const at = asClock(floor);
  if (!at) return new Map(cleared);
  const out = new Map<string, string>();
  for (const [id, stamp] of cleared) {
    if (compareBeijingClock(stamp, at) > 0) out.set(id, stamp);
  }
  return out;
}

/**
 * 日志回放要认的取消记录。
 * wipeAt 是记下的清空时刻，整表打上的那一笔不算逐条手动取消。
 * server 为 null：缓存里没有账号取消列表，只用本机，不按「同一秒出现两次」猜测。
 * server 有列表：以账号为准。本机多出来、且同一个时刻出现在两个以上任务上的，是旧版清空留下的，丢掉。
 * 账号上同一秒取消的两个任务仍保留。
 */
export function clearedMarksForReplay(
  local: ReadonlyMap<string, string>,
  server: ReadonlyMap<string, string> | null,
  wipeAt = "",
): Map<string, string> {
  const stamp = asClock(wipeAt);
  const out = new Map<string, string>();
  const put = (id: string, at: string) => {
    if (!id || !at || (stamp && at === stamp)) return;
    out.set(id, laterBeijingClock(out.get(id) || "", at));
  };
  if (server == null) {
    for (const [id, at] of local) put(id, at);
    return out;
  }
  for (const [id, at] of server) put(id, at);
  const localOnly: Array<[string, string]> = [];
  for (const [id, at] of local) {
    if (!id || !at || (stamp && at === stamp)) continue;
    if (server.has(id)) {
      put(id, at);
      continue;
    }
    localOnly.push([id, at]);
  }
  const counts = new Map<string, number>();
  for (const [, at] of localOnly) counts.set(at, (counts.get(at) || 0) + 1);
  for (const [id, at] of localOnly) {
    if ((counts.get(at) || 0) >= 2) continue;
    put(id, at);
  }
  return out;
}

export function loadQuestProfileId(mode: TarkovGameMode): string {
  return asProfileId(readState().questProfileId?.[mode]);
}

export function saveQuestProfileId(mode: TarkovGameMode, profileId: string): void {
  const id = asProfileId(profileId);
  if (!id) return;
  const state = readState();
  state.questProfileId = { ...state.questProfileId, [mode]: id };
  writeState(state);
}

export function loadQuestProfileResetPending(mode: TarkovGameMode): boolean {
  return Boolean(readState().questProfileResetPending?.[mode]);
}

export function loadQuestSyncFromLatest(mode: TarkovGameMode): boolean {
  return Boolean(readState().questSyncFromLatest?.[mode]);
}

export function loadQuestProgressFloor(mode: TarkovGameMode): string {
  return asClock(readState().questProgressFloor?.[mode]);
}

/** 本机缓存的回放下限只增不减：更早的时刻会把清空 / 转生之前的旧任务放回来。 */
/** 取消转生归档：本机下限清掉，之后同步可以再读更早的日志。 */
export function clearQuestProgressFloor(mode: TarkovGameMode): void {
  const state = readState();
  if (!state.questProgressFloor?.[mode]) return;
  state.questProgressFloor = { ...state.questProgressFloor, [mode]: "" };
  writeState(state);
}

export function saveQuestProgressFloor(mode: TarkovGameMode, at: string): void {
  const stamp = asClock(at);
  if (!stamp) return;
  const state = readState();
  const current = asClock(state.questProgressFloor?.[mode]);
  if (current && compareBeijingClock(current, stamp) >= 0) return;
  state.questProgressFloor = { ...state.questProgressFloor, [mode]: stamp };
  writeState(state);
}

/** 账号读到的边界写进本机缓存：下限只往后挪。账号记过边界（epoch>0）时，待同步的清空也以账号为准。 */
export function adoptQuestBoundary(
  mode: TarkovGameMode,
  boundary: {
    resetAt: string;
    pendingClearAt: string;
    profileId: string;
    epoch: number;
  },
): void {
  const state = readState();
  let changed = false;
  const resetAt = asClock(boundary.resetAt);
  const current = asClock(state.questProgressFloor?.[mode]);
  if (resetAt && (!current || compareBeijingClock(current, resetAt) < 0)) {
    state.questProgressFloor = { ...state.questProgressFloor, [mode]: resetAt };
    changed = true;
  }
  const profileId = asProfileId(boundary.profileId);
  if (profileId && asProfileId(state.questProfileId?.[mode]) !== profileId) {
    state.questProfileId = { ...state.questProfileId, [mode]: profileId };
    changed = true;
  }
  if (boundary.epoch > 0) {
    const pendingAt = asClock(boundary.pendingClearAt);
    if (Boolean(state.questSyncFromLatest?.[mode]) !== Boolean(pendingAt)) {
      state.questSyncFromLatest = { ...state.questSyncFromLatest, [mode]: Boolean(pendingAt) };
      changed = true;
    }
    if (asClock(state.questClearedAt?.[mode]) !== pendingAt) {
      state.questClearedAt = { ...state.questClearedAt, [mode]: pendingAt };
      changed = true;
    }
  }
  if (changed) writeState(state);
}

/** 本机任务账基于账号的哪个 reset_epoch；undefined = 还没和账号对过（新浏览器 / 登出后 / 升级前）。 */
export function loadQuestServerEpoch(mode: TarkovGameMode): number | undefined {
  return readState().questServerEpoch?.[mode];
}

/**
 * 本标签页内存里那份进度（面板 state）基于的 reset_epoch。批量写入带的是它，不是 localStorage 里的：
 * 别的标签页清空后 localStorage 已是新 epoch，这个页还拿着清空前的账，必须被服务端 409 拦下。
 */
const tabQuestEpochs = new Map<TarkovGameMode, number>();

export function loadTabQuestEpoch(mode: TarkovGameMode): number | undefined {
  return tabQuestEpochs.get(mode);
}

export function saveQuestServerEpoch(mode: TarkovGameMode, epoch: number): void {
  if (!Number.isInteger(epoch) || epoch < 0) return;
  tabQuestEpochs.set(mode, epoch);
  const state = readState();
  if (state.questServerEpoch?.[mode] === epoch) return;
  state.questServerEpoch = { ...state.questServerEpoch, [mode]: epoch };
  writeState(state);
}

/** 别的标签页改了本机账、并已对齐到新的 epoch：本页内存进度随之换成 localStorage 那份。 */
export function followStoredQuestEpoch(mode: TarkovGameMode): boolean {
  const stored = loadQuestServerEpoch(mode);
  if (stored === undefined || tabQuestEpochs.get(mode) === stored) return false;
  tabQuestEpochs.set(mode, stored);
  return true;
}

/** 测试用：模拟换标签页。 */
export function resetTabQuestEpochsForTests(): void {
  tabQuestEpochs.clear();
}

/**
 * 本机账已过期：账号在别处清空 / 转生重置过（reset_epoch 对不上），或本机从没和账号对过而账号已有边界。
 * 账号 epoch 为 0（从没清空过）时本机账照常与账号并集。
 */
export function questLedgerIsStale(
  localEpoch: number | undefined,
  serverEpoch: number,
): boolean {
  if (serverEpoch <= 0) return localEpoch !== undefined && localEpoch !== serverEpoch;
  return localEpoch !== serverEpoch;
}

/**
 * 以账号为准整份替换本模式本机账（别处清空 / 重置过）。取消标记也只留账号上的。
 */
export function adoptServerTaskLedger(
  mode: TarkovGameMode,
  data: {
    done: readonly string[];
    started: readonly string[];
    failed: readonly string[];
    objectives: readonly TaskObjectivePair[];
    cleared: ReadonlyMap<string, string>;
    boundary: { resetAt: string; pendingClearAt: string; profileId: string; epoch: number };
  },
): void {
  const state = readState();
  const cleaned = cleanTaskProgress(data.done, data.started, data.failed);
  const modeCleared: Record<string, string> = {};
  for (const [id, at] of data.cleared) {
    if (!id || !at) continue;
    modeCleared[id] = at;
  }
  for (const id of cleaned.done) delete modeCleared[id];
  state[mode] = cleaned.done;
  state.started = { ...state.started, [mode]: cleaned.started };
  state.failed = { ...state.failed, [mode]: cleaned.failed };
  state.objectives = { ...state.objectives, [mode]: asObjectivePairs(data.objectives) };
  state.clearedDone = { ...state.clearedDone, [mode]: modeCleared };
  state.questProfileResetPending = { ...state.questProfileResetPending, [mode]: false };
  state.questServerEpoch = { ...state.questServerEpoch, [mode]: data.boundary.epoch };
  tabQuestEpochs.set(mode, data.boundary.epoch);
  state.migrated = { ...state.migrated, [mode]: true };
  state.startedMigrated = { ...state.startedMigrated, [mode]: true };
  writeState(state);
  adoptQuestBoundary(mode, data.boundary);
  bumpQuestLedgerEpoch();
}

/** 批量写入被账号 409 拒掉（本机账过期）时广播；账号同步钩子收到后重新拉账号并替换本机账。 */
export const TARKOV_TASK_LEDGER_STALE_EVENT = "zhange-tarkov-task-ledger-stale";

export function notifyTaskLedgerStale(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(TARKOV_TASK_LEDGER_STALE_EVENT));
}

export function clearQuestSyncFromLatest(mode: TarkovGameMode): void {
  const state = readState();
  if (!state.questSyncFromLatest?.[mode]) return;
  state.questSyncFromLatest = {
    ...state.questSyncFromLatest,
    [mode]: false,
  };
  writeState(state);
}

/** 去掉这些任务的「已清空」标记，让随后的日志重放能重新记上。 */
export function releaseClearedTasks(
  mode: TarkovGameMode,
  ids: readonly string[],
): void {
  const state = readState();
  const modeCleared = { ...(state.clearedDone?.[mode] || {}) };
  let changed = false;
  for (const raw of ids) {
    const id = raw.trim().toLowerCase();
    if (!id || !(id in modeCleared)) continue;
    delete modeCleared[id];
    changed = true;
  }
  if (!changed) return;
  state.clearedDone = { ...state.clearedDone, [mode]: modeCleared };
  writeState(state);
}

/**
 * 清空当前模式的任务账，并记下待同步的清空。
 * 完成、进行中、失败、小步骤和逐条取消标记都清掉，避免这些取消时间挡住之后的日志回放。
 * 下限由随后的同步定。本机回放下限不在这里设：登录时以账号为准。
 */
export function clearTaskProgressForResync(mode: TarkovGameMode): void {
  const state = readState();
  const stamp = nowBeijingStamp();
  state[mode] = [];
  state.started = { ...state.started, [mode]: [] };
  state.failed = { ...state.failed, [mode]: [] };
  state.objectives = { ...state.objectives, [mode]: [] };
  state.clearedDone = { ...state.clearedDone, [mode]: {} };
  state.questSyncFromLatest = { ...state.questSyncFromLatest, [mode]: true };
  state.questClearedAt = { ...state.questClearedAt, [mode]: stamp };
  state.questProfileResetPending = {
    ...state.questProfileResetPending,
    [mode]: true,
  };
  writeState(state);
  bumpQuestLedgerEpoch();
}

/** 本机未提交的清空时刻（访客 / 离线时用；登录时以账号的 pending_clear_at 为准）。 */
export function loadQuestClearedAt(mode: TarkovGameMode): string {
  return asClock(readState().questClearedAt?.[mode]);
}

/**
 * 本机缓存的回放边界（访客用；登录时与账号合并，见 combineQuestBoundary）。
 * 升级前点过清空的本机账只有 questSyncFromLatest + questProgressFloor，把下限当作清空时刻。
 */
export function loadLocalQuestBoundary(mode: TarkovGameMode): {
  resetAt: string;
  pendingClearAt: string;
  profileId: string;
  epoch: number;
} {
  const state = readState();
  const resetAt = asClock(state.questProgressFloor?.[mode]);
  const pending = state.questSyncFromLatest?.[mode]
    ? asClock(state.questClearedAt?.[mode]) || resetAt || nowBeijingStamp()
    : "";
  return {
    resetAt,
    pendingClearAt: pending,
    profileId: asProfileId(state.questProfileId?.[mode]),
    epoch: 0,
  };
}

/**
 * 一次带日志的回放整表替换了本模式进度：写入结果，推进本机下限，撤掉待同步的清空。
 * 保留 clearedDone 里结果没用到的标记（下限之后才勾掉的那些仍要挡住）。
 */
export function applyQuestReplayReset(
  mode: TarkovGameMode,
  input: {
    profileId: string;
    fromAt: string;
    done: readonly string[];
    started: readonly string[];
    failed: readonly string[];
  },
): void {
  const state = readState();
  const cleaned = cleanTaskProgress(input.done, input.started, input.failed);
  const kept = new Set([...cleaned.done, ...cleaned.started, ...cleaned.failed]);
  const modeCleared = { ...(state.clearedDone?.[mode] || {}) };
  const floor = asClock(input.fromAt);
  for (const [id, at] of Object.entries(modeCleared)) {
    if (kept.has(id) || (floor && compareBeijingClock(at, floor) <= 0)) {
      delete modeCleared[id];
    }
  }
  state[mode] = cleaned.done;
  state.started = { ...state.started, [mode]: cleaned.started };
  state.failed = { ...state.failed, [mode]: cleaned.failed };
  state.objectives = { ...state.objectives, [mode]: [] };
  state.clearedDone = { ...state.clearedDone, [mode]: modeCleared };
  const profileId = asProfileId(input.profileId);
  if (profileId) state.questProfileId = { ...state.questProfileId, [mode]: profileId };
  const current = asClock(state.questProgressFloor?.[mode]);
  if (floor && (!current || compareBeijingClock(current, floor) < 0)) {
    state.questProgressFloor = { ...state.questProgressFloor, [mode]: floor };
  }
  state.questSyncFromLatest = { ...state.questSyncFromLatest, [mode]: false };
  state.questClearedAt = { ...state.questClearedAt, [mode]: "" };
  state.questProfileResetPending = {
    ...state.questProfileResetPending,
    [mode]: true,
  };
  state.migrated = { ...state.migrated, [mode]: true };
  state.startedMigrated = { ...state.startedMigrated, [mode]: true };
  writeState(state);
  bumpQuestLedgerEpoch();
}

export function clearQuestProfileResetPending(mode: TarkovGameMode): void {
  const state = readState();
  if (!state.questProfileResetPending?.[mode]) return;
  state.questProfileResetPending = {
    ...state.questProfileResetPending,
    [mode]: false,
  };
  writeState(state);
}

/** 换成另一个选中角色：清掉本模式任务账，并用新角色出现的时刻挡住更早的完成日志。不是转生。 */
export function resetTaskProgressForProfile(
  mode: TarkovGameMode,
  profileId: string,
  clearedAt: string,
): void {
  const id = asProfileId(profileId);
  if (!id) return;
  const state = readState();
  const stamp = asClock(clearedAt) || nowBeijingStamp();
  const modeCleared = { ...(state.clearedDone?.[mode] || {}) };
  const wiped = new Set<string>([
    ...asIdList(state[mode]),
    ...asIdList(state.started?.[mode]),
    ...asIdList(state.failed?.[mode]),
  ]);
  for (const taskId of wiped) {
    const existing = modeCleared[taskId] || "";
    modeCleared[taskId] =
      existing && compareBeijingClock(existing, stamp) > 0 ? existing : stamp;
  }
  state[mode] = [];
  state.started = { ...state.started, [mode]: [] };
  state.failed = { ...state.failed, [mode]: [] };
  state.objectives = { ...state.objectives, [mode]: [] };
  state.clearedDone = { ...state.clearedDone, [mode]: modeCleared };
  state.questProfileId = { ...state.questProfileId, [mode]: id };
  const current = asClock(state.questProgressFloor?.[mode]);
  if (!current || compareBeijingClock(current, stamp) < 0) {
    state.questProgressFloor = { ...state.questProgressFloor, [mode]: stamp };
  }
  state.questProfileResetPending = {
    ...state.questProfileResetPending,
    [mode]: true,
  };
  state.migrated = { ...state.migrated, [mode]: true };
  state.startedMigrated = { ...state.startedMigrated, [mode]: true };
  writeState(state);
  bumpQuestLedgerEpoch();
}

/** merge PUT 只加不删；这些 id 要从账号账上 DELETE 掉，手改未完成才能站住。 */
export function ledgerIdsToClear(
  prev: {
    done?: readonly string[];
    started?: readonly string[];
    failed?: readonly string[];
  },
  next: {
    done?: readonly string[];
    started?: readonly string[];
    failed?: readonly string[];
  },
): string[] {
  const nextDone = new Set(asIdList(next.done));
  const nextStarted = new Set(asIdList(next.started));
  const nextFailed = new Set(asIdList(next.failed));
  const seen = new Set<string>();
  const out: string[] = [];
  const push = (id: string) => {
    if (!id || seen.has(id)) return;
    seen.add(id);
    out.push(id);
  };
  for (const id of asIdList(prev.done)) {
    if (!nextDone.has(id)) push(id);
  }
  for (const id of asIdList(prev.started)) {
    if (!nextDone.has(id) && !nextStarted.has(id) && !nextFailed.has(id)) {
      push(id);
    }
  }
  for (const id of asIdList(prev.failed)) {
    if (!nextDone.has(id) && !nextStarted.has(id) && !nextFailed.has(id)) {
      push(id);
    }
  }
  return out;
}

export function unionTaskProgress(
  left: {
    done?: readonly string[];
    started?: readonly string[];
    failed?: readonly string[];
  },
  right: {
    done?: readonly string[];
    started?: readonly string[];
    failed?: readonly string[];
  },
): { done: string[]; started: string[]; failed: string[] } {
  return cleanTaskProgress(
    [...(left.done || []), ...(right.done || [])],
    [...(left.started || []), ...(right.started || [])],
    [...(left.failed || []), ...(right.failed || [])],
  );
}

export function planAccountTaskHydrate(input: {
  serverDone: readonly string[];
  serverStarted: readonly string[];
  serverFailed?: readonly string[] | null;
  serverObjectives?: readonly TaskObjectivePair[] | null;
  localDone?: readonly string[] | null;
  localStarted?: readonly string[] | null;
  localFailed?: readonly string[] | null;
  localObjectives?: readonly TaskObjectivePair[] | null;
  clearedDone?: ReadonlyMap<string, string> | null;
  mutexById?: ReadonlyMap<string, readonly string[]> | null;
  /** 转生已清本机账：不要把账号上的旧完成 / 进行中 / 步骤并回来。 */
  authoritativeLocal?: boolean;
}): AccountTaskHydratePlan {
  const local = {
    done: input.localDone || [],
    started: input.localStarted || [],
    failed: input.localFailed || [],
  };
  const merged = input.authoritativeLocal
    ? cleanTaskProgress(local.done, local.started, local.failed)
    : unionTaskProgress(
        {
          done: input.serverDone,
          started: input.serverStarted,
          failed: input.serverFailed || [],
        },
        local,
      );
  const cleared = input.clearedDone;
  const localDone = new Set(asIdList(input.localDone));
  const localStarted = new Set(asIdList(input.localStarted));
  const localFailed = new Set(asIdList(input.localFailed));
  const done = cleared
    ? merged.done.filter((id) => !cleared.has(id))
    : merged.done;
  const cleaned = input.mutexById?.size
    ? applyMutexLedger(
        done,
        merged.started,
        merged.failed,
        input.mutexById,
      )
    : cleanTaskProgress(done, merged.started, merged.failed);
  const started = cleared
    ? cleaned.started.filter((id) => !cleared.has(id) || localStarted.has(id))
    : cleaned.started;
  const failed = cleared
    ? cleaned.failed.filter((id) => !cleared.has(id) || localFailed.has(id))
    : cleaned.failed;
  const objectiveRows = input.authoritativeLocal
    ? asObjectivePairs(input.localObjectives)
    : unionObjectivePairs(
        asObjectivePairs(input.serverObjectives),
        asObjectivePairs(input.localObjectives),
      );
  const objectives = cleared
    ? objectiveRows.filter((pair) => {
        const id = pair.task_id.trim().toLowerCase();
        if (!cleared.has(id)) return true;
        return localDone.has(id) || localStarted.has(id);
      })
    : objectiveRows;
  const server = taskProgressQueryData(
    input.serverDone,
    input.serverStarted,
    input.serverObjectives || [],
    input.serverFailed || [],
  );
  return {
    done: cleaned.done,
    started,
    failed,
    objectives,
    upload:
      !sameIdLists(cleaned.done, server.task_ids) ||
      !sameIdLists(cleaned.started, server.started_ids) ||
      !sameIdLists(cleaned.failed, server.failed_ids) ||
      !sameObjectiveLists(objectives, server.objective_dones),
  };
}

export function resolveAccountTaskProgress(
  data: AccountTaskProgress | null | undefined,
  mode: TarkovGameMode,
  mutexById?: ReadonlyMap<string, readonly string[]> | null,
): {
  done: string[];
  started: string[];
  failed: string[];
  objectives: TaskObjectivePair[];
} {
  if (!data) {
    const local = {
      done: loadTaskDoneIds(mode),
      started: loadTaskStartedIds(mode),
      failed: loadTaskFailedIds(mode),
    };
    const next = mutexById?.size
      ? applyMutexLedger(local.done, local.started, local.failed, mutexById)
      : local;
    return {
      ...next,
      objectives: loadTaskObjectivePairs(mode),
    };
  }
  const plan = planAccountTaskHydrate({
    serverDone: data.task_ids || [],
    serverStarted: data.started_ids || [],
    serverFailed: data.failed_ids || [],
    serverObjectives: data.objective_dones || [],
    localDone: loadTaskDoneIds(mode),
    localStarted: loadTaskStartedIds(mode),
    localFailed: loadTaskFailedIds(mode),
    localObjectives: loadTaskObjectivePairs(mode),
    clearedDone: loadTaskClearedDone(mode),
    mutexById,
    authoritativeLocal: loadQuestProfileResetPending(mode),
  });
  return {
    done: plan.done,
    started: plan.started,
    failed: plan.failed,
    objectives: plan.objectives,
  };
}

export function loadTaskSyncAt(mode: TarkovGameMode): string {
  return asClock(readState().syncedAt?.[mode]);
}

export function loadTaskCursorAt(mode: TarkovGameMode): string {
  return asClock(readState().cursorAt?.[mode]);
}

export function saveTaskSyncMark(
  mode: TarkovGameMode,
  syncedAt: string,
  cursorAt?: string,
): { syncedAt: string; cursorAt: string } {
  const state = readState();
  const stamped = asClock(syncedAt);
  const existing = asClock(state.cursorAt?.[mode]);
  const incoming = asClock(cursorAt);
  const nextCursor = incoming ? laterBeijingClock(existing, incoming) : existing;
  state.syncedAt = { ...state.syncedAt, [mode]: stamped };
  if (nextCursor) {
    state.cursorAt = { ...state.cursorAt, [mode]: nextCursor };
  }
  writeState(state);
  return { syncedAt: stamped, cursorAt: nextCursor };
}

export {
  displayTaskProgressName,
  factionTaskSuffix,
  taskLineHintSuffix,
} from "@/lib/tarkovTaskName";
