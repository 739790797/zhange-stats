import { describe, expect, it } from "vitest";
import {
  addedIdList,
  formatLiveLogBackfillHint,
  formatLogSyncActionLabel,
  formatLiveWatchLogLine,
  formatLiveWatchShotLine,
  formatPollClock,
  logStampFromParsed,
  nextLiveQuestProgress,
  planLogSessionReads,
  planRaidLogImport,
  sameIdLists,
} from "./tarkovLiveWatch";

describe("formatPollClock", () => {
  it("prints Beijing YYYY-MM-DD HH:mm:ss or a dash", () => {
    expect(formatPollClock("2026-08-30 20:11:02.100")).toBe(
      "2026-08-30 20:11:02",
    );
    expect(formatPollClock(null)).toBe("—");
    expect(formatPollClock("")).toBe("—");
    expect(formatLiveWatchShotLine("2026-08-30 21:04:33")).toBe(
      "最近截图：2026-08-30 21:04:33",
    );
    expect(formatLiveWatchLogLine(null)).toBe("最近日志：—");
  });
});

describe("formatLogSyncActionLabel", () => {
  it("matches the personal-center sync-log button", () => {
    expect(formatLogSyncActionLabel(false)).toBe("同步日志");
    expect(formatLogSyncActionLabel(true)).toBe("正在同步日志…");
    expect(formatLogSyncActionLabel(true, { done: 2, total: 9 })).toBe(
      "正在读取 2 / 9",
    );
  });
});

describe("formatLiveLogBackfillHint", () => {
  it("explains empty folders and counts sessions", () => {
    expect(
      formatLiveLogBackfillHint(0, "backfill", {
        done: 0,
        started: 0,
        unfinished: 0,
      }),
    ).toBe("这个目录里没有启动记录。");
    expect(
      formatLiveLogBackfillHint(3, "backfill", {
        done: 2,
        started: 1,
        unfinished: -3,
      }),
    ).toBe("已从日志回填 已完成 +2，进行中 +1，未完成 -3（3 次启动）");
  });
});

describe("sameIdLists", () => {
  it("ignores order", () => {
    expect(sameIdLists(["b", "a"], ["a", "b"])).toBe(true);
    expect(sameIdLists(["a"], ["a", "b"])).toBe(false);
    expect(sameIdLists([], [])).toBe(true);
  });
});

describe("planLogSessionReads", () => {
  it("reads newest, then only when the folder or fingerprint changes", () => {
    expect(planLogSessionReads(null, "", null)).toEqual({
      skip: true,
      folders: [],
    });
    expect(planLogSessionReads("a", "f1", null)).toEqual({
      skip: false,
      folders: ["a"],
    });
    expect(planLogSessionReads("a", "f1", null, ["a", "b", "c"])).toEqual({
      skip: false,
      folders: ["a", "b", "c"],
    });
    expect(
      planLogSessionReads("a", "f1", { folder: "a", fingerprint: "f1" }),
    ).toEqual({ skip: true, folders: [] });
    expect(
      planLogSessionReads("a", "f2", { folder: "a", fingerprint: "f1" }),
    ).toEqual({ skip: false, folders: ["a"] });
    expect(
      planLogSessionReads("b", "f2", { folder: "a", fingerprint: "f1" }),
    ).toEqual({ skip: false, folders: ["a", "b"] });
    expect(
      planLogSessionReads("b", "f2", { folder: "a", fingerprint: "f1" }, [
        "b",
        "c",
      ]),
    ).toEqual({ skip: false, folders: ["a", "b"] });
  });
});

describe("addedIdList", () => {
  it("keeps next-only ids in original order", () => {
    expect(addedIdList(["a", "b"], ["b", "c", "a", "d"])).toEqual(["c", "d"]);
    expect(addedIdList(["a"], ["a"])).toEqual([]);
    expect(addedIdList([], ["x", ""])).toEqual(["x"]);
  });
});

