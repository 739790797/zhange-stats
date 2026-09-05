import { describe, expect, it } from "vitest";
import { tarkovRaidRoomHref, tarkovRaidRoomShareUrl } from "./tarkovHomeNav";
import {
  applyRoomWsEvent,
  keepRaidRoomPresence,
  raidRoomLiveSig,
  claimedTaskIds,
  claimTaskIdsForUser,
  formatKeyBringHint,
  formatKeyChipHint,
  formatKeyOwnHint,
  formatKeyOwnToggleLabel,
  keyOwnsForUser,
  patchRaidRoomKeyOwns,
  userOwnsKey,
  formatRoomRemain,
  groupClaimsByTask,
  groupKeyBringsByItem,
  markMatchesFloor,
  markStrokePoints,
  isMapDrawTool,
  shouldRightButtonPanMap,
  mergeBoardMarks,
  parseRaidRoomPublicId,
  parseRaidRoomLogPhases,
  overlayRaidRoomLocalPhase,
  raidRoomActingHostUserId,
  raidRoomCanAutoSwitchMap,
  raidRoomHostLogMapId,
  raidRoomSharedRaidMapId,
  raidRoomLiveStatus,
  formatRaidRoomLiveStatus,
  formatRaidRoomMemberChipLine,
  raidRoomMemberRegionLabel,
  RAID_ROOM_SLOT_IDS,
  mergeRaidLobbySeats,
  raidRoomSlotIdsForMode,
  parseStrokePoints,
  partitionRaidLobbyRooms,
  raidRoomReturnHref,
  raidRoomIsFull,
  defaultRaidRoomTitle,
  raidRoomJoinNeedsPassword,
  RAID_ROOM_WS_PING_MS,
  raidRoomWsRetryDelayMs,
  remainMs,
  roomDisplayTitle,
  simplifyStroke,
  strokeFingerprint,
  userBroughtKey,
  withRaidRoomViewerFlags,
  type RaidRoomSnapshotLike,
  buildSoloRaidRoomDetail,
  isSoloRaidSession,
  soloRaidActor,
  SOLO_RAID_ROOM_PUBLIC_ID,
  dropPlayerFixesNotIn,
  formatRaidRoomOverlapCell,
  raidRoomOverlapPeopleLabel,
  raidRoomOverlapTasksForUser,
  sortRaidRoomMapOverlap,
  raidRoomPickDockMapId,
  parsePlayerFixEvent,
  playerFixMatchesRoomMap,
  shouldSuppressLocalPlayerFix,
  playerFixMarkerCaption,
  collectPlayerFixMarks,
  pruneStalePlayerFixes,
  upsertPlayerFix,
  colorForUserId,
  PULSE_DEMO_BOTS,
  PULSE_DEMO_MAP_ID,
  isPulseDemoSession,
  pulseDemoFixAt,
  pulseDemoMembers,
  PLAYER_FIX_PULSE_MS,
  buildPlayerFixPulseLines,
  detectPlayerFixPulseUpdaters,
  playerFixPulseCrossFloor,
  playerFixPulseLinesEqual,
  playerFixPulseOpacity,
  replacePlayerFixPulseLines,
  retainPlayerFixPulseLines,
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
    expect(parseRaidRoomPublicId("1", "pve")).toBe("pve-1");
    expect(parseRaidRoomPublicId("pve-3")).toBe("pve-3");
    expect(parseRaidRoomPublicId("https://x/guides/tarkov/raid-prep/rooms/pve-2")).toBe(
      "pve-2",
    );
    expect(parseRaidRoomPublicId("https://x/guides/tarkov/raid-prep/rooms/3")).toBe(
      "3",
    );
    expect(parseRaidRoomPublicId("ab12cd34")).toBe("ab12cd34");
    expect(parseRaidRoomPublicId("https://x/guides/tarkov/raid-prep/rooms/ab12cd34")).toBe(
      "ab12cd34",
    );
    expect(parseRaidRoomPublicId("ABCDEF123456")).toBe("abcdef123456");
    expect(parseRaidRoomPublicId("nope")).toBe("");
    expect(parseRaidRoomPublicId("solo")).toBe("");
    expect(defaultRaidRoomTitle("甲")).toBe("甲的房间");
    expect(defaultRaidRoomTitle("")).toBe("房间的房间");
    expect(defaultRaidRoomTitle("一".repeat(40)).length).toBe(40);
    expect(
      raidRoomJoinNeedsPassword({
        response: { status: 403, data: { detail: "需要房间密码" } },
      }),
    ).toBe(true);
    expect(
      raidRoomJoinNeedsPassword({
        response: { status: 403, data: { detail: "房间密码错误" } },
      }),
    ).toBe(false);
    expect(
      raidRoomJoinNeedsPassword({
        response: { status: 404, data: { detail: "需要房间密码" } },
      }),
    ).toBe(false);
    expect(isSoloRaidSession("solo")).toBe(true);
    expect(isSoloRaidSession("3")).toBe(false);
    expect(RAID_ROOM_SLOT_IDS).toEqual(["1", "2", "3", "4", "5"]);
    expect(raidRoomSlotIdsForMode("pve")).toEqual([
      "pve-1",
      "pve-2",
      "pve-3",
      "pve-4",
      "pve-5",
    ]);
    expect(raidRoomLiveStatus([1, 2], [])).toBe("preparing");
    expect(
      raidRoomLiveStatus(
        [1, 2],
        [{ userId: 2, kind: "raid_started", mapId: "", mapLabel: "", raidId: "", at: "" }],
      ),
    ).toBe("in_raid");
    expect(
      raidRoomLiveStatus(
        [1, 2],
        [{ userId: 2, kind: "raid_exited", mapId: "", mapLabel: "", raidId: "", at: "" }],
      ),
    ).toBe("preparing");
    expect(raidRoomActingHostUserId(1, [
      { user_id: 1, online: true, joined_at: "2026-09-01T00:00:00" },
      { user_id: 2, online: true, joined_at: "2026-09-01T00:01:00" },
    ])).toBe(1);
    expect(raidRoomActingHostUserId(1, [
      { user_id: 1, online: false, joined_at: "2026-09-01T00:00:00" },
      { user_id: 2, online: true, joined_at: "2026-09-01T00:02:00" },
      { user_id: 3, online: true, joined_at: "2026-09-01T00:01:00" },
    ])).toBe(3);
    expect(raidRoomCanAutoSwitchMap(3, 1, [
      { user_id: 1, online: false, joined_at: "2026-09-01T00:00:00" },
      { user_id: 3, online: true, joined_at: "2026-09-01T00:01:00" },
    ])).toBe(true);
    expect(raidRoomCanAutoSwitchMap(2, 1, [
      { user_id: 1, online: false, joined_at: "2026-09-01T00:00:00" },
      { user_id: 2, online: true, joined_at: "2026-09-01T00:02:00" },
      { user_id: 3, online: true, joined_at: "2026-09-01T00:01:00" },
    ])).toBe(false);
    expect(raidRoomCanAutoSwitchMap(2, 1, [
      { user_id: 1, online: true, joined_at: "2026-09-01T00:00:00" },
      { user_id: 2, online: true, joined_at: "2026-09-01T00:01:00" },
    ])).toBe(false);
    expect(
      raidRoomSharedRaidMapId({
        myUserId: 2,
        myRaidId: "pqxkr6",
        myMapId: "customs",
        myKind: "raid_started",
        currentMapId: "woods",
        occupantIds: [1, 2],
        phases: [
          { userId: 1, raidId: "PQXKR6", mapId: "customs", kind: "raid_started" },
          { userId: 2, raidId: "PQXKR6", mapId: "customs", kind: "raid_started" },
        ],
      }),
    ).toBe("customs");
    expect(
      raidRoomSharedRaidMapId({
        myUserId: 2,
        myRaidId: "PQXKR6",
        myMapId: "customs",
        myKind: "raid_started",
        currentMapId: "woods",
        occupantIds: [1, 2],
        phases: [
          { userId: 1, raidId: "AB12CD", mapId: "woods", kind: "raid_started" },
        ],
      }),
    ).toBe("");
    expect(
      raidRoomSharedRaidMapId({
        myUserId: 2,
        myRaidId: "PQXKR6",
        myMapId: "customs",
        myKind: "raid_exited",
        currentMapId: "woods",
        occupantIds: [1, 2],
        phases: [
          { userId: 1, raidId: "PQXKR6", mapId: "customs", kind: "raid_started" },
        ],
      }),
    ).toBe("");
    expect(
      raidRoomHostLogMapId({
        canSwitchMap: true,
        currentMapId: "woods",
        logMapId: "customs",
        phaseKind: "raid_started",
      }),
    ).toBe("customs");
    expect(
      raidRoomHostLogMapId({
        canSwitchMap: true,
        currentMapId: "woods",
        logMapId: "customs",
        phaseKind: "map_loading",
      }),
    ).toBe("customs");
    expect(
      raidRoomHostLogMapId({
        canSwitchMap: true,
        currentMapId: "woods",
        logMapId: "customs",
        phaseKind: "raid_exited",
      }),
    ).toBe("");
    expect(
      raidRoomHostLogMapId({
        canSwitchMap: false,
        currentMapId: "woods",
        logMapId: "customs",
        phaseKind: "raid_started",
      }),
    ).toBe("");
    expect(
      raidRoomHostLogMapId({
        canSwitchMap: true,
        currentMapId: "",
        logMapId: "customs",
        phaseKind: "raid_exited",
      }),
    ).toBe("customs");
    expect(formatRaidRoomLiveStatus("in_raid")).toBe("已在战局中");
    expect(
      formatRaidRoomMemberChipLine({
        name: "BaiYi",
        isHost: true,
        online: true,
        kind: "raid_started",
        mapLabel: "塔科夫街区",
      }),
    ).toBe("⭐BaiYi 在线 塔科夫街区");
    expect(
      formatRaidRoomMemberChipLine({
        name: "BaiYi",
        isHost: true,
        online: true,
        kind: "raid_exited",
        mapLabel: "塔科夫街区",
      }),
    ).toBe("⭐BaiYi 在线 大厅");
    expect(raidRoomMemberRegionLabel({ kind: "matching_aborted" })).toBe("大厅");
    expect(raidRoomMemberRegionLabel({ kind: "match_found", mapId: "streets" })).toBe(
      "塔科夫街区",
    );
    expect(
      formatRaidRoomMemberChipLine({
        name: "Teammate",
        isHost: false,
        online: false,
      }),
    ).toBe("Teammate 离线");
    expect(
      parseRaidRoomLogPhases([
        { user_id: 3, kind: "raid_started", map_id: "customs", raid_id: "AB12" },
      ]),
    ).toEqual([
      {
        userId: 3,
        kind: "raid_started",
        mapId: "customs",
        mapLabel: "",
        raidId: "AB12",
        at: "",
      },
    ]);
    expect(
      overlayRaidRoomLocalPhase(
        [
          {
            userId: 1,
            kind: "raid_started",
            mapId: "customs",
            mapLabel: "海关",
            raidId: "AB12",
            at: "1",
          },
          {
            userId: 2,
            kind: "raid_started",
            mapId: "customs",
            mapLabel: "海关",
            raidId: "AB12",
            at: "1",
          },
        ],
        2,
        {
          kind: "raid_exited",
          mapId: "customs",
          mapLabel: "海关",
          raidId: "AB12",
          at: "2",
        },
      ).map((row) => ({ userId: row.userId, kind: row.kind })),
    ).toEqual([
      { userId: 1, kind: "raid_started" },
      { userId: 2, kind: "raid_exited" },
    ]);
    expect(
      overlayRaidRoomLocalPhase([], 0, {
        kind: "raid_exited",
        mapId: "",
        mapLabel: "",
        raidId: "",
        at: "",
      }),
    ).toEqual([]);
    expect(
      mergeRaidLobbySeats(
        [
          { public_id: "1", member_count: 3 },
          { public_id: "pve-1", member_count: 2, map_slug: "customs" },
        ],
        raidRoomSlotIdsForMode("pve").map((id) => ({
          public_id: id,
          member_count: 0,
          map_slug: "",
        })),
      ),
    ).toEqual([
      { public_id: "pve-1", member_count: 2, map_slug: "customs" },
      { public_id: "pve-2", member_count: 0, map_slug: "" },
      { public_id: "pve-3", member_count: 0, map_slug: "" },
      { public_id: "pve-4", member_count: 0, map_slug: "" },
      { public_id: "pve-5", member_count: 0, map_slug: "" },
    ]);
    expect(
      mergeRaidLobbySeats(undefined, [
        { public_id: "1", member_count: 0 },
        { public_id: "2", member_count: 0 },
      ]),
    ).toEqual([
      { public_id: "1", member_count: 0 },
      { public_id: "2", member_count: 0 },
    ]);
    expect(raidRoomWsRetryDelayMs(0)).toBe(1000);
    expect(raidRoomWsRetryDelayMs(5)).toBe(30_000);
    expect(RAID_ROOM_WS_PING_MS).toBe(25_000);
    expect(
      roomDisplayTitle({ title: "", host_display_name: "甲" }, "海关"),
    ).toBe("甲 的 海关");
    expect(
      roomDisplayTitle({ title: "夜厂局", host_display_name: "甲" }, "海关"),
    ).toBe("夜厂局");
  });

  it("returns 回到房间 href only when seated elsewhere", () => {
    const items = [
      { public_id: "3", is_member: true },
      { public_id: "4", is_member: false },
    ];
    expect(raidRoomReturnHref(items, "/guides/tarkov")).toBe(
      "/guides/tarkov/raid-prep/rooms/3",
    );
    expect(raidRoomReturnHref(items, "/guides/tarkov/items/ammo")).toBe(
      "/guides/tarkov/raid-prep/rooms/3",
    );
    expect(raidRoomReturnHref(items, "/guides/tarkov/raid-prep/rooms/3")).toBe(
      "",
    );
    expect(raidRoomReturnHref(items, "/guides/tarkov/raid-prep/rooms/3/")).toBe(
      "",
    );
    expect(raidRoomReturnHref([{ public_id: "pve-2", is_member: true }], "/guides/tarkov")).toBe(
      "/guides/tarkov/raid-prep/rooms/pve-2",
    );
    expect(raidRoomReturnHref(items, "/guides/tarkov/raid-prep/rooms/pve-2")).toBe(
      "/guides/tarkov/raid-prep/rooms/3",
    );
    expect(raidRoomReturnHref([], "/guides/tarkov")).toBe("");
    expect(raidRoomReturnHref(null, "/guides/tarkov")).toBe("");
    expect(raidRoomReturnHref([{ public_id: "3", is_member: false }], "/guides/tarkov")).toBe(
      "",
    );
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
      "甲、乙拥有这把钥匙。\n丙带了这把钥匙。",
    );
    expect(keyOwnsForUser(["k1"], { userId: 3, name: "丙" })).toEqual([
      { item_id: "k1", user_id: 3, display_name: "丙" },
    ]);
    expect(userOwnsKey(keyOwnsForUser(["k1"], { userId: 3, name: "丙" }), "k1", 3)).toBe(
      true,
    );
    expect(userOwnsKey([], "k1", 3)).toBe(false);
    expect(formatKeyOwnToggleLabel(false)).toBe("我有");
    expect(formatKeyOwnToggleLabel(true)).toBe("取消");
    expect(
      patchRaidRoomKeyOwns([], "k1", { userId: 3, name: "丙" }, true),
    ).toEqual([{ item_id: "k1", user_id: 3, display_name: "丙" }]);
    expect(
      patchRaidRoomKeyOwns(
        [{ item_id: "k1", user_id: 3, display_name: "丙" }],
        "k1",
        { userId: 3, name: "丙" },
        false,
      ),
    ).toEqual([]);
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
    const same = applyRoomWsEvent(
      { ...room, claims: [{ user_id: 1, task_id: "t1", display_name: "甲" }] },
      {
        event: "snapshot",
        snapshot: {
          ...room,
          claims: [{ user_id: 1, task_id: "t1", display_name: "甲" }],
        },
        online_user_ids: [1],
      },
      1,
    );
    expect(same?.members?.map((row) => row.online)).toEqual([true, false]);
    expect(raidRoomLiveSig(same)).toBe(
      raidRoomLiveSig({ ...room, claims: [{ user_id: 1, task_id: "t1", display_name: "甲" }] }),
    );
    const kept = keepRaidRoomPresence(
      {
        ...room,
        members: [
          { user_id: 1, display_name: "甲", online: false },
          { user_id: 2, display_name: "乙", online: false },
        ],
      },
      {
        ...room,
        members: [
          { user_id: 1, display_name: "甲", online: true },
          { user_id: 2, display_name: "乙", online: true },
        ],
      },
    );
    expect(kept.members?.map((row) => row.online)).toEqual([true, true]);
    expect(keepRaidRoomPresence(room, null).members?.map((row) => row.online)).toEqual([
      false,
      false,
    ]);
    const staleSnap = applyRoomWsEvent(
      {
        ...room,
        members: [
          { user_id: 1, display_name: "甲", online: true },
          { user_id: 2, display_name: "乙", online: true },
        ],
      },
      {
        event: "snapshot",
        snapshot: {
          ...room,
          claims: [{ user_id: 1, task_id: "t2", display_name: "甲" }],
        },
      },
      1,
    );
    expect(staleSnap?.members?.map((row) => row.online)).toEqual([true, true]);
  });

  it("applies mark / claim / board patches without a snapshot", () => {
    const room: RaidRoomSnapshotLike = {
      public_id: "1",
      map_slug: "customs",
      host_user_id: 1,
      host_display_name: "甲",
      members: [{ user_id: 1, display_name: "甲", online: true }],
      marks: [],
      claims: [],
    };
    const added = applyRoomWsEvent(
      room,
      {
        event: "mark_add",
        mark: { id: 9, kind: "pin", x: 1, z: 2, author_user_id: 1 },
      },
      1,
    );
    expect(added?.marks).toEqual([
      { id: 9, kind: "pin", x: 1, z: 2, author_user_id: 1 },
    ]);
    const removed = applyRoomWsEvent(
      added,
      { event: "mark_remove", mark_id: 9 },
      1,
    );
    expect(removed?.marks).toEqual([]);
    const claimed = applyRoomWsEvent(
      room,
      {
        event: "claim_add",
        claims: [{ task_id: "t1", user_id: 1, display_name: "甲" }],
      },
      1,
    );
    expect(claimed?.claims).toEqual([
      { task_id: "t1", user_id: 1, display_name: "甲" },
    ]);
    const cleared = applyRoomWsEvent(
      { ...room, marks: [{ id: 1, kind: "pin", x: 0, z: 0, author_user_id: 1 }] },
      { event: "board_clear" },
      1,
    );
    expect(cleared?.marks).toEqual([]);
    const progress = applyRoomWsEvent(
      room,
      {
        event: "task_progress",
        map_overlap: [{ map_slug: "customs", with_tasks_count: 1, synced_count: 1, occupant_count: 1 }],
        task_progress: [{ user_id: 1, uploaded: true, started_count: 2 }],
      },
      1,
    );
    expect(progress?.map_overlap?.[0]?.map_slug).toBe("customs");
    expect(progress?.task_progress?.[0]?.started_count).toBe(2);
    const owns = applyRoomWsEvent(
      room,
      {
        event: "key_own_change",
        key_owns: [{ user_id: 1, item_id: "key-1", display_name: "甲" }],
      },
      1,
    );
    expect(owns?.key_owns).toEqual([
      { user_id: 1, item_id: "key-1", display_name: "甲" },
    ]);
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
    expect(isMapDrawTool("pin")).toBe(true);
    expect(isMapDrawTool("line")).toBe(true);
    expect(isMapDrawTool("erase")).toBe(true);
    expect(shouldRightButtonPanMap("pan")).toBe(false);
    expect(shouldRightButtonPanMap("pen")).toBe(true);
    expect(shouldRightButtonPanMap("erase")).toBe(true);
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
    expect(
      shouldSuppressLocalPlayerFix({
        viewMapId: "customs",
        logMapId: "woods",
        phaseKind: "raid_exited",
      }),
    ).toBe(false);
    expect(
      shouldSuppressLocalPlayerFix({
        viewMapId: "customs",
        logMapId: "woods",
        phaseKind: "raid_started",
      }),
    ).toBe(true);
    expect(
      shouldSuppressLocalPlayerFix({
        viewMapId: "customs",
        logMapId: "woods",
        phaseKind: "map_loading",
      }),
    ).toBe(true);
    expect(
      shouldSuppressLocalPlayerFix({
        viewMapId: "customs",
        logMapId: "bigmap",
        phaseKind: "raid_started",
      }),
    ).toBe(false);
    expect(
      shouldSuppressLocalPlayerFix({
        viewMapId: "customs",
        logMapId: "woods",
      }),
    ).toBe(false);
    expect(playerFixMarkerCaption("  BaiYi  ")).toBe("BaiYi");
    expect(playerFixMarkerCaption("")).toBe("");
    const local: Parameters<typeof collectPlayerFixMarks>[1] = {
      key: "self",
      userId: 12,
      name: "BaiYi",
      color: "#c8932a",
      x: 1,
      y: 0,
      z: 2,
      yaw: 0,
    };
    const remoteSelf = {
      ...local,
      key: "u:12",
      name: "BaiYi",
    };
    const teammate = {
      ...local,
      key: "u:3",
      userId: 3,
      name: "甲",
    };
    const collected = collectPlayerFixMarks([remoteSelf, teammate], local);
    expect(collected.map((row) => row.key)).toEqual(["u:3", "self"]);
    expect(collected.find((row) => row.self)?.name).toBe("BaiYi");
    expect(collected.find((row) => row.userId === 3)?.name).toBe("甲");
    expect(collectPlayerFixMarks([teammate], null).map((row) => row.key)).toEqual([
      "u:3",
    ]);
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

  it("builds a star of find-teammate pulse lines to the updater", () => {
    const marks = [
      { userId: 1, x: 0, y: 0, z: 0, key: "self", floor: "ground" },
      { userId: 2, x: 10, y: 0, z: 0, key: "u:2", floor: "ground" },
      { userId: 3, x: 0, y: 8, z: 10, key: "u:3", floor: "second" },
    ];
    expect(
      buildPlayerFixPulseLines({
        marks,
        updaterId: 2,
        now: 1000,
        seatedCount: 1,
      }),
    ).toEqual([]);
    expect(
      buildPlayerFixPulseLines({
        marks: [marks[1]!],
        updaterId: 2,
        now: 1000,
        seatedCount: 3,
      }),
    ).toEqual([]);
    const lines = buildPlayerFixPulseLines({
      marks,
      updaterId: 2,
      now: 1000,
      seatedCount: 3,
    });
    expect(lines.map((row) => `${row.fromUserId}->${row.toUserId}`).sort()).toEqual(
      ["1->2", "3->2"],
    );
    expect(lines.some((row) => row.fromUserId === 2)).toBe(false);
    expect(new Set(lines.map((row) => row.color))).toEqual(
      new Set([colorForUserId(2)]),
    );
    expect(lines.find((row) => row.fromUserId === 1)?.crossFloor).toBe(false);
    expect(lines.find((row) => row.fromUserId === 3)?.crossFloor).toBe(true);
    expect(playerFixPulseCrossFloor("", "second")).toBe(false);
    expect(playerFixPulseCrossFloor("ground", "second")).toBe(true);
    expect(playerFixPulseOpacity(1000, 1000)).toBe(1);
    expect(playerFixPulseOpacity(1000, 1000 + PLAYER_FIX_PULSE_MS / 2)).toBe(0.5);
    expect(playerFixPulseOpacity(1000, 1000 + PLAYER_FIX_PULSE_MS)).toBe(0);
    const replaced = replacePlayerFixPulseLines(
      lines,
      buildPlayerFixPulseLines({
        marks: [
          { userId: 1, x: 1, y: 0, z: 1, key: "self" },
          { userId: 2, x: 20, y: 0, z: 20, key: "u:2:next" },
        ],
        updaterId: 2,
        now: 2000,
        seatedCount: 3,
      }),
      2,
    );
    expect(replaced).toHaveLength(1);
    expect(replaced[0]).toMatchObject({
      fromUserId: 1,
      toUserId: 2,
      x2: 20,
      z2: 20,
      bornAt: 2000,
    });
    const otherPulse = buildPlayerFixPulseLines({
      marks,
      updaterId: 3,
      now: 1500,
      seatedCount: 3,
    });
    const both = replacePlayerFixPulseLines(lines, otherPulse, 3);
    expect(both.filter((row) => row.toUserId === 2)).toHaveLength(2);
    expect(both.filter((row) => row.toUserId === 3)).toHaveLength(2);
    expect(
      retainPlayerFixPulseLines(lines, { now: 1000, seatedCount: 1 }),
    ).toEqual([]);
    expect(
      retainPlayerFixPulseLines(lines, {
        now: 1000 + PLAYER_FIX_PULSE_MS,
        seatedCount: 3,
      }),
    ).toEqual([]);
    expect(
      retainPlayerFixPulseLines(lines, {
        now: 1000,
        seatedCount: 3,
        seatedUserIds: new Set([1, 2]),
      }).map((row) => row.fromUserId),
    ).toEqual([1]);
    expect(
      retainPlayerFixPulseLines(lines, {
        now: 1000,
        seatedCount: 3,
        locatedUserIds: new Set([2, 3]),
      }).map((row) => row.fromUserId),
    ).toEqual([3]);
    const hydrated = detectPlayerFixPulseUpdaters(null, marks);
    expect(hydrated.updaterIds).toEqual([]);
    expect(
      detectPlayerFixPulseUpdaters(hydrated.next, [
        marks[0]!,
        { ...marks[1]!, key: "u:2:shot2", x: 11 },
        marks[2]!,
      ]).updaterIds,
    ).toEqual([2]);
    expect(
      detectPlayerFixPulseUpdaters(hydrated.next, marks).updaterIds,
    ).toEqual([]);
    expect(playerFixPulseLinesEqual(lines, lines)).toBe(true);
    expect(playerFixPulseLinesEqual(lines, replaced)).toBe(false);
  });

  it("walks pulse-demo bots around customs waypoints", () => {
    expect(isPulseDemoSession("pulse-demo")).toBe(true);
    expect(isPulseDemoSession("solo")).toBe(false);
    const first = pulseDemoFixAt({
      userId: PULSE_DEMO_BOTS[0].userId,
      step: 0,
      now: 10,
    });
    const next = pulseDemoFixAt({
      userId: PULSE_DEMO_BOTS[0].userId,
      step: 1,
      now: 20,
    });
    expect(first).toMatchObject({
      userId: 900001,
      mapId: PULSE_DEMO_MAP_ID,
      at: 10,
    });
    expect(next?.x).not.toBe(first?.x);
    expect(pulseDemoFixAt({ userId: 7, step: 0 })).toBeNull();
    expect(pulseDemoMembers(null).map((row) => row.user_id)).toEqual([
      900001, 900002,
    ]);
    expect(
      pulseDemoMembers({ user_id: 12, display_name: "我" }).map(
        (row) => row.user_id,
      ),
    ).toEqual([12, 900001, 900002]);
  });

  it("formats overlap cells and ranks map rows", () => {
    expect(formatRaidRoomOverlapCell(undefined)).toBe("—");
    expect(formatRaidRoomOverlapCell({ user_id: 1, count: 0, uploaded: false })).toBe("—");
    expect(formatRaidRoomOverlapCell({ user_id: 1, count: 3, uploaded: true })).toBe("3");
    expect(raidRoomOverlapPeopleLabel(2)).toBe("2人");
    expect(
      raidRoomOverlapTasksForUser(
        {
          map_slug: "customs",
          with_tasks_count: 2,
          synced_count: 2,
          occupant_count: 2,
          tasks: [
            { id: "t1", name: "A", user_ids: [1, 2] },
            { id: "t2", name: "B", user_ids: [1] },
          ],
        },
        2,
      ).map((row) => row.id),
    ).toEqual(["t1"]);
    const ranked = sortRaidRoomMapOverlap(
      [
        {
          map_slug: "woods",
          with_tasks_count: 1,
          synced_count: 2,
          occupant_count: 2,
        },
        {
          map_slug: "customs",
          with_tasks_count: 2,
          synced_count: 2,
          occupant_count: 2,
          cells: [
            { user_id: 1, count: 3, uploaded: true },
            { user_id: 2, count: 1, uploaded: true },
          ],
        },
        {
          map_slug: "factory",
          with_tasks_count: 2,
          synced_count: 2,
          occupant_count: 2,
          cells: [
            { user_id: 1, count: 1, uploaded: true },
            { user_id: 2, count: 1, uploaded: true },
          ],
        },
      ],
      ["factory", "customs", "woods"],
    );
    expect(ranked.map((row) => row.map_slug)).toEqual(["customs", "factory", "woods"]);
    expect(
      raidRoomPickDockMapId({
        goonMapSlug: "woods",
        overlapSlugs: ["customs", "factory"],
        mapOptionIds: ["factory", "customs", "woods"],
      }),
    ).toBe("woods");
    expect(
      raidRoomPickDockMapId({
        overlapSlugs: ["customs", "factory"],
        mapOptionIds: ["factory", "customs", "woods"],
      }),
    ).toBe("customs");
  });
});

