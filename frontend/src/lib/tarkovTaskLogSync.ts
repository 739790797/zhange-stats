/** 从 notifications.log 的任务事件回放进度。 */

import type { TarkovGameMode } from "@/lib/tarkovGameMode";
import type {
  TarkovLogParseResult,
  TarkovLogQuestEvent,
  TarkovLogQuestKind,
  TarkovLogSessionStub,
} from "@/lib/tarkovGameLogs";
import {
  compareBeijingClock,
  formatBeijing,
  laterBeijingClock,
} from "@/lib/time";

export type QuestLogState = TarkovLogQuestKind;

export function sessionModeMatchesGameMode(
  sessionMode: string | undefined,
  gameMode: TarkovGameMode,
): boolean {
  const key = (sessionMode || "").trim().toLowerCase();
  if (!key) return true;
  if (key === "pve") return gameMode === "pve";
  if (key === "pvp" || key === "regular") return gameMode === "pvp";
  return true;
}

export function replayQuestEvents(
  events: readonly TarkovLogQuestEvent[],
): Map<string, QuestLogState> {
  const out = new Map<string, QuestLogState>();
  const ordered = [...events].sort((a, b) =>
    (a.at || "").localeCompare(b.at || ""),
  );
  for (const event of ordered) {
    const id = event.taskId.trim();
    if (!id) continue;
    out.set(id, event.kind);
  }
  return out;
}

export function applyQuestLogState(
  doneIds: Iterable<string>,
  startedIds: Iterable<string>,
  logState: Map<string, QuestLogState>,
  knownIds?: ReadonlySet<string>,
): { done: string[]; started: string[] } {
  const nextDone = new Set(doneIds);
  const nextStarted = new Set(startedIds);
  for (const [id, state] of logState) {
    if (knownIds && !knownIds.has(id)) continue;
    if (state === "completed") {
      nextDone.add(id);
      nextStarted.delete(id);
    } else if (state === "started") {
      nextStarted.add(id);
      nextDone.delete(id);
    } else {
      nextStarted.delete(id);
      nextDone.delete(id);
    }
  }
  return { done: [...nextDone], started: [...nextStarted] };
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

export function filterQuestEventsAfter(
  events: readonly TarkovLogQuestEvent[],
  afterAt: string | null | undefined,
): TarkovLogQuestEvent[] {
  const cursor = (afterAt || "").trim();
  if (!cursor) return [...events];
  return events.filter((event) => {
    const at = (event.at || "").trim();
    return at && compareBeijingClock(at, cursor) > 0;
  });
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

/** 有游标时只读游标之后启动的目录，并始终留下最近两场（当前+上一场）。 */
export function takeQuestSyncSessions(
  stubs: readonly TarkovLogSessionStub[],
  afterAt: string | null | undefined,
  keepNewest = 2,
): TarkovLogSessionStub[] {
  const cursor = (afterAt || "").trim();
  if (!cursor) return [...stubs];
  const keep = new Set(
    stubs.slice(0, Math.max(0, keepNewest)).map((stub) => stub.folder),
  );
  for (const stub of stubs) {
    if (!stub.startedAt || compareBeijingClock(stub.startedAt, cursor) > 0) {
      keep.add(stub.folder);
    }
  }
  return stubs.filter((stub) => keep.has(stub.folder));
}

export function formatLastQuestSyncLine(
  at: string | null | undefined,
): string {
  return `上次同步时间：${at ? formatBeijing(at) : "—"}`;
}

export type QuestProgressDelta = {
  done: number;
  started: number;
  unfinished: number;
};

export function questProgressDelta(
  prevDone: readonly string[],
  prevStarted: readonly string[],
  nextDone: readonly string[],
  nextStarted: readonly string[],
): QuestProgressDelta {
  const done = nextDone.length - prevDone.length;
  const started = nextStarted.length - prevStarted.length;
  return { done, started, unfinished: -(done + started) || 0 };
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
    `未完成 ${formatSignedDelta(delta.unfinished)}`
  );
}

export type QuestLogMergeResult = {
  done: string[];
  started: string[];
  eventCount: number;
  latestEventAt: string;
};

export function mergeQuestProgressFromLogs(
  doneIds: Iterable<string>,
  startedIds: Iterable<string>,
  sessions: Array<{ parsed: TarkovLogParseResult }>,
  gameMode: TarkovGameMode,
  knownIds?: ReadonlySet<string>,
  afterAt?: string | null,
): QuestLogMergeResult {
  const events = filterQuestEventsAfter(
    collectQuestEventsFromSessions(sessions, gameMode),
    afterAt,
  );
  const applied = applyQuestLogState(
    doneIds,
    startedIds,
    replayQuestEvents(events),
    knownIds,
  );
  return {
    ...applied,
    eventCount: events.length,
    latestEventAt: latestQuestEventAt(events),
  };
}
