import { describe, expect, it } from "vitest";

import { steamProfileUrl } from "@/components/steam/timelineUtils";

describe("steamProfileUrl", () => {
  it("opens the official Steam profile for a steamid64", () => {
    expect(steamProfileUrl("76561198000000001")).toBe(
      "https://steamcommunity.com/profiles/76561198000000001",
    );
  });
});
