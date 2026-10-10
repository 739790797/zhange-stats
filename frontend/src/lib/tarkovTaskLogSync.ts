/** 从 notifications.log 的任务事件回放进度。 */

import type { TarkovGameMode } from "@/lib/tarkovGameMode";
import type {
  TarkovLogIdentity,
  TarkovLogParseResult,
  TarkovLogQuestDrop,
  TarkovLogQuestEvent,
  TarkovLogQuestKind,
} from "@/lib/tarkovGameLogs";
import { classifyLogSessionMode } from "@/lib/tarkovGameLogs";
import {
  breakpointMatchesGameMode,
  latestIdentityForMode,
} from "@/lib/tarkovLogBreakpoints";
import { compareBeijingClock, formatBeijing, laterBeijingClock } from "@/lib/time";
import { applyMutexLedger } from "@/lib/tarkovTaskMutex";
import {
  dropBlockedProgress,
  taskLineIndexFromTasks,
} from "@/lib/tarkovTaskLineLedger";
import { displayTaskProgressName } from "@/lib/tarkovTaskName";
import {
  resolveTaskStatus,
  TASK_STATUS_LABELS,
  type TaskStatusKind,
} from "@/lib/tarkovTaskTree";

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
  blockedById: ReadonlyMap<string, readonly string[]>;
};

export function emptyQuestLogCatalog(): QuestLogCatalog {
  return {
    restartableIds: new Set(),
    mutexById: new Map(),
    prereqById: new Map(),
    blockedById: new Map(),
  };
}

export function buildQuestLogCatalog(
  items: ReadonlyArray<{
    id?: string | null;
    restartable?: boolean | null;
    mutex_ids?: readonly string[] | null;
    prereq_ids?: readonly string[] | null;
    blocked_by?: readonly string[] | null;
  }>,
): QuestLogCatalog {
  const knownIds = new Set<string>();
  const restartableIds = new Set<string>();
  const line = taskLineIndexFromTasks(items);
  for (const item of items) {
    const id = normalizeQuestId(String(item.id || ""));
    if (!id) continue;
    knownIds.add(id);
    if (item.restartable) restartableIds.add(id);
  }
  return {
    knownIds,
    restartableIds,
    mutexById: line.mutexById,
    prereqById: line.prereqById,
    blockedById: line.blockedById,
  };
}

export type QuestProfileResetPlan = {
  profileId: string;
  /** 该角色第一次出现的北京墙钟。更早的完成日志不再写回。 */
  at: string;
  reset: boolean;
};

function earliestProfileAt(
  identities: readonly TarkovLogIdentity[],
  gameMode: TarkovGameMode,
  profileId: string,
): string {
  let at = "";
  for (const row of identities) {
    if ((row.profileId || "").trim() !== profileId) continue;
    if (!breakpointMatchesGameMode(row, gameMode)) continue;
    const clock = (row.at || "").trim();
    if (!at || compareBeijingClock(clock, at) < 0) at = clock;
  }
  return at;
}

/**
 * 转生会换 ProfileId。正在回放的如果是该模式最新角色，且和账上记的不是同一个，
 * 先清空再重放。回放更早的角色、或日志里只有这一个角色时保持合并。
 */
export function questProfileResetPlan(input: {
  gameMode: TarkovGameMode;
  storedProfileId?: string;
  identities: readonly TarkovLogIdentity[];
  replayProfileId?: string;
}): QuestProfileResetPlan | null {
  const latestId = (
    latestIdentityForMode(input.identities, input.gameMode)?.profileId || ""
  ).trim();
  const replayId = (input.replayProfileId || latestId).trim();
  if (!replayId) return null;
  const seenReplay = input.identities.some((row) => {
    if ((row.profileId || "").trim() !== replayId) return false;
    return breakpointMatchesGameMode(row, input.gameMode);
  });
  if (!seenReplay) return null;
  const at = earliestProfileAt(input.identities, input.gameMode, replayId);
  if (latestId && replayId !== latestId) {
    return { profileId: replayId, at, reset: false };
  }
  const stored = (input.storedProfileId || "").trim();
  if (stored === replayId) return { profileId: replayId, at, reset: false };
  if (stored) return { profileId: replayId, at, reset: true };
  const older = input.identities.some((row) => {
    if (!breakpointMatchesGameMode(row, input.gameMode)) return false;
    const id = (row.profileId || "").trim();
    return Boolean(id) && id !== replayId;
  });
  return { profileId: replayId, at, reset: older };
}

