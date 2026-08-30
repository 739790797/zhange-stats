import { describe, expect, it } from "vitest";
import {
  buildRaidsFromEvents,
  classifyLogsRoot,
  classifyScreenshotsRoot,
  formatBindPath,
  formatLatestLogPreview,
  formatLogClock,
  latestLogActivityAt,
  latestLogMapId,
  formatResolvedWalk,
  hasDriveLetter,
  joinBindPath,
  mergeBindPath,
  historyRaidsFromSessions,
  isApplicationLogFileName,
  isNotificationsLogFileName,
  isReadableTarkovLogFileName,
  isNewerScreenshot,
  isScreenshotFileName,
  screenshotNamesToInspect,
  screenshotPollHint,
  isSessionFolderName,
  logWalkCandidatesFrom,
  listSessionStubs,
  logEventLabel,
  logMapHref,
  logMapLabel,
  mapLogLocationToMapId,
  mapLogSceneToMapId,
  parseLogRaidMode,
  parseSessionFolderTime,
  parseTarkovLogBundle,
  parseTarkovLogText,
  taskIdFromQuestTemplate,
  raidModeLabel,
  screenshotWalkCandidatesFrom,
  sessionModeLabel,
  takeSessionStubs,
  toRaidLogImportRows,
} from "./tarkovGameLogs";

const MATCH_LINE =
  "2023-12-29 19:03:20.911 +01:00|0.14.0.0.28375|Debug|application|TRACE-NetworkGameCreate profileStatus: 'Profileid: 60008306b4df3523a949cf7b, Status: Busy, RaidMode: Online, Ip: 37.19.203.86, Port: 17003, Location: Shoreline, Sid: 37.19.203.86-17003_PID_29.12.23_18.01.18, GameMode: deathmatch, shortId: PQXKR6'";

const NIGHT_FACTORY_LINE =
  "2026-08-30 20:11:02.100|0.16.0.0.40000|Debug|application|TRACE-NetworkGameCreate profileStatus: 'RaidMode: Online, Location: factory4_night, shortId: AB12CD'";

describe("session folder names", () => {
  it("parses TarkovMonitor-style log folders", () => {
    expect(isSessionFolderName("log_2023.12.29_19-03-20_0.14.0.0.28375")).toBe(
      true,
    );
    expect(parseSessionFolderTime("log_2021.03.09_17-48-09_0.12.9.10988")).toBe(
      "2021-03-09 17:48:09",
    );
    expect(parseSessionFolderTime("log_2026.08.30_8-01-02")).toBe(
      "2026-08-30 08:01:02",
    );
    expect(isSessionFolderName("Settings")).toBe(false);
  });

  it("recognizes rotated application / notifications files", () => {
    expect(isApplicationLogFileName("application.log")).toBe(true);
    expect(
      isApplicationLogFileName(
        "2025.01.20_14-30-45_192.168.1.100 application_000.log",
      ),
    ).toBe(true);
    expect(isNotificationsLogFileName("notifications.log")).toBe(true);
    expect(isReadableTarkovLogFileName("output.log")).toBe(false);
  });
});

