import { describe, expect, it } from "vitest";
import {
  CHECKIN_PLATFORM_ORDER,
  communityGameRank,
  displayCheckinChannelName,
  formatCheckinTime,
  platformRank,
} from "./checkinDisplay";

describe("checkinDisplay", () => {
  it("excludes steam from checkin platform order", () => {
    expect(CHECKIN_PLATFORM_ORDER).not.toContain("steam");
    expect(platformRank("skland")).toBeLessThan(platformRank("unknown"));
  });

  it("ranks community game codes first", () => {
    expect(communityGameRank("app")).toBe(0);
    expect(communityGameRank("kujiequ")).toBe(0);
    expect(communityGameRank("exilium_bbs")).toBe(0);
    expect(communityGameRank("mihoyo")).toBe(0);
    expect(communityGameRank("genshin")).toBe(1);
  });

  it("normalizes legacy community channel copy", () => {
    expect(displayCheckinChannelName("社区签到")).toBe("社区");
    expect(displayCheckinChannelName("官服")).toBe("官服");
    expect(displayCheckinChannelName("  ")).toBeNull();
  });

  it("pads checkin clock", () => {
    expect(formatCheckinTime(8, 5)).toBe("08:05");
    expect(formatCheckinTime(0, 0)).toBe("00:00");
  });
});
