/** 同步弹窗的日历：按北京日期汇总当前角色的启动，并算出转生归档的回放下限。 */

import type { TarkovGameMode } from "@/features/guides/tarkov/model/tarkovGameMode";
import type {
  TarkovLogIdentity,
  TarkovLogParseResult,
  TarkovLogPreviewRaid,
  TarkovLogSessionStub,
} from "@/features/guides/tarkov/model/tarkovGameLogs";
import { breakpointMatchesGameMode, latestIdentityForMode } from "@/features/guides/tarkov/model/tarkovLogBreakpoints";
import { compareBeijingClock, formatBeijing, parseBeijing } from "@/shared/lib/time";

export type LogSyncCalendarRaid = TarkovLogPreviewRaid;

export type LogSyncCalendarLaunch = {
  folder: string;
  startedAt: string;
  day: string;
  version: string;
  profileId: string;
  sessionMode: string;
  /** 当天内从 1 起。 */
  index: number;
  raids: LogSyncCalendarRaid[];
};

function modeAt(identities: readonly TarkovLogIdentity[], at: string): string {
  let mode = "";
  const clock = at || "";
  for (const row of identities) {
    if ((row.at || "") <= clock) mode = row.sessionMode || mode;
  }
  return mode;
}

/** 预览已经扫过 application.log，把能进列表的战局留下。 */
export function previewRaidsFromParsed(
  parsed: Pick<TarkovLogParseResult, "raids"> | null | undefined,
  identities: readonly TarkovLogIdentity[] = [],
): TarkovLogPreviewRaid[] {
  const out: TarkovLogPreviewRaid[] = [];
  for (const raid of parsed?.raids || []) {
    if (raid.aborted && !raid.startedAt && !raid.raidId) continue;
    if (!raid.startedAt && !raid.mapId && !raid.location && !raid.mapLabel) continue;
    const at = raid.startedAt || raid.endedAt || "";
    out.push({
      key: [raid.raidId || "", raid.startedAt || "", raid.mapId || raid.location || ""].join("|"),
      mapId: raid.mapId || "",
      mapLabel: (raid.mapLabel || "").trim() || "未知地图",
      startedAt: raid.startedAt || "",
      endedAt: raid.endedAt || "",
      raidId: raid.raidId || "",
      sessionMode: modeAt(identities, at),
    });
  }
  return out;
}

function identityForMode(
  identities: readonly TarkovLogIdentity[],
  gameMode: TarkovGameMode,
  profileId: string,
): TarkovLogIdentity | undefined {
  let found: TarkovLogIdentity | undefined;
  for (const row of identities) {
    if ((row.profileId || "").trim() !== profileId) continue;
    if (!breakpointMatchesGameMode(row, gameMode)) continue;
    if (!found || compareBeijingClock(row.at, found.at) >= 0) found = row;
  }
  return found;
}

/** 当前模式、当前角色的启动，按时间排序，并标上当天第几次。 */
export function logSyncCalendarLaunches(
  sessions: readonly TarkovLogSessionStub[],
  gameMode: TarkovGameMode,
): LogSyncCalendarLaunch[] {
  const latest = latestIdentityForMode(
    sessions.flatMap((session) => session.identities || []),
    gameMode,
  );
  const profileId = (latest?.profileId || "").trim();
  if (!profileId) return [];
  const launches: LogSyncCalendarLaunch[] = [];
  for (const session of sessions) {
    const startedAt = (session.startedAt || "").trim();
    if (!startedAt || !parseBeijing(startedAt).isValid()) continue;
    const identities = session.identities || [];
    const ident = identityForMode(identities, gameMode, profileId);
    if (!ident) continue;
    const raids = (session.raids || []).filter((raid) => {
      const mode = raid.sessionMode || ident.sessionMode;
      return breakpointMatchesGameMode({ sessionMode: mode }, gameMode);
    });
    launches.push({
      folder: session.folder,
      startedAt,
      day: formatBeijing(startedAt, "YYYY-MM-DD"),
      version: ident.version || "",
      profileId: ident.profileId,
      sessionMode: ident.sessionMode,
      index: 0,
      raids,
    });
  }
  launches.sort((a, b) => compareBeijingClock(a.startedAt, b.startedAt) || a.folder.localeCompare(b.folder));
  const seen = new Map<string, number>();
  for (const launch of launches) {
    const next = (seen.get(launch.day) || 0) + 1;
    seen.set(launch.day, next);
    launch.index = next;
  }
  return launches;
}

export function launchCountByDay(
  launches: readonly LogSyncCalendarLaunch[],
): Map<string, number> {
  const counts = new Map<string, number>();
  for (const launch of launches) {
    counts.set(launch.day, (counts.get(launch.day) || 0) + 1);
  }
  return counts;
}

/**
 * 该局及之前的日志不写回。有结束时间就从结束的下一秒起；
 * 只有开局时间时用开局的下一秒，并标明这是近似切点。
 */
export function raidArchiveFrom(raid: {
  startedAt?: string;
  endedAt?: string;
}): { at: string; approximate: boolean } | null {
  const ended = (raid.endedAt || "").trim();
  const started = (raid.startedAt || "").trim();
  const basis = ended || started;
  const parsed = parseBeijing(basis);
  if (!basis || !parsed.isValid()) return null;
  return {
    at: parsed.add(1, "second").format("YYYY-MM-DD HH:mm:ss"),
    approximate: !ended,
  };
}

/**
 * 启动是否可能含有下限之后的日志。
 * 下一次启动已经不晚于下限时，这一次整段都在归档之前，不用读。
 * 没有下一次启动、或下一次启动晚于下限时，这一次可能跨过切点，仍要读。
 */
export function launchOverlapsArchive(
  startedAt: string,
  nextStartedAt: string,
  floor: string,
): boolean {
  const cut = (floor || "").trim();
  if (!cut) return true;
  const start = (startedAt || "").trim();
  if (start && compareBeijingClock(start, cut) >= 0) return true;
  const next = (nextStartedAt || "").trim();
  if (!next) return true;
  return compareBeijingClock(next, cut) > 0;
}

export type AccountArchiveAnchor = {
  day: string;
  raidAt: string;
  raidKey: string;
};

/** 账号上的回放下限对应日历里最后一局仍早于该时刻的战局。 */
export function accountArchiveFromFloor(
  launches: readonly LogSyncCalendarLaunch[],
  resetAt: string,
): AccountArchiveAnchor | null {
  const floor = (resetAt || "").trim();
  if (!floor) return null;
  let best: AccountArchiveAnchor & { at: string } | null = null;
  for (const launch of launches) {
    for (const raid of launch.raids) {
      const at = (raid.endedAt || raid.startedAt || "").trim();
      if (!at || compareBeijingClock(at, floor) >= 0) continue;
      if (best && compareBeijingClock(at, best.at) <= 0) continue;
      best = {
        at,
        day: launch.day,
        raidAt: raid.startedAt || launch.startedAt,
        raidKey: `${launch.folder}|${raid.key}`,
      };
    }
  }
  if (!best) return null;
  return { day: best.day, raidAt: best.raidAt, raidKey: best.raidKey };
}

/** 下限只增不减：切点必须晚于账号上已有的 resetAt。 */
export function raidArchiveAllowed(archiveAt: string, resetAt: string): boolean {
  const floor = (resetAt || "").trim();
  const at = (archiveAt || "").trim();
  if (!at) return false;
  if (!floor) return true;
  return compareBeijingClock(floor, at) < 0;
}
