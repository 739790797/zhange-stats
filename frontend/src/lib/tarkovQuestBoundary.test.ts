import { describe, expect, it } from "vitest";
import type { TarkovLogIdentity, TarkovLogQuestEvent } from "./tarkovGameLogs";
import {
  clearedMapFromServer,
  clockToSecond,
  combineQuestBoundary,
  detectQuestPrestige,
  emptyQuestBoundary,
  mergeClearedMaps,
  planQuestReplay,
  questBoundaryFromServer,
  type QuestBoundary,
} from "./tarkovQuestBoundary";

const CUR = "aa11bb22cc33dd44ee55ff66";
const OLD = "0011223344556677889900aa";
const NEW = "ffeeddccbbaa998877665544";
const T = (n: number) => `t${String(n).padStart(23, "0")}`;

function ident(profileId: string, at: string, sessionMode = "regular"): TarkovLogIdentity {
  return { at, sessionMode, profileId, accountId: "1", version: "1.0.0" };
}

function ev(
  kind: TarkovLogQuestEvent["kind"],
  taskId: string,
  at: string,
  profileId = CUR,
): TarkovLogQuestEvent {
  return { kind, taskId, at, profileId, sessionMode: "regular" };
}

const CATALOG = {
  knownIds: new Set([T(1), T(2), T(3), T(4), T(5)]),
  restartableIds: new Set([T(5)]),
};

function boundary(patch: Partial<QuestBoundary> = {}): QuestBoundary {
  return { ...emptyQuestBoundary(), ...patch };
}

describe("questBoundaryFromServer", () => {
  it("maps the account fields and tolerates nulls", () => {
    expect(questBoundaryFromServer(null)).toEqual(emptyQuestBoundary());
    expect(
      questBoundaryFromServer({
        reset_at: "2026-10-13 15:00:00",
        pending_clear_at: null,
        reset_profile_id: CUR,
        reset_epoch: 3,
      }),
    ).toEqual({ resetAt: "2026-10-13 15:00:00", pendingClearAt: "", profileId: CUR, epoch: 3 });
  });

  it("merges cleared marks keeping the later time", () => {
    const server = clearedMapFromServer([{ task_id: "A", cleared_at: "2026-10-13 15:00:00" }]);
    expect(server.get("a")).toBe("2026-10-13 15:00:00");
    const local = new Map([["a", "2026-10-13 16:00:00"], ["b", "2026-10-01 00:00:00"]]);
    expect(Object.fromEntries(mergeClearedMaps(server, local))).toEqual({
      a: "2026-10-13 16:00:00",
      b: "2026-10-01 00:00:00",
    });
  });
});

describe("clockToSecond", () => {
  it("truncates log milliseconds so local replay and the stored floor agree", () => {
    expect(clockToSecond("2026-10-13 10:00:00.000")).toBe("2026-10-13 10:00:00");
    expect(clockToSecond("2026-10-13 10:00:00.250")).toBe("2026-10-13 10:00:00");
    expect(clockToSecond("")).toBe("");
  });
});

describe("combineQuestBoundary", () => {
  const local = boundary({
    resetAt: "2026-10-13 15:00:00",
    pendingClearAt: "2026-10-13 15:00:00",
    profileId: CUR,
  });

  it("the account wins once it has recorded any boundary", () => {
    const server = boundary({ resetAt: "2026-10-01 00:00:00", epoch: 2 });
    expect(combineQuestBoundary(server, local)).toEqual(server);
  });

  it("an account that never recorded one keeps the legacy local floor and clear", () => {
    expect(combineQuestBoundary(boundary(), local)).toEqual({ ...local, epoch: 0 });
  });

  it("guests use local only", () => {
    expect(combineQuestBoundary(null, local)).toEqual({ ...local, epoch: 0 });
  });
});