/** 清空进度后的同步：忽略所选旧断点，定位当前模式最新 ProfileId。 */
export function planLatestProfileReplay(
  identities: readonly TarkovLogIdentity[],
  gameMode: TarkovGameMode,
): { profileId: string; at: string } | null {
  const profileId = (
    latestIdentityForMode(identities, gameMode)?.profileId || ""
  ).trim();
  if (!profileId) return null;
  return {
    profileId,
    at: earliestProfileAt(identities, gameMode, profileId),
  };
}

export type ClearedQuestReplayPlan = {
  profileId: string;
  fromAt: string;
  /** 日志里已经换成另一个 ProfileId，从该角色第一次出现整段重放。 */
  freshProfile: boolean;
};

/**
 * 清空后再同步。
 * ProfileId 变了：从新角色第一次出现重放，转生前的日志不写回。
 * ProfileId 没变（转生常常不换 id）：从清空时刻起，更早的完成日志不写回。
 */
export function planClearedQuestReplay(input: {
  gameMode: TarkovGameMode;
  identities: readonly TarkovLogIdentity[];
  storedProfileId?: string;
  clearedAt?: string;
}): ClearedQuestReplayPlan | null {
  const latest = planLatestProfileReplay(input.identities, input.gameMode);
  if (!latest?.profileId) return null;
  const decision = questProfileResetPlan({
    gameMode: input.gameMode,
    storedProfileId: input.storedProfileId,
    identities: input.identities,
    replayProfileId: latest.profileId,
  });
  const freshProfile = Boolean(decision?.reset);
  const clearedAt = (input.clearedAt || "").trim();
  if (freshProfile || !clearedAt) {
    return {
      profileId: latest.profileId,
      fromAt: decision?.at || latest.at,
      freshProfile,
    };
  }
  return {
    profileId: latest.profileId,
    fromAt: laterBeijingClock(latest.at, clearedAt),
    freshProfile: false,
  };
}

export function clampQuestReplayFromAt(
  fromAt: string | undefined,
  floor: string | undefined,
): string {
  return laterBeijingClock((fromAt || "").trim(), (floor || "").trim());
}

function isBeforeReplayFloor(at: string, fromAt: string): boolean {
  const floor = fromAt.trim();
  if (!floor) return false;
  const clock = (at || "").trim();
  if (!clock) return true;
  return compareBeijingClock(clock, floor) < 0;
}

export function sessionModeMatchesGameMode(
  sessionMode: string | undefined,
  gameMode: TarkovGameMode,
): boolean {
  const kind = classifyLogSessionMode(sessionMode);
  if (kind === "pve") return gameMode === "pve";
  if (kind === "pvp") return gameMode === "pvp";
  return false;
}

export type QuestReplayFilter = {
  gameMode: TarkovGameMode;
  profileId?: string;
  fromAt?: string;
};

export function questReplayDropReason(
  quest: TarkovLogQuestEvent,
  parsed: Pick<TarkovLogParseResult, "sessionMode">,
  filter: QuestReplayFilter,
): TarkovLogQuestDrop["reason"] | null {
  const mode = quest.sessionMode || parsed.sessionMode;
  const kind = classifyLogSessionMode(mode);
  if (!kind) return "no_session_mode";
  if (kind === "unknown") return "unknown_mode";
  if (kind === "seasonal") return "seasonal";
  if (!sessionModeMatchesGameMode(mode, filter.gameMode)) return null;
  const wantProfile = (filter.profileId || "").trim();
  if (wantProfile && (quest.profileId || "").trim() !== wantProfile) {
    return "profile";
  }
  return null;
}

export function questsMatchingReplay(
  parsed: Pick<TarkovLogParseResult, "sessionMode" | "quests">,
  filter: QuestReplayFilter,
): TarkovLogQuestEvent[] {
  const fromAt = (filter.fromAt || "").trim();
  const out: TarkovLogQuestEvent[] = [];
  for (const quest of parsed.quests || []) {
    if (isBeforeReplayFloor(quest.at || "", fromAt)) continue;
    if (questReplayDropReason(quest, parsed, filter)) continue;
    const mode = quest.sessionMode || parsed.sessionMode;
    if (!sessionModeMatchesGameMode(mode, filter.gameMode)) continue;
    out.push(quest);
  }
  return out;
}