describe("solo as one-person room", () => {
  it("projects prep state into a listed=false 1-seat room", () => {
    expect(soloRaidActor(null)).toEqual({ userId: 0, name: "游客" });
    expect(soloRaidActor({ id: 7, displayName: "鸽" })).toEqual({
      userId: 7,
      name: "鸽",
    });
    const room = buildSoloRaidRoomDetail({
      gameMode: "pve",
      mapSlug: "customs",
      user: { id: 7, displayName: "鸽" },
      selectedIds: ["task-a"],
      keyBringIds: ["key-1"],
      keyOwnIds: ["key-2"],
      objectiveDones: [{ task_id: "task-a", objective_id: "obj-1" }],
    });
    expect(room.public_id).toBe(SOLO_RAID_ROOM_PUBLIC_ID);
    expect(room.listed).toBe(false);
    expect(room.member_count).toBe(1);
    expect(room.max_members).toBe(1);
    expect(room.is_member).toBe(true);
    expect(room.is_host).toBe(true);
    expect(room.can_edit).toBe(true);
    expect(room.claims).toEqual([
      { task_id: "task-a", user_id: 7, display_name: "鸽" },
    ]);
    expect(room.key_brings).toEqual([
      { item_id: "key-1", user_id: 7, display_name: "鸽" },
    ]);
    expect(room.key_owns).toEqual([
      { item_id: "key-2", user_id: 7, display_name: "鸽" },
    ]);
    expect(room.objective_dones).toEqual([
      {
        task_id: "task-a",
        objective_id: "obj-1",
        user_id: 7,
        display_name: "鸽",
      },
    ]);
    expect(room.marks).toEqual([]);
  });

  it("keeps guest seat editable without occupying a lobby slot", () => {
    const room = buildSoloRaidRoomDetail({
      gameMode: "pvp",
      mapSlug: "woods",
    });
    expect(room.host_user_id).toBeNull();
    expect(room.members[0]?.user_id).toBe(0);
    expect(room.occupants[0]?.display_name).toBe("游客");
    expect(isSoloRaidSession(room.public_id)).toBe(true);
  });
});

