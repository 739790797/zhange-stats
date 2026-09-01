/** 个人中心任务勾选：按商人分组、本机/账号完成态。 */

import type { TarkovGameMode } from "@/lib/tarkovGameMode";
import { notifyTarkovTaskProgress } from "@/lib/tarkovLiveWatch";
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
  trader_slug?: string;
  trader_name?: string;
  min_player_level?: number;
  min_trader_level?: number;
  map_slug?: string;
  map_name?: string;
  lightkeeper_required?: boolean;
  faction_name?: string;
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
};

export type TraderTaskGroup = {
  traderSlug: string;
  traderName: string;
  done: number;
  total: number;
  items: TaskListItem[];
};

export type TarkovTaskDonesState = {
  v: 1;
  pvp?: string[];
  pve?: string[];
  started?: { pvp?: string[]; pve?: string[] };
  migrated?: { pvp?: boolean; pve?: boolean };
  syncedAt?: { pvp?: string; pve?: string };
  cursorAt?: { pvp?: string; pve?: string };
};

function asIdList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (id): id is string => typeof id === "string" && id.trim().length > 0,
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

function taskMatchesQuery(task: TaskListItem, q: string): boolean {
  if (!q) return true;
  const hay = `${task.name} ${task.id}`.toLowerCase();
  return hay.includes(q);
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
): TaskProgressSummary {
  let completed = 0;
  let active = 0;
  for (const item of items) {
    if (done.has(item.id)) completed += 1;
    else if (started.has(item.id)) active += 1;
  }
  return {
    total: items.length,
    incomplete: items.length - completed - active,
    active,
    completed,
  };
}

export const TASK_STATUS_KINDS = ["todo", "active", "done"] as const;
export type TaskStatusKind = (typeof TASK_STATUS_KINDS)[number];

export function resolveTaskStatus(
  taskId: string,
  done: ReadonlySet<string>,
  started: ReadonlySet<string>,
): TaskStatusKind {
  if (done.has(taskId)) return "done";
  if (started.has(taskId)) return "active";
  return "todo";
}

export function setTaskStatus(
  doneIds: readonly string[],
  startedIds: readonly string[],
  taskId: string,
  status: TaskStatusKind,
): { done: string[]; started: string[] } {
  const ident = taskId.trim();
  const done = new Set(doneIds);
  const started = new Set(startedIds.filter((id) => !done.has(id)));
  if (!ident) return { done: [...done], started: [...started] };
  done.delete(ident);
  started.delete(ident);
  if (status === "done") done.add(ident);
  else if (status === "active") started.add(ident);
  return { done: [...done], started: [...started] };
}

/** 写下拉状态到本机进度，并通知联机大厅 / 个人中心刷新。 */
export function commitTaskStatus(
  mode: TarkovGameMode,
  taskId: string,
  status: TaskStatusKind,
): { done: string[]; started: string[] } {
  const next = setTaskStatus(
    loadTaskDoneIds(mode),
    loadTaskStartedIds(mode),
    taskId,
    status,
  );
  saveTaskProgress(mode, next.done, next.started);
  notifyTarkovTaskProgress({
    mode,
    done: next.done,
    started: next.started,
    changed: true,
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
        migrated: parsed.migrated,
        syncedAt: asClockMap(parsed.syncedAt),
        cursorAt: asClockMap(parsed.cursorAt),
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

export function saveTaskProgress(
  mode: TarkovGameMode,
  doneIds: string[],
  startedIds: string[],
  migrated = false,
): void {
  const state = readState();
  state[mode] = asIdList(doneIds);
  state.started = { ...state.started, [mode]: asIdList(startedIds) };
  if (migrated) {
    state.migrated = { ...state.migrated, [mode]: true };
  }
  writeState(state);
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

export function markTaskDonesMigrated(mode: TarkovGameMode, ids: string[]): void {
  saveTaskDoneIds(mode, ids, true);
}

export function factionTaskSuffix(value: string | undefined): string {
  const text = (value || "").trim();
  if (!text || text === "Any") return "";
  return ` (${text})`;
}
