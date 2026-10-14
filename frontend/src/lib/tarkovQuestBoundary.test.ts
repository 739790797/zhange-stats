import { describe, expect, it } from "vitest";
import type { TarkovLogIdentity } from "./tarkovGameLogs";
import {
  clearedMapFromServer,
  clockToSecond,
  combineQuestBoundary,
  emptyQuestBoundary,
  mergeClearedMaps,
  planQuestReplay,
  questBoundaryFromServer,
  type QuestBoundary,
} from "./tarkovQuestBoundary";

const CUR = "aa11bb22cc33dd44ee55ff66";
const OLD = "0011223344556677889900aa";
const NEW = "ffeeddccbbaa998877665544";

function ident(profileId: string, at: string, sessionMode = "regular"): TarkovLogIdentity {
  return { at, sessionMode, profileId, accountId: "1", version: "1.0.0" };
}

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

const SEASON = [ident(CUR, "2025-11-16 10:00:00"), ident(CUR, "2026-10-13 09:55:00")];

describe("planQuestReplay", () => {
  it("does not treat a ProfileId change or an older PMC as prestige", () => {
    expect(
      planQuestReplay({
        gameMode: "pvp",
        identities: [ident(OLD, "2025-10-01 20:00:00"), ident(CUR, "2026-06-01 10:00:00"), ident(NEW, "2026-10-13 09:00:00")],
        boundary: boundary({ profileId: CUR }),
      }),
    ).toMatchObject({ profileId: NEW, fromAt: "", reset: false, reason: null });
  });

  it("a player-chosen launch later than the floor replaces the ledger from that launch", () => {
    expect(
      planQuestReplay({
        gameMode: "pvp",
        identities: SEASON,
        boundary: boundary({ profileId: CUR }),
        restartAt: "2026-10-13 09:55:00.250",
      }),
    ).toMatchObject({
      profileId: CUR,
      fromAt: "2026-10-13 09:55:00",
      reset: true,
      reason: "prestige",
      confirm: false,
    });
  });

  it("ignores a chosen launch that is not later than the stored floor", () => {
    expect(
      planQuestReplay({
        gameMode: "pvp",
        identities: SEASON,
        boundary: boundary({ resetAt: "2026-10-13 15:00:00", profileId: CUR }),
        restartAt: "2026-10-13 09:55:00",
      }),
    ).toMatchObject({ fromAt: "2026-10-13 15:00:00", reset: false, reason: null });
  });

  it("after a clear, replays from the character's first sighting instead of the click", () => {
    expect(
      planQuestReplay({
        gameMode: "pvp",
        identities: [ident(OLD, "2025-10-01 20:00:00"), ...SEASON],
        boundary: boundary({ pendingClearAt: "2026-10-13 15:00:00", profileId: CUR }),
      }),
    ).toMatchObject({
      profileId: CUR,
      fromAt: "2025-11-16 10:00:00",
      reset: true,
      reason: "clear",
    });
  });

  it("after a clear, a chosen launch still wins and may be earlier than the click", () => {
    expect(
      planQuestReplay({
        gameMode: "pvp",
        identities: SEASON,
        boundary: boundary({ pendingClearAt: "2026-10-13 15:00:00", profileId: CUR }),
        restartAt: "2026-10-13 09:55:00",
      }),
    ).toMatchObject({ fromAt: "2026-10-13 09:55:00", reset: true, reason: "prestige" });
  });

  it("keeps an existing floor when settling a clear without a new launch", () => {
    expect(
      planQuestReplay({
        gameMode: "pvp",
        identities: SEASON,
        boundary: boundary({
          resetAt: "2026-06-01 10:00:00",
          pendingClearAt: "2026-10-13 15:00:00",
          profileId: CUR,
        }),
      }),
    ).toMatchObject({ fromAt: "2026-06-01 10:00:00", reset: true, reason: "clear" });
  });

  it("returns null when the logs show no profile for this mode", () => {
    expect(
      planQuestReplay({
        gameMode: "pve",
        identities: SEASON,
        boundary: boundary({ pendingClearAt: "2026-10-13 15:00:00" }),
      }),
    ).toBeNull();
  });

  it("plain incremental sync when nothing changed", () => {
    expect(
      planQuestReplay({
        gameMode: "pvp",
        identities: SEASON,
        boundary: boundary({ profileId: CUR }),
      }),
    ).toMatchObject({ fromAt: "", reset: false, reason: null });
  });
});
