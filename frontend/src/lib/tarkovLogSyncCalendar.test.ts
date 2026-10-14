import { describe, expect, it } from "vitest";
import type { TarkovLogSessionStub } from "./tarkovGameLogs";
import {
  accountArchiveFromFloor,
  launchCountByDay,
  launchOverlapsArchive,
  logSyncCalendarLaunches,
  previewRaidsFromParsed,
  raidArchiveAllowed,
  raidArchiveFrom,
} from "./tarkovLogSyncCalendar";

const PROFILE = "aa11bb22cc33dd44ee55ff66";

function session(patch: Partial<TarkovLogSessionStub> & Pick<TarkovLogSessionStub, "folder" | "startedAt">): TarkovLogSessionStub {
  return {
    identities: [
      {
        at: patch.startedAt || "",
        sessionMode: "Pve",
        profileId: PROFILE,
        accountId: "1",
        version: "1.0.0",
      },
    ],
    raids: [],
    ...patch,
  };
}

describe("logSyncCalendarLaunches", () => {
  it("counts only the current mode and numbers launches within the Beijing day", () => {
    const launches = logSyncCalendarLaunches(
      [
        session({
          folder: "a",
          startedAt: "2026-08-16 09:00:00",
          raids: [
            {
              key: "r1",
              mapId: "customs",
              mapLabel: "海关",
              startedAt: "2026-08-16 09:10:00",
              endedAt: "2026-08-16 09:40:00",
              raidId: "AAAAAA",
              sessionMode: "Pve",
            },
          ],
        }),
        session({
          folder: "b",
          startedAt: "2026-08-16 21:00:00",
          identities: [
            {
              at: "2026-08-16 21:00:00",
              sessionMode: "regular",
              profileId: PROFILE,
              accountId: "1",
              version: "1.0.0",
            },
          ],
        }),
        session({ folder: "c", startedAt: "2026-08-17 01:05:00" }),
      ],
      "pve",
    );
    expect(launches.map((row) => [row.day, row.index, row.folder])).toEqual([
      ["2026-08-16", 1, "a"],
      ["2026-08-17", 1, "c"],
    ]);
    expect(launchCountByDay(launches).get("2026-08-16")).toBe(1);
    expect(launches[0]?.raids.map((raid) => raid.mapLabel)).toEqual(["海关"]);
  });
});

describe("previewRaidsFromParsed", () => {
  it("drops aborted matches that never started and stamps the mode active at that time", () => {
    const raids = previewRaidsFromParsed(
      {
        raids: [
          {
            raidId: "",
            location: "",
            mapId: "",
            mapLabel: "未知地图",
            raidMode: "unknown",
            aborted: true,
          },
          {
            raidId: "PQXKR6",
            location: "Shoreline",
            mapId: "shoreline",
            mapLabel: "海岸线",
            raidMode: "online",
            startedAt: "2026-08-16 10:00:00",
            endedAt: "",
          },
        ],
      },
      [
        {
          at: "2026-08-16 09:00:00",
          sessionMode: "Pve",
          profileId: PROFILE,
          accountId: "1",
          version: "1.0.0",
        },
      ],
    );
    expect(raids).toEqual([
      {
        key: "PQXKR6|2026-08-16 10:00:00|shoreline",
        mapId: "shoreline",
        mapLabel: "海岸线",
        startedAt: "2026-08-16 10:00:00",
        endedAt: "",
        raidId: "PQXKR6",
        sessionMode: "Pve",
      },
    ]);
  });
});

describe("launchOverlapsArchive", () => {
  it("skips a launch whose next launch is already before the floor", () => {
    expect(
      launchOverlapsArchive(
        "2026-09-01 10:00:00",
        "2026-09-02 10:00:00",
        "2026-09-09 00:08:13",
      ),
    ).toBe(false);
  });

  it("keeps the launch that crosses the floor and later launches", () => {
    expect(
      launchOverlapsArchive(
        "2026-09-08 21:00:00",
        "2026-09-09 10:00:00",
        "2026-09-09 00:08:13",
      ),
    ).toBe(true);
    expect(
      launchOverlapsArchive("2026-09-10 08:00:00", "", "2026-09-09 00:08:13"),
    ).toBe(true);
  });
});

describe("accountArchiveFromFloor", () => {
  it("uses the latest raid still before the account floor, on that launch's calendar day", () => {
    const launches = logSyncCalendarLaunches(
      [
        session({
          folder: "sept8",
          startedAt: "2026-09-08 21:00:00",
          raids: [
            {
              key: "early",
              mapId: "lighthouse",
              mapLabel: "灯塔",
              startedAt: "2026-09-08 23:01:10",
              endedAt: "2026-09-08 23:32:45",
              raidId: "A",
              sessionMode: "Pve",
            },
            {
              key: "streets",
              mapId: "streets",
              mapLabel: "塔科夫街区",
              startedAt: "2026-09-09 00:02:08",
              endedAt: "2026-09-09 00:08:12",
              raidId: "B",
              sessionMode: "Pve",
            },
          ],
        }),
        session({
          folder: "later",
          startedAt: "2026-09-09 18:00:00",
          raids: [
            {
              key: "after",
              mapId: "customs",
              mapLabel: "海关",
              startedAt: "2026-09-09 18:10:00",
              endedAt: "2026-09-09 18:40:00",
              raidId: "C",
              sessionMode: "Pve",
            },
          ],
        }),
      ],
      "pve",
    );
    expect(accountArchiveFromFloor(launches, "2026-09-09 00:08:13")).toEqual({
      day: "2026-09-08",
      raidAt: "2026-09-09 00:02:08",
      raidKey: "sept8|streets",
    });
  });
});

describe("raidArchiveFrom", () => {
  it("starts the next replay one second after the raid ends, including that raid", () => {
    expect(
      raidArchiveFrom({
        startedAt: "2026-08-16 10:00:00",
        endedAt: "2026-08-16 10:32:18",
      }),
    ).toEqual({ at: "2026-08-16 10:32:19", approximate: false });
  });

  it("uses the start when the raid has no end time", () => {
    expect(raidArchiveFrom({ startedAt: "2026-08-16 10:00:00", endedAt: "" })).toEqual({
      at: "2026-08-16 10:00:01",
      approximate: true,
    });
    expect(raidArchiveFrom({ startedAt: "", endedAt: "" })).toBeNull();
  });

  it("refuses a cutoff that is not later than the stored floor", () => {
    expect(raidArchiveAllowed("2026-08-16 10:32:19", "")).toBe(true);
    expect(raidArchiveAllowed("2026-08-16 10:32:19", "2026-08-16 10:32:19")).toBe(false);
    expect(raidArchiveAllowed("2026-08-16 11:00:00", "2026-08-16 10:32:19")).toBe(true);
  });
});
