/** 个人中心任务勾选：按商人分组；完成/进行中本机缓存 + 账号进度账。 */

import type { TarkovGameMode } from "@/lib/tarkovGameMode";
import { notifyTarkovTaskProgress, sameIdLists } from "@/lib/tarkovLiveWatch";
import { TARKOV_MAPS } from "@/lib/tarkovHomeNav";
import { laterBeijingClock } from "@/lib/time";
import {
  mapSlugKeys,
  normalizeRaidPrepMapId,
  raidPrepMapOptions,
} from "@/lib/tarkovRaidPrep";

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
  restartable?: boolean;
};

export type TaskLineRef = {
  mutex_ids?: readonly string[] | null;
  blocked_by?: readonly string[] | null;
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
};

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

export function summarizeTaskProgress(
  items: TaskListItem[],
  done: ReadonlySet<string>,
  started: ReadonlySet<string> = new Set(),
  failed: ReadonlySet<string> = new Set(),
): TaskProgressSummary {
  let completed = 0;
  let active = 0;
  let failedCount = 0;
  let unreachable = 0;
  let incomplete = 0;
  for (const item of items) {
    const status = resolveTaskStatus(item.id, done, started, item, failed);
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

export const TASK_WRITABLE_STATUS_KINDS = ["todo", "active", "done"] as const;
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
  return status === "todo" || status === "active" || status === "done";
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
): TaskStatusKind {
  const ident = String(taskId || "").trim().toLowerCase();
  if (ident && done.has(ident)) return "done";
  if (ident && failed.has(ident)) return "failed";
  if (lineIdHits(line?.mutex_ids, done)) return "failed";
  if (lineIdHits(line?.blocked_by, done, started)) return "unreachable";
  if (ident && started.has(ident)) return "active";
  return "todo";
}

export function setTaskStatus(
  doneIds: readonly string[],
  startedIds: readonly string[],
  taskId: string,
  status: TaskWritableStatus,
  failedIds: readonly string[] = [],
): { done: string[]; started: string[]; failed: string[] } {
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
  return { done: [...done], started: [...started], failed: [...failed] };
}

/** 写下拉状态到本机进度，并通知联机大厅 / 个人中心刷新。 */
export function commitTaskStatus(
  mode: TarkovGameMode,
  taskId: string,
  status: TaskWritableStatus,
  fillObjectiveIds?: readonly string[],
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
    const raw = localStorage.getItem(TARKOV_TASK_DONES_STORAGE_KEY);
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

export function saveTaskStartedIds(mode: TarkovGameMode, ids: string[]): void {
  const state = readState();
  state.started = { ...state.started, [mode]: asIdList(ids) };
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
  state[mode] = cleaned.done;
  state.started = { ...state.started, [mode]: cleaned.started };
  state.failed = { ...state.failed, [mode]: cleaned.failed };
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
}): AccountTaskHydratePlan {
  const merged = unionTaskProgress(
    {
      done: input.serverDone,
      started: input.serverStarted,
      failed: input.serverFailed || [],
    },
    {
      done: input.localDone || [],
      started: input.localStarted || [],
      failed: input.localFailed || [],
    },
  );
  const objectives = unionObjectivePairs(
    asObjectivePairs(input.serverObjectives),
    asObjectivePairs(input.localObjectives),
  );
  const server = taskProgressQueryData(
    input.serverDone,
    input.serverStarted,
    input.serverObjectives || [],
    input.serverFailed || [],
  );
  return {
    ...merged,
    objectives,
    upload:
      !sameIdLists(merged.done, server.task_ids) ||
      !sameIdLists(merged.started, server.started_ids) ||
      !sameIdLists(merged.failed, server.failed_ids) ||
      !sameObjectiveLists(objectives, server.objective_dones),
  };
}

export function resolveAccountTaskProgress(
  data: AccountTaskProgress | null | undefined,
  mode: TarkovGameMode,
): {
  done: string[];
  started: string[];
  failed: string[];
  objectives: TaskObjectivePair[];
} {
  if (!data) {
    return {
      done: loadTaskDoneIds(mode),
      started: loadTaskStartedIds(mode),
      failed: loadTaskFailedIds(mode),
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

export function takeLocalTaskDonesForMigrate(
  mode: TarkovGameMode,
): string[] | null {
  try {
    const raw = localStorage.getItem(TARKOV_TASK_DONES_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<TarkovTaskDonesState> | string[];
    if (Array.isArray(parsed)) {
      return mode === "pvp" && parsed.length ? asIdList(parsed) : null;
    }
    if (parsed && parsed.v === 1 && parsed.migrated?.[mode]) return null;
    const ids = parseTaskDonesState(raw, mode);
    return ids.length ? ids : null;
  } catch {
    return null;
  }
}

export function takeLocalTaskStartedForMigrate(
  mode: TarkovGameMode,
): string[] | null {
  try {
    const raw = localStorage.getItem(TARKOV_TASK_DONES_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<TarkovTaskDonesState> | string[];
    if (Array.isArray(parsed) || !parsed || parsed.v !== 1) return null;
    if (parsed.startedMigrated?.[mode]) return null;
    const ids = parseTaskStartedState(raw, mode);
    return ids.length ? ids : null;
  } catch {
    return null;
  }
}

export function markTaskDonesMigrated(mode: TarkovGameMode, ids: string[]): void {
  saveTaskDoneIds(mode, ids, true);
}

export function markTaskStartedMigrated(
  mode: TarkovGameMode,
  ids: string[],
): void {
  saveTaskProgress(mode, loadTaskDoneIds(mode), ids, false, true);
}

export {
  displayTaskProgressName,
  factionTaskSuffix,
  taskLineHintSuffix,
} from "@/lib/tarkovTaskName";
