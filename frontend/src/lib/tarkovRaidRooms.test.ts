import { describe, expect, it } from "vitest";
import { tarkovRaidRoomHref } from "./tarkovHomeNav";
import {
  applyRoomWsEvent,
  claimedTaskIds,
  claimTaskIdsForUser,
  formatRoomRemain,
  groupClaimsByTask,
  markMatchesFloor,
  markStrokePoints,
  isMapDrawTool,
  mergeBoardMarks,
  parseRaidRoomPublicId,
  parseStrokePoints,
  raidRoomWsRetryDelayMs,
  remainMs,
  roomDisplayTitle,
  simplifyStroke,
  strokeFingerprint,
} from "./tarkovRaidRooms";

describe("raid room helpers", () => {
  it("builds room href and default title", () => {
    expect(tarkovRaidRoomHref("abc")).toBe("/guides/tarkov/raid-prep/rooms/abc");
    expect(
      parseRaidRoomPublicId("https://x/guides/tarkov/raid-prep/rooms/AbCdef123456"),
    ).toBe("abcdef123456");
    expect(parseRaidRoomPublicId("ABCDEF123456")).toBe("abcdef123456");
    expect(parseRaidRoomPublicId("nope")).toBe("");
    expect(raidRoomWsRetryDelayMs(0)).toBe(1000);
    expect(raidRoomWsRetryDelayMs(5)).toBe(30_000);
    expect(
      roomDisplayTitle({ title: "", host_display_name: "甲" }, "海关"),
    ).toBe("甲 的 海关");
    expect(
      roomDisplayTitle({ title: "夜厂局", host_display_name: "甲" }, "海关"),
    ).toBe("夜厂局");
  });

  it("formats remaining time", () => {
    expect(formatRoomRemain(0)).toBe("已到期");
    expect(formatRoomRemain(90_000)).toBe("剩余 1 分钟");
    expect(formatRoomRemain(3_600_000 + 120_000)).toBe("剩余 1 小时 2 分");
    expect(remainMs("2099-01-01T00:00:00", Date.parse("2099-01-01T00:00:00"))).toBe(
      0,
    );
  });

  it("groups claims as a union with names", () => {
    const claims = [
      { task_id: "t1", user_id: 1, display_name: "甲" },
      { task_id: "t1", user_id: 2, display_name: "乙" },
      { task_id: "t2", user_id: 2, display_name: "乙" },
    ];
    const groups = groupClaimsByTask(claims);
    expect(groups).toEqual([
      { taskId: "t1", userIds: [1, 2], names: ["甲", "乙"] },
      { taskId: "t2", userIds: [2], names: ["乙"] },
    ]);
    expect(claimedTaskIds(claims)).toEqual(["t1", "t2"]);
    expect(claimTaskIdsForUser(claims, 1)).toEqual(["t1"]);
    expect(claimTaskIdsForUser(claims, 2)).toEqual(["t1", "t2"]);
    expect(claimTaskIdsForUser(claims, 9)).toEqual([]);
    expect(claimTaskIdsForUser(claims, null)).toEqual([]);
  });

  it("matches floors and applies snapshot / presence", () => {
    expect(markMatchesFloor({ floor: "" }, "")).toBe(true);
    expect(markMatchesFloor({ floor: "bunker" }, "")).toBe(false);
    const room = {
      public_id: "r1",
      map_slug: "customs",
      status: "live",
      host_user_id: 1,
      host_display_name: "甲",
      members: [
        { user_id: 1, display_name: "甲", online: false },
        { user_id: 2, display_name: "乙", online: false },
      ],
    };
    const next = applyRoomWsEvent(room, { event: "presence", online_user_ids: [2] });
    expect(next?.members?.map((row) => row.online)).toEqual([false, true]);
    const snap = applyRoomWsEvent(room, {
      event: "snapshot",
      snapshot: { ...room, status: "archived" },
    });
    expect(snap?.status).toBe("archived");
  });

  it("simplifies freehand strokes and reads mark points", () => {
    expect(parseStrokePoints([[1, 2], { x: 3, z: 4 }, ["bad"]])).toEqual([
      { x: 1, z: 2 },
      { x: 3, z: 4 },
    ]);
    const long = Array.from({ length: 40 }, (_, i) => ({ x: i * 0.2, z: 0 }));
    const simplified = simplifyStroke(long, 1.6, 160);
    expect(simplified[0]).toEqual({ x: 0, z: 0 });
    expect(simplified[simplified.length - 1]).toEqual({ x: 7.8, z: 0 });
    expect(simplified.length).toBeLessThan(long.length);
    const capped = simplifyStroke(
      Array.from({ length: 400 }, (_, i) => ({ x: i * 2, z: i })),
      1.6,
      20,
    );
    expect(capped).toHaveLength(20);
    expect(
      markStrokePoints({
        id: 1,
        kind: "stroke",
        x: 0,
        z: 0,
        points: [
          [0, 0],
          [5, 5],
        ],
        author_user_id: 1,
      }),
    ).toEqual([
      { x: 0, z: 0 },
      { x: 5, z: 5 },
    ]);
    expect(
      markStrokePoints({
        id: 2,
        kind: "line",
        x: 1,
        z: 2,
        x2: 3,
        z2: 4,
        author_user_id: 1,
      }),
    ).toEqual([
      { x: 1, z: 2 },
      { x: 3, z: 4 },
    ]);
  });

  it("keeps optimistic strokes until the board snapshot contains them", () => {
    const first: Parameters<typeof mergeBoardMarks>[1][number] = {
      id: -1,
      kind: "stroke",
      floor: "",
      x: 0,
      z: 0,
      x2: 4,
      z2: 0,
      points: [
        [0, 0],
        [4, 0],
      ],
      author_user_id: 1,
    };
    const second = { ...first, id: -2, x: 1, x2: 5, points: [[1, 0], [5, 0]] };
    expect(mergeBoardMarks([], [first, second])).toEqual([first, second]);
    expect(mergeBoardMarks([{ ...first, id: 9 }], [first, second])).toEqual([
      { ...first, id: 9 },
      second,
    ]);
  });

  it("treats pan as a map tool, not a draw tool", () => {
    expect(isMapDrawTool("pan")).toBe(false);
    expect(isMapDrawTool("pen")).toBe(true);
    expect(isMapDrawTool("erase")).toBe(true);
  });

  it("fingerprints two freehand strokes separately even with the same endpoints", () => {
    const base = {
      id: 1,
      kind: "stroke" as const,
      floor: "",
      x: 0,
      z: 0,
      x2: 10,
      z2: 0,
      author_user_id: 1,
    };
    expect(
      strokeFingerprint({
        ...base,
        points: [
          [0, 0],
          [5, 4],
          [10, 0],
        ],
      }),
    ).not.toBe(
      strokeFingerprint({
        ...base,
        id: 2,
        points: [
          [0, 0],
          [5, -4],
          [10, 0],
        ],
      }),
    );
  });
});
