/** 从 notifications.log 的任务事件回放进度。 */

import type { TarkovGameMode } from "@/lib/tarkovGameMode";
import type {
  TarkovLogParseResult,
  TarkovLogQuestEvent,
  TarkovLogQuestKind,
} from "@/lib/tarkovGameLogs";
import { compareBeijingClock, formatBeijing, laterBeijingClock } from "@/lib/time";

export type QuestLogState = TarkovLogQuestKind;

export function normalizeQuestId(id: string): string {
  return id.trim().toLowerCase();
}

const HEX_QUEST_ID_RE = /^[a-f0-9]{20,32}$/;
const PREREQ_WALK_MAX = 32;

export type QuestLogCatalog = {
  knownIds?: ReadonlySet<string>;
  restartableIds: ReadonlySet<string>;
  mutexById: ReadonlyMap<string, readonly string[]>;
  prereqById: ReadonlyMap<string, readonly string[]>;
};

export function emptyQuestLogCatalog(): QuestLogCatalog {
  return {
    restartableIds: new Set(),
    mutexById: new Map(),
    prereqById: new Map(),
  };
}

export function buildQuestLogCatalog(
  items: ReadonlyArray<{
    id?: string | null;
    restartable?: boolean | null;
    mutex_ids?: readonly string[] | null;
    prereq_ids?: readonly string[] | null;
  }>,
): QuestLogCatalog {
  const knownIds = new Set<string>();
  const restartableIds = new Set<string>();
  const mutexById = new Map<string, string[]>();
  const prereqById = new Map<string, string[]>();
  for (const item of items) {
    const id = normalizeQuestId(String(item.id || ""));
    if (!id) continue;
    knownIds.add(id);
    if (item.restartable) restartableIds.add(id);
    const mutex = [
      ...new Set(
        (item.mutex_ids || []).map((raw) => normalizeQuestId(String(raw || ""))),
      ),
    ].filter(Boolean);
    if (mutex.length) mutexById.set(id, mutex);
    const prereqs = [
      ...new Set(
        (item.prereq_ids || []).map((raw) => normalizeQuestId(String(raw || ""))),
      ),
    ].filter(Boolean);
    if (prereqs.length) prereqById.set(id, prereqs);
  }
  return { knownIds, restartableIds, mutexById, prereqById };
}

export function sessionModeMatchesGameMode(
  sessionMode: string | undefined,
  gameMode: TarkovGameMode,
): boolean {
  const key = (sessionMode || "").trim().toLowerCase();
  if (!key) return true;
  if (key === "pve") return gameMode === "pve";
  if (
    key === "pvp" ||
    key === "regular" ||
    key === "seasonal" ||
    key === "pvp-season" ||
    key === "pvpseason"
  ) {
    return gameMode === "pvp";
  }
  return true;
}

export type FoldedQuestEntry = {
  kind: QuestLogState;
  at: string;
  everCompleted: boolean;
};

function asIdSet(ids: Iterable<string>): Set<string> {
  const out = new Set<string>();
  for (const raw of ids) {
    const id = normalizeQuestId(raw);
    if (id) out.add(id);
  }
  return out;
}

/** 账号已有同等或更强进度时，这条日志不再改状态。 */
export function accountHasQuestState(
  done: ReadonlySet<string>,
  started: ReadonlySet<string>,
  taskId: string,
  state: QuestLogState,
  failed: ReadonlySet<string> = new Set(),
  restartable = false,
): boolean {
  const id = normalizeQuestId(taskId);
  if (!id) return true;
  if (state === "completed") return done.has(id);
  if (done.has(id)) return true;
  if (state === "failed") {
    if (restartable) return started.has(id);
    return failed.has(id);
  }
  if (failed.has(id) && !restartable) return true;
  return started.has(id);
}

function shouldKeepLogQuestId(
  id: string,
  knownIds?: ReadonlySet<string>,
): boolean {
  if (!knownIds) return true;
  if (knownIds.has(id)) return true;
  return HEX_QUEST_ID_RE.test(id);
}

function isRestartable(id: string, catalog?: QuestLogCatalog): boolean {
  return Boolean(catalog?.restartableIds.has(id));
}

function markDone(
  id: string,
  nextDone: Set<string>,
  nextStarted: Set<string>,
  nextFailed: Set<string>,
  catalog: QuestLogCatalog | undefined,
  walking: Set<string>,
): void {
  if (!id || walking.has(id)) return;
  walking.add(id);
  nextDone.add(id);
  nextStarted.delete(id);
  nextFailed.delete(id);
  for (const other of catalog?.mutexById.get(id) || []) {
    if (!other || nextDone.has(other)) continue;
    nextFailed.add(other);
    nextStarted.delete(other);
  }
  if (walking.size > PREREQ_WALK_MAX) return;
  for (const prereq of catalog?.prereqById.get(id) || []) {
    if (!prereq || nextDone.has(prereq)) continue;
    markDone(prereq, nextDone, nextStarted, nextFailed, catalog, walking);
  }
}

