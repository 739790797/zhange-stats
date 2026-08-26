import { describe, expect, it } from "vitest";
import type { DailyTaskInput } from "./myDaily";
import {
  DAILY_CRED_BROKEN_HINT,
  DAILY_CRED_BROKEN_TITLE,
  buildDailyPlatformGroups,
  checkinPlatformHref,
  dailyAttentionRank,
  dailyHeadline,
  dailyLastCheckinHint,
  dailyRoleLabel,
  overlayDailyLiveStatus,
  summarizeDailyTasks,
} from "./myDaily";

function task(partial: Partial<DailyTaskInput> & Pick<DailyTaskInput, "task_key">): DailyTaskInput {
  return {
    platform: "skland",
    platform_name: "森空岛",
    auto_checkin: true,
    checkin_hour: 0,
    checkin_minute: 5,
    ...partial,
  };
}

describe("dailyAttentionRank", () => {
  it("orders failure before unsigned before signed", () => {
    expect(dailyAttentionRank("error")).toBeLessThan(dailyAttentionRank("pending"));
    expect(dailyAttentionRank(null)).toBe(dailyAttentionRank("pending"));
    expect(dailyAttentionRank("pending")).toBeLessThan(dailyAttentionRank("ok"));
    expect(dailyAttentionRank("already")).toBe(dailyAttentionRank("ok"));
  });
});

describe("summarizeDailyTasks", () => {
  it("counts status buckets and auto-on", () => {
    const summary = summarizeDailyTasks([
      task({ task_key: "a", today_status: "ok", auto_checkin: true }),
      task({ task_key: "b", today_status: "already", auto_checkin: false }),
      task({ task_key: "c", today_status: "pending", auto_checkin: true }),
      task({ task_key: "d", today_status: null, auto_checkin: false }),
      task({ task_key: "e", today_status: "error", auto_checkin: true }),
      task({ task_key: "f", today_status: "unknown", auto_checkin: false }),
      task({ task_key: "g", today_status: "skipped", auto_checkin: false }),
    ]);
    expect(summary).toEqual({
      total: 7,
      signed: 2,
      pending: 2,
      failed: 1,
      unknown: 1,
      skipped: 1,
      autoOn: 3,
      credBroken: 0,
      credPlatforms: 0,
    });
  });
});

describe("dailyHeadline", () => {
  it("prioritizes credential failure then pending then complete", () => {
    expect(dailyHeadline(summarizeDailyTasks([]))).toBe("还没有加入本站的角色");
    expect(
      dailyHeadline(
        summarizeDailyTasks([
          task({ task_key: "a", cred_broken: true, today_status: "ok" }),
          task({ task_key: "b", today_status: "pending" }),
        ]),
      ),
    ).toBe("有 1 个平台凭证失效，请重新绑定");
    expect(DAILY_CRED_BROKEN_TITLE).toBe("凭证已失效");
    expect(DAILY_CRED_BROKEN_HINT).toBe("请重新绑定后再查看签到状态");
    expect(
      dailyHeadline(
        summarizeDailyTasks([
          task({ task_key: "a", today_status: "error" }),
          task({ task_key: "b", today_status: "pending" }),
        ]),
      ),
    ).toBe("有 1 个签到失败，可到对应平台处理");
    expect(
      dailyHeadline(
        summarizeDailyTasks([task({ task_key: "a", today_status: "pending" })]),
      ),
    ).toBe("还有 1 个角色待签到");
    expect(
      dailyHeadline(
        summarizeDailyTasks([task({ task_key: "a", today_status: "ok" })]),
      ),
    ).toBe("今日签到已全部完成");
  });
});

describe("checkinPlatformHref", () => {
  it("maps checkin platforms and skips steam", () => {
    expect(checkinPlatformHref("skland")).toBe("/skland");
    expect(checkinPlatformHref("mihoyo")).toBe("/mihoyo");
    expect(checkinPlatformHref("steam")).toBeNull();
    expect(checkinPlatformHref("unknown")).toBeNull();
  });
});

describe("dailyRoleLabel", () => {
  it("prefers role name then uid", () => {
    expect(
      dailyRoleLabel(task({ task_key: "a", role_name: "白衣#5820", role_uid: "1" })),
    ).toBe("白衣#5820");
    expect(dailyRoleLabel(task({ task_key: "b", role_uid: "123" }))).toBe("123");
    expect(dailyRoleLabel(task({ task_key: "c" }))).toBe("未选择角色的平台任务");
  });
});

