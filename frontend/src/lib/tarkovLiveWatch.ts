/** 塔科夫本机目录轮询：顶栏时钟、任务回填、截图定位。 */

import type { TarkovGameMode } from "@/lib/tarkovGameMode";
import {
  latestLogActivityAt,
  raidLogEndedKey,
  toRaidLogImportRows,
  type TarkovLogParseResult,
  type TarkovRaidLogImportRow,
} from "@/lib/tarkovGameLogs";
import { mergeQuestProgressFromLogs } from "@/lib/tarkovTaskLogSync";
import { formatBeijing } from "@/lib/time";

export const TARKOV_LIVE_DIRS_EVENT = "zhange-tarkov-live-dirs";
export const TARKOV_TASK_PROGRESS_EVENT = "zhange-tarkov-task-progress";

export type TarkovTaskProgressDetail = {
  mode: TarkovGameMode;
  done: string[];
  started: string[];
  syncedAt?: string;
  changed?: boolean;
  /** 相对上一轮新完成的整任务 id；小步骤日志里没有。 */
  completedIds?: string[];
  /** user 手改；log 日志回放；hydrate 账号对账。日志不得挡住账号增量合并。 */
  source?: "user" | "log" | "hydrate";
};

export type LogPollCursor = {
  folder: string;
  fingerprint: string;
};

export function notifyTarkovLiveDirsChanged() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(TARKOV_LIVE_DIRS_EVENT));
}

export function notifyTarkovTaskProgress(detail: TarkovTaskProgressDetail) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent<TarkovTaskProgressDetail>(TARKOV_TASK_PROGRESS_EVENT, {
      detail,
    }),
  );
}

export function formatPollClock(
  input: number | string | Date | null | undefined,
): string {
  if (input == null || input === "") return "—";
  return formatBeijing(input, "YYYY-MM-DD HH:mm:ss");
}

export function formatLiveWatchShotLine(
  at: number | string | Date | null | undefined,
): string {
  return `最近截图：${formatPollClock(at)}`;
}

export function formatLiveWatchLogLine(
  at: number | string | Date | null | undefined,
): string {
  return `最近日志：${formatPollClock(at)}`;
}

export function sameIdLists(
  left: readonly string[],
  right: readonly string[],
): boolean {
  if (left.length !== right.length) return false;
  const a = [...left].sort();
  const b = [...right].sort();
  return a.every((id, index) => id === b[index]);
}

/** `next` 里多出来的 id，保序。 */
export function addedIdList(
  prev: readonly string[],
  next: readonly string[],
): string[] {
  const have = new Set(prev);
  return next.filter((id) => Boolean(id) && !have.has(id));
}

export function planLogSessionReads(
  newestFolder: string | null,
  newestFingerprint: string,
  prev: LogPollCursor | null,
  allFolders: readonly string[] = [],
): { skip: boolean; folders: string[] } {
  if (!newestFolder) return { skip: true, folders: [] };
  if (!prev) {
    const seen = new Set<string>();
    const folders: string[] = [];
    for (const folder of allFolders) {
      const ident = folder.trim();
      if (!ident || seen.has(ident)) continue;
      seen.add(ident);
      folders.push(ident);
    }
    return {
      skip: false,
      folders: folders.length ? folders : [newestFolder],
    };
  }
  if (prev.folder === newestFolder && prev.fingerprint === newestFingerprint) {
    return { skip: true, folders: [] };
  }
  if (prev.folder !== newestFolder) {
    return { skip: false, folders: [prev.folder, newestFolder] };
  }
  return { skip: false, folders: [newestFolder] };
}

export type LiveQuestProgressPlan = {
  done: string[];
  started: string[];
  changed: boolean;
  eventCount: number;
  latestEventAt: string;
};

export function nextLiveQuestProgress(
  doneIds: readonly string[],
  startedIds: readonly string[],
  sessions: Array<{ parsed: TarkovLogParseResult }>,
  gameMode: TarkovGameMode,
  knownIds?: ReadonlySet<string>,
): LiveQuestProgressPlan {
  const merged = mergeQuestProgressFromLogs(
    doneIds,
    startedIds,
    sessions,
    gameMode,
    knownIds,
  );
  return {
    done: merged.done,
    started: merged.started,
    changed:
      !sameIdLists(doneIds, merged.done) ||
      !sameIdLists(startedIds, merged.started),
    eventCount: merged.eventCount,
    latestEventAt: merged.latestEventAt,
  };
}

export function logStampFromParsed(
  parsed: TarkovLogParseResult | null | undefined,
  fileTimes: readonly number[],
): number | string | null {
  const at = latestLogActivityAt(parsed);
  if (at) return at;
  if (!fileTimes.length) return null;
  return Math.max(...fileTimes);
}

/** UserMatchOver 后本机把战局摘要推到账号；有新的 ended_at 才导入。 */
export function planRaidLogImport(
  prevEndedKeys: ReadonlySet<string>,
  sessions: Array<{ folder: string; parsed: TarkovLogParseResult }>,
): { nextKeys: Set<string>; rows: TarkovRaidLogImportRow[] } {
  const all = toRaidLogImportRows(sessions);
  const ended = all.filter((row) => Boolean(row.ended_at));
  const nextKeys = new Set(ended.map((row) => raidLogEndedKey(row)));
  const hasFresh =
    prevEndedKeys.size > 0 &&
    ended.some((row) => !prevEndedKeys.has(raidLogEndedKey(row)));
  return { nextKeys, rows: hasFresh ? all : [] };
}
