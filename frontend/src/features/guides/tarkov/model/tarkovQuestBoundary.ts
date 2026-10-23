/**
 * 任务账的日志回放边界：清空进度或玩家选定转生起点之后，从哪一刻起回放游戏日志。
 *
 * 边界的权威在账号（`GET …/task-dones` 的 reset_at / pending_clear_at / reset_profile_id / reset_epoch）。
 * 本机 localStorage 只做缓存与访客兜底，登出、换浏览器、战鸽助手都读同一份服务端边界。
 *
 * 游戏日志里没有转生事件。`SelectProfile` 的 ProfileId 只说明这次启动选的是哪个角色，
 * 转生不会另写一个 ProfileId。新起点只能由玩家在同步日历里对某一局点「转生归档」。
 */

import type { TarkovGameMode } from "@/features/guides/tarkov/model/tarkovGameMode";
import type { TarkovLogIdentity } from "@/features/guides/tarkov/model/tarkovGameLogs";
import { breakpointMatchesGameMode } from "@/features/guides/tarkov/model/tarkovLogBreakpoints";
import { compareBeijingClock, laterBeijingClock, parseBeijing } from "@/shared/lib/time";

export type QuestBoundary = {
  /** 回放下限；早于它的任务事件不写回。空 = 无下限。 */
  resetAt: string;
  /** 玩家点了清空、还没被带日志的同步定下来的时刻。 */
  pendingClearAt: string;
  /** 定下 resetAt 时当前模式的游戏 ProfileId。 */
  profileId: string;
  epoch: number;
};

export type QuestResetReason = "clear" | "prestige" | "profile";

export function emptyQuestBoundary(): QuestBoundary {
  return { resetAt: "", pendingClearAt: "", profileId: "", epoch: 0 };
}

function clock(raw: unknown): string {
  return typeof raw === "string" ? raw.trim() : "";
}

export function questBoundaryFromServer(
  data:
    | {
        reset_at?: string | null;
        pending_clear_at?: string | null;
        reset_profile_id?: string | null;
        reset_epoch?: number | null;
      }
    | null
    | undefined,
): QuestBoundary {
  if (!data) return emptyQuestBoundary();
  return {
    resetAt: clock(data.reset_at),
    pendingClearAt: clock(data.pending_clear_at),
    profileId: clock(data.reset_profile_id),
    epoch: Number.isFinite(data.reset_epoch) ? Number(data.reset_epoch) : 0,
  };
}

/** 服务端 cleared 列表 → 任务 id → 清除时刻。 */
export function clearedMapFromServer(
  rows: ReadonlyArray<{ task_id?: string | null; cleared_at?: string | null }> | null | undefined,
): Map<string, string> {
  const out = new Map<string, string>();
  for (const row of rows || []) {
    const id = clock(row.task_id).toLowerCase();
    const at = clock(row.cleared_at);
    if (id && at) out.set(id, at);
  }
  return out;
}

/** 两份清除标记取并集，同一任务留更晚的时刻。 */
export function mergeClearedMaps(
  ...maps: ReadonlyArray<ReadonlyMap<string, string> | null | undefined>
): Map<string, string> {
  const out = new Map<string, string>();
  for (const map of maps) {
    if (!map) continue;
    for (const [id, at] of map) {
      out.set(id, laterBeijingClock(out.get(id) || "", at));
    }
  }
  return out;
}

/**
 * 截到整秒。服务端只存到秒；本机回放与写进账号的下限用同一个值，两边才对得上。
 * （边界都来自选角 / 清空这种秒级动作，同一秒里它之前的任务通知实际不会出现。）
 */
export function clockToSecond(raw: string): string {
  const text = (raw || "").trim();
  if (!text) return "";
  const d = parseBeijing(text);
  if (!d.isValid()) return "";
  return d.startOf("second").format("YYYY-MM-DD HH:mm:ss");
}

/**
 * 登录用户以账号边界为准。账号从没记过边界（epoch 0，升级前的老账号）时，
 * 把本机遗留的下限 / 未提交的清空也算上，免得升级当天又把旧任务放回来。
 */
export function combineQuestBoundary(
  server: QuestBoundary | null,
  local: QuestBoundary,
): QuestBoundary {
  if (!server) return { ...local, epoch: 0 };
  if (server.epoch > 0) return server;
  return {
    resetAt: laterBeijingClock(server.resetAt, local.resetAt),
    pendingClearAt: server.pendingClearAt || local.pendingClearAt,
    profileId: server.profileId || local.profileId,
    epoch: server.epoch,
  };
}

function before(a: string, b: string): boolean {
  return compareBeijingClock(a, b) < 0;
}

export type QuestReplayPlan = {
  profileId: string;
  /** 回放下限；空 = 从该角色全部日志。 */
  fromAt: string;
  /** true：用本次回放结果整表替换账号进度，并把下限写到服务端。false：在现有进度上增量合并。 */
  reset: boolean;
  reason: QuestResetReason | null;
  /** 保留给调用方；转生不再靠推断，玩家勾选断点时这里是 false。 */
  confirm: boolean;
};

function firstSighting(
  identities: readonly TarkovLogIdentity[],
  gameMode: TarkovGameMode,
  profileId: string,
): string {
  let at = "";
  for (const row of identities) {
    if ((row.profileId || "").trim() !== profileId) continue;
    if (!breakpointMatchesGameMode(row, gameMode)) continue;
    const rowAt = (row.at || "").trim();
    if (rowAt && (!at || before(rowAt, at))) at = rowAt;
  }
  return at;
}

function latestProfile(
  identities: readonly TarkovLogIdentity[],
  gameMode: TarkovGameMode,
): string {
  let found: TarkovLogIdentity | null = null;
  for (const row of identities) {
    if (!(row.profileId || "").trim()) continue;
    if (!breakpointMatchesGameMode(row, gameMode)) continue;
    if (!found || compareBeijingClock(row.at, found.at) >= 0) found = row;
  }
  return (found?.profileId || "").trim();
}

/**
 * 决定这次同步从哪一刻回放、要不要整表替换账号进度。
 *
 * 下限只增不减，不早于服务端 resetAt。日志里没有转生，ProfileId 也不代表转生。
 * - restartAt：玩家在日历里把某一局标成转生归档之后的时刻（该局本身不写回）。晚于已有下限才整表替换，reason=prestige。
 * - 只点过清空、没有新断点：从该角色第一次出现（或已有下限）回放，reason=clear。
 *   不用点击时刻当下限，否则清空之后立刻同步会把历史任务全部丢掉。
 * - 其余：从 resetAt 起增量合并。
 */
export function planQuestReplay(input: {
  gameMode: TarkovGameMode;
  identities: readonly TarkovLogIdentity[];
  boundary: QuestBoundary;
  restartAt?: string;
}): QuestReplayPlan | null {
  const profileId = latestProfile(input.identities, input.gameMode);
  if (!profileId) return null;
  const { resetAt, pendingClearAt } = input.boundary;
  const restartAt = clockToSecond((input.restartAt || "").trim());
  if (restartAt && (!resetAt || before(resetAt, restartAt))) {
    return {
      profileId,
      fromAt: laterBeijingClock(restartAt, resetAt),
      reset: true,
      reason: "prestige",
      confirm: false,
    };
  }
  if (pendingClearAt) {
    const sighted = firstSighting(input.identities, input.gameMode, profileId);
    return {
      profileId,
      fromAt: resetAt || sighted,
      reset: true,
      reason: "clear",
      confirm: false,
    };
  }
  return { profileId, fromAt: resetAt, reset: false, reason: null, confirm: false };
}
