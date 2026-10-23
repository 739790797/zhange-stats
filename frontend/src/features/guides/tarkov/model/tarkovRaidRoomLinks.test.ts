import { describe, expect, it } from "vitest";
import { tarkovRaidRoomHref } from "./tarkovHomeNav";
import {
  RAID_ROOM_SLOT_COUNT,
  normalizeRaidRoomPublicId,
  parseRaidRoomPublicId,
  raidRoomReturnHref,
  raidRoomSlotPublicId,
} from "./tarkovRaidRoomLinks";

describe("raid room link helpers", () => {
  it("parses pasted room codes and urls", () => {
    expect(parseRaidRoomPublicId("https://x/guides/tarkov/raid-prep/rooms/3")).toBe("3");
    expect(parseRaidRoomPublicId("https://x/guides/tarkov/raid-prep/rooms/pve-2")).toBe("pve-2");
    expect(parseRaidRoomPublicId("https://x/guides/tarkov/raid-prep/rooms/ab12cd34")).toBe("ab12cd34");
    expect(parseRaidRoomPublicId("1")).toBe("1");
    expect(parseRaidRoomPublicId("1", "pve")).toBe("pve-1");
    expect(parseRaidRoomPublicId("ABCDEF123456")).toBe("abcdef123456");
    expect(parseRaidRoomPublicId("solo")).toBe("");
    expect(parseRaidRoomPublicId("")).toBe("");
  });

  it("rejects codes that are neither a slot nor a random id", () => {
    expect(parseRaidRoomPublicId("6")).toBe("");
    expect(parseRaidRoomPublicId("nope")).toBe("");
    expect(normalizeRaidRoomPublicId("  SOLO ")).toBe("");
  });

  it("builds legacy slot ids", () => {
    expect(raidRoomSlotPublicId(3)).toBe("3");
    expect(raidRoomSlotPublicId(3, "pve")).toBe("pve-3");
    expect(raidRoomSlotPublicId(0)).toBe("");
    expect(raidRoomSlotPublicId(RAID_ROOM_SLOT_COUNT + 1)).toBe("");
  });
});

describe("raidRoomReturnHref", () => {
  const items = [
    { public_id: "3", is_member: true },
    { public_id: "4", is_member: false },
  ];

  it("points back to the seated room from elsewhere", () => {
    expect(raidRoomReturnHref(items, "/guides/tarkov")).toBe(
      tarkovRaidRoomHref("3"),
    );
    expect(raidRoomReturnHref([{ public_id: "pve-2", is_member: true }], "/guides/tarkov")).toBe(
      tarkovRaidRoomHref("pve-2"),
    );
  });

  it("returns nothing when not seated or already in that room", () => {
    expect(raidRoomReturnHref(items, "/guides/tarkov/raid-prep/rooms/3")).toBe("");
    expect(raidRoomReturnHref(items, "/guides/tarkov/raid-prep/rooms/3/")).toBe("");
    expect(raidRoomReturnHref([], "/guides/tarkov")).toBe("");
    expect(raidRoomReturnHref(null, "/guides/tarkov")).toBe("");
    expect(raidRoomReturnHref([{ public_id: "3", is_member: false }], "/guides/tarkov")).toBe("");
  });
});