export function collectQuestReplayDrops(
  parsed: Pick<TarkovLogParseResult, "sessionMode" | "quests" | "drops">,
  filter: QuestReplayFilter,
): TarkovLogQuestDrop[] {
  const fromAt = (filter.fromAt || "").trim();
  const out: TarkovLogQuestDrop[] = [];
  for (const drop of parsed.drops || []) {
    if (isBeforeReplayFloor(drop.at || "", fromAt)) continue;
    out.push(drop);
  }
  for (const quest of parsed.quests || []) {
    if (isBeforeReplayFloor(quest.at || "", fromAt)) continue;
    const reason = questReplayDropReason(quest, parsed, filter);
    if (!reason) continue;
    out.push({
      at: quest.at || "",
      reason,
      line: quest.line,
      sessionMode: quest.sessionMode || parsed.sessionMode,
      profileId: quest.profileId,
    });
  }
  return out;
}

const DROP_REASON_LABEL: Record<TarkovLogQuestDrop["reason"], string> = {
  json_bad: "JSON 坏块",
  no_session_mode: "无 Session mode",
  unknown_mode: "未知模式",
  seasonal: "赛季",
  profile: "其他角色",
};

export function formatQuestLogDropHint(
  drops: readonly TarkovLogQuestDrop[],
): string {
  if (!drops.length) return "";
  const counts = new Map<TarkovLogQuestDrop["reason"], number>();
  for (const drop of drops) {
    counts.set(drop.reason, (counts.get(drop.reason) || 0) + 1);
  }
  const bits = [...counts.entries()]
    .filter(([, n]) => n > 0)
    .map(([reason, n]) => `${DROP_REASON_LABEL[reason]} ${n}`);
  return `丢弃 ${drops.length} 条：${bits.join("，")}`;
}