describe("classifyLogsRoot", () => {
  it("detects Logs, install root, or a single session folder", () => {
    expect(
      classifyLogsRoot(["log_2026.08.30_20-00-00", "log_2026.08.29_10-00-00"]),
    ).toBe("logs");
    expect(classifyLogsRoot(["Logs", "EscapeFromTarkov.exe"])).toBe("install");
    expect(classifyLogsRoot(["build", "EscapeFromTarkov.exe"])).toBe("install");
    expect(classifyLogsRoot(["steamapps"])).toBe("install");
    expect(classifyLogsRoot(["application.log", "notifications.log"])).toBe(
      "session",
    );
    expect(classifyLogsRoot(["readme.txt"])).toBe("unknown");
  });

  it("walks Steam build/Logs and Documents/Screenshots", () => {
    expect(logWalkCandidatesFrom(["build", "BattlEye"])).toEqual([
      ["build", "Logs"],
    ]);
    expect(
      logWalkCandidatesFrom(["Escape from Tarkov", "steam.dll"])[0],
    ).toEqual(["Escape from Tarkov", "build", "Logs"]);
    expect(logWalkCandidatesFrom(["steamapps"])[0]).toEqual([
      "steamapps",
      "common",
      "Escape from Tarkov",
      "build",
      "Logs",
    ]);
    expect(
      screenshotWalkCandidatesFrom(["Escape from Tarkov", "My Games"]),
    ).toEqual([["Escape from Tarkov", "Screenshots"]]);
    expect(
      screenshotWalkCandidatesFrom(["2026-08-30_12-00-00.png", "note.txt"]),
    ).toEqual([[]]);
    expect(classifyScreenshotsRoot(["Screenshots"])).toBe("ancestor");
    expect(isScreenshotFileName("raid.jpg")).toBe(true);
    expect(
      isNewerScreenshot(
        { name: "a.png", lastModified: 10 },
        { name: "b.png", lastModified: 20 },
      ),
    ).toBe(true);
    expect(
      screenshotNamesToInspect(
        ["old.png", "2026-08-30[21-35]_19.91 (0).png", "note.txt"],
        new Set(),
        1,
      ),
    ).toEqual(["2026-08-30[21-35]_19.91 (0).png"]);
    expect(
      screenshotNamesToInspect(
        ["old.png", "2026-08-30[21-35]_19.91 (0).png"],
        new Set(["old.png"]),
      ),
    ).toEqual(["2026-08-30[21-35]_19.91 (0).png"]);
    expect(screenshotPollHint(2000)).toBe("每 2 秒检查新截图");
    expect(
      formatResolvedWalk("Escape from Tarkov", ["build", "Logs"]),
    ).toBe("Escape from Tarkov / build / Logs");
    expect(formatBindPath("Escape from Tarkov", ["build", "Logs"])).toBe(
      "Escape from Tarkov\\build\\Logs",
    );
    expect(formatBindPath("Screenshots", [])).toBe("Screenshots");
    expect(formatBindPath("D:", ["Steam", "steamapps"])).toBe(
      "D:\\Steam\\steamapps",
    );
    expect(hasDriveLetter("D:\\Steam\\Logs")).toBe(true);
    expect(joinBindPath(["D:", "Steam", "Logs"])).toBe("D:\\Steam\\Logs");
    expect(
      mergeBindPath(
        "D:\\Steam\\steamapps\\common\\Escape from Tarkov\\build\\Logs",
        "Steam\\steamapps\\common\\Escape from Tarkov\\build\\Logs",
      ),
    ).toBe("D:\\Steam\\steamapps\\common\\Escape from Tarkov\\build\\Logs");
    expect(
      mergeBindPath(
        "D:\\Steam",
        "Steam\\steamapps\\common\\Escape from Tarkov\\build\\Logs",
      ),
    ).toBe("D:\\Steam\\steamapps\\common\\Escape from Tarkov\\build\\Logs");
    expect(
      mergeBindPath(
        "C:\\Users\\BaiYi\\Documents\\Escape from Tarkov\\Screenshots",
        "Escape from Tarkov\\Screenshots",
      ),
    ).toBe("C:\\Users\\BaiYi\\Documents\\Escape from Tarkov\\Screenshots");
    expect(
      mergeBindPath(
        "D:\\Steam\\steamapps\\common\\Escape from Tarkov\\build\\Logs",
        "Documents\\Escape from Tarkov\\Screenshots",
      ),
    ).toBe("Documents\\Escape from Tarkov\\Screenshots");
  });

  it("lists session stubs newest first", () => {
    const stubs = listSessionStubs([
      "log_2026.08.29_10-00-00",
      "log_2026.08.30_20-00-00",
      "Settings",
    ]);
    expect(stubs.map((row) => row.folder)).toEqual([
      "log_2026.08.30_20-00-00",
      "log_2026.08.29_10-00-00",
    ]);
    expect(takeSessionStubs(stubs, 1)).toHaveLength(1);
    expect(takeSessionStubs(stubs, 0)).toHaveLength(2);
  });
});

