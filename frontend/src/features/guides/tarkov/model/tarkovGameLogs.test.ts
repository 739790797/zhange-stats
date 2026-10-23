import { describe, expect, it } from "vitest";
import {
  logTextGrownFrom,
  readTarkovLogText,
  type TarkovLogTextEntry,
} from "./tarkovLogTextCache";
import {
  buildRaidsFromEvents,
  classifyLogsRoot,
  classifyLogSessionMode,
  formatBindPath,
  formatLatestLogPreview,
  formatLogClock,
  latestLogActivityAt,
  latestLogMapId,
  logPhaseFromParsed,
  hasDriveLetter,
  joinBindPath,
  mergeBindPath,
  historyRaidsFromSessions,
  identitiesFromParsed,
  isApplicationLogFileName,
  isNotificationsLogFileName,
  isOutputLogFileName,
  isReadableTarkovLogFileName,
  isNewerScreenshot,
  isScreenshotFileName,
  isTarkovGameScreenshotName,
  latestScreenshotName,
  parseScreenshotPrunePref,
  screenshotNamesToInspect,
  screenshotNamesToPrune,
  screenshotPruneVerifyResult,
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
  versionFromLogLine,
  logClockToBeijing,
  folderTimeToBeijing,
  sessionStubInBeijing,
  type TarkovLogBundleMemo,
} from "./tarkovGameLogs";

const MATCH_LINE =
  "2023-12-29 19:03:20.911 +08:00|0.14.0.0.28375|Debug|application|TRACE-NetworkGameCreate profileStatus: 'Profileid: 60008306b4df3523a949cf7b, Status: Busy, RaidMode: Online, Ip: 37.19.203.86, Port: 17003, Location: Shoreline, Sid: 37.19.203.86-17003_PID_29.12.23_18.01.18, GameMode: deathmatch, shortId: PQXKR6'";

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
    expect(
      isNotificationsLogFileName(
        "2026.08.31_19-08-07_1.1.0.1.46911 push-notifications_000.log",
      ),
    ).toBe(true);
    expect(isNotificationsLogFileName("notifications_001.log")).toBe(true);
    expect(isApplicationLogFileName("application_002.log")).toBe(true);
    expect(isReadableTarkovLogFileName("output.log")).toBe(true);
    expect(isOutputLogFileName("output.log")).toBe(true);
    expect(isOutputLogFileName("output_001.log")).toBe(true);
    expect(isOutputLogFileName("notifications.log")).toBe(false);
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
    expect(isScreenshotFileName("raid.jpg")).toBe(true);
    expect(
      isNewerScreenshot(
        { name: "a.png", lastModified: 10 },
        { name: "b.png", lastModified: 20 },
      ),
    ).toBe(true);
    expect(latestScreenshotName(["old.png", "2026-08-30[21-35]_19.91 (0).png"])).toBe(
      "2026-08-30[21-35]_19.91 (0).png",
    );
    expect(
      latestScreenshotName([
        "2026-08-30[21-35]_19.91 (0).png",
        "2026-08-30[21-36]_20.00 (0).png",
      ]),
    ).toBe("2026-08-30[21-36]_20.00 (0).png");
    expect(isTarkovGameScreenshotName("2026-08-30[21-35]_19.91 (0).png")).toBe(
      true,
    );
    expect(isTarkovGameScreenshotName("vacation.jpg")).toBe(false);
    expect(
      screenshotNamesToInspect(
        ["old.png", "2026-08-30[21-35]_19.91 (0).png", "note.txt"],
        new Set(),
      ),
    ).toEqual(["2026-08-30[21-35]_19.91 (0).png"]);
    expect(
      screenshotNamesToInspect(
        [
          "2026-08-30[21-35]_19.91 (0).png",
          "2026-08-30[21-36]_20.00 (0).png",
        ],
        new Set(),
      ),
    ).toEqual(["2026-08-30[21-35]_19.91 (0).png", "2026-08-30[21-36]_20.00 (0).png"]);
    // 同一分钟两张：字符串序会把 14.31 排在 175.30 前；按修改时间才是真新旧，两张都要看
    expect(
      screenshotNamesToInspect(
        [
          { name: "2026-08-30[21-36]_14.31 (0).png", lastModified: 2000 },
          { name: "2026-08-30[21-36]_175.30 (0).png", lastModified: 1000 },
        ],
        new Set(),
      ),
    ).toEqual(["2026-08-30[21-36]_175.30 (0).png", "2026-08-30[21-36]_14.31 (0).png"]);
    // 一位数小时：9 点早于 10 点，不能按字符串比
    expect(
      latestScreenshotName(["2026-08-30[9-59]_1.00 (0).png", "2026-08-30[10-01]_1.00 (0).png"]),
    ).toBe("2026-08-30[10-01]_1.00 (0).png");
    expect(
      screenshotNamesToPrune(
        ["2026-08-30[9-59]_1.00 (0).png", "2026-08-30[10-01]_1.00 (0).png"],
        null,
        1,
      ),
    ).toEqual(["2026-08-30[9-59]_1.00 (0).png"]);
    expect(
      screenshotNamesToInspect(
        ["old.png", "2026-08-30[21-35]_19.91 (0).png"],
        new Set(["2026-08-30[21-35]_19.91 (0).png"]),
      ),
    ).toEqual([]);
    expect(
      screenshotNamesToPrune(
        [
          "vacation.jpg",
          "2026-08-30[21-35]_19.91 (0).png",
          "2026-08-30[21-36]_20.00 (0).png",
        ],
        "2026-08-30[21-36]_20.00 (0).png",
        1,
      ),
    ).toEqual(["2026-08-30[21-35]_19.91 (0).png"]);
    expect(
      screenshotNamesToPrune(
        [
          "2026-08-30[21-34]_1.png",
          "2026-08-30[21-35]_2.png",
          "2026-08-30[21-36]_3.png",
        ],
        "2026-08-30[21-36]_3.png",
        2,
      ),
    ).toEqual(["2026-08-30[21-34]_1.png"]);
    expect(
      screenshotNamesToPrune(
        [
          "2026-08-30[21-34]_1.png",
          "2026-08-30[21-35]_2.png",
          "2026-08-30[21-36]_3.png",
        ],
        "2026-08-30[21-36]_3.png",
        20,
      ),
    ).toEqual([]);
    const thirtyFour = Array.from({ length: 34 }, (_, index) => {
      const stamp = String(index).padStart(2, "0");
      return `2026-08-31[20-${stamp}]_${index}.jpg`;
    });
    expect(
      screenshotNamesToPrune(thirtyFour, thirtyFour[33]!, 20),
    ).toHaveLength(14);
    expect(
      screenshotNamesToPrune(
        [thirtyFour[0]!, thirtyFour[33]!],
        thirtyFour[33]!,
        20,
      ),
    ).toEqual([]);
    expect(parseScreenshotPrunePref(null).enabled).toBe(false);
    expect(parseScreenshotPrunePref('{"enabled":true,"keepMax":8}')).toEqual({
      enabled: true,
      keepMax: 8,
    });
    expect(screenshotPruneVerifyResult({ pruneEnabled: false, canWrite: false })).toEqual({
      ok: true,
      text: "截图目录校验通过",
    });
    expect(screenshotPruneVerifyResult({ pruneEnabled: true, canWrite: false })).toEqual({
      ok: false,
      text: "自动删截图需要写入授权。请点「更换」重新选择 Screenshots 文件夹，并在弹窗里允许查看并编辑。",
    });
    expect(screenshotPruneVerifyResult({ pruneEnabled: true, canWrite: true }).ok).toBe(
      true,
    );
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