describe("nextLiveQuestProgress", () => {
  it("marks unchanged when the replay matches current lists", () => {
    expect(
      nextLiveQuestProgress(
        ["done"],
        ["active"],
        [
          {
            parsed: {
              events: [],
              raids: [],
              sessionMode: "regular",
              quests: [
                {
                  kind: "completed",
                  taskId: "done",
                  at: "2026-01-01 10:00:00",
                },
                {
                  kind: "started",
                  taskId: "active",
                  at: "2026-01-01 11:00:00",
                },
              ],
            },
          },
        ],
        "pvp",
      ),
    ).toEqual({
      done: ["done"],
      started: ["active"],
      changed: false,
      eventCount: 2,
      latestEventAt: "2026-01-01 11:00:00",
    });
  });

  it("returns the merged lists when a new quest event appears", () => {
    expect(
      nextLiveQuestProgress(
        [],
        [],
        [
          {
            parsed: {
              events: [],
              raids: [],
              sessionMode: "pve",
              quests: [
                {
                  kind: "started",
                  taskId: "q1",
                  at: "2026-01-01 10:00:00",
                },
              ],
            },
          },
        ],
        "pve",
      ),
    ).toEqual({
      done: [],
      started: ["q1"],
      changed: true,
      eventCount: 1,
      latestEventAt: "2026-01-01 10:00:00",
    });
  });

  it("applies historical log tasks even when their clock is old", () => {
    expect(
      nextLiveQuestProgress(
        ["keep"],
        [],
        [
          {
            parsed: {
              events: [],
              raids: [],
              sessionMode: "pve",
              quests: [
                {
                  kind: "started",
                  taskId: "keep",
                  at: "2026-01-01 10:00:00",
                },
                {
                  kind: "completed",
                  taskId: "missed",
                  at: "2026-01-01 09:00:00",
                },
              ],
            },
          },
        ],
        "pve",
      ),
    ).toMatchObject({
      done: ["keep", "missed"],
      started: [],
      changed: true,
      eventCount: 2,
    });
  });

  it("does not un-complete an account task from an older start event", () => {
    expect(
      nextLiveQuestProgress(
        ["keep"],
        [],
        [
          {
            parsed: {
              events: [],
              raids: [],
              sessionMode: "pve",
              quests: [
                {
                  kind: "started",
                  taskId: "keep",
                  at: "2026-01-01 10:00:00",
                },
              ],
            },
          },
        ],
        "pve",
      ),
    ).toMatchObject({
      done: ["keep"],
      started: [],
      changed: false,
    });
  });

  it("updates only the logged raid task and leaves the rest of the ledger", () => {
    expect(
      nextLiveQuestProgress(
        ["old-done"],
        ["old-start"],
        [
          {
            parsed: {
              events: [],
              raids: [],
              sessionMode: "regular",
              quests: [
                {
                  kind: "completed",
                  taskId: "raid-only",
                  at: "2026-09-01 16:00:00",
                },
              ],
            },
          },
        ],
        "pvp",
      ),
    ).toMatchObject({
      done: ["old-done", "raid-only"],
      started: ["old-start"],
      changed: true,
      eventCount: 1,
    });
  });
});

describe("logStampFromParsed", () => {
  it("prefers the newest event or quest clock, then file mtime", () => {
    expect(
      logStampFromParsed(
        {
          events: [{ kind: "raid_started", at: "2026-08-30 20:00:00.000" }],
          raids: [],
          quests: [
            { kind: "started", taskId: "q", at: "2026-08-30 20:11:02.100" },
          ],
        },
        [1],
      ),
    ).toBe("2026-08-30 20:11:02.100");
    expect(logStampFromParsed({ events: [], raids: [] }, [10, 30, 20])).toBe(
      30,
    );
    expect(logStampFromParsed(null, [])).toBeNull();
  });
});

describe("planRaidLogImport", () => {
  const endedSession = {
    folder: "log_new",
    parsed: {
      events: [],
      raids: [
        {
          raidId: "PQXKR6",
          location: "Shoreline",
          mapId: "shoreline",
          mapLabel: "海岸线",
          raidMode: "online" as const,
          startedAt: "2023-12-29 19:03:40.000",
          endedAt: "2023-12-29 19:41:00.000",
        },
      ],
    },
  };

  it("records ended raids on first sight without uploading", () => {
    const first = planRaidLogImport(new Set(), [endedSession]);
    expect(first.rows).toEqual([]);
    expect([...first.nextKeys]).toEqual(["log_new|PQXKR6"]);
  });

  it("uploads all ended raids when force-backfilling old logs", () => {
    const forced = planRaidLogImport(new Set(), [endedSession], { force: true });
    expect(forced.rows).toHaveLength(1);
    expect(forced.rows[0]?.raid_id).toBe("PQXKR6");
  });

  it("uploads when a new UserMatchOver appears", () => {
    const seen = planRaidLogImport(new Set(), [endedSession]).nextKeys;
    const second = planRaidLogImport(seen, [
      {
        folder: "log_new",
        parsed: {
          events: [],
          raids: [
            ...endedSession.parsed.raids,
            {
              raidId: "ZZZZZZ",
              location: "Woods",
              mapId: "woods",
              mapLabel: "森林",
              raidMode: "online" as const,
              startedAt: "2026-08-31 12:00:00.000",
              endedAt: "2026-08-31 12:40:00.000",
            },
          ],
        },
      },
    ]);
    expect(second.rows).toHaveLength(2);
    expect(second.rows.some((row) => row.raid_id === "ZZZZZZ")).toBe(true);
  });
});
