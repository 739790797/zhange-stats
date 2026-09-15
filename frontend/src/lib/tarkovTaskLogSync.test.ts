import { describe, expect, it } from "vitest";
import {
  accountHasQuestState,
  applyQuestLogState,
  buildQuestLogCatalog,
  buildQuestLogSyncReview,
  collectQuestEventsFromSessions,
  collectQuestReplayDrops,
  foldQuestEvents,
  foldSessionQuests,
  formatLastQuestSyncLine,
  formatQuestLogDropHint,
  formatQuestLogEventLine,
  formatQuestLogStatusChange,
  formatQuestSyncDeltaLine,
  formatSignedDelta,
  mergeQuestProgressFromFolded,
  questProgressDelta,
  mergeQuestProgressFromLogs,
  questsMatchingReplay,
  replayQuestEvents,
  sessionModeMatchesGameMode,
} from "./tarkovTaskLogSync";
import type { TarkovLogQuestEvent } from "./tarkovGameLogs";

function ev(
  kind: TarkovLogQuestEvent["kind"],
  taskId: string,
  at: string,
): TarkovLogQuestEvent {
  return { kind, taskId, at };
}

describe("sessionModeMatchesGameMode", () => {
  it("maps regular / pvp / pve and drops blank or unknown modes", () => {
    expect(sessionModeMatchesGameMode("regular", "pvp")).toBe(true);
    expect(sessionModeMatchesGameMode("pvp", "pvp")).toBe(true);
    expect(sessionModeMatchesGameMode("pve", "pve")).toBe(true);
    expect(sessionModeMatchesGameMode("pve", "pvp")).toBe(false);
    expect(sessionModeMatchesGameMode("regular", "pve")).toBe(false);
    expect(sessionModeMatchesGameMode("", "pve")).toBe(false);
    expect(sessionModeMatchesGameMode(undefined, "pvp")).toBe(false);
    expect(sessionModeMatchesGameMode("unknown", "pvp")).toBe(false);
    expect(sessionModeMatchesGameMode("seasonal", "pvp")).toBe(false);
    expect(sessionModeMatchesGameMode("szn", "pvp")).toBe(false);
    expect(sessionModeMatchesGameMode("pvpseason", "pve")).toBe(false);
  });
});

describe("replayQuestEvents", () => {
  it("lets the latest event win", () => {
    const state = replayQuestEvents([
      ev("started", "t1", "2026-01-01 10:00:00"),
      ev("completed", "t1", "2026-01-01 12:00:00"),
      ev("started", "t2", "2026-01-01 11:00:00"),
      ev("failed", "t2", "2026-01-01 13:00:00"),
    ]);
    expect(state.get("t1")?.kind).toBe("completed");
    expect(state.get("t1")?.everCompleted).toBe(true);
    expect(state.get("t2")?.kind).toBe("failed");
    expect(state.get("t2")?.everCompleted).toBe(false);
  });
});

describe("accountHasQuestState", () => {
  it("treats done as covering start/fail, and only done as covering complete", () => {
    const done = new Set(["done"]);
    const started = new Set(["active"]);
    expect(accountHasQuestState(done, started, "done", "completed")).toBe(true);
    expect(accountHasQuestState(done, started, "done", "started")).toBe(true);
    expect(accountHasQuestState(done, started, "active", "started")).toBe(true);
    expect(accountHasQuestState(done, started, "active", "failed")).toBe(false);
    expect(
      accountHasQuestState(done, started, "active", "failed", new Set(["active"])),
    ).toBe(true);
    expect(accountHasQuestState(done, started, "active", "completed")).toBe(
      false,
    );
    expect(accountHasQuestState(done, started, "new", "started")).toBe(false);
    expect(accountHasQuestState(done, started, "new", "completed")).toBe(false);
  });
});