describe("detectQuestPrestige", () => {
  const identities = [
    ident(CUR, "2026-06-01 10:00:00"),
    ident(CUR, "2026-10-13 09:55:00"), // the relog right after prestige
    ident(CUR, "2026-10-13 18:00:00"),
  ];

  it("finds User same-profile prestige from completed-then-started tasks", () => {
    const events = [
      ev("completed", T(1), "2026-06-05 12:00:00"),
      ev("completed", T(2), "2026-09-20 12:00:00"),
      ev("started", T(1), "2026-10-13 10:00:00"),
      ev("started", T(2), "2026-10-13 10:00:01"),
      ev("started", T(3), "2026-10-13 10:05:00"),
    ];
    expect(
      detectQuestPrestige({
        events,
        identities,
        gameMode: "pvp",
        profileId: CUR,
        catalog: CATALOG,
      }),
    ).toEqual({
      at: "2026-10-13 09:55:00",
      startedAt: "2026-10-13 10:00:00",
      taskIds: [T(1), T(2)].sort(),
    });
  });

  it("does not fire on User single regression, restartable tasks, or unknown ids", () => {
    const base = { identities, gameMode: "pvp" as const, profileId: CUR, catalog: CATALOG };
    expect(
      detectQuestPrestige({
        ...base,
        events: [ev("completed", T(1), "2026-06-05 12:00:00"), ev("started", T(1), "2026-10-13 10:00:00")],
      }),
    ).toBeNull();
    expect(
      detectQuestPrestige({
        ...base,
        events: [
          ev("failed", T(5), "2026-06-05 12:00:00"),
          ev("started", T(5), "2026-06-05 12:10:00"),
          ev("completed", "daily-weekly-x", "2026-06-06 12:00:00"),
          ev("started", "daily-weekly-x", "2026-06-07 12:00:00"),
          ev("completed", "daily-weekly-y", "2026-06-06 12:00:00"),
          ev("started", "daily-weekly-y", "2026-06-07 12:00:00"),
        ],
      }),
    ).toBeNull();
  });

  it("only trusts the logs: tasks ticked on the site and then accepted in-game are not User prestige", () => {
    // the account says T1/T2 are done (ticked on the website), the logs only show them being accepted
    expect(
      detectQuestPrestige({
        events: [
          ev("started", T(1), "2026-10-13 10:00:00"),
          ev("started", T(2), "2026-10-13 10:01:00"),
        ],
        identities,
        gameMode: "pvp",
        profileId: CUR,
        catalog: CATALOG,
      }),
    ).toBeNull();
  });

  it("ignores events of other profiles and before the floor", () => {
    const events = [
      ev("completed", T(1), "2026-06-05 12:00:00"),
      ev("completed", T(2), "2026-06-05 12:00:00"),
      ev("started", T(1), "2026-10-13 10:00:00", OLD),
      ev("started", T(2), "2026-10-13 10:00:00", OLD),
    ];
    const base = { identities, gameMode: "pvp" as const, profileId: CUR, catalog: CATALOG };
    expect(detectQuestPrestige({ ...base, events })).toBeNull();
    const own = [
      ev("completed", T(1), "2026-06-05 12:00:00"),
      ev("completed", T(2), "2026-06-05 12:00:00"),
      ev("started", T(1), "2026-10-13 10:00:00"),
      ev("started", T(2), "2026-10-13 10:00:00"),
    ];
    expect(detectQuestPrestige({ ...base, events: own, floor: "2026-10-13 12:00:00" })).toBeNull();
  });

  it("picks the most recent of two prestiges", () => {
    const events = [
      ev("completed", T(1), "2026-02-01 12:00:00"),
      ev("completed", T(2), "2026-02-01 12:00:00"),
      ev("started", T(1), "2026-05-01 10:00:00"),
      ev("started", T(2), "2026-05-01 10:00:00"),
      ev("completed", T(1), "2026-06-01 12:00:00"),
      ev("completed", T(2), "2026-06-01 12:00:00"),
      ev("started", T(1), "2026-10-13 10:00:00"),
      ev("started", T(2), "2026-10-13 10:00:00"),
    ];
    expect(
      detectQuestPrestige({
        events,
        identities: [ident(CUR, "2026-01-01 00:00:00"), ident(CUR, "2026-10-13 09:55:00")],
        gameMode: "pvp",
        profileId: CUR,
        catalog: CATALOG,
      })?.startedAt,
    ).toBe("2026-10-13 10:00:00");
  });

  it("needs the catalog; without it there is no guess", () => {
    expect(
      detectQuestPrestige({
        events: [ev("completed", T(1), "2026-06-05 12:00:00"), ev("started", T(1), "2026-10-13 10:00:00")],
        identities,
        gameMode: "pvp",
        profileId: CUR,
        catalog: { restartableIds: new Set() },
        minTasks: 1,
      }),
    ).toBeNull();
  });
});

