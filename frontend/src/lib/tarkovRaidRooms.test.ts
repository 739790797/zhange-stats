import { describe, expect, it } from "vitest";
import { tarkovRaidRoomHref } from "./tarkovHomeNav";
import {
  applyRoomWsEvent,
  claimedTaskIds,
  formatRoomRemain,
  groupClaimsByTask,
  markMatchesFloor,
  remainMs,
  roomDisplayTitle,
} from "./tarkovRaidRooms";

describe("raid room helpers", () => {
  it("builds room href and default title", () => {
    expect(tarkovRaidRoomHref("abc")).toBe("/guides/tarkov/raid-prep/rooms/abc");
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
});