describe("applyQuestLogState", () => {
  it("merges log state onto existing progress and drops unknown ids", () => {
    const merged = applyQuestLogState(
      ["old"],
      ["t2"],
      new Map([
        ["t1", "completed"],
        ["t2", "started"],
        ["ghost", "completed"],
      ]),
      new Set(["old", "t1", "t2"]),
    );
    expect(merged.done.sort()).toEqual(["old", "t1"]);
    expect(merged.started).toEqual(["t2"]);
    expect(merged.failed).toEqual([]);
  });

  it("keeps hex quest ids even when the catalog is stale", () => {
    const merged = applyQuestLogState(
      ["5AC346A886F7744E1B083D67"],
      [],
      new Map([
        ["5ac346a886f7744e1b083d67", "started"],
        ["625d6ffaf7308432be1d44c5", "completed"],
      ]),
      new Set(["5ac346a886f7744e1b083d67"]),
    );
    expect(merged.done.sort()).toEqual([
      "5ac346a886f7744e1b083d67",
      "625d6ffaf7308432be1d44c5",
    ]);
    expect(merged.started).toEqual([]);
  });

  it("records a failed attempt as failed unless the task is restartable", () => {
    const merged = applyQuestLogState(
      [],
      ["t2"],
      new Map([
        ["t1", "failed"],
        ["t2", "failed"],
      ]),
    );
    expect(merged.done).toEqual([]);
    expect(merged.started).toEqual([]);
    expect(merged.failed.sort()).toEqual(["t1", "t2"]);
  });

  it("keeps a restartable failure as in-progress", () => {
    const catalog = buildQuestLogCatalog([
      { id: "t1", restartable: true },
      { id: "t2", restartable: true },
    ]);
    const merged = applyQuestLogState(
      [],
      ["t2"],
      new Map([
        ["t1", "failed"],
        ["t2", "failed"],
      ]),
      catalog,
    );
    expect(merged.done).toEqual([]);
    expect(merged.failed).toEqual([]);
    expect(merged.started.sort()).toEqual(["t1", "t2"]);
  });

  it("fills missing historical tasks without un-completing the account", () => {
    const merged = applyQuestLogState(
      ["done"],
      ["active"],
      new Map([
        ["done", "started"],
        ["active", "failed"],
        ["old-complete", "completed"],
        ["old-start", "started"],
      ]),
    );
    expect(merged.done.sort()).toEqual(["done", "old-complete"]);
    expect(merged.started.sort()).toEqual(["old-start"]);
    expect(merged.failed).toEqual(["active"]);
  });

  it("sticks a later start/fail after a completed log and fails mutex neighbors", () => {
    const catalog = buildQuestLogCatalog([
      { id: "chem", mutex_ids: ["curio", "big"], prereq_ids: ["pre"] },
      { id: "curio", mutex_ids: ["chem", "big"] },
      { id: "big", mutex_ids: ["chem", "curio"] },
      { id: "pre" },
    ]);
    const folded = foldQuestEvents(new Map(), [
      ev("completed", "chem", "2026-01-01 10:00:00"),
      ev("started", "chem", "2026-01-01 12:00:00"),
      ev("failed", "chem", "2026-01-01 13:00:00"),
    ]);
    expect(folded.get("chem")?.kind).toBe("failed");
    expect(folded.get("chem")?.everCompleted).toBe(true);
    const merged = applyQuestLogState([], [], folded, catalog);
    expect(merged.done.sort()).toEqual(["chem", "pre"]);
    expect(merged.failed.sort()).toEqual(["big", "curio"]);
    expect(merged.started).toEqual([]);
  });

  it("does not keep the chemical-4 trio completed together", () => {
    const catalog = buildQuestLogCatalog([
      { id: "chem", mutex_ids: ["curio", "big"] },
      { id: "curio", mutex_ids: ["chem", "big"] },
      { id: "big", mutex_ids: ["chem", "curio"] },
    ]);
    const folded = foldQuestEvents(new Map(), [
      ev("completed", "chem", "2026-01-01 10:00:00"),
      ev("completed", "curio", "2026-01-01 11:00:00"),
      ev("completed", "big", "2026-01-01 12:00:00"),
    ]);
    const merged = applyQuestLogState([], [], folded, catalog);
    expect(merged.done).toEqual(["big"]);
    expect(merged.failed.sort()).toEqual(["chem", "curio"]);
    expect(merged.started).toEqual([]);
  });

  it("does not re-complete a task the user unmarked unless logs are newer", () => {
    const folded = foldQuestEvents(new Map(), [
      ev("completed", "t1", "2026-01-01 10:00:00"),
    ]);
    const cleared = new Map([["t1", "2026-01-01 12:00:00"]]);
    expect(applyQuestLogState(["t1"], [], folded, undefined, [], cleared)).toEqual({
      done: [],
      started: [],
      failed: [],
    });
    expect(
      applyQuestLogState(
        [],
        [],
        folded,
        undefined,
        [],
        new Map([["t1", "2026-01-01 09:00:00"]]),
      ).done,
    ).toEqual(["t1"]);
  });

  it("does not glue a later start after the user unmarked complete", () => {
    const folded = foldQuestEvents(new Map(), [
      ev("completed", "t1", "2026-01-01 10:00:00"),
      ev("started", "t1", "2026-01-01 13:00:00"),
    ]);
    expect(folded.get("t1")?.kind).toBe("started");
    expect(folded.get("t1")?.everCompleted).toBe(true);
    expect(folded.get("t1")?.completedAt).toBe("2026-01-01 10:00:00");
    expect(
      applyQuestLogState(
        [],
        [],
        folded,
        undefined,
        [],
        new Map([["t1", "2026-01-01 12:00:00"]]),
      ),
    ).toEqual({
      done: [],
      started: ["t1"],
      failed: [],
    });
  });

  it("drops blocked follow-ups once their blocker is done or started", () => {
    const catalog = buildQuestLogCatalog([
      { id: "bat1" },
      { id: "price2", blocked_by: ["bat1"] },
    ]);
    const folded = foldQuestEvents(new Map(), [
      ev("completed", "price2", "2026-01-01 10:00:00"),
      ev("completed", "bat1", "2026-01-01 11:00:00"),
    ]);
    expect(applyQuestLogState([], [], folded, catalog)).toEqual({
      done: ["bat1"],
      started: [],
      failed: [],
    });
  });
});