export type FoldedQuestEntry = {
  kind: QuestLogState;
  at: string;
  everCompleted: boolean;
  /** 最后一次 completed 事件时间；互斥组里后完成的留下。 */
  completedAt?: string;
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

function shouldHonorClearedDone(
  id: string,
  logAt: string,
  clearedDone?: ReadonlyMap<string, string>,
): boolean {
  const clearedAt = clearedDone?.get(id) || "";
  if (!clearedAt) return false;
  if (!logAt.trim()) return true;
  return compareBeijingClock(clearedAt, logAt) >= 0;
}

function markDone(
  id: string,
  nextDone: Set<string>,
  nextStarted: Set<string>,
  nextFailed: Set<string>,
  catalog: QuestLogCatalog | undefined,
  walking: Set<string>,
  clearedDone?: ReadonlyMap<string, string>,
  logAt = "",
): void {
  if (!id || walking.has(id)) return;
  if (shouldHonorClearedDone(id, logAt, clearedDone)) return;
  walking.add(id);
  nextDone.add(id);
  nextStarted.delete(id);
  nextFailed.delete(id);
  for (const other of catalog?.mutexById.get(id) || []) {
    if (!other) continue;
    if (shouldHonorClearedDone(other, logAt, clearedDone)) continue;
    nextDone.delete(other);
    nextFailed.add(other);
    nextStarted.delete(other);
  }
  if (walking.size > PREREQ_WALK_MAX) return;
  for (const prereq of catalog?.prereqById.get(id) || []) {
    if (!prereq || nextDone.has(prereq)) continue;
    markDone(
      prereq,
      nextDone,
      nextStarted,
      nextFailed,
      catalog,
      walking,
      clearedDone,
      logAt,
    );
  }
}

export function applyQuestLogState(
  doneIds: Iterable<string>,
  startedIds: Iterable<string>,
  logState: ReadonlyMap<string, QuestLogState | FoldedQuestEntry>,
  knownIds?: ReadonlySet<string> | QuestLogCatalog,
  failedIds: Iterable<string> = [],
  clearedDone?: ReadonlyMap<string, string>,
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
      const completedAt = logCompletedAt(folded);
      if (shouldHonorClearedDone(taskId, completedAt, clearedDone)) {
        nextDone.delete(taskId);
        if (folded.kind === "completed") {
          walking.clear();
          continue;
        }
      } else {
        markDone(
          taskId,
          nextDone,
          nextStarted,
          nextFailed,
          catalog,
          walking,
          clearedDone,
          completedAt || folded.at,
        );
        walking.clear();
        continue;
      }
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
  if (clearedDone) {
    for (const [id, at] of clearedDone) {
      if (!id) continue;
      const folded = logState.get(id);
      const eventAt =
        folded == null || typeof folded === "string" ? "" : folded.at || "";
      const completionAt =
        folded == null
          ? ""
          : logCompletedAt(typeof folded === "string" ? folded : folded);
      const ever =
        typeof folded === "object"
          ? Boolean(folded.everCompleted) || folded.kind === "completed"
          : folded === "completed";
      const clearWins = shouldHonorClearedDone(
        id,
        completionAt || eventAt,
        new Map([[id, at]]),
      );
      if (nextDone.has(id) && (!ever || clearWins)) nextDone.delete(id);
      if (clearWins && shouldHonorClearedDone(id, eventAt, new Map([[id, at]]))) {
        nextStarted.delete(id);
        nextFailed.delete(id);
      }
    }
  }
  for (const id of nextFailed) nextStarted.delete(id);
  const raw = {
    done: [...nextDone],
    started: [...nextStarted],
    failed: [...nextFailed],
  };
  let next = raw;
  if (catalog?.mutexById.size) {
    const ranked: Array<{ id: string; at: string }> = [];
    for (const [rawId, rawState] of logState) {
      const taskId = normalizeQuestId(rawId);
      if (!taskId || !logEverCompleted(rawState)) continue;
      ranked.push({ id: taskId, at: logCompletedAt(rawState) });
    }
    ranked.sort((a, b) => {
      const cmp = (a.at || "").localeCompare(b.at || "");
      return cmp !== 0 ? cmp : a.id.localeCompare(b.id);
    });
    next = applyMutexLedger(
      raw.done,
      raw.started,
      raw.failed,
      catalog.mutexById,
      ranked.map((row) => row.id),
    );
  }
  if (catalog?.blockedById.size) {
    next = dropBlockedProgress(
      next.done,
      next.started,
      next.failed,
      catalog.blockedById,
    );
  }
  return next;
}

function logEverCompleted(raw: QuestLogState | FoldedQuestEntry): boolean {
  if (typeof raw === "string") return raw === "completed";
  return Boolean(raw.everCompleted) || raw.kind === "completed";
}

function logCompletedAt(raw: QuestLogState | FoldedQuestEntry): string {
  if (typeof raw === "string") return "";
  if (!logEverCompleted(raw)) return "";
  if (raw.completedAt) return raw.completedAt;
  if (raw.kind === "completed") return raw.at || "";
  return "";
}

export function collectQuestEventsFromSessions(
  sessions: Array<{ parsed: TarkovLogParseResult }>,
  gameModeOrFilter: TarkovGameMode | QuestReplayFilter,
): TarkovLogQuestEvent[] {
  const filter =
    typeof gameModeOrFilter === "string"
      ? { gameMode: gameModeOrFilter }
      : gameModeOrFilter;
  const out: TarkovLogQuestEvent[] = [];
  for (const session of sessions) {
    out.push(...questsMatchingReplay(session.parsed, filter));
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
  clearedDone?: ReadonlyMap<string, string>,
): { done: string[]; started: string[]; failed: string[] } {
  return applyQuestLogState(
    doneIds,
    startedIds,
    foldQuestEvents(new Map(), events),
    catalog,
    failedIds,
    clearedDone,
  );
}

export function mergeQuestProgressFromLogs(
  doneIds: Iterable<string>,
  startedIds: Iterable<string>,
  sessions: Array<{ parsed: TarkovLogParseResult }>,
  gameModeOrFilter: TarkovGameMode | QuestReplayFilter,
  catalog?: QuestLogCatalog | ReadonlySet<string>,
  failedIds: Iterable<string> = [],
  clearedDone?: ReadonlyMap<string, string>,
): QuestLogMergeResult {
  const events = collectQuestEventsFromSessions(sessions, gameModeOrFilter);
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
    clearedDone,
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
        next.set(id, {
          ...existing,
          everCompleted: true,
          completedAt: laterBeijingClock(existing.completedAt || "", at),
        });
      }
      continue;
    }
    const everCompleted =
      event.kind === "completed" || Boolean(existing?.everCompleted);
    const completedAt =
      event.kind === "completed"
        ? laterBeijingClock(existing?.completedAt || "", at)
        : existing?.completedAt;
    next.set(id, { kind: event.kind, at, everCompleted, completedAt });
  }
  return next;
}

