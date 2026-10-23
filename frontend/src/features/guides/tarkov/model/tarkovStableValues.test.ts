import { describe, expect, it } from "vitest";
import {
  keepLogPhase,
  sameLogPhase,
  sameMemberPhases,
  samePlayerMarks,
  sameRaidRoomPhaseList,
  sameRaidRoomPhases,
  type RaidRoomLogPhaseLike,
} from "@/features/guides/tarkov/model/tarkovStableValues";
import type { TarkovLogPhasePayload } from "@/features/guides/tarkov/model/tarkovGameLogs";
import type { TarkovMapPlayerMark } from "@/features/guides/tarkov/model/tarkovRaidRooms";

const phase = (
  over: Partial<TarkovLogPhasePayload> = {},
): TarkovLogPhasePayload => ({
  kind: "raid_started",
  mapId: "customs",
  mapLabel: "海关",
  raidId: "r1",
  at: "2026-01-01T00:00:00",
  raidMode: "online",
  ...over,
});

describe("sameLogPhase", () => {
  it("treats a re-parsed identical phase as unchanged", () => {
    expect(sameLogPhase(phase(), phase())).toBe(true);
    expect(sameLogPhase(phase({ at: "2026-01-01T01:00:00" }), phase())).toBe(false);
  });

  it("keeps the previous object so the phase context does not re-render", () => {
    const prev = phase();
    expect(keepLogPhase(prev, phase())).toBe(prev);
    const next = phase({ mapId: "woods" });
    expect(keepLogPhase(prev, next)).toBe(next);
    expect(keepLogPhase(null, null)).toBeNull();
    expect(keepLogPhase(prev, null)).toBeNull();
  });
});

describe("sameMemberPhases", () => {
  it("ignores new maps built from the same rows", () => {
    const a = new Map([[1, { kind: "raid_started", online: true }]]);
    const b = new Map([[1, { kind: "raid_started", online: true }]]);
    expect(sameMemberPhases(a, b)).toBe(true);
    expect(sameMemberPhases(a, a)).toBe(true);
    expect(
      sameMemberPhases(a, new Map([[1, { kind: "matching", online: true }]])),
    ).toBe(false);
    expect(
      sameMemberPhases(a, new Map([[1, { kind: "raid_started", online: false }]])),
    ).toBe(false);
    expect(sameMemberPhases(a, new Map([[2, { kind: "raid_started", online: true }]]))).toBe(false);
  });
});

describe("sameRaidRoomPhases", () => {
  it("compares the seated phase per user", () => {
    const a: Map<number, RaidRoomLogPhaseLike> = new Map([
      [1, { kind: "matching", mapId: "customs", raidId: "" }],
    ]);
    const b = new Map(a);
    expect(sameRaidRoomPhases(a, b)).toBe(true);
    expect(
      sameRaidRoomPhases(
        a,
        new Map([[1, { kind: "matching", mapId: "woods", raidId: "" }]]),
      ),
    ).toBe(false);
    expect(
      sameRaidRoomPhases(
        a,
        new Map([[1, { kind: "matching", mapId: "customs", raidId: "r9" }]]),
      ),
    ).toBe(false);
  });

  it("treats missing map fields as empty", () => {
    expect(
      sameRaidRoomPhases(
        new Map([[1, { kind: "matching" }]]),
        new Map([[1, { kind: "matching", mapId: "", raidId: "" }]]),
      ),
    ).toBe(true);
  });
});

describe("sameRaidRoomPhaseList", () => {
  it("compares each row including our own", () => {
    const a = [
      { userId: 1, kind: "raid_started", mapId: "customs", raidId: "r1", at: "t" },
    ];
    const b = [...a];
    expect(sameRaidRoomPhaseList(a, b)).toBe(true);
    expect(sameRaidRoomPhaseList(a, [...a, { userId: 2, kind: "matching" }])).toBe(
      false,
    );
    expect(sameRaidRoomPhaseList(a, [{ ...a[0]!, at: "t2" }])).toBe(false);
  });
});

describe("samePlayerMarks", () => {
  const mark = (over: Partial<TarkovMapPlayerMark> = {}): TarkovMapPlayerMark => ({
    key: "u:1:a",
    userId: 1,
    name: "甲",
    color: "#fff",
    x: 1,
    y: 2,
    z: 3,
    yaw: 0,
    self: false,
    ...over,
  });

  it("treats a rebuilt identical mark list as unchanged", () => {
    expect(samePlayerMarks([mark()], [mark()])).toBe(true);
    expect(samePlayerMarks([mark()], [mark({ x: 2 })])).toBe(false);
    expect(samePlayerMarks([mark()], [mark(), mark({ userId: 2 })])).toBe(false);
    expect(samePlayerMarks([], [])).toBe(true);
  });
});
