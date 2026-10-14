/**
 * 任务账的日志回放边界：清空进度 / 转生 / 换角色之后，从哪一刻起回放游戏日志。
 *
 * 边界的权威在账号（`GET …/task-dones` 的 reset_at / pending_clear_at / reset_profile_id / reset_epoch）。
 * 本机 localStorage 只做缓存与访客兜底，登出、换浏览器、战鸽助手都读同一份服务端边界。
 *
 * 游戏日志里没有「转生」事件（TarkovMonitor 也只认 ProfileId），同一 ProfileId 的转生只能推断：
 * 图鉴里的非重复任务已经完成过，之后又收到「开始」，说明进度被重置了。
 */

import type { TarkovGameMode } from "@/lib/tarkovGameMode";
import type { TarkovLogIdentity, TarkovLogQuestEvent } from "@/lib/tarkovGameLogs";
import { breakpointMatchesGameMode } from "@/lib/tarkovLogBreakpoints";
import { compareBeijingClock, laterBeijingClock, parseBeijing } from "@/lib/time";

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

/** 同一转生至少要这么多个不同任务「完成后又开始」才认。单个任务可能是日志噪声。 */
export const PRESTIGE_MIN_TASKS = 2;

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

export type QuestPrestigeCatalog = {
  knownIds?: ReadonlySet<string>;
  restartableIds: ReadonlySet<string>;
};

export type QuestPrestige = {
  /** 回放下限：转生点（最后一次旧进度之后、第一次「完成后又开始」之前的那次选角）。 */
  at: string;
  /** 第一次「完成后又开始」的时刻。 */
  startedAt: string;
  taskIds: string[];
};

type Regression = { id: string; at: string; undoneAt: string };

/**
 * 在同一 ProfileId 的任务事件里找最近一次转生。只看日志，不看账号：
 * 网站上先勾了完成、进游戏才接任务很常见，拿账号当「之前完成过」会把正常游玩误判成转生、整账清掉。
 * - 只看图鉴里有、且不可重开的任务（每日 / 每周不在图鉴里，可重开任务本来就能再开）；
 * - 日志里「完成（或不可重开的失败）之后又开始」记一次回退；
 * - 回退按转生分组：被撤销的那次完成早于本组第一次回退，就算同一次转生；
 * - 取最近一组达到 minTasks 的；下限取组内第一次回退之前、最后一次旧完成之后的最近一次选角，没有就取第一次回退本身。
 */
export function detectQuestPrestige(input: {
  events: readonly TarkovLogQuestEvent[];
  identities: readonly TarkovLogIdentity[];
  gameMode: TarkovGameMode;
  profileId: string;
  catalog: QuestPrestigeCatalog;
  floor?: string;
  minTasks?: number;
}): QuestPrestige | null {
  const known = input.catalog.knownIds;
  if (!known?.size) return null;
  const restartable = input.catalog.restartableIds;
  const profileId = (input.profileId || "").trim();
  if (!profileId) return null;
  const floor = (input.floor || "").trim();
  const minTasks = Math.max(1, input.minTasks ?? PRESTIGE_MIN_TASKS);

  const state = new Map<string, { kind: TarkovLogQuestEvent["kind"]; at: string }>();
  const ordered = [...input.events]
    .filter((event) => {
      if ((event.profileId || "").trim() && event.profileId !== profileId) return false;
      if (floor && before(event.at || "", floor)) return false;
      return true;
    })
    .sort((a, b) => compareBeijingClock(a.at || "", b.at || ""));

  const regressions: Regression[] = [];
  for (const event of ordered) {
    const id = (event.taskId || "").trim().toLowerCase();
    if (!id || !known.has(id) || restartable.has(id)) continue;
    const prev = state.get(id);
    if (
      event.kind === "started" &&
      prev &&
      (prev.kind === "completed" || prev.kind === "failed")
    ) {
      regressions.push({ id, at: event.at || "", undoneAt: prev.at });
    }
    state.set(id, { kind: event.kind, at: event.at || "" });
  }
  if (!regressions.length) return null;

  type Cluster = { startAt: string; lastUndone: string; ids: Set<string> };
  const clusters: Cluster[] = [];
  for (const row of regressions) {
    const current = clusters[clusters.length - 1];
    if (current && before(row.undoneAt, current.startAt)) {
      current.ids.add(row.id);
      current.lastUndone = laterBeijingClock(current.lastUndone, row.undoneAt);
      continue;
    }
    clusters.push({ startAt: row.at, lastUndone: row.undoneAt, ids: new Set([row.id]) });
  }
  let chosen: Cluster | null = null;
  for (let i = clusters.length - 1; i >= 0; i -= 1) {
    if (clusters[i].ids.size >= minTasks) {
      chosen = clusters[i];
      break;
    }
  }
  if (!chosen) return null;

  let at = "";
  for (const row of input.identities) {
    if ((row.profileId || "").trim() !== profileId) continue;
    if (!breakpointMatchesGameMode(row, input.gameMode)) continue;
    const rowAt = (row.at || "").trim();
    if (!rowAt || before(chosen.startAt, rowAt)) continue;
    if (chosen.lastUndone && !before(chosen.lastUndone, rowAt)) continue;
    if (!at || before(at, rowAt)) at = rowAt;
  }
  return {
    at: at || chosen.startAt,
    startedAt: chosen.startAt,
    taskIds: [...chosen.ids].sort(),
  };
}

