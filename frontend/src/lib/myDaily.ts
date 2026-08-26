import {
  CHECKIN_PLATFORM_LABELS,
  communityGameRank,
  platformRank,
} from "@/lib/checkinDisplay";
import { isBindTokenBroken, isCheckinSuccess } from "@/lib/checkinStatus";
import { PLATFORM_NAV } from "@/lib/platformFeatures";
import { parseBeijing } from "@/lib/time";

/** 「我的日常」分组所需的最小任务字段。 */
export type DailyTaskInput = {
  task_key: string;
  platform: string;
  platform_name: string;
  game_code?: string | null;
  game_name?: string | null;
  role_uid?: string | null;
  role_name?: string | null;
  channel_name?: string | null;
  auto_checkin: boolean;
  checkin_hour: number;
  checkin_minute: number;
  today_status?: string | null;
  today_status_label?: string | null;
  today_awards_text?: string | null;
  today_awards?: unknown;
  last_checkin_at?: string | null;
  last_checkin_date?: string | null;
  /** 平台凭证失效：不沿用日志里的今日已签/奖励。 */
  cred_broken?: boolean;
  cred_error?: string | null;
};

export type DailySummary = {
  total: number;
  signed: number;
  pending: number;
  failed: number;
  unknown: number;
  skipped: number;
  autoOn: number;
  credBroken: number;
  credPlatforms: number;
};

export type DailyGameGroup<T extends DailyTaskInput = DailyTaskInput> = {
  key: string;
  game_code: string | null;
  game_name: string;
  tasks: T[];
};

export type DailyPlatformGroup<T extends DailyTaskInput = DailyTaskInput> = {
  platform: string;
  platform_name: string;
  signed: number;
  total: number;
  attention: number;
  credBroken?: boolean;
  credError?: string | null;
  games: DailyGameGroup<T>[];
};

/** 平台签到页同源的 status（token_ok + 今日结果）。 */
export type DailyLivePlatformStatus = {
  bound?: boolean;
  token_ok?: boolean | null;
  token_error?: string | null;
  today_results?: Array<{
    game_code?: string | null;
    role_uid?: string | null;
    status?: string | null;
    status_label?: string | null;
    awards_text?: string | null;
    awards?: unknown;
    message?: string | null;
    channel_name?: string | null;
  }>;
};

/** 越小越需要先看：凭证失效 → 失败 → 待确认 → 未签 → 跳过 → 已签。 */
export function dailyAttentionRank(
  status?: string | null,
  credBroken?: boolean,
): number {
  if (credBroken) return -1;
  const s = (status || "").trim();
  if (s === "error") return 0;
  if (s === "unknown") return 1;
  if (!s || s === "pending") return 2;
  if (s === "skipped") return 3;
  if (isCheckinSuccess(s)) return 4;
  return 2;
}

export function summarizeDailyTasks(tasks: DailyTaskInput[]): DailySummary {
  const summary: DailySummary = {
    total: tasks.length,
    signed: 0,
    pending: 0,
    failed: 0,
    unknown: 0,
    skipped: 0,
    autoOn: 0,
    credBroken: 0,
    credPlatforms: 0,
  };
  const brokenPlatforms = new Set<string>();
  for (const task of tasks) {
    if (task.auto_checkin) summary.autoOn += 1;
    if (task.cred_broken) {
      summary.credBroken += 1;
      brokenPlatforms.add(task.platform);
      continue;
    }
    const status = (task.today_status || "").trim();
    if (isCheckinSuccess(status)) summary.signed += 1;
    else if (status === "error") summary.failed += 1;
    else if (status === "unknown") summary.unknown += 1;
    else if (status === "skipped") summary.skipped += 1;
    else summary.pending += 1;
  }
  summary.credPlatforms = brokenPlatforms.size;
  return summary;
}

export const DAILY_CRED_BROKEN_TITLE = "凭证已失效";
export const DAILY_CRED_BROKEN_HINT = "请重新绑定后再查看签到状态";

export function dailyHeadline(summary: DailySummary): string {
  if (summary.total === 0) return "还没有加入本站的角色";
  if (summary.credPlatforms > 0) {
    return `有 ${summary.credPlatforms} 个平台凭证失效，请重新绑定`;
  }
  if (summary.failed > 0) {
    return `有 ${summary.failed} 个签到失败，可到对应平台处理`;
  }
  if (summary.unknown > 0) {
    return `有 ${summary.unknown} 个状态待确认`;
  }
  if (summary.pending > 0) {
    return `还有 ${summary.pending} 个角色待签到`;
  }
  if (summary.skipped > 0) {
    return `今日签到已完成（含 ${summary.skipped} 个跳过）`;
  }
  return "今日签到已全部完成";
}

export function checkinPlatformHref(platform: string): string | null {
  const nav = PLATFORM_NAV.find((item) => item.featureId === platform);
  if (!nav || nav.featureId === "steam") return null;
  return nav.path;
}

export function dailyRoleLabel(task: DailyTaskInput): string {
  const name = (task.role_name || task.role_uid || "").trim();
  if (name) return name;
  return "未选择角色的平台任务";
}