export function foldSessionQuests(
  prev: ReadonlyMap<string, FoldedQuestEntry>,
  parsed: Pick<TarkovLogParseResult, "sessionMode" | "quests">,
  gameModeOrFilter: TarkovGameMode | QuestReplayFilter,
): { next: Map<string, FoldedQuestEntry>; eventCount: number } {
  const filter =
    typeof gameModeOrFilter === "string"
      ? { gameMode: gameModeOrFilter }
      : gameModeOrFilter;
  const events = questsMatchingReplay(parsed, filter);
  if (!events.length) {
    return { next: new Map(prev), eventCount: 0 };
  }
  return { next: foldQuestEvents(prev, events), eventCount: events.length };
}

export function mergeQuestProgressFromFolded(
  doneIds: Iterable<string>,
  startedIds: Iterable<string>,
  folded: ReadonlyMap<string, FoldedQuestEntry>,
  eventCount: number,
  catalog?: QuestLogCatalog | ReadonlySet<string>,
  failedIds: Iterable<string> = [],
  clearedDone?: ReadonlyMap<string, string>,
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
    clearedDone,
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

export type QuestLogNameItem = {
  id?: string | null;
  name?: string | null;
  faction_name?: string | null;
  line_hint?: string | null;
  mutex_ids?: readonly string[] | null;
  blocked_by?: readonly string[] | null;
};

export type QuestLogSyncReviewRow = {
  at: string;
  line: string;
  taskId: string;
  taskName: string;
  from: TaskStatusKind;
  to: TaskStatusKind;
  change: string;
};

export type QuestLogSyncReview = {
  hint: string;
  rows: QuestLogSyncReviewRow[];
  dropHint?: string;
  drops?: TarkovLogQuestDrop[];
};

export function formatQuestLogEventLine(event: TarkovLogQuestEvent): string {
  const line = (event.line || "").trim();
  if (line) return line;
  const at = (event.at || "").trim();
  const kind = event.kind || "";
  if (at && kind) return `${at} ChatMessageReceived ${kind}`;
  if (at) return at;
  return kind ? `ChatMessageReceived ${kind}` : "";
}

export function formatQuestLogStatusChange(
  from: TaskStatusKind,
  to: TaskStatusKind,
): string {
  return `${TASK_STATUS_LABELS[from]}→${TASK_STATUS_LABELS[to]}`;
}

export function buildQuestLogSyncReview(
  events: readonly TarkovLogQuestEvent[],
  base: {
    done?: readonly string[];
    started?: readonly string[];
    failed?: readonly string[];
  },
  opts?: {
    catalog?: QuestLogCatalog;
    items?: readonly QuestLogNameItem[];
    clearedDone?: ReadonlyMap<string, string>;
  },
): QuestLogSyncReviewRow[] {
  const byId = new Map<string, QuestLogNameItem>();
  for (const item of opts?.items || []) {
    const id = normalizeQuestId(String(item.id || ""));
    if (id) byId.set(id, item);
  }
  const ordered = [...events].sort((a, b) =>
    (a.at || "").localeCompare(b.at || ""),
  );
  let done = [...(base.done || [])];
  let started = [...(base.started || [])];
  let failed = [...(base.failed || [])];
  const rows: QuestLogSyncReviewRow[] = [];
  for (const event of ordered) {
    const taskId = normalizeQuestId(event.taskId);
    if (!taskId) continue;
    const item = byId.get(taskId);
    const from = resolveTaskStatus(
      taskId,
      new Set(done),
      new Set(started),
      item,
      new Set(failed),
    );
    const next = applyQuestLogStateFromEvents(
      done,
      started,
      [event],
      opts?.catalog,
      failed,
      opts?.clearedDone,
    );
    done = next.done;
    started = next.started;
    failed = next.failed;
    const to = resolveTaskStatus(
      taskId,
      new Set(done),
      new Set(started),
      item,
      new Set(failed),
    );
    rows.push({
      at: event.at || "",
      line: formatQuestLogEventLine(event),
      taskId,
      taskName: item
        ? displayTaskProgressName({
            id: taskId,
            name: item.name,
            faction_name: item.faction_name,
            line_hint: item.line_hint,
          })
        : taskId,
      from,
      to,
      change: formatQuestLogStatusChange(from, to),
    });
  }
  return rows;
}
