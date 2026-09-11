import { describe, expect, it } from "vitest";
import {
  axiosRequestPath,
  formatRumMs,
  isImagePath,
  shouldCollectApiUrl,
  shouldCollectImageResource,
} from "./rumCollect";

describe("shouldCollectApiUrl", () => {
  it("skips ingest and polling", () => {
    expect(shouldCollectApiUrl("/api/client-rum")).toBe(false);
    expect(shouldCollectApiUrl("/api/client-errors")).toBe(false);
    expect(shouldCollectApiUrl("/api/settings/runtime-logs")).toBe(false);
    expect(shouldCollectApiUrl("/api/settings/runtime-health")).toBe(false);
    expect(shouldCollectApiUrl("/api/settings/rum")).toBe(false);
    expect(shouldCollectApiUrl("/health")).toBe(false);
  });

  it("collects business APIs", () => {
    expect(shouldCollectApiUrl("/api/guides/tarkov/items")).toBe(true);
    expect(shouldCollectApiUrl("/guides/tarkov/maps")).toBe(true);
  });
});

describe("axiosRequestPath", () => {
  it("joins baseURL and relative url", () => {
    expect(axiosRequestPath({ baseURL: "/api", url: "/guides/tarkov/items" })).toBe(
      "/api/guides/tarkov/items",
    );
    expect(
      axiosRequestPath({
        baseURL: "/api",
        url: "guides/tarkov/items?game_mode=pve",
      }),
    ).toBe("/api/guides/tarkov/items");
  });

  it("uses pathname of absolute urls", () => {
    expect(
      axiosRequestPath({ url: "https://example.test/api/members/1?x=1" }),
    ).toBe("/api/members/1");
  });
});

describe("shouldCollectImageResource", () => {
  const origin = "https://zhange.example";

  it("collects third-party img and tile png", () => {
    expect(
      shouldCollectImageResource({
        name: "https://assets.tarkov.dev/foo-icon.webp",
        initiatorType: "img",
        pageOrigin: origin,
      }),
    ).toBe(true);
    expect(
      shouldCollectImageResource({
        name: "https://assets.tarkov.dev/maps/factory/0/0/0.png",
        initiatorType: "css",
        pageOrigin: origin,
      }),
    ).toBe(true);
  });

  it("skips same-origin, scripts, fetch, data", () => {
    expect(
      shouldCollectImageResource({
        name: `${origin}/uploads/avatars/1.jpg`,
        initiatorType: "img",
        pageOrigin: origin,
      }),
    ).toBe(false);
    expect(
      shouldCollectImageResource({
        name: "https://static.geetest.com/gt.js",
        initiatorType: "script",
        pageOrigin: origin,
      }),
    ).toBe(false);
    expect(
      shouldCollectImageResource({
        name: "https://assets.tarkov.dev/items.json",
        initiatorType: "fetch",
        pageOrigin: origin,
      }),
    ).toBe(false);
    expect(
      shouldCollectImageResource({
        name: "data:image/png;base64,aaa",
        initiatorType: "img",
        pageOrigin: origin,
      }),
    ).toBe(false);
  });
});

describe("isImagePath / formatRumMs", () => {
  it("detects image extensions", () => {
    expect(isImagePath("/a/b.webp")).toBe(true);
    expect(isImagePath("/a/b.js")).toBe(false);
  });

  it("formats wait time", () => {
    expect(formatRumMs(null)).toBe("—");
    expect(formatRumMs(340)).toBe("340 ms");
    expect(formatRumMs(1200)).toBe("1.20 s");
  });
});