describe("dailyLastCheckinHint", () => {
  it("hides hint when already signed today", () => {
    expect(
      dailyLastCheckinHint(
        task({
          task_key: "a",
          today_status: "ok",
          last_checkin_at: "2026-08-26 00:05:00",
        }),
      ),
    ).toBeNull();
  });

  it("formats last checkin for pending roles", () => {
    expect(
      dailyLastCheckinHint(
        task({
          task_key: "b",
          today_status: "pending",
          last_checkin_at: "2026-08-25 00:06:11",
        }),
      ),
    ).toBe("上次 8月25日 00:06");
    expect(
      dailyLastCheckinHint(
        task({
          task_key: "c",
          today_status: "error",
          last_checkin_date: "2026-08-24",
        }),
      ),
    ).toBe("上次 8月24日");
    expect(
      dailyLastCheckinHint(
        task({
          task_key: "d",
          cred_broken: true,
          last_checkin_at: "2026-08-25 00:06:11",
        }),
      ),
    ).toBeNull();
  });
});

describe("buildDailyPlatformGroups", () => {
  it("groups by platform and game, community first, attention first", () => {
    const groups = buildDailyPlatformGroups([
      task({
        task_key: "signed",
        platform: "skland",
        game_code: "arknights",
        game_name: "明日方舟",
        role_name: "已签角色",
        today_status: "ok",
      }),
      task({
        task_key: "fail",
        platform: "skland",
        game_code: "arknights",
        game_name: "明日方舟",
        role_name: "失败角色",
        today_status: "error",
      }),
      task({
        task_key: "endfield",
        platform: "skland",
        game_code: "endfield",
        game_name: "终末地",
        role_name: "终末地角色",
        today_status: "ok",
      }),
      task({
        task_key: "kuro",
        platform: "kujiequ",
        game_code: "kujiequ",
        game_name: "库街区",
        role_name: "社区号",
        today_status: "pending",
      }),
      task({
        task_key: "legacy",
        platform: "kujiequ",
        game_code: null,
        today_status: "ok",
      }),
    ]);

    expect(groups.map((g) => g.platform)).toEqual(["skland", "kujiequ"]);
    expect(groups[0].signed).toBe(2);
    expect(groups[0].total).toBe(3);
    expect(groups[0].games[0].game_code).toBe("arknights");
    expect(groups[0].games[0].tasks.map((t) => t.role_name)).toEqual([
      "失败角色",
      "已签角色",
    ]);
    expect(groups[1].games.map((g) => g.game_code)).toEqual(["kujiequ", null]);
  });
});

describe("overlayDailyLiveStatus", () => {
  it("strips today sign-in data when the platform token is broken", () => {
    const overlaid = overlayDailyLiveStatus(
      [
        task({
          task_key: "a",
          today_status: "ok",
          today_awards_text: "狙击芯片×1",
          today_awards: [{ name: "狙击芯片" }],
        }),
      ],
      {
        skland: {
          bound: true,
          token_ok: false,
          token_error: "登录已失效，请重新绑定",
        },
      },
    );
    expect(overlaid[0].cred_broken).toBe(true);
    expect(overlaid[0].cred_error).toBe("登录已失效，请重新绑定");
    expect(overlaid[0].today_status).toBeNull();
    expect(overlaid[0].today_awards_text).toBeNull();
    expect(overlaid[0].today_awards).toEqual([]);
  });

  it("replaces log status with live today_results", () => {
    const overlaid = overlayDailyLiveStatus(
      [
        task({
          task_key: "a",
          game_code: "arknights",
          role_uid: "1",
          today_status: "ok",
        }),
      ],
      {
        skland: {
          bound: true,
          token_ok: true,
          today_results: [
            {
              game_code: "arknights",
              role_uid: "1",
              status: "pending",
              status_label: "未签",
              channel_name: "官服",
            },
          ],
        },
      },
    );
    expect(overlaid[0].cred_broken).toBe(false);
    expect(overlaid[0].today_status).toBe("pending");
    expect(overlaid[0].today_status_label).toBe("未签");
    expect(overlaid[0].channel_name).toBe("官服");
  });
});