export function applyQuestLogState(
  doneIds: Iterable<string>,
  startedIds: Iterable<string>,
  logState: ReadonlyMap<string, QuestLogState | FoldedQuestEntry>,
  knownIds?: ReadonlySet<string> | QuestLogCatalog,
  failedIds: Iterable<string> = [],
): { done: string[]; started: string[]; failed: string[] } {
  const catalog: QuestLogCatalog | undefined =
    knownIds && typeof knownIds === "object" && "mutexById" in knownIds
      ? knownIds
      : knownIds instanceof Set
        ? { ...emptyQuestLogCatalog(), knownIds }
        : undefined;
  const known = catalog?.knownIds
    ? new Set([...catalog.knownIds].map(normalizeQuestId))
    : knownIds instanceof Set
      ? new Set([...knownIds].map(normalizeQuestId))
      : undefined;
  const nextDone = asIdSet(doneIds);
  const nextFailed = asIdSet(failedIds);
  const nextStarted = asIdSet(startedIds);
  for (const id of nextDone) {
    nextStarted.delete(id);
    nextFailed.delete(id);
  }
  for (const id of nextFailed) nextStarted.delete(id);

  const walking = new Set<string>();
  for (const [rawId, rawState] of logState) {
    const taskId = normalizeQuestId(rawId);
    if (!taskId || !shouldKeepLogQuestId(taskId, known)) continue;
    const folded: FoldedQuestEntry =
      typeof rawState === "string"
        ? {
            kind: rawState,
            at: "",
            everCompleted: rawState === "completed",
          }
        : {
            kind: rawState.kind,
            at: rawState.at || "",
            everCompleted: Boolean(rawState.everCompleted) || rawState.kind === "completed",
          };
    const restartable = isRestartable(taskId, catalog);
    if (folded.everCompleted) {
      markDone(taskId, nextDone, nextStarted, nextFailed, catalog, walking);
      walking.clear();
      continue;
    }
    if (
      accountHasQuestState(
        nextDone,
        nextStarted,
        taskId,
        folded.kind,
        nextFailed,
        restartable,
      )
    ) {
      continue;
    }
    if (folded.kind === "failed") {
      if (restartable) {
        nextStarted.add(taskId);
        nextFailed.delete(taskId);
      } else {
        nextFailed.add(taskId);
        nextStarted.delete(taskId);
      }
      continue;
    }
    nextStarted.add(taskId);
    nextFailed.delete(taskId);
  }
  for (const id of nextDone) {
    nextStarted.delete(id);
    nextFailed.delete(id);
  }
  for (const id of nextFailed) nextStarted.delete(id);
  return {
    done: [...nextDone],
    started: [...nextStarted],
    failed: [...nextFailed],
  };
}

export function collectQuestEventsFromSessions(
  sessions: Array<{ parsed: TarkovLogParseResult }>,
  gameMode: TarkovGameMode,
): TarkovLogQuestEvent[] {
  const out: TarkovLogQuestEvent[] = [];
  for (const session of sessions) {
    if (!sessionModeMatchesGameMode(session.parsed.sessionMode, gameMode)) {
      continue;
    }
    out.push(...(session.parsed.quests || []));
  }
  out.sort((a, b) => (a.at || "").localeCompare(b.at || ""));
  return out;
}

export function latestQuestEventAt(
  events: readonly TarkovLogQuestEvent[],
): string {
  let latest = "";
  for (const event of events) {
    latest = laterBeijingClock(latest, event.at || "");
  }
  return latest;
}

export function formatLastQuestSyncLine(
  at: string | null | undefined,
): string {
  return `上次同步时间：${at ? formatBeijing(at) : "—"}`;
}

export type QuestProgressDelta = {
  done: number;
  started: number;
  failed?: number;
  unfinished: number;
};

export function questProgressDelta(
  prevDone: readonly string[],
  prevStarted: readonly string[],
  nextDone: readonly string[],
  nextStarted: readonly string[],
  prevFailed: readonly string[] = [],
  nextFailed: readonly string[] = [],
): QuestProgressDelta {
  const done = nextDone.length - prevDone.length;
  const started = nextStarted.length - prevStarted.length;
  const failed = nextFailed.length - prevFailed.length;
  return { done, started, failed, unfinished: -(done + started + failed) || 0 };
}

export function formatSignedDelta(n: number): string {
  return n > 0 ? `+${n}` : `${n}`;
}