describe("logClockToBeijing", () => {
  it("converts the game's local offset to the Beijing wall clock", () => {
    expect(logClockToBeijing("2023-12-29 19:03:40.000", "+", "01", "00")).toBe(
      "2023-12-30 02:03:40.000",
    );
    expect(logClockToBeijing("2026-10-13 09:30:00.250", "-", "05", "00")).toBe(
      "2026-10-13 22:30:00.250",
    );
    expect(logClockToBeijing("2026-03-01 00:15:00.000", "+", "09", "00")).toBe(
      "2026-02-28 23:15:00.000",
    );
    expect(logClockToBeijing("2026-10-13 05:00:00.000", "+", "05", "30")).toBe(
      "2026-10-13 07:30:00.000",
    );
  });

  it("leaves Beijing-offset and offset-less clocks untouched", () => {
    expect(logClockToBeijing("2026-10-13 15:00:00.000", "+", "08", "00")).toBe(
      "2026-10-13 15:00:00.000",
    );
    expect(logClockToBeijing("2026-10-13 15:00:00.000")).toBe("2026-10-13 15:00:00.000");
  });

  it("parses event and quest times from an offset log in Beijing time", () => {
    const parsed = parseTarkovLogText(
      [
        "2026-10-13 08:00:00.000 +01:00|1.0.0.0.1|Info|application|Session mode: regular",
        "2026-10-13 08:00:01.000 +01:00|1.0.0.0.1|Info|application|SelectProfile ProfileId:aa11bb22cc33dd44ee55ff66 AccountId:1",
        "2026-10-13 08:05:00.000 +01:00|1.0.0.0.1|Info|push-notifications|Got notification | ChatMessageReceived",
        '{ "message": { "type": 12, "templateId": "5ac346a886f7744e1b083d67 successMessageText" } }',
      ].join("\n"),
    );
    expect(parsed.events[0]?.at).toBe("2026-10-13 15:00:00.000");
    expect(parsed.quests?.[0]).toMatchObject({
      at: "2026-10-13 15:05:00.000",
      kind: "completed",
      profileId: "aa11bb22cc33dd44ee55ff66",
    });
  });
});