describe("map locations", () => {
  it("maps nameId, display name, and scene bundles", () => {
    expect(mapLogLocationToMapId("Shoreline")).toBe("shoreline");
    expect(mapLogLocationToMapId("bigmap")).toBe("customs");
    expect(mapLogLocationToMapId("factory4_night")).toBe("night-factory");
    expect(mapLogLocationToMapId("Sandbox_high")).toBe("ground-zero");
    expect(mapLogLocationToMapId("The Lab")).toBe("lab");
    expect(mapLogSceneToMapId("maps/tarkovstreets.bundle")).toBe("streets");
    expect(logMapLabel("night-factory")).toBe("夜间工厂");
    expect(logMapHref("night-factory")).toBe("/guides/tarkov/maps/factory");
    expect(logMapHref("customs")).toBe("/guides/tarkov/maps/customs");
  });
});

describe("parseTarkovLogText", () => {
  it("extracts raid identity without keeping the server IP", () => {
    const parsed = parseTarkovLogText(
      [
        "2023-12-29 19:03:00.000 +01:00|0.14.0.0.28375|Info|application|Session mode: regular",
        "2023-12-29 19:03:10.000 +01:00|0.14.0.0.28375|Info|application|scene preset path:maps/shoreline.bundle",
        "2023-12-29 19:03:20.711 +01:00|0.14.0.0.28375|Info|application|LocationLoaded:66.88 real:77.66",
        MATCH_LINE,
        "2023-12-29 19:03:21.000 +01:00|0.14.0.0.28375|Info|application|GameStarting",
        "2023-12-29 19:03:40.000 +01:00|0.14.0.0.28375|Info|application|GameStarted",
      ].join("\n"),
    );
    expect(parsed.sessionMode).toBe("regular");
    expect(parsed.raids).toHaveLength(1);
    expect(parsed.raids[0]).toMatchObject({
      raidId: "PQXKR6",
      location: "Shoreline",
      mapId: "shoreline",
      mapLabel: "海岸线",
      raidMode: "online",
      startedAt: "2023-12-29 19:03:40.000",
    });
    expect(JSON.stringify(parsed.raids)).not.toContain("37.19.203.86");
    expect(parsed.events.some((event) => event.kind === "match_found")).toBe(
      true,
    );
    expect(latestLogMapId(parsed)).toBe("shoreline");
  });

  it("reads quest start / fail / complete from ChatMessageReceived", () => {
    expect(taskIdFromQuestTemplate("5ac346a886f7744e1b083d67 description")).toBe(
      "5ac346a886f7744e1b083d67",
    );
    const parsed = parseTarkovLogBundle([
      {
        name: "application.log",
        text: "2024-02-05 19:00:00.000|x|Info|application|Session mode: regular",
      },
      {
        name: "notifications.log",
        text: [
          "2024-02-05 19:03:08.398|x|Info|push-notifications|Got notification | ChatMessageReceived",
          '{ "type": "new_message", "message": { "type": 10, "templateId": "5ac346a886f7744e1b083d67 description" } }',
          "2024-02-05 19:04:00.000|x|Info|push-notifications|Got notification | ChatMessageReceived",
          '{ "type": "new_message", "message": { "type": 12, "templateId": "5ac346a886f7744e1b083d67 description" } }',
          "2024-02-05 19:05:00.000|x|Info|push-notifications|Got notification | ChatMessageReceived",
          '{ "type": "new_message", "message": { "type": 4, "templateId": "5bdabfb886f7743e152e867e 0" } }',
        ].join("\n"),
      },
    ]);
    expect(parsed.sessionMode).toBe("regular");
    expect(parsed.quests).toEqual([
      {
        kind: "started",
        at: "2024-02-05 19:03:08.398",
        taskId: "5ac346a886f7744e1b083d67",
      },
      {
        kind: "completed",
        at: "2024-02-05 19:04:00.000",
        taskId: "5ac346a886f7744e1b083d67",
      },
    ]);
    expect(latestLogActivityAt(parsed)).toBe("2024-02-05 19:04:00.000");
  });

  it("closes a raid from notifications UserMatchOver JSON", () => {
    const parsed = parseTarkovLogBundle([
      {
        name: "application.log",
        text: [MATCH_LINE, "2023-12-29 19:03:40.000|x|Info|application|GameStarted"].join(
          "\n",
        ),
      },
      {
        name: "notifications.log",
        text: [
          "2023-12-29 19:41:00.000|x|Info|notifications|Got notification | UserMatchOver",
          '{ "location": "Shoreline", "shortId": "PQXKR6" }',
        ].join("\n"),
      },
    ]);
    expect(parsed.raids[0]).toMatchObject({
      raidId: "PQXKR6",
      endedAt: "2023-12-29 19:41:00.000",
      mapId: "shoreline",
    });
  });

  it("marks cancelled matching and night factory", () => {
    const parsed = parseTarkovLogText(
      [
        "2026-08-30 20:10:00.000|x|Info|application|scene preset path:maps/factory4_night.bundle",
        "2026-08-30 20:10:30.000|x|Info|application|Network game matching cancelled",
        NIGHT_FACTORY_LINE,
        "2026-08-30 20:11:10.000|x|Info|application|GameStarted",
      ].join("\n"),
    );
    expect(parsed.raids.some((raid) => raid.aborted)).toBe(true);
    const live = parsed.raids.find((raid) => raid.raidId === "AB12CD");
    expect(live).toMatchObject({
      mapId: "night-factory",
      mapLabel: "夜间工厂",
      startedAt: "2026-08-30 20:11:10.000",
    });
  });

  it("marks reconnects on the same shortId", () => {
    const events = parseTarkovLogText(
      [MATCH_LINE, MATCH_LINE.replace("19:03:20.911", "19:20:00.000")].join(
        "\n",
      ),
    ).events;
    const raids = buildRaidsFromEvents(events);
    expect(raids).toHaveLength(1);
    expect(raids[0].reconnected).toBe(true);
  });
});