export function formatQuestSyncDeltaLine(
  kind: "incremental" | "backfill",
  delta: QuestProgressDelta,
): string {
  const prefix = kind === "incremental" ? "已增量同步" : "已从日志回填";
  return (
    `${prefix} 已完成 ${formatSignedDelta(delta.done)}，` +
    `进行中 ${formatSignedDelta(delta.started)}，` +
    `失败 ${formatSignedDelta(delta.failed ?? 0)}，` +
    `未完成 ${formatSignedDelta(delta.unfinished)}`
  );
}

export type QuestLogMergeResult = {
  done: string[];
  started: string[];
  failed: string[];
  eventCount: number;
  latestEventAt: string;
};

export function replayQuestEvents(
  events: readonly TarkovLogQuestEvent[],
): Map<string, FoldedQuestEntry> {
  return foldQuestEvents(new Map(), events);
}

export function applyQuestLogStateFromEvents(
  doneIds: Iterable<string>,
  startedIds: Iterable<string>,
  events: readonly TarkovLogQuestEvent[],
  catalog?: QuestLogCatalog,
  failedIds: Iterable<string> = [],
): { done: string[]; started: string[]; failed: string[] } {
  return applyQuestLogState(
    doneIds,
    startedIds,
    foldQuestEvents(new Map(), events),
    catalog,
    failedIds,
  );
}

export function mergeQuestProgressFromLogs(
  doneIds: Iterable<string>,
  startedIds: Iterable<string>,
  sessions: Array<{ parsed: TarkovLogParseResult }>,
  gameMode: TarkovGameMode,
  catalog?: QuestLogCatalog | ReadonlySet<string>,
  failedIds: Iterable<string> = [],
): QuestLogMergeResult {
  const events = collectQuestEventsFromSessions(sessions, gameMode);
  const rules =
    catalog && typeof catalog === "object" && "mutexById" in catalog
      ? catalog
      : catalog instanceof Set
        ? { ...emptyQuestLogCatalog(), knownIds: catalog }
        : undefined;
  const applied = applyQuestLogState(
    doneIds,
    startedIds,
    foldQuestEvents(new Map(), events),
    rules,
    failedIds,
  );
  return {
    ...applied,
    eventCount: events.length,
    latestEventAt: latestQuestEventAt(events),
  };
}

/** 按事件时间折任务状态；后到的覆盖先到的，已完成粘住。 */
export function foldQuestEvents(
  prev: ReadonlyMap<string, FoldedQuestEntry>,
  events: readonly TarkovLogQuestEvent[],
): Map<string, FoldedQuestEntry> {
  const next = new Map(prev);
  const ordered = [...events].sort((a, b) =>
    (a.at || "").localeCompare(b.at || ""),
  );
  for (const event of ordered) {
    const id = normalizeQuestId(event.taskId);
    if (!id) continue;
    const at = event.at || "";
    const existing = next.get(id);
    if (existing && compareBeijingClock(existing.at, at) > 0) {
      if (event.kind === "completed") {
        next.set(id, { ...existing, everCompleted: true });
      }
      continue;
    }
    const everCompleted =
      event.kind === "completed" || Boolean(existing?.everCompleted);
    next.set(id, { kind: event.kind, at, everCompleted });
  }
  return next;
}

export function foldSessionQuests(
  prev: ReadonlyMap<string, FoldedQuestEntry>,
  parsed: Pick<TarkovLogParseResult, "sessionMode" | "quests">,
  gameMode: TarkovGameMode,
): { next: Map<string, FoldedQuestEntry>; eventCount: number } {
  if (!sessionModeMatchesGameMode(parsed.sessionMode, gameMode)) {
    return { next: new Map(prev), eventCount: 0 };
  }
  const events = parsed.quests || [];
  return { next: foldQuestEvents(prev, events), eventCount: events.length };
}

export function questStateFromFolded(
  folded: ReadonlyMap<string, FoldedQuestEntry>,
): Map<string, FoldedQuestEntry> {
  return new Map(folded);
}

export function mergeQuestProgressFromFolded(
  doneIds: Iterable<string>,
  startedIds: Iterable<string>,
  folded: ReadonlyMap<string, FoldedQuestEntry>,
  eventCount: number,
  catalog?: QuestLogCatalog | ReadonlySet<string>,
  failedIds: Iterable<string> = [],
): QuestLogMergeResult {
  const rules =
    catalog && typeof catalog === "object" && "mutexById" in catalog
      ? catalog
      : catalog instanceof Set
        ? { ...emptyQuestLogCatalog(), knownIds: catalog }
        : undefined;
  const applied = applyQuestLogState(
    doneIds,
    startedIds,
    folded,
    rules,
    failedIds,
  );
  let latestEventAt = "";
  for (const row of folded.values()) {
    latestEventAt = laterBeijingClock(latestEventAt, row.at || "");
  }
  return {
    ...applied,
    eventCount,
    latestEventAt,
  };
}