export type QuestReplayPlan = {
  profileId: string;
  /** 回放下限；空 = 从该角色全部日志。 */
  fromAt: string;
  /** true：用本次回放结果整表替换账号进度，并把下限写到服务端。false：在现有进度上增量合并。 */
  reset: boolean;
  reason: QuestResetReason | null;
  /**
   * 重置只是推断出来的（日志猜转生；账号不知道旧 ProfileId、日志里另有角色），玩家也没点清空：
   * 整表重置不可撤销，要先问。不答应就按 resetAt 增量合并。
   */
  confirm: boolean;
  prestige: QuestPrestige | null;
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

function hasOtherProfile(
  identities: readonly TarkovLogIdentity[],
  gameMode: TarkovGameMode,
  profileId: string,
): boolean {
  return identities.some((row) => {
    const id = (row.profileId || "").trim();
    return Boolean(id) && id !== profileId && breakpointMatchesGameMode(row, gameMode);
  });
}

/**
 * 决定这次同步从哪一刻回放、要不要整表替换账号进度。
 *
 * 规则（下限只增不减，永远不早于服务端 resetAt）：
 * - 玩家点过清空（pendingClearAt）：有转生 / 明确换角色的证据就取证据时刻（保留转生之后、清空之前打的任务），
 *   否则取清空时刻。账号上不知道旧 ProfileId 时，日志里的别的角色不算换角色——那可能是上个赛季的号，
 *   拿它的首次出现当下限会把同一角色转生前的任务全放回来。
 * - 没点清空：识别出转生、或换了角色（账号记的 ProfileId 不同；账号没记而日志里有别的角色也算）就整表重置；
 *   否则从 resetAt 起增量合并。
 */
export function planQuestReplay(input: {
  gameMode: TarkovGameMode;
  identities: readonly TarkovLogIdentity[];
  events: readonly TarkovLogQuestEvent[];
  boundary: QuestBoundary;
  catalog: QuestPrestigeCatalog;
}): QuestReplayPlan | null {
  const profileId = latestProfile(input.identities, input.gameMode);
  if (!profileId) return null;
  const { resetAt, pendingClearAt } = input.boundary;
  const known = (input.boundary.profileId || "").trim();
  const sighted = firstSighting(input.identities, input.gameMode, profileId);
  const explicitSwitch = Boolean(known) && known !== profileId;
  const implicitSwitch =
    !known && hasOtherProfile(input.identities, input.gameMode, profileId);

  const prestige = detectQuestPrestige({
    events: input.events,
    identities: input.identities,
    gameMode: input.gameMode,
    profileId,
    catalog: input.catalog,
    floor: resetAt,
  });

  /** inferred：只是推断（猜转生；账号不知道旧角色、日志里另有角色），整表重置前要问。 */
  type Evidence = { at: string; reason: QuestResetReason; inferred: boolean };
  const evidence: Evidence[] = [];
  if (prestige?.at) {
    evidence.push({ at: clockToSecond(prestige.at), reason: "prestige", inferred: true });
  }
  if (sighted && (explicitSwitch || (implicitSwitch && !pendingClearAt))) {
    evidence.push({ at: clockToSecond(sighted), reason: "profile", inferred: !explicitSwitch });
  }
  let latest: Evidence | null = null;
  for (const row of evidence) {
    if (!latest || before(latest.at, row.at)) latest = row;
  }
  if (latest && resetAt && !before(resetAt, latest.at)) latest = null;

  if (pendingClearAt) {
    // 玩家点过清空，整表重置是他要的；证据只决定从哪一刻起，不用再问
    const pick = latest || { at: pendingClearAt, reason: "clear" as const };
    return {
      profileId,
      fromAt: laterBeijingClock(pick.at, resetAt),
      reset: true,
      reason: pick.reason,
      confirm: false,
      prestige,
    };
  }
  if (latest) {
    return {
      profileId,
      fromAt: laterBeijingClock(latest.at, resetAt),
      reset: true,
      reason: latest.reason,
      confirm: latest.inferred,
      prestige,
    };
  }
  return { profileId, fromAt: resetAt, reset: false, reason: null, confirm: false, prestige };
}