describe("history helpers", () => {
  it("flattens raids newest first and skips empty aborts", () => {
    const rows = historyRaidsFromSessions([
      {
        folder: "log_new",
        parsed: {
          events: [],
          raids: [
            {
              raidId: "ZZZZZZ",
              location: "Woods",
              mapId: "woods",
              mapLabel: "森林",
              raidMode: "online",
              startedAt: "2026-08-30 21:00:00.000",
            },
          ],
        },
      },
      {
        folder: "log_old",
        parsed: {
          events: [],
          raids: [
            {
              raidId: "",
              location: "",
              mapId: "",
              mapLabel: "未知地图",
              raidMode: "unknown",
              aborted: true,
            },
          ],
        },
      },
    ]);
    expect(rows).toHaveLength(1);
    expect(rows[0].folder).toBe("log_new");
  });

  it("projects import rows without extra fields", () => {
    const rows = toRaidLogImportRows([
      {
        folder: "log_new",
        parsed: {
          events: [],
          sessionMode: "regular",
          raids: [
            {
              raidId: "ABCDEF",
              location: "Woods",
              mapId: "woods",
              mapLabel: "森林",
              raidMode: "online",
              startedAt: "2026-08-30 21:00:00.000",
            },
          ],
        },
      },
    ]);
    expect(rows).toEqual([
      {
        folder: "log_new",
        raid_id: "ABCDEF",
        location: "Woods",
        map_id: "woods",
        map_label: "森林",
        raid_mode: "online",
        session_mode: "regular",
        started_at: "2026-08-30 21:00:00.000",
        ended_at: "",
        reconnected: false,
        aborted: false,
      },
    ]);
  });

  it("formats clocks and labels", () => {
    expect(formatLogClock("2023-12-29 19:03:40.000")).toBe(
      "2023-12-29 19:03:40",
    );
    expect(raidModeLabel("offline")).toBe("离线");
    expect(sessionModeLabel("pve")).toBe("PvE");
    expect(logEventLabel("raid_started")).toBe("开战");
    expect(parseLogRaidMode("Local")).toBe("offline");
    expect(
      formatLatestLogPreview(
        { folder: "log_2026.08.30_20-00-00", startedAt: "2026-08-30 20:00:00" },
        {
          events: [
            {
              kind: "raid_started",
              at: "2026-08-30 20:11:10.000",
              mapLabel: "夜间工厂",
            },
          ],
          raids: [],
        },
      ),
    ).toBe("2026-08-30 20:11:10 开战 · 夜间工厂");
    expect(
      formatLatestLogPreview({
        folder: "log_2026.08.30_20-00-00",
        startedAt: "2026-08-30 20:00:00",
      }),
    ).toBe("2026-08-30 20:00:00");
  });
});