describe("collectQuestEventsFromSessions", () => {
  it("keeps only the current game mode", () => {
    const events = collectQuestEventsFromSessions(
      [
        {
          parsed: {
            events: [],
            raids: [],
            sessionMode: "regular",
            quests: [ev("completed", "pvp-q", "2026-01-01 10:00:00")],
          },
        },
        {
          parsed: {
            events: [],
            raids: [],
            sessionMode: "pve",
            quests: [ev("completed", "pve-q", "2026-01-01 11:00:00")],
          },
        },
      ],
      "pvp",
    );
    expect(events.map((row) => row.taskId)).toEqual(["pvp-q"]);
  });

  it("splits a folder that switched Session mode mid-session", () => {
    const parsed = {
      events: [],
      raids: [],
      sessionMode: "Pve",
      quests: [
        {
          kind: "completed" as const,
          taskId: "pvp-q",
          at: "2026-01-01 10:00:00",
          sessionMode: "regular",
        },
        {
          kind: "started" as const,
          taskId: "pve-q",
          at: "2026-01-01 11:00:00",
          sessionMode: "Pve",
        },
      ],
    };
    expect(
      collectQuestEventsFromSessions([{ parsed }], "pvp").map((row) => row.taskId),
    ).toEqual(["pvp-q"]);
    expect(
      collectQuestEventsFromSessions([{ parsed }], "pve").map((row) => row.taskId),
    ).toEqual(["pve-q"]);
  });
});

describe("mergeQuestProgressFromLogs", () => {
  it("replays matching sessions onto current lists", () => {
    const merged = mergeQuestProgressFromLogs(
      [],
      [],
      [
        {
          parsed: {
            events: [],
            raids: [],
            sessionMode: "pve",
            quests: [
              ev("started", "a", "2026-01-01 10:00:00"),
              ev("completed", "b", "2026-01-01 11:00:00"),
            ],
          },
        },
      ],
      "pve",
    );
    expect(merged.done).toEqual(["b"]);
    expect(merged.started).toEqual(["a"]);
    expect(merged.failed).toEqual([]);
    expect(merged.eventCount).toBe(2);
    expect(merged.latestEventAt).toBe("2026-01-01 11:00:00");
  });

  it("applies historical log tasks the account is still missing", () => {
    const merged = mergeQuestProgressFromLogs(
      ["old"],
      [],
      [
        {
          parsed: {
            events: [],
            raids: [],
            sessionMode: "pve",
            quests: [
              ev("completed", "old", "2026-01-01 10:00:00"),
              ev("started", "old", "2026-01-01 12:00:00"),
              ev("completed", "missed", "2026-01-01 09:00:00"),
              ev("started", "fresh", "2026-01-01 12:00:01"),
            ],
          },
        },
      ],
      "pve",
    );
    expect(merged.done.sort()).toEqual(["missed", "old"]);
    expect(merged.started).toEqual(["fresh"]);
    expect(merged.failed).toEqual([]);
    expect(merged.eventCount).toBe(4);
  });
});

