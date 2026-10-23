import { describe, expect, it } from "vitest";
import { isBilibiliArknightsChannel } from "./arknightsChannel";

describe("isBilibiliArknightsChannel", () => {
  it("matches bili aliases", () => {
    expect(isBilibiliArknightsChannel("Bilibili")).toBe(true);
    expect(isBilibiliArknightsChannel("哔哩哔哩")).toBe(true);
    expect(isBilibiliArknightsChannel("B服")).toBe(true);
    expect(isBilibiliArknightsChannel("b 服")).toBe(true);
  });

  it("rejects empty and official", () => {
    expect(isBilibiliArknightsChannel(null)).toBe(false);
    expect(isBilibiliArknightsChannel("")).toBe(false);
    expect(isBilibiliArknightsChannel("官服")).toBe(false);
  });
});