/** Shared fixture: same-ProfileId prestige at ~10:00, clear clicked at 15:00. */
const SEASON = [ident(CUR, "2025-11-16 10:00:00"), ident(CUR, "2026-10-13 09:55:00")];
const PRE_PRESTIGE = [
  ev("completed", T(1), "2026-06-05 12:00:00"),
  ev("completed", T(2), "2026-09-20 12:00:00"),
];

describe("planQuestReplay — clear progress (the reported bug)", () => {
  it("same profile, no prestige evidence: replays from the clear, not from the season start", () => {
    expect(
      planQuestReplay({
        gameMode: "pvp",
        identities: SEASON,
        events: [...PRE_PRESTIGE, ev("started", T(3), "2026-10-13 16:00:00")],
        boundary: boundary({ pendingClearAt: "2026-10-13 15:00:00", profileId: CUR }),
        catalog: CATALOG,
      }),
    ).toMatchObject({ fromAt: "2026-10-13 15:00:00", reset: true, reason: "clear", confirm: false });
  });

  it("works with nothing in localStorage — boundary comes from the account", () => {
    // logout / other browser / assistant: storedProfileId and floor used to be empty here
    expect(
      planQuestReplay({
        gameMode: "pvp",
        identities: SEASON,
        events: PRE_PRESTIGE,
        boundary: boundary({ pendingClearAt: "2026-10-13 15:00:00" }),
        catalog: CATALOG,
      }),
    ).toMatchObject({ fromAt: "2026-10-13 15:00:00", reset: true });
  });

  it("an older PMC left in Logs does not drag the floor back to its first sighting", () => {
    // previously: freshProfile=true and fromAt = 2025-11-16 → 11 months of pre-prestige quests
    const plan = planQuestReplay({
      gameMode: "pvp",
      identities: [ident(OLD, "2025-10-01 20:00:00"), ...SEASON],
      events: PRE_PRESTIGE,
      boundary: boundary({ pendingClearAt: "2026-10-13 15:00:00" }),
      catalog: CATALOG,
    });
    expect(plan).toMatchObject({ profileId: CUR, fromAt: "2026-10-13 15:00:00", reason: "clear" });
  });

  it("prestige evidence before the clear keeps quests played between prestige and clear", () => {
    const plan = planQuestReplay({
      gameMode: "pvp",
      identities: SEASON,
      events: [
        ...PRE_PRESTIGE,
        ev("started", T(1), "2026-10-13 10:00:00"),
        ev("started", T(2), "2026-10-13 10:00:01"),
        ev("completed", T(1), "2026-10-13 11:00:00"),
      ],
      boundary: boundary({ pendingClearAt: "2026-10-13 15:00:00", profileId: CUR }),
      catalog: CATALOG,
    });
    expect(plan).toMatchObject({ fromAt: "2026-10-13 09:55:00", reset: true, reason: "prestige" });
  });

  it("a real profile switch the account already knew about uses the new profile's first sighting", () => {
    expect(
      planQuestReplay({
        gameMode: "pvp",
        identities: [ident(CUR, "2026-06-01 10:00:00"), ident(NEW, "2026-10-13 09:00:00")],
        events: [],
        boundary: boundary({ pendingClearAt: "2026-10-13 15:00:00", profileId: CUR }),
        catalog: CATALOG,
      }),
    ).toMatchObject({ profileId: NEW, fromAt: "2026-10-13 09:00:00", reason: "profile" });
  });

  it("returns null when the logs show no profile for this mode", () => {
    expect(
      planQuestReplay({
        gameMode: "pve",
        identities: SEASON,
        events: [],
        boundary: boundary({ pendingClearAt: "2026-10-13 15:00:00" }),
        catalog: CATALOG,
      }),
    ).toBeNull();
  });
});

