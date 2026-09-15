/** 同步日志断点：版本 + ProfileId + Session mode，对齐 TarkovMonitor Read Past Logs。 */

import { compareBeijingClock } from "@/lib/time";
import type { TarkovGameMode } from "@/lib/tarkovGameMode";
import {
  classifyLogSessionMode,
  sessionModeLabel,
  type TarkovLogIdentity,
  type TarkovLogSessionStub,
} from "@/lib/tarkovGameLogs";

export type TarkovLogBreakpoint = {
  version: string;
  profileId: string;
  accountId: string;
  sessionMode: string;
  at: string;
  folder: string;
};

export function breakpointKey(row: {
  version: string;
  profileId: string;
  sessionMode: string;
}): string {
  const mode = classifyLogSessionMode(row.sessionMode) || row.sessionMode;
  return `${row.version}|${row.profileId}|${mode}`;
}

export function collectLogBreakpoints(
  identities: readonly TarkovLogIdentity[],
): TarkovLogBreakpoint[] {
  const first = new Map<string, TarkovLogBreakpoint>();
  const ordered = [...identities].sort((a, b) =>
    compareBeijingClock(a.at || "", b.at || ""),
  );
  for (const row of ordered) {
    const profileId = (row.profileId || "").trim();
    const sessionMode = (row.sessionMode || "").trim();
    if (!profileId || !classifyLogSessionMode(sessionMode)) continue;
    const item: TarkovLogBreakpoint = {
      version: (row.version || "").trim(),
      profileId,
      accountId: (row.accountId || "").trim(),
      sessionMode,
      at: row.at || "",
      folder: row.folder || "",
    };
    const key = breakpointKey(item);
    if (!first.has(key)) first.set(key, item);
  }
  return [...first.values()].sort((a, b) =>
    compareBeijingClock(a.at, b.at),
  );
}

export function breakpointMatchesGameMode(
  breakpoint: Pick<TarkovLogBreakpoint, "sessionMode"> | null | undefined,
  gameMode: TarkovGameMode,
): boolean {
  if (!breakpoint) return false;
  const kind = classifyLogSessionMode(breakpoint.sessionMode);
  if (kind === "pve") return gameMode === "pve";
  if (kind === "pvp") return gameMode === "pvp";
  return false;
}

export function defaultLogBreakpoint(
  breakpoints: readonly TarkovLogBreakpoint[],
  opts: {
    gameMode: TarkovGameMode;
    wipeFrom?: string;
    latest?: TarkovLogIdentity | null;
  },
): TarkovLogBreakpoint | null {
  const matching = breakpoints.filter((row) =>
    breakpointMatchesGameMode(row, opts.gameMode),
  );
  if (!matching.length) return null;
  const wipeFrom = (opts.wipeFrom || "").trim();
  const inWipe = wipeFrom
    ? matching.filter((row) => compareBeijingClock(row.at, wipeFrom) >= 0)
    : matching;
  const pool = inWipe.length ? inWipe : matching;
  const latest = opts.latest;
  const profileId = (latest?.profileId || "").trim();
  const latestMode = classifyLogSessionMode(latest?.sessionMode);
  const forProfile = profileId
    ? pool.filter((row) => {
        if (row.profileId !== profileId) return false;
        if (!latestMode) return true;
        return classifyLogSessionMode(row.sessionMode) === latestMode;
      })
    : pool;
  const chosen = forProfile.length ? forProfile : pool;
  return chosen[0] || null;
}

export function latestIdentityForMode(
  identities: readonly TarkovLogIdentity[],
  gameMode: TarkovGameMode,
): TarkovLogIdentity | null {
  let found: TarkovLogIdentity | null = null;
  for (const row of identities) {
    if (!row.profileId) continue;
    if (!breakpointMatchesGameMode(row, gameMode)) continue;
    if (!found || compareBeijingClock(row.at, found.at) >= 0) found = row;
  }
  return found;
}

export function sessionStubMatchesBreakpoint(
  stub: TarkovLogSessionStub,
  breakpoint: Pick<TarkovLogBreakpoint, "profileId" | "sessionMode" | "at"> | null | undefined,
): boolean {
  if (!breakpoint) return true;
  const rows = stub.identities || [];
  if (!rows.length) return true;
  const wantMode = classifyLogSessionMode(breakpoint.sessionMode);
  return rows.some((row) => {
    if (row.profileId !== breakpoint.profileId) return false;
    if (classifyLogSessionMode(row.sessionMode) !== wantMode) return false;
    return compareBeijingClock(row.at || stub.startedAt || "", breakpoint.at) >= 0;
  });
}

export function formatLogBreakpointLabel(row: TarkovLogBreakpoint): string {
  const version = row.version || "未知版本";
  const mode = sessionModeLabel(row.sessionMode) || row.sessionMode;
  const profile = row.profileId.length > 10
    ? `${row.profileId.slice(0, 8)}…`
    : row.profileId;
  const at = (row.at || "").replace(/\.\d+$/, "") || "—";
  return `${version} · ${mode} · ${profile} · ${at}`;
}
