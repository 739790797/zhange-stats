import { describe, expect, it } from "vitest";
import {
  accountHasQuestState,
  applyQuestLogState,
  collectQuestEventsFromSessions,
  foldQuestEvents,
  foldSessionQuests,
  formatLastQuestSyncLine,
  formatQuestSyncDeltaLine,
  formatSignedDelta,
  mergeQuestProgressFromFolded,
  questProgressDelta,
  mergeQuestProgressFromLogs,
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
  it("maps regular / pvp / pve and treats blank as current mode", () => {
    expect(sessionModeMatchesGameMode("regular", "pvp")).toBe(true);
    expect(sessionModeMatchesGameMode("pvp", "pvp")).toBe(true);
    expect(sessionModeMatchesGameMode("pve", "pve")).toBe(true);
    expect(sessionModeMatchesGameMode("pve", "pvp")).toBe(false);
    expect(sessionModeMatchesGameMode("regular", "pve")).toBe(false);
    expect(sessionModeMatchesGameMode("", "pve")).toBe(true);
    expect(sessionModeMatchesGameMode(undefined, "pvp")).toBe(true);
    expect(sessionModeMatchesGameMode("seasonal", "pvp")).toBe(true);
    expect(sessionModeMatchesGameMode("seasonal", "pve")).toBe(false);
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
    expect(state.get("t1")).toBe("completed");
    expect(state.get("t2")).toBe("failed");
  });
});

describe("accountHasQuestState", () => {
  it("treats done as covering start/fail, and only done as covering complete", () => {
    const done = new Set(["done"]);
    const started = new Set(["active"]);
    expect(accountHasQuestState(done, started, "done", "completed")).toBe(true);
    expect(accountHasQuestState(done, started, "done", "started")).toBe(true);
    expect(accountHasQuestState(done, started, "active", "started")).toBe(true);
    expect(accountHasQuestState(done, started, "active", "failed")).toBe(true);
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

  it("keeps a failed attempt as in-progress instead of wiping it", () => {
    const merged = applyQuestLogState(
      [],
      ["t2"],
      new Map([
        ["t1", "failed"],
        ["t2", "failed"],
      ]),
    );
    expect(merged.done).toEqual([]);
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
    expect(merged.started.sort()).toEqual(["active", "old-start"]);
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
      unfinished: 0,
    });
    expect(questProgressDelta([], [], ["a"], ["b", "c"])).toEqual({
      done: 1,
      started: 2,
      unfinished: -3,
    });
    expect(formatSignedDelta(3)).toBe("+3");
    expect(formatSignedDelta(-2)).toBe("-2");
    expect(formatSignedDelta(0)).toBe("0");
    expect(
      formatQuestSyncDeltaLine("incremental", {
        done: 2,
        started: -1,
        unfinished: -1,
      }),
    ).toBe("已增量同步 已完成 +2，进行中 -1，未完成 -1");
    expect(
      formatQuestSyncDeltaLine("backfill", {
        done: 72,
        started: 14,
        unfinished: -86,
      }),
    ).toBe("已从日志回填 已完成 +72，进行中 +14，未完成 -86");
  });
});