describe("parseTarkovLogText", () => {
  it("extracts raid identity without keeping the server IP", () => {
    const parsed = parseTarkovLogText(
      [
        "2023-12-29 19:03:00.000 +08:00|0.14.0.0.28375|Info|application|Session mode: regular",
        "2023-12-29 19:03:10.000 +08:00|0.14.0.0.28375|Info|application|scene preset path:maps/shoreline.bundle",
        "2023-12-29 19:03:20.711 +08:00|0.14.0.0.28375|Info|application|LocationLoaded:66.88 real:77.66",
        MATCH_LINE,
        "2023-12-29 19:03:21.000 +08:00|0.14.0.0.28375|Info|application|GameStarting",
        "2023-12-29 19:03:40.000 +08:00|0.14.0.0.28375|Info|application|GameStarted",
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
    expect(taskIdFromQuestTemplate("5AC346A886F7744E1B083D67 description")).toBe(
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
        line: "2024-02-05 19:03:08.398|x|Info|push-notifications|Got notification | ChatMessageReceived",
        sessionMode: "regular",
      },
      {
        kind: "completed",
        at: "2024-02-05 19:04:00.000",
        taskId: "5ac346a886f7744e1b083d67",
        line: "2024-02-05 19:04:00.000|x|Info|push-notifications|Got notification | ChatMessageReceived",
        sessionMode: "regular",
      },
    ]);
    expect(latestLogActivityAt(parsed)).toBe("2024-02-05 19:04:00.000");
  });

  it("stamps quests with the Session mode active at that clock, not the last mode in the folder", () => {
    const parsed = parseTarkovLogBundle([
      {
        name: "application.log",
        text: [
          "2024-02-05 19:00:00.000|x|Info|application|Session mode: regular",
          "2024-02-05 19:00:01.000|x|Info|application|SelectProfile ProfileId:aa11bb22cc33dd44ee55ff66 AccountId:123",
          "2024-02-05 20:00:00.000|x|Info|application|Session mode: Pve",
          "2024-02-05 20:00:01.000|x|Info|application|SelectProfile ProfileId:11223344556677889900aabb AccountId:123",
        ].join("\n"),
      },
      {
        name: "notifications.log",
        text: [
          "2024-02-05 19:03:00.000|x|Info|push-notifications|Got notification | ChatMessageReceived",
          '{ "type": "new_message", "message": { "type": 12, "templateId": "5ac346a886f7744e1b083d67 description" } }',
          "2024-02-05 20:03:00.000|x|Info|push-notifications|Got notification | ChatMessageReceived",
          '{ "type": "new_message", "message": { "type": 10, "templateId": "625d6ffaf7308432be1d44c5 description" } }',
        ].join("\n"),
      },
    ]);
    expect(parsed.sessionMode).toBe("Pve");
    expect(parsed.quests).toEqual([
      {
        kind: "completed",
        at: "2024-02-05 19:03:00.000",
        taskId: "5ac346a886f7744e1b083d67",
        line: "2024-02-05 19:03:00.000|x|Info|push-notifications|Got notification | ChatMessageReceived",
        sessionMode: "regular",
        profileId: "aa11bb22cc33dd44ee55ff66",
      },
      {
        kind: "started",
        at: "2024-02-05 20:03:00.000",
        taskId: "625d6ffaf7308432be1d44c5",
        line: "2024-02-05 20:03:00.000|x|Info|push-notifications|Got notification | ChatMessageReceived",
        sessionMode: "Pve",
        profileId: "11223344556677889900aabb",
      },
    ]);
  });

  it("records identities with version and does not mix session modes in one folder", () => {
    const parsed = parseTarkovLogBundle([
      {
        name: "application.log",
        text: [
          "2024-02-05 19:00:00.000|0.14.0.0.28375|Info|application|Session mode: regular",
          "2024-02-05 19:00:01.000|0.14.0.0.28375|Info|application|SelectProfile ProfileId:aa11bb22cc33dd44ee55ff66 AccountId:123",
          "2024-02-05 20:00:00.000|0.14.1.0.29000|Info|application|Session mode: Pve",
          "2024-02-05 20:00:01.000|0.14.1.0.29000|Info|application|SelectProfile ProfileId:11223344556677889900aabb AccountId:123",
        ].join("\n"),
      },
    ]);
    expect(identitiesFromParsed(parsed, "log_2024.02.05_19-00-00")).toEqual([
      {
        at: "2024-02-05 19:00:01.000",
        sessionMode: "regular",
        profileId: "aa11bb22cc33dd44ee55ff66",
        accountId: "123",
        version: "0.14.0.0",
        folder: "log_2024.02.05_19-00-00",
      },
      {
        at: "2024-02-05 20:00:01.000",
        sessionMode: "Pve",
        profileId: "11223344556677889900aabb",
        accountId: "123",
        version: "0.14.1.0",
        folder: "log_2024.02.05_19-00-00",
      },
    ]);
  });

  it("drops truncated ChatMessage JSON and ignores flea type 4", () => {
    const parsed = parseTarkovLogText(
      [
        "2024-02-05 19:03:08.398|x|Info|push-notifications|Got notification | ChatMessageReceived",
        '{ "type": "new_message", "message": { "type": 10, "templateId": "5ac346a886f7744e1b083d67 description"',
        "2024-02-05 19:05:00.000|x|Info|push-notifications|Got notification | ChatMessageReceived",
        '{ "type": "new_message", "message": { "type": 4, "templateId": "5bdabfb886f7743e152e867e 0" } }',
      ].join("\n"),
    );
    expect(parsed.quests).toEqual([]);
    expect(parsed.drops).toEqual([
      {
        at: "2024-02-05 19:03:08.398",
        reason: "json_bad",
        line: "2024-02-05 19:03:08.398|x|Info|push-notifications|Got notification | ChatMessageReceived",
      },
    ]);
  });

  it("reads PascalCase quest messages used in newer clients", () => {
    const parsed = parseTarkovLogText(
      [
        "2026-09-05 20:00:00.000|x|Info|push-notifications|Got notification | ChatMessageReceived",
        '{ "Type": "new_message", "Message": { "Type": 12, "TemplateId": "5AC346A886F7744E1B083D67 description" } }',
      ].join("\n"),
    );
    expect(parsed.quests).toEqual([
      {
        kind: "completed",
        at: "2026-09-05 20:00:00.000",
        taskId: "5ac346a886f7744e1b083d67",
        line: "2026-09-05 20:00:00.000|x|Info|push-notifications|Got notification | ChatMessageReceived",
      },
    ]);
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
    expect(logPhaseFromParsed(parsed)).toMatchObject({
      kind: "raid_exited",
      raidId: "PQXKR6",
      mapId: "shoreline",
    });
    expect(
      logPhaseFromParsed(
        parseTarkovLogText(
          [MATCH_LINE, "2023-12-29 19:03:40.000|x|Info|application|GameStarted"].join(
            "\n",
          ),
        ),
      ),
    ).toMatchObject({ kind: "raid_started", raidId: "PQXKR6" });
  });

  it("closes a raid from PrepareSelectedProfileLocally after GameStarted", () => {
    const parsed = parseTarkovLogText(
      [
        "2026-09-01 00:15:02.474|1.1.0.1.46911|Debug|application|TRACE-NetworkGameCreate profileStatus: 'Profileid: 6a747cbf7637ff24e00a67cd, Status: Busy, RaidMode: Online, Location: TarkovStreets, GameMode: deathmatch, shortId: 28B9YK'",
        "2026-09-01 00:15:58.467|1.1.0.1.46911|Info|application|GameStarted:121.03(9.69) real:136.76(12.03) diff:15.72",
        "2026-09-01 00:23:39.306|1.1.0.1.46911|Info|application|PrepareSelectedProfileLocally ProfileId:6a747cbf7637ff24e00a67cc AccountId:14901032",
        "2026-09-01 00:23:46.686|1.1.0.1.46911|Info|application|CompleteSelectedProfile ProfileId:6a747cbf7637ff24e00a67cc AccountId:14901032",
      ].join("\n"),
    );
    expect(parsed.raids).toHaveLength(1);
    expect(parsed.raids[0]).toMatchObject({
      raidId: "28B9YK",
      endedAt: "2026-09-01 00:23:39.306",
      mapId: "streets",
    });
    expect(logPhaseFromParsed(parsed)).toMatchObject({
      kind: "raid_exited",
      raidId: "28B9YK",
      mapId: "streets",
    });
  });

  it("keeps raid_exited after post-raid hideout GameStarted", () => {
    const parsed = parseTarkovLogBundle([
      {
        name: "application.log",
        text: [
          MATCH_LINE,
          "2023-12-29 19:03:40.000|x|Info|application|GameStarted",
          "2023-12-29 19:42:00.000|x|Info|application|LocationLoaded:1.00 real:1.00",
          "2023-12-29 19:42:01.000|x|Info|application|GameStarted",
        ].join("\n"),
      },
      {
        name: "notifications.log",
        text: [
          "2023-12-29 19:41:00.000|x|Info|notifications|Got notification | UserMatchOver",
          '{ "location": "Shoreline", "shortId": "PQXKR6" }',
        ].join("\n"),
      },
    ]);
    expect(parsed.raids).toHaveLength(1);
    expect(logPhaseFromParsed(parsed)).toMatchObject({
      kind: "raid_exited",
      raidId: "PQXKR6",
      mapId: "shoreline",
    });
    expect(
      logPhaseFromParsed({
        events: [],
        raids: [
          {
            raidId: "PQXKR6",
            location: "Shoreline",
            mapId: "shoreline",
            mapLabel: "海岸线",
            raidMode: "online",
            startedAt: "2023-12-29 19:03:40.000",
            endedAt: "2023-12-29 19:41:00.000",
          },
          {
            raidId: "",
            location: "",
            mapId: "",
            mapLabel: "未知地图",
            raidMode: "unknown",
            startedAt: "2023-12-29 19:42:01.000",
          },
        ],
      }),
    ).toMatchObject({ kind: "raid_exited", raidId: "PQXKR6" });
    expect(
      logPhaseFromParsed({
        events: [],
        raids: [
          {
            raidId: "PQXKR6",
            location: "Shoreline",
            mapId: "shoreline",
            mapLabel: "海岸线",
            raidMode: "online",
            startedAt: "2023-12-29 19:03:40.000",
            endedAt: "2023-12-29 19:41:00.000",
          },
          {
            raidId: "",
            location: "",
            mapId: "woods",
            mapLabel: "森林",
            raidMode: "unknown",
            startedAt: "2023-12-29 19:51:00.000",
          },
        ],
      }),
    ).toMatchObject({ kind: "raid_started", mapId: "woods" });
  });

  it("closes a raid from output.log GameStopping when UserMatchOver is missing", () => {
    const parsed = parseTarkovLogBundle([
      {
        name: "application.log",
        text: [MATCH_LINE, "2023-12-29 19:03:40.000|x|Info|application|GameStarted"].join(
          "\n",
        ),
      },
      {
        name: "output.log",
        text: "2023-12-29 19:41:12.000|x|Info|application|EFT.NetworkGame`1:GameStopping()",
      },
    ]);
    expect(parsed.raids[0]).toMatchObject({
      raidId: "PQXKR6",
      endedAt: "2023-12-29 19:41:12.000",
      mapId: "shoreline",
    });
    expect(logPhaseFromParsed(parsed)).toMatchObject({ kind: "raid_exited" });
  });

  it("reuses per-file parses from the memo only while the text is unchanged", () => {
    const app = {
      name: "application.log",
      text: [MATCH_LINE, "2023-12-29 19:03:40.000|x|Info|application|GameStarted"].join("\n"),
    };
    const notifications = {
      name: "notifications.log",
      text: [
        "2023-12-29 19:10:00.000|x|Info|push-notifications|Got notification | ChatMessageReceived",
        '{ "type": "new_message", "message": { "type": 10, "templateId": "5ac346a886f7744e1b083d67 description" } }',
      ].join("\n"),
    };
    const output = {
      name: "output.log",
      text: "2023-12-29 19:41:12.000|x|Info|application|EFT.NetworkGame`1:GameStopping()",
    };
    const memo: TarkovLogBundleMemo = new WeakMap();
    const first = parseTarkovLogBundle([app, notifications, output], memo);
    expect(first).toEqual(parseTarkovLogBundle([app, notifications, output]));

    const again = parseTarkovLogBundle([app, notifications, output], memo);
    expect(again).toEqual(first);
    expect(again.events[0]).toBe(first.events[0]);

    const grownApp = {
      ...app,
      text: `${app.text}\n2023-12-29 19:42:01.000|x|Info|application|LocationLoaded:1.00 real:1.00`,
    };
    const grown = parseTarkovLogBundle([grownApp, notifications, output], memo);
    expect(grown).toEqual(parseTarkovLogBundle([grownApp, notifications, output]));
    expect(grown.events[0]).not.toBe(first.events[0]);
    expect(grown.quests?.[0]?.taskId).toBe(first.quests?.[0]?.taskId);

    output.text = "";
    expect(parseTarkovLogBundle([grownApp, notifications, output], memo)).toEqual(
      parseTarkovLogBundle([grownApp, notifications, output]),
    );
  });

  it("does not inherit the previous map for an offline raid without Location", () => {
    const parsed = parseTarkovLogBundle([
      {
        name: "application.log",
        text: [
          MATCH_LINE,
          "2023-12-29 19:03:40.000|x|Info|application|GameStarted",
          "2023-12-29 19:41:00.000|x|Info|notifications|Got notification | UserMatchOver",
          '{ "location": "Shoreline", "shortId": "PQXKR6" }',
          "2023-12-29 20:00:00.000|x|Info|application|TRACE-NetworkGameCreate profileStatus: 'RaidMode: Offline, shortId: LOCAL1'",
          "2023-12-29 20:00:10.000|x|Info|application|GameStarted",
        ].join("\n"),
      },
    ]);
    expect(latestLogMapId(parsed)).toBe("");
    expect(logPhaseFromParsed(parsed)).toMatchObject({
      kind: "raid_started",
      raidMode: "offline",
      mapId: "",
    });
  });

  it("opens a new raid after exit on map_loading with a known map", () => {
    const parsed = parseTarkovLogBundle([
      {
        name: "application.log",
        text: [
          MATCH_LINE,
          "2023-12-29 19:03:40.000|x|Info|application|GameStarted",
          "2023-12-29 19:42:01.000|x|Info|application|LocationLoaded:1.00 real:1.00",
          "2023-12-29 19:42:02.000|x|Info|application|GameStarted",
          "2023-12-29 19:50:00.000|x|Info|application|scene preset path:maps/woods.bundle",
          "2023-12-29 19:50:10.000|x|Info|application|LocationLoaded:1.00 real:1.00",
          "2023-12-29 19:51:00.000|x|Info|application|GameStarted",
        ].join("\n"),
      },
      {
        name: "notifications.log",
        text: [
          "2023-12-29 19:41:00.000|x|Info|notifications|Got notification | UserMatchOver",
          '{ "location": "Shoreline", "shortId": "PQXKR6" }',
        ].join("\n"),
      },
    ]);
    expect(parsed.raids.map((raid) => raid.mapId)).toEqual(["shoreline", "woods"]);
    expect(logPhaseFromParsed(parsed)).toMatchObject({
      kind: "raid_started",
      mapId: "woods",
    });
  });

  it("opens a new raid after exit on match_found", () => {
    const parsed = parseTarkovLogBundle([
      {
        name: "application.log",
        text: [
          MATCH_LINE,
          "2023-12-29 19:03:40.000|x|Info|application|GameStarted",
          "2023-12-29 19:42:01.000|x|Info|application|GameStarted",
          NIGHT_FACTORY_LINE.replace("2026-08-30 20:11:02.100", "2023-12-29 20:00:00.000"),
          "2023-12-29 20:00:10.000|x|Info|application|GameStarted",
        ].join("\n"),
      },
      {
        name: "notifications.log",
        text: [
          "2023-12-29 19:41:00.000|x|Info|notifications|Got notification | UserMatchOver",
          '{ "location": "Shoreline", "shortId": "PQXKR6" }',
        ].join("\n"),
      },
    ]);
    expect(parsed.raids.map((raid) => raid.raidId)).toEqual(["PQXKR6", "AB12CD"]);
    expect(logPhaseFromParsed(parsed)).toMatchObject({
      kind: "raid_started",
      raidId: "AB12CD",
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
    expect(sessionModeLabel("seasonal")).toBe("赛季");
    expect(sessionModeLabel("szn")).toBe("赛季");
    expect(classifyLogSessionMode("regular")).toBe("pvp");
    expect(classifyLogSessionMode("PvpSeason")).toBe("seasonal");
    expect(classifyLogSessionMode("mystery")).toBe("unknown");
    expect(classifyLogSessionMode("")).toBe("");
    expect(versionFromLogLine("2023-12-29 19:03:00.000 +01:00|0.14.0.0.28375|Info|")).toBe(
      "0.14.0.0",
    );
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

describe("incremental live-log parsing", () => {
  const APP = [
    "2026-10-13 08:00:00.000 +01:00|1.0.0.0.1|Info|application|Session mode: regular",
    "2026-10-13 08:00:01.000 +01:00|1.0.0.0.1|Info|application|SelectProfile ProfileId:aa11bb22cc33dd44ee55ff66 AccountId:1",
    MATCH_LINE.replace("2023-12-29 19:03:20.911 +08:00", "2026-10-13 08:01:00.000 +01:00"),
    "2026-10-13 08:01:30.000 +01:00|1.0.0.0.1|Info|application|GameStarted",
    "2026-10-13 08:20:00.000 +01:00|1.0.0.0.1|Info|application|Session mode: Pve",
  ].join("\n") + "\n";
  const NOTIFY = [
    "2026-10-13 08:05:00.000 +01:00|1.0.0.0.1|Info|push-notifications|Got notification | ChatMessageReceived",
    '{ "type": "new_message",',
    '  "message": { "type": 10, "templateId": "5ac346a886f7744e1b083d67 description" } }',
    "2026-10-13 08:10:00.000 +01:00|1.0.0.0.1|Info|push-notifications|Got notification | UserMatchOver",
    '{ "location": "Shoreline", "shortId": "PQXKR6" }',
    "2026-10-13 08:15:00.000 +01:00|1.0.0.0.1|Info|push-notifications|Got notification | ChatMessageReceived",
    '{ "type": "new_message", "message": { "type": 12, "templateId": "5ac346a886f7744e1b083d67 description" } }',
  ].join("\n") + "\n";

  function oneShot(app: string, notify: string) {
    return parseTarkovLogBundle([
      { name: "application.log", text: app },
      { name: "notifications.log", text: notify },
    ]);
  }

  it("parsing a growing file chunk by chunk equals one full parse at every step", () => {
    // deterministic pseudo-random cut points, including mid-line and mid-JSON cuts
    let seed = 7;
    const rand = (n: number) => {
      seed = (seed * 1103515245 + 12345) % 2147483648;
      return seed % n;
    };
    for (let round = 0; round < 25; round += 1) {
      const memo: TarkovLogBundleMemo = new WeakMap();
      const appPart = { name: "application.log", text: "" };
      const notifyPart = { name: "notifications.log", text: "" };
      let a = 0;
      let n = 0;
      while (a < APP.length || n < NOTIFY.length) {
        a = Math.min(APP.length, a + 1 + rand(60));
        n = Math.min(NOTIFY.length, n + 1 + rand(60));
        appPart.text = APP.slice(0, a);
        notifyPart.text = NOTIFY.slice(0, n);
        const live = parseTarkovLogBundle([appPart, notifyPart], memo);
        expect(live).toEqual(oneShot(appPart.text, notifyPart.text));
      }
    }
  });

  it("the final incremental result has the full events, quests and Beijing clocks", () => {
    const memo: TarkovLogBundleMemo = new WeakMap();
    const appPart = { name: "application.log", text: APP.slice(0, 200) };
    const notifyPart = { name: "notifications.log", text: NOTIFY.slice(0, 150) };
    parseTarkovLogBundle([appPart, notifyPart], memo);
    appPart.text = APP;
    notifyPart.text = NOTIFY;
    const parsed = parseTarkovLogBundle([appPart, notifyPart], memo);
    expect(parsed.quests?.map((q) => [q.kind, q.at])).toEqual([
      ["started", "2026-10-13 15:05:00.000"],
      ["completed", "2026-10-13 15:15:00.000"],
    ]);
    expect(parsed.raids[0]).toMatchObject({ raidId: "PQXKR6", endedAt: "2026-10-13 15:10:00.000" });
    expect(parsed.sessionMode).toBe("Pve");
  });

  it("an unfinished trailing line never leaves a wrong session mode behind", () => {
    const memo: TarkovLogBundleMemo = new WeakMap();
    const part = {
      name: "application.log",
      text: "2026-10-13 08:00:00.000 +01:00|1|Info|application|Session mode: regular\n2026-10-13 08:20:00.000 +01:00|1|Info|application|Session mode: Pv",
    };
    parseTarkovLogBundle([part], memo);
    part.text += "e\n";
    expect(parseTarkovLogBundle([part], memo).sessionMode).toBe("Pve");
  });

  /** 一次喂一片：每片后都和整份重扫比；文本对象换新时（readTarkovLogText 在文件变长时返回新对象）也一样。 */
  function growInSteps(
    names: string[],
    full: string[],
    steps: Array<number[]>,
    freshObjects: boolean,
  ) {
    const memo: TarkovLogBundleMemo = new WeakMap();
    let parts = names.map((name) => ({ name, text: "" }));
    for (const cut of steps) {
      const next = names.map((name, i) => ({ name, text: full[i]!.slice(0, cut[i]) }));
      if (freshObjects) {
        parts = next;
      } else {
        next.forEach((row, i) => {
          parts[i]!.text = row.text;
        });
      }
      const live = parseTarkovLogBundle(parts, memo);
      expect(live).toEqual(parseTarkovLogBundle(next.map((row) => ({ ...row }))));
    }
    return parseTarkovLogBundle(parts, memo);
  }

  it("rotated application parts parse the same chunk by chunk as in one shot", () => {
    const head = APP;
    const rotated = [
      "2026-10-13 08:30:00.000 +01:00|1.0.0.0.1|Info|application|Session mode: regular",
      MATCH_LINE.replace("2023-12-29 19:03:20.911 +08:00", "2026-10-13 08:31:00.000 +01:00").replace(
        "PQXKR6",
        "ZZTOP9",
      ),
      "2026-10-13 08:31:30.000 +01:00|1.0.0.0.1|Info|application|GameStarted",
    ].join("\n") + "\n";
    const names = ["application_1.log", "application.log", "notifications.log"];
    const full = [rotated, head, NOTIFY];
    // 真实轮转：application.log 写满后改名 application_1.log 冻住，新的 application.log 接着写。
    const steps: number[][] = [];
    for (let a = 0; a <= head.length; a += 37) steps.push([0, a, Math.min(NOTIFY.length, a)]);
    steps.push([0, head.length, NOTIFY.length]);
    for (let r = 1; r <= rotated.length; r += 29) steps.push([r, head.length, NOTIFY.length]);
    steps.push([rotated.length, head.length, NOTIFY.length]);
    for (const fresh of [false, true]) {
      const last = growInSteps(names, full, steps, fresh);
      expect(last.raids.map((raid) => raid.raidId)).toEqual(["PQXKR6", "ZZTOP9"]);
      expect(last.raids[1]).toMatchObject({ startedAt: "2026-10-13 15:31:30.000" });
      expect(last.sessionMode).toBe("regular");
      // 冻结的上一份 + 这次启动的两份合起来 = 三份各自的解析结果。
      expect(last.events.filter((event) => event.kind === "raid_started")).toHaveLength(2);
      expect(last.quests?.map((quest) => quest.kind)).toEqual(["started", "completed"]);
    }
  });

  it("output.log keeps only GameStopping lines whether parsed at once or as it grows", () => {
    const output = [
      "2026-10-13 08:01:00.000 +01:00|1.0.0.0.1|Info|application|Session mode: Pve",
      "noise without stamp",
      "2026-10-13 08:09:59.000 +01:00|1.0.0.0.1|Info|application|EFT.NetworkGame`1:GameStopping()",
      "  at stack frame",
      "2026-10-13 08:40:00.000 +01:00|1.0.0.0.1|Info|application|EFT.NetworkGame`1:GameStopping()",
    ].join("\n");
    const names = ["application.log", "output.log"];
    const full = [APP, output];
    const steps: number[][] = [[APP.length, 0]];
    for (let o = 1; o <= output.length; o += 11) steps.push([APP.length, o]);
    steps.push([APP.length, output.length]);
    for (const fresh of [false, true]) {
      const last = growInSteps(names, full, steps, fresh);
      const exits = last.events.filter((event) => event.kind === "raid_exited").map((e) => e.at);
      expect(exits).toEqual(["2026-10-13 15:09:59.000", "2026-10-13 15:40:00.000"]);
      // output.log 里的 Session mode 不算数（只看 GameStopping）。
      expect(last.sessionMode).toBe("Pve");
      expect(last.events.filter((event) => event.kind === "session_mode")).toHaveLength(2);
    }
  });

  it("resumes through the new text objects the live reader hands back as files grow", async () => {
    const memo: TarkovLogBundleMemo = new WeakMap();
    const files = ["application.log", "application_1.log", "output.log"];
    const output =
      "2026-10-13 08:40:00.000 +01:00|1|Info|application|EFT.NetworkGame`1:GameStopping()\n";
    const full = [APP, APP.replace(/08:(\d\d):/g, "09:$1:"), output];
    const prev: Array<TarkovLogTextEntry | undefined> = [];
    const states = new Map<string, unknown>();
    let grown = 0;
    for (let step = 1; step <= 6; step += 1) {
      const parts = [];
      const linked: boolean[] = [];
      for (let i = 0; i < files.length; i += 1) {
        const text = full[i]!.slice(0, Math.ceil((full[i]!.length * step) / 6));
        const entry = await readTarkovLogText(
          files[i]!,
          new File([text], files[i]!, { lastModified: step }),
          prev[i],
        );
        prev[i] = entry;
        parts.push(entry.read);
        linked.push(Boolean(logTextGrownFrom(entry.read)));
      }
      const live = parseTarkovLogBundle(parts, memo);
      expect(live).toEqual(parseTarkovLogBundle(parts.map((part) => ({ ...part }))));
      parts.forEach((part, i) => {
        const state = (memo.get(part) as { state?: unknown } | undefined)?.state;
        // 文本是续读出来的新对象时，解析也接着上一轮的扫描状态，而不是整份重扫。
        if (linked[i]) {
          grown += 1;
          expect(state).toBe(states.get(part.name));
        }
        states.set(part.name, state);
      });
    }
    expect(grown).toBeGreaterThanOrEqual(8);
  });
});

describe("session folder time zones", () => {
  it("converts folder wall time with the offset read from that session's logs", () => {
    expect(folderTimeToBeijing("2026-10-13 08:00:00", "+01:00")).toBe("2026-10-13 15:00:00");
    expect(folderTimeToBeijing("2026-10-13 20:30:00", "-05:00")).toBe("2026-10-14 09:30:00");
    expect(folderTimeToBeijing("2026-10-13 08:00:00", "+08:00")).toBe("2026-10-13 08:00:00");
    expect(folderTimeToBeijing("2026-10-13 08:00:00", "")).toBe("2026-10-13 08:00:00");
    expect(folderTimeToBeijing("2026-10-13 08:00:00", undefined)).toBe("2026-10-13 08:00:00");
    expect(folderTimeToBeijing("2026-10-13 08:00:00", "nonsense")).toBe("2026-10-13 08:00:00");
    expect(folderTimeToBeijing("2026-10-13 08:00:00.250", "+01:00")).toBe("2026-10-13 15:00:00");
    expect(folderTimeToBeijing("not a clock", "+01:00")).toBe("not a clock");
    expect(folderTimeToBeijing(null, "+01:00")).toBeNull();
    expect(folderTimeToBeijing("", "+01:00")).toBeNull();
  });

  it("agrees with the log line clocks of the same session", () => {
    const folder = "log_2026.10.13_8-00-00_1.0.0.0.1";
    const parsed = parseTarkovLogText(
      "2026-10-13 08:00:00.000 +01:00|1.0.0.0.1|Info|application|Session mode: regular",
    );
    expect(parsed.clockOffset).toBe("+01:00");
    const stub = { folder, startedAt: parseSessionFolderTime(folder) };
    const beijing = sessionStubInBeijing(stub, parsed);
    expect(beijing.startedAt).toBe(parsed.events[0]!.at.replace(/\.\d{3}$/, ""));
    expect(beijing).not.toBe(stub);
    expect(stub.startedAt).toBe("2026-10-13 08:00:00");

    const legacy = parseTarkovLogText("2026-10-13 08:00:00.000|1|Info|application|Session mode: regular");
    expect(legacy.clockOffset).toBeUndefined();
    expect(sessionStubInBeijing(stub, legacy)).toBe(stub);
    expect(sessionStubInBeijing(stub, null)).toBe(stub);
  });

  it("carries the clock offset through a multi-part bundle (the live sync path)", () => {
    const folder = "log_2026.10.13_23-30-00_1.0.0.0.1";
    const parsed = parseTarkovLogBundle([
      {
        name: "2026.10.13_23-30-00_1.0.0.0.1 application_000.log",
        text: "2026-10-13 23:30:00.000 +02:00|1.0.0.0.1|Info|application|Session mode: regular",
      },
      {
        name: "2026.10.13_23-30-00_1.0.0.0.1 backend_000.log",
        text: "2026-10-13 23:31:00.000 +02:00|1.0.0.0.1|Info|backend|ping",
      },
    ]);
    expect(parsed.clockOffset).toBe("+02:00");
    const stub = { folder, startedAt: parseSessionFolderTime(folder) };
    /* UTC+2 的 23:30 是北京次日 05:30：按日期筛选时要落在 10-14。 */
    expect(sessionStubInBeijing(stub, parsed).startedAt).toBe("2026-10-14 05:30:00");
    expect(parseTarkovLogBundle([]).clockOffset).toBeUndefined();
  });

  it("falls back to the converted folder time in the verify preview", () => {
    expect(
      formatLatestLogPreview(
        { folder: "log_2026.10.13_08-00-00", startedAt: "2026-10-13 08:00:00" },
        { events: [], raids: [], clockOffset: "+01:00" },
      ),
    ).toBe("2026-10-13 15:00:00");
  });
});