describe("foldQuestEvents", () => {
  it("keeps the later clock when sessions arrive out of order", () => {
    const first = foldQuestEvents(
      new Map(),
      [ev("completed", "t1", "2026-01-01 12:00:00")],
    );
    const second = foldQuestEvents(first, [
      ev("started", "t1", "2026-01-01 10:00:00"),
      ev("started", "t2", "2026-01-01 11:00:00"),
    ]);
    expect(second.get("t1")).toEqual({
      kind: "completed",
      at: "2026-01-01 12:00:00",
      everCompleted: true,
      completedAt: "2026-01-01 12:00:00",
    });
    expect(second.get("t2")?.kind).toBe("started");
  });
});

describe("foldSessionQuests", () => {
  it("skips the other game mode and does not keep file text", () => {
    const skipped = foldSessionQuests(
      new Map(),
      {
        sessionMode: "pve",
        quests: [ev("completed", "pve-q", "2026-01-01 10:00:00")],
      },
      "pvp",
    );
    expect(skipped.eventCount).toBe(0);
    expect(skipped.next.size).toBe(0);

    const folded = foldSessionQuests(
      new Map(),
      {
        sessionMode: "regular",
        quests: [ev("completed", "pvp-q", "2026-01-01 10:00:00")],
      },
      "pvp",
    );
    expect(folded.eventCount).toBe(1);
    expect(folded.next.get("pvp-q")?.kind).toBe("completed");
  });

  it("keeps matching quests when the folder later switched mode", () => {
    const folded = foldSessionQuests(
      new Map(),
      {
        sessionMode: "Pve",
        quests: [
          {
            kind: "completed",
            taskId: "pvp-q",
            at: "2026-01-01 10:00:00",
            sessionMode: "regular",
          },
          {
            kind: "started",
            taskId: "pve-q",
            at: "2026-01-01 11:00:00",
            sessionMode: "Pve",
          },
        ],
      },
      "pvp",
    );
    expect(folded.eventCount).toBe(1);
    expect(folded.next.get("pvp-q")?.kind).toBe("completed");
    expect(folded.next.has("pve-q")).toBe(false);
  });

  it("does not fold seasonal quests into the PVP ledger", () => {
    const folded = foldSessionQuests(
      new Map(),
      {
        sessionMode: "seasonal",
        quests: [
          {
            kind: "completed",
            taskId: "szn-q",
            at: "2026-01-01 10:00:00",
            sessionMode: "SZN",
            profileId: "season-pmc",
          },
        ],
      },
      "pvp",
    );
    expect(folded.eventCount).toBe(0);
    expect(folded.next.size).toBe(0);
  });
});

describe("questsMatchingReplay", () => {
  it("keeps the current profile and reports drop reasons", () => {
    const parsed = {
      sessionMode: "",
      quests: [
        {
          kind: "completed" as const,
          taskId: "mine",
          at: "2026-01-01 12:00:00",
          sessionMode: "regular",
          profileId: "aaa",
        },
        {
          kind: "started" as const,
          taskId: "other",
          at: "2026-01-01 12:01:00",
          sessionMode: "regular",
          profileId: "bbb",
        },
        {
          kind: "started" as const,
          taskId: "szn",
          at: "2026-01-01 12:02:00",
          sessionMode: "seasonal",
          profileId: "aaa",
        },
        {
          kind: "started" as const,
          taskId: "blank",
          at: "2026-01-01 12:03:00",
          profileId: "aaa",
        },
      ],
      drops: [
        {
          at: "2026-01-01 11:00:00",
          reason: "json_bad" as const,
        },
        {
          at: "2026-01-01 12:04:00",
          reason: "json_bad" as const,
        },
      ],
    };
    const filter = {
      gameMode: "pvp" as const,
      profileId: "aaa",
      fromAt: "2026-01-01 12:00:00",
    };
    expect(questsMatchingReplay(parsed, filter).map((row) => row.taskId)).toEqual([
      "mine",
    ]);
    const drops = collectQuestReplayDrops(parsed, filter);
    expect(drops.map((row) => row.reason).sort()).toEqual([
      "json_bad",
      "no_session_mode",
      "profile",
      "seasonal",
    ]);
    expect(formatQuestLogDropHint(drops)).toBe(
      "丢弃 4 条：JSON 坏块 1，其他角色 1，赛季 1，无 Session mode 1",
    );
  });
});