describe("planQuestReplay — floor is monotonic", () => {
  it("never replays before the account's resetAt, whatever the evidence says", () => {
    const plan = planQuestReplay({
      gameMode: "pvp",
      identities: [ident(OLD, "2025-10-01 20:00:00"), ...SEASON],
      events: PRE_PRESTIGE,
      boundary: boundary({ resetAt: "2026-10-13 15:00:00", profileId: CUR }),
      catalog: CATALOG,
    });
    expect(plan).toMatchObject({ fromAt: "2026-10-13 15:00:00", reset: false });
  });

  it("evidence older than resetAt is ignored rather than resetting again", () => {
    const plan = planQuestReplay({
      gameMode: "pvp",
      identities: SEASON,
      events: [
        ...PRE_PRESTIGE,
        ev("started", T(1), "2026-10-13 10:00:00"),
        ev("started", T(2), "2026-10-13 10:00:01"),
      ],
      boundary: boundary({ resetAt: "2026-10-13 15:00:00", profileId: CUR }),
      catalog: CATALOG,
    });
    expect(plan).toMatchObject({ fromAt: "2026-10-13 15:00:00", reset: false, reason: null });
  });
});

describe("planQuestReplay — automatic prestige without clicking clear", () => {
  it("detects same-profile prestige and resets from the relog before it", () => {
    const plan = planQuestReplay({
      gameMode: "pvp",
      identities: SEASON,
      events: [
        ...PRE_PRESTIGE,
        ev("started", T(1), "2026-10-13 10:00:00"),
        ev("started", T(2), "2026-10-13 10:00:01"),
      ],
      boundary: boundary({ profileId: CUR }),
      catalog: CATALOG,
    });
    expect(plan).toMatchObject({
      fromAt: "2026-10-13 09:55:00",
      reset: true,
      reason: "prestige",
      confirm: true,
    });
  });

  it("an unknown-profile account with an older PMC in Logs asks before resetting", () => {
    // legacy accounts never recorded a ProfileId; the old PMC may just be last wipe's leftover
    expect(
      planQuestReplay({
        gameMode: "pvp",
        identities: [ident(OLD, "2025-10-01 20:00:00"), ...SEASON],
        events: PRE_PRESTIGE,
        boundary: boundary(),
        catalog: CATALOG,
      }),
    ).toMatchObject({
      profileId: CUR,
      fromAt: "2025-11-16 10:00:00",
      reset: true,
      reason: "profile",
      confirm: true,
    });
  });

  it("detects User new ProfileId the account knew the old one of", () => {
    expect(
      planQuestReplay({
        gameMode: "pvp",
        identities: [ident(CUR, "2026-06-01 10:00:00"), ident(NEW, "2026-10-13 09:00:00")],
        events: [],
        boundary: boundary({ profileId: CUR }),
        catalog: CATALOG,
      }),
    ).toMatchObject({
      profileId: NEW,
      fromAt: "2026-10-13 09:00:00",
      reset: true,
      reason: "profile",
      confirm: false,
    });
  });

  it("plain incremental sync when nothing changed", () => {
    expect(
      planQuestReplay({
        gameMode: "pvp",
        identities: SEASON,
        events: PRE_PRESTIGE,
        boundary: boundary({ profileId: CUR }),
        catalog: CATALOG,
      }),
    ).toMatchObject({ fromAt: "", reset: false, reason: null, prestige: null });
  });
});
