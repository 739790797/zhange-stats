import { describe, expect, it } from "vitest";
import { tarkovRaidRoomHref, tarkovRaidRoomShareUrl } from "./tarkovHomeNav";
import {
  applyRoomWsEvent,
  claimedTaskIds,
  claimTaskIdsForUser,
  formatKeyBringHint,
  formatKeyChipHint,
  formatKeyOwnHint,
  keyOwnsForUser,
  formatRoomRemain,
  groupClaimsByTask,
  groupKeyBringsByItem,
  markMatchesFloor,
  markStrokePoints,
  isMapDrawTool,
  mergeBoardMarks,
  parseRaidRoomPublicId,
  RAID_ROOM_SLOT_IDS,
  parseStrokePoints,
  partitionRaidLobbyRooms,
  raidRoomIsFull,
  raidRoomWsRetryDelayMs,
  remainMs,
  roomDisplayTitle,
  simplifyStroke,
  strokeFingerprint,
  userBroughtKey,
  withRaidRoomViewerFlags,
  dropPlayerFixesNotIn,
  parsePlayerFixEvent,
  playerFixMatchesRoomMap,
  pruneStalePlayerFixes,
  upsertPlayerFix,
} from "./tarkovRaidRooms";

describe("raid room helpers", () => {
  it("builds room href and default title", () => {
    expect(tarkovRaidRoomHref("3")).toBe("/guides/tarkov/raid-prep/rooms/3");
    expect(tarkovRaidRoomShareUrl("3", "https://stats.example/")).toBe(
      "https://stats.example/guides/tarkov/raid-prep/rooms/3",
    );
    expect(
      parseRaidRoomPublicId("https://x/guides/tarkov/raid-prep/rooms/3"),
    ).toBe("3");
    expect(parseRaidRoomPublicId("1")).toBe("1");
    expect(parseRaidRoomPublicId("5")).toBe("5");
    expect(parseRaidRoomPublicId("6")).toBe("");
    expect(parseRaidRoomPublicId("ABCDEF123456")).toBe("");
    expect(parseRaidRoomPublicId("nope")).toBe("");
    expect(RAID_ROOM_SLOT_IDS).toEqual(["1", "2", "3", "4", "5"]);
    expect(raidRoomWsRetryDelayMs(0)).toBe(1000);
    expect(raidRoomWsRetryDelayMs(5)).toBe(30_000);
    expect(
      roomDisplayTitle({ title: "", host_display_name: "甲" }, "海关"),
    ).toBe("甲 的 海关");
    expect(
      roomDisplayTitle({ title: "夜厂局", host_display_name: "甲" }, "海关"),
    ).toBe("夜厂局");
  });

  it("partitions lobby rooms into mine, hosted, and joinable", () => {
    const items = [
      {
        public_id: "a",
        is_member: true,
        host_user_id: 1,
        member_count: 2,
        max_members: 8,
      },
      {
        public_id: "b",
        is_member: false,
        host_user_id: 2,
        member_count: 8,
        max_members: 8,
      },
      {
        public_id: "c",
        is_member: false,
        host_user_id: 3,
        member_count: 1,
        max_members: 8,
      },
    ];
    const parts = partitionRaidLobbyRooms(items, 1);
    expect(parts.mine.map((row) => row.public_id)).toEqual(["a"]);
    expect(parts.hosted.map((row) => row.public_id)).toEqual(["a"]);
    expect(parts.joinable.map((row) => row.public_id)).toEqual(["b", "c"]);
    expect(raidRoomIsFull(items[1])).toBe(true);
    expect(raidRoomIsFull(items[2])).toBe(false);
    expect(raidRoomIsFull({ member_count: 0, max_members: 0 })).toBe(false);
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

  it("groups key brings and formats who-brought hints", () => {
    const brings = [
      { item_id: "k1", user_id: 1, display_name: "甲" },
      { item_id: "k1", user_id: 2, display_name: "乙" },
      { item_id: "k2", user_id: 2, display_name: "乙" },
    ];
    expect(groupKeyBringsByItem(brings)).toEqual([
      { itemId: "k1", userIds: [1, 2], names: ["甲", "乙"] },
      { itemId: "k2", userIds: [2], names: ["乙"] },
    ]);
    expect(userBroughtKey(brings, "k1", 1)).toBe(true);
    expect(userBroughtKey(brings, "k2", 1)).toBe(false);
    expect(userBroughtKey(brings, "k1", null)).toBe(false);
    expect(formatKeyBringHint([])).toBe("点击声明我带了这把钥匙");
    expect(formatKeyBringHint([], { canToggle: false })).toBe(
      "还没人声明带这把钥匙",
    );
    expect(formatKeyBringHint(["甲"])).toBe("甲带了这把钥匙。");
    expect(formatKeyBringHint(["甲", "乙"])).toBe("甲、乙带了这把钥匙。");
    expect(formatKeyBringHint(["甲"], { canToggle: true })).toBe(
      "甲带了这把钥匙。",
    );
    expect(formatKeyOwnHint([])).toBe("");
    expect(formatKeyOwnHint(["甲"])).toBe("甲拥有这把钥匙。");
    expect(formatKeyOwnHint(["甲", "乙"])).toBe("甲、乙拥有这把钥匙。");
    expect(formatKeyChipHint(["甲", "乙"], ["丙"])).toBe(
      "甲、乙拥有这把钥匙。 丙带了这把钥匙。",
    );
    expect(keyOwnsForUser(["k1"], { userId: 3, name: "丙" })).toEqual([
      { item_id: "k1", user_id: 3, display_name: "丙" },
    ]);
  });

  it("matches floors and applies snapshot / presence", () => {
    expect(markMatchesFloor({ floor: "" }, "")).toBe(true);
    expect(markMatchesFloor({ floor: "bunker" }, "")).toBe(false);
    const room = {
      public_id: "1",
      map_slug: "customs",
      host_user_id: 1,
      host_display_name: "甲",
      members: [
        { user_id: 1, display_name: "甲", online: false },
        { user_id: 2, display_name: "乙", online: false },
      ],
    };
    const next = applyRoomWsEvent(room, { event: "presence", online_user_ids: [2] }, 2);
    expect(next?.members?.map((row) => row.online)).toEqual([false, true]);
    expect(next?.is_member).toBe(true);
    expect(next?.is_host).toBe(false);
    expect(next?.can_edit).toBe(true);
    const snap = applyRoomWsEvent(
      room,
      {
        event: "snapshot",
        snapshot: { ...room, host_user_id: 2, map_slug: "" },
      },
      2,
    );
    expect(snap?.is_host).toBe(true);
    expect(snap?.can_edit).toBe(false);
    expect(withRaidRoomViewerFlags(room, 9).is_member).toBe(false);
    expect(withRaidRoomViewerFlags(room, 1).is_host).toBe(true);
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

  it("parses and prunes shared screenshot positions", () => {
    const parsed = parsePlayerFixEvent(
      {
        user_id: 12,
        x: 175.3,
        y: 1.37,
        z: 150.68,
        yaw: -12.4,
        map_id: "streets-of-tarkov",
        file_name: "shot.png",
      },
      1000,
    );
    expect(parsed).toMatchObject({
      userId: 12,
      x: 175.3,
      y: 1.37,
      z: 150.68,
      yaw: -12.4,
      mapId: "streets-of-tarkov",
      fileName: "shot.png",
      at: 1000,
    });
    expect(parsePlayerFixEvent({ user_id: 1, x: 1, y: 2 })).toBeNull();
    expect(playerFixMatchesRoomMap("", "customs")).toBe(true);
    expect(playerFixMatchesRoomMap("streets-of-tarkov", "streets")).toBe(true);
    expect(playerFixMatchesRoomMap("woods", "customs")).toBe(false);
    expect(playerFixMatchesRoomMap("customs", "")).toBe(false);
    const first = parsed!;
    const second = { ...first, userId: 12, x: 10, at: 2000 };
    const other = { ...first, userId: 3, at: 2000 };
    const merged = upsertPlayerFix([first, other], second);
    expect(merged.find((row) => row.userId === 12)?.x).toBe(10);
    expect(merged.map((row) => row.userId).sort((a, b) => a - b)).toEqual([
      3, 12,
    ]);
    expect(
      dropPlayerFixesNotIn([first, other], new Set([12])).map((row) => row.userId),
    ).toEqual([12]);
    expect(pruneStalePlayerFixes([first], 1000 + 8 * 60_000 + 1)).toEqual([]);
    expect(pruneStalePlayerFixes([first], 1000 + 60_000)).toEqual([first]);
  });
});
