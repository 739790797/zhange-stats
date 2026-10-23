import { describe, expect, it } from "vitest";
import type { TarkovLogSessionStub } from "./tarkovGameLogs";
import {
  defaultLogSyncRange,
  filterSessionStubsByRange,
  formatCrossWipeHint,
  formatLogSyncRangeDays,
  formatLogSyncSessionCount,
  rangeStartsBeforeCurrentWipe,
  resolveLogSyncRange,
  sessionStartedAtInRange,
  sessionStubDateBounds,
  wipesTouchedBySessions,
} from "./tarkovLogSyncRange";
import type { TarkovWipeStart } from "./tarkovWipeLength";

const WIPES: TarkovWipeStart[] = [
  { name: "0.16.8.0", start: "2025-07-09T07:00:00.000Z" },
  { name: "1.0.0.0", start: "2025-11-15T09:00:00.000Z" },
];

function stub(folder: string, startedAt: string | null): TarkovLogSessionStub {
  return { folder, startedAt };
}

describe("defaultLogSyncRange", () => {
  it("defaults to every session from the earliest wipe through end of today", () => {
    const now = new Date("2026-09-05T12:00:00+08:00");
    expect(defaultLogSyncRange(now, WIPES)).toEqual({
      all: true,
      from: "2025-07-09 15:00:00",
      to: "2026-09-05 23:59:59",
    });
  });
});

describe("resolveLogSyncRange", () => {
  const now = new Date("2026-09-05T12:00:00+08:00");

  it("uses all sessions as the default preset", () => {
    expect(resolveLogSyncRange({ preset: "all" }, now, WIPES)).toEqual({
      all: true,
      from: "2025-07-09 15:00:00",
      to: "2026-09-05 23:59:59",
    });
  });

  it("keeps the current wipe as an explicit preset", () => {
    expect(resolveLogSyncRange({ preset: "wipe" }, now, WIPES)).toEqual({
      from: "2025-11-15 17:00:00",
      to: "2026-09-05 23:59:59",
    });
  });

  it("uses seven inclusive Beijing calendar days", () => {
    expect(resolveLogSyncRange({ preset: "7d" }, now, WIPES)).toEqual({
      from: "2026-08-30 00:00:00",
      to: "2026-09-05 23:59:59",
    });
  });

  it("uses thirty inclusive Beijing calendar days", () => {
    expect(resolveLogSyncRange({ preset: "30d" }, now, WIPES)).toEqual({
      from: "2026-08-07 00:00:00",
      to: "2026-09-05 23:59:59",
    });
  });

  it("turns custom dates into inclusive Beijing days and swaps inverted bounds", () => {
    expect(
      resolveLogSyncRange(
        { preset: "custom", customFrom: "2026-01-02", customTo: "2026-01-10" },
        now,
        WIPES,
      ),
    ).toEqual({
      from: "2026-01-02 00:00:00",
      to: "2026-01-10 23:59:59",
    });
    expect(
      resolveLogSyncRange(
        { preset: "custom", customFrom: "2026-02-10", customTo: "2026-02-01" },
        now,
        WIPES,
      ),
    ).toEqual({
      from: "2026-02-01 00:00:00",
      to: "2026-02-10 23:59:59",
    });
  });
});

describe("filterSessionStubsByRange", () => {
  const range = {
    from: "2025-11-15 17:00:00",
    to: "2026-09-05 23:59:59",
  };

  it("keeps folders whose startedAt falls in range, including cross-midnight starts", () => {
    const stubs = [
      stub("log_2025.11.15_16-59-59", "2025-11-15 16:59:59"),
      stub("log_2025.11.15_17-00-00", "2025-11-15 17:00:00"),
      stub("log_2026.08.30_23-50-00", "2026-08-30 23:50:00"),
      stub("log_2026.09.06_00-10-00", "2026-09-06 00:10:00"),
      stub("log_unknown", null),
    ];
    expect(
      filterSessionStubsByRange(stubs, range).map((row) => row.folder),
    ).toEqual(["log_2025.11.15_17-00-00", "log_2026.08.30_23-50-00"]);
  });

  it("keeps undated folders when the range is all", () => {
    const stubs = [
      stub("log_unknown", null),
      stub("log_2025.07.01_10-00-00", "2025-07-01 10:00:00"),
    ];
    expect(
      filterSessionStubsByRange(stubs, {
        all: true,
        from: "2017-01-01 00:00:00",
        to: "2026-09-05 23:59:59",
      }).map((row) => row.folder),
    ).toEqual(["log_unknown", "log_2025.07.01_10-00-00"]);
  });

  it("treats the range as inclusive on both ends", () => {
    expect(sessionStartedAtInRange("2025-11-15 17:00:00", range)).toBe(true);
    expect(sessionStartedAtInRange("2026-09-05 23:59:59", range)).toBe(true);
    expect(sessionStartedAtInRange("2025-11-15 16:59:59", range)).toBe(false);
  });
});

describe("sessionStubDateBounds", () => {
  it("reads min/max calendar days from folder clocks", () => {
    expect(
      sessionStubDateBounds([
        stub("b", "2026-03-02 01:00:00"),
        stub("a", "2026-01-10 22:00:00"),
        stub("skip", null),
      ]),
    ).toEqual({ min: "2026-01-10", max: "2026-03-02" });
  });
});

describe("rangeStartsBeforeCurrentWipe", () => {
  const now = new Date("2026-09-05T12:00:00+08:00");

  it("flags a custom range that reaches into the previous wipe", () => {
    expect(
      rangeStartsBeforeCurrentWipe(
        { from: "2025-11-15 16:59:59", to: "2026-09-05 23:59:59" },
        now,
        WIPES,
      ),
    ).toBe(true);
    expect(
      rangeStartsBeforeCurrentWipe(
        { from: "2025-11-15 17:00:00", to: "2026-09-05 23:59:59" },
        now,
        WIPES,
      ),
    ).toBe(false);
  });
});

describe("formatLogSyncSessionCount", () => {
  it("prints the folder count the modal shows", () => {
    expect(formatLogSyncSessionCount(18)).toBe("约 18 次启动");
    expect(formatLogSyncRangeDays({
      from: "2025-11-15 17:00:00",
      to: "2026-09-05 23:59:59",
    })).toBe("2025-11-15 ～ 2026-09-05");
    expect(formatLogSyncRangeDays({
      all: true,
      from: "2017-01-01 00:00:00",
      to: "2026-09-05 23:59:59",
    })).toBe("全部");
  });
});

describe("wipesTouchedBySessions", () => {
  it("names every wipe that has a dated session", () => {
    const wipes = wipesTouchedBySessions(
      [
        stub("old", "2025-07-10 12:00:00"),
        stub("now", "2026-01-02 08:00:00"),
        stub("skip", null),
      ],
      WIPES,
    );
    expect(wipes.map((row) => row.name)).toEqual(["0.16.8.0", "1.0.0.0"]);
    expect(formatCrossWipeHint(wipes)).toContain("0.16.8.0");
    expect(formatCrossWipeHint(wipes)).toContain("1.0.0.0");
    expect(formatCrossWipeHint(wipes.slice(0, 1))).toBe("");
  });
});