/** 未完成今日签到时展示上次成功时间，已签则留给奖励行。 */
export function dailyLastCheckinHint(task: DailyTaskInput): string | null {
  if (task.cred_broken || isCheckinSuccess(task.today_status)) return null;
  const at = (task.last_checkin_at || "").trim();
  if (at) {
    const parsed = parseBeijing(at);
    if (parsed.isValid()) return `上次 ${parsed.format("M月D日 HH:mm")}`;
  }
  const date = (task.last_checkin_date || "").trim();
  if (!date) return null;
  const parsed = parseBeijing(date);
  if (!parsed.isValid()) return null;
  return `上次 ${parsed.format("M月D日")}`;
}

function compareTasks<T extends DailyTaskInput>(a: T, b: T): number {
  const byAttention =
    dailyAttentionRank(a.today_status, a.cred_broken) -
    dailyAttentionRank(b.today_status, b.cred_broken);
  if (byAttention !== 0) return byAttention;
  const left = (a.role_name || a.role_uid || "").trim();
  const right = (b.role_name || b.role_uid || "").trim();
  return left.localeCompare(right, "zh");
}

export function buildDailyPlatformGroups<T extends DailyTaskInput>(
  tasks: T[],
): DailyPlatformGroup<T>[] {
  const byPlatform = new Map<string, T[]>();
  for (const task of tasks) {
    const list = byPlatform.get(task.platform) || [];
    list.push(task);
    byPlatform.set(task.platform, list);
  }

  const platforms = [...byPlatform.keys()].sort(
    (a, b) => platformRank(a) - platformRank(b) || a.localeCompare(b),
  );

  const groups = platforms.map((platform) => {
    const list = byPlatform.get(platform) || [];
    const platformName =
      CHECKIN_PLATFORM_LABELS[platform] || list[0]?.platform_name || platform;

    const withGame = list.filter((task) => task.game_code);
    const legacy = list.filter((task) => !task.game_code);

    const byGame = new Map<string, T[]>();
    for (const task of withGame) {
      const gameCode = String(task.game_code);
      const gameList = byGame.get(gameCode) || [];
      gameList.push(task);
      byGame.set(gameCode, gameList);
    }

    const games: DailyGameGroup<T>[] = [...byGame.entries()]
      .sort(
        ([a], [b]) =>
          communityGameRank(a) - communityGameRank(b) || a.localeCompare(b),
      )
      .map(([gameCode, roles]) => ({
        key: `game:${platform}:${gameCode}`,
        game_code: gameCode,
        game_name: roles[0]?.game_name || gameCode,
        tasks: roles.slice().sort(compareTasks),
      }));

    if (legacy.length) {
      games.push({
        key: `legacy:${platform}`,
        game_code: null,
        game_name: "平台任务",
        tasks: legacy.slice().sort(compareTasks),
      });
    }

    const signed = list.filter(
      (task) => !task.cred_broken && isCheckinSuccess(task.today_status),
    ).length;
    const credBroken = list.some((task) => task.cred_broken);
    const credError =
      list.find((task) => task.cred_broken)?.cred_error?.trim() || null;

    return {
      platform,
      platform_name: platformName,
      signed,
      total: list.length,
      attention: Math.min(
        ...list.map((task) =>
          dailyAttentionRank(task.today_status, task.cred_broken),
        ),
      ),
      credBroken,
      credError,
      games,
    };
  });

  return groups.sort((a, b) => {
    if (a.attention !== b.attention) return a.attention - b.attention;
    return platformRank(a.platform) - platformRank(b.platform);
  });
}

function liveRowKey(gameCode?: string | null, roleUid?: string | null) {
  return `${String(gameCode || "")}::${String(roleUid || "")}`;
}

/**
 * 用签到页同源的 status 覆盖日志：凭证失效不再展示今日已签/奖励；
 * token 正常则用 today_results 同步状态。
 */
export function overlayDailyLiveStatus<T extends DailyTaskInput>(
  tasks: T[],
  live: Record<string, DailyLivePlatformStatus | undefined>,
): T[] {
  return tasks.map((task) => {
    const status = live[task.platform];
    if (!status) return task;
    if (
      isBindTokenBroken({
        bound: status.bound ?? true,
        token_ok: status.token_ok,
      })
    ) {
      const error = (status.token_error || "").trim() || null;
      return {
        ...task,
        cred_broken: true,
        cred_error: error,
        today_status: null,
        today_status_label: null,
        today_awards_text: null,
        today_awards: [],
      };
    }
    const rows = status.today_results || [];
    if (!rows.length) return { ...task, cred_broken: false, cred_error: null };
    const row = rows.find(
      (item) =>
        liveRowKey(item.game_code, item.role_uid) ===
        liveRowKey(task.game_code, task.role_uid),
    );
    if (!row) return { ...task, cred_broken: false, cred_error: null };
    return {
      ...task,
      cred_broken: false,
      cred_error: null,
      today_status: row.status ?? task.today_status,
      today_status_label: row.status_label ?? task.today_status_label,
      today_awards_text: row.awards_text ?? task.today_awards_text,
      today_awards: row.awards ?? task.today_awards,
      channel_name: row.channel_name ?? task.channel_name,
    };
  });
}
