/** 日志回填：按启动文件夹 startedAt 筛日期，默认全部。 */

import type { TarkovLogSessionStub } from "@/lib/tarkovGameLogs";
import { compareBeijingClock, parseBeijing } from "@/lib/time";
import {
  currentWipeStart,
  TARKOV_WIPE_STARTS,
  type TarkovWipeStart,
} from "@/lib/tarkovWipeLength";

export type TarkovLogSyncPreset = "all" | "wipe" | "7d" | "30d" | "custom";

export type TarkovLogSyncRange = {
  /** 北京墙钟，含当日/当时。 */
  from: string;
  to: string;
  /** 全部启动记录，含没有 startedAt 的文件夹。 */
  all?: boolean;
};

export type TarkovLogSyncRangeInput = {
  preset: TarkovLogSyncPreset;
  /** 自定义时用 YYYY-MM-DD（北京日历日）。 */
  customFrom?: string;
  customTo?: string;
};

export type TarkovLogSyncOpts = TarkovLogSyncRange & {
  signal?: AbortSignal;
};

function beijingDayStart(input: Date | string): string {
  return parseBeijing(input).startOf("day").format("YYYY-MM-DD HH:mm:ss");
}

function beijingDayEnd(input: Date | string): string {
  return parseBeijing(input).endOf("day").format("YYYY-MM-DD HH:mm:ss");
}

export function wipeStartBeijingClock(
  wipe: TarkovWipeStart,
): string {
  return parseBeijing(wipe.start).format("YYYY-MM-DD HH:mm:ss");
}

export function defaultLogSyncRange(
  now: Date = new Date(),
  starts?: TarkovWipeStart[],
): TarkovLogSyncRange {
  const table = starts?.length ? starts : TARKOV_WIPE_STARTS;
  const earliest = table[0];
  return {
    all: true,
    from: earliest
      ? wipeStartBeijingClock(earliest)
      : beijingDayStart("2017-01-01"),
    to: beijingDayEnd(now),
  };
}

export function resolveLogSyncRange(
  input: TarkovLogSyncRangeInput,
  now: Date = new Date(),
  starts?: TarkovWipeStart[],
): TarkovLogSyncRange {
  if (input.preset === "all") return defaultLogSyncRange(now, starts);
  if (input.preset === "wipe") {
    const wipe = currentWipeStart(starts, now);
    return {
      from: wipeStartBeijingClock(wipe),
      to: beijingDayEnd(now),
    };
  }
  if (input.preset === "7d") {
    return {
      from: parseBeijing(now)
        .subtract(6, "day")
        .startOf("day")
        .format("YYYY-MM-DD HH:mm:ss"),
      to: beijingDayEnd(now),
    };
  }
  if (input.preset === "30d") {
    return {
      from: parseBeijing(now)
        .subtract(29, "day")
        .startOf("day")
        .format("YYYY-MM-DD HH:mm:ss"),
      to: beijingDayEnd(now),
    };
  }
  const fromDay = (input.customFrom || "").trim();
  const toDay = (input.customTo || "").trim();
  if (!fromDay || !toDay) return defaultLogSyncRange(now, starts);
  if (fromDay > toDay) {
    return { from: beijingDayStart(toDay), to: beijingDayEnd(fromDay) };
  }
  return { from: beijingDayStart(fromDay), to: beijingDayEnd(toDay) };
}

export function sessionStartedAtInRange(
  startedAt: string | null | undefined,
  range: TarkovLogSyncRange,
): boolean {
  if (range.all) return true;
  const at = (startedAt || "").trim();
  if (!at || !parseBeijing(at).isValid()) return false;
  return (
    compareBeijingClock(at, range.from) >= 0 &&
    compareBeijingClock(at, range.to) <= 0
  );
}

export function filterSessionStubsByRange(
  stubs: readonly TarkovLogSessionStub[],
  range: TarkovLogSyncRange,
): TarkovLogSessionStub[] {
  if (range.all) return [...stubs];
  return stubs.filter((stub) => sessionStartedAtInRange(stub.startedAt, range));
}

/** 列目录后的可选最早/最晚启动日（北京 YYYY-MM-DD）。 */
export function sessionStubDateBounds(
  stubs: readonly TarkovLogSessionStub[],
): { min: string | null; max: string | null } {
  let min: string | null = null;
  let max: string | null = null;
  for (const stub of stubs) {
    const at = (stub.startedAt || "").trim();
    if (!at || !parseBeijing(at).isValid()) continue;
    const day = parseBeijing(at).format("YYYY-MM-DD");
    if (!min || day < min) min = day;
    if (!max || day > max) max = day;
  }
  return { min, max };
}

export function wipeAtBeijingClock(
  startedAt: string,
  starts: TarkovWipeStart[] = TARKOV_WIPE_STARTS,
): TarkovWipeStart | null {
  const at = parseBeijing(startedAt);
  if (!at.isValid()) return null;
  const ts = at.valueOf();
  let current: TarkovWipeStart | null = null;
  for (const wipe of starts) {
    if (new Date(wipe.start).getTime() <= ts) current = wipe;
  }
  return current;
}

/** 这些启动记录落在哪些赛季；无名日期不算。 */
export function wipesTouchedBySessions(
  stubs: readonly TarkovLogSessionStub[],
  starts?: TarkovWipeStart[],
): TarkovWipeStart[] {
  const table = starts?.length ? starts : TARKOV_WIPE_STARTS;
  const seen = new Set<string>();
  const out: TarkovWipeStart[] = [];
  for (const stub of stubs) {
    const at = (stub.startedAt || "").trim();
    if (!at) continue;
    const wipe = wipeAtBeijingClock(at, table);
    if (!wipe || seen.has(wipe.name)) continue;
    seen.add(wipe.name);
    out.push(wipe);
  }
  return out;
}

export function rangeStartsBeforeCurrentWipe(
  range: TarkovLogSyncRange,
  now: Date = new Date(),
  starts?: TarkovWipeStart[],
): boolean {
  if (range.all) return false;
  const wipeFrom = wipeStartBeijingClock(currentWipeStart(starts, now));
  return compareBeijingClock(range.from, wipeFrom) < 0;
}

export function formatLogSyncSessionCount(count: number): string {
  return `约 ${count} 次启动`;
}

export function formatLogSyncRangeDays(range: TarkovLogSyncRange): string {
  if (range.all) return "全部";
  const from = parseBeijing(range.from);
  const to = parseBeijing(range.to);
  if (!from.isValid() || !to.isValid()) return "—";
  return `${from.format("YYYY-MM-DD")} ～ ${to.format("YYYY-MM-DD")}`;
}

export function formatCrossWipeHint(wipes: readonly TarkovWipeStart[]): string {
  if (wipes.length <= 1) return "";
  const names = wipes.map((row) => row.name).join("、");
  return `这些启动记录跨了多个赛季（${names}）。任务进度会按日志回放合并；若只想保留本赛季，可改成「本赛季」。`;
}

/** 让出主线程，再读下一份启动文件夹。 */
export function yieldLogSyncQueue(): Promise<void> {
  return new Promise((resolve) => {
    const ric = (
      globalThis as typeof globalThis & {
        requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => void;
      }
    ).requestIdleCallback;
    if (typeof ric === "function") {
      ric(() => resolve(), { timeout: 48 });
      return;
    }
    setTimeout(resolve, 0);
  });
}
