import { describe, expect, it } from "vitest";
import {
  addedIdList,
  formatLiveWatchLogLine,
  formatLiveWatchShotLine,
  formatPollClock,
  logStampFromParsed,
  nextLiveQuestProgress,
  planLogSessionReads,
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
    expect(
      planLogSessionReads("a", "f1", { folder: "a", fingerprint: "f1" }),
    ).toEqual({ skip: true, folders: [] });
    expect(
      planLogSessionReads("a", "f2", { folder: "a", fingerprint: "f1" }),
    ).toEqual({ skip: false, folders: ["a"] });
    expect(
      planLogSessionReads("b", "f2", { folder: "a", fingerprint: "f1" }),
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

  it("ignores log events at or before the cursor", () => {
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
        undefined,
        "2026-01-01 10:00:00",
      ),
    ).toMatchObject({
      done: ["keep"],
      started: [],
      changed: false,
      eventCount: 0,
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