describe("mergeQuestProgressFromFolded", () => {
  it("applies the folded map the same way as replaying sessions", () => {
    const { next, eventCount } = foldSessionQuests(
      new Map(),
      {
        sessionMode: "pve",
        quests: [
          ev("started", "a", "2026-01-01 10:00:00"),
          ev("completed", "b", "2026-01-01 11:00:00"),
        ],
      },
      "pve",
    );
    const merged = mergeQuestProgressFromFolded([], [], next, eventCount);
    expect(merged.done).toEqual(["b"]);
    expect(merged.started).toEqual(["a"]);
    expect(merged.failed).toEqual([]);
    expect(merged.eventCount).toBe(2);
    expect(merged.latestEventAt).toBe("2026-01-01 11:00:00");
  });
});

describe("formatLastQuestSyncLine", () => {
  it("prints the last sync clock", () => {
    expect(formatLastQuestSyncLine(null)).toBe("上次同步时间：—");
    expect(formatLastQuestSyncLine("2026-08-31 00:40:05")).toBe(
      "上次同步时间：2026-08-31 00:40:05",
    );
  });
});

describe("questProgressDelta", () => {
  it("reports signed bucket changes", () => {
    expect(questProgressDelta(["a"], ["b", "c"], ["a", "b"], ["c"])).toEqual({
      done: 1,
      started: -1,
      failed: 0,
      unfinished: 0,
    });
    expect(questProgressDelta([], [], ["a"], ["b", "c"])).toEqual({
      done: 1,
      started: 2,
      failed: 0,
      unfinished: -3,
    });
    expect(formatSignedDelta(3)).toBe("+3");
    expect(formatSignedDelta(-2)).toBe("-2");
    expect(formatSignedDelta(0)).toBe("0");
    expect(
      formatQuestSyncDeltaLine("incremental", {
        done: 2,
        started: -1,
        failed: 0,
        unfinished: -1,
      }),
    ).toBe("已增量同步 已完成 +2，进行中 -1，失败 0，未完成 -1");
    expect(
      formatQuestSyncDeltaLine("backfill", {
        done: 72,
        started: 14,
        failed: 0,
        unfinished: -86,
      }),
    ).toBe("已从日志回填 已完成 +72，进行中 +14，失败 0，未完成 -86");
  });
});

describe("buildQuestLogSyncReview", () => {
  it("keeps the timestamped log line and labels the status jump", () => {
    expect(
      formatQuestLogEventLine(
        ev("completed", "t1", "2026-01-01 10:00:00"),
      ),
    ).toBe("2026-01-01 10:00:00 ChatMessageReceived completed");
    expect(formatQuestLogStatusChange("todo", "done")).toBe("未完成→已完成");
    const rows = buildQuestLogSyncReview(
      [
        {
          kind: "started",
          taskId: "t1",
          at: "2026-01-01 10:00:00",
          line: "2026-01-01 10:00:00.000|x|Info|Got notification | ChatMessageReceived",
        },
        {
          kind: "completed",
          taskId: "t1",
          at: "2026-01-01 11:00:00",
          line: "2026-01-01 11:00:00.000|x|Info|Got notification | ChatMessageReceived",
        },
      ],
      { done: [], started: [], failed: [] },
      { items: [{ id: "t1", name: "惩罚者 - 1" }] },
    );
    expect(rows.map((row) => ({
      line: row.line,
      taskName: row.taskName,
      change: row.change,
    }))).toEqual([
      {
        line: "2026-01-01 10:00:00.000|x|Info|Got notification | ChatMessageReceived",
        taskName: "惩罚者 - 1",
        change: "未完成→进行中",
      },
      {
        line: "2026-01-01 11:00:00.000|x|Info|Got notification | ChatMessageReceived",
        taskName: "惩罚者 - 1",
        change: "进行中→已完成",
      },
    ]);
  });
});
