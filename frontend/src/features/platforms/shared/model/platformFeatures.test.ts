import { describe, expect, it } from "vitest";
import {
  PLATFORM_NAV,
  firstEnabledPlatformPath,
  isFeatureOn,
  platformFeatureMenuKey,
  resolvePlatformFeaturePageTitle,
  resolvePlatformFeatureTabKey,
} from "@/features/platforms/shared/model/platformFeatures";

describe("platform feature navigation", () => {
  it("uses the check-in tab as the platform landing page", () => {
    const items = [{ key: "exchange" }, { key: "checkin" }, { key: "ww" }];
    expect(resolvePlatformFeatureTabKey(items, null, "checkin")).toBe("checkin");
  });

  it("uses the selected submenu label as the page title", () => {
    expect(
      resolvePlatformFeaturePageTitle("森空岛", { key: "checkin", label: "签到" }),
    ).toBe("森空岛");
    expect(
      resolvePlatformFeaturePageTitle("森空岛", {
        key: "endfield",
        label: "明日方舟：终末地",
      }),
    ).toBe("明日方舟：终末地");
  });

  it("selects a requested submenu feature and falls back for stale links", () => {
    const items = [{ key: "checkin" }, { key: "arknights" }];
    expect(resolvePlatformFeatureTabKey(items, "arknights", "checkin")).toBe(
      "arknights",
    );
    expect(resolvePlatformFeatureTabKey(items, "removed", "checkin")).toBe(
      "checkin",
    );
  });

  it("does not show another feature on the landing page if check-in is disabled", () => {
    expect(
      resolvePlatformFeatureTabKey([{ key: "exchange" }], null, "checkin"),
    ).toBe("");
  });

  it("builds stable query-based links for submenu entries", () => {
    expect(platformFeatureMenuKey("/skland", "endfield")).toBe(
      "/skland?tab=endfield",
    );
    expect(platformFeatureMenuKey("/platform", "feature / one")).toBe(
      "/platform?tab=feature%20%2F%20one",
    );
  });

  it("gives every check-in platform child an icon", () => {
    const checkinPlatforms = PLATFORM_NAV.filter((item) => item.path !== "/steam");
    expect(checkinPlatforms.every((item) => item.children?.length)).toBe(true);
    expect(
      checkinPlatforms.every((item) =>
        item.children?.every((child) => Boolean(child.icon)),
      ),
    ).toBe(true);
  });
});

describe("platformFeatures", () => {
  it("fail-closed when map missing", () => {
    expect(isFeatureOn(null, "steam")).toBe(false);
    expect(isFeatureOn(undefined, "steam")).toBe(false);
  });

  it("requires exact true", () => {
    expect(isFeatureOn({ steam: true }, "steam")).toBe(true);
    expect(isFeatureOn({ steam: false }, "steam")).toBe(false);
    expect(isFeatureOn({}, "steam")).toBe(false);
  });

  it("picks first enabled nav path", () => {
    expect(firstEnabledPlatformPath(null)).toBe("/profile");
    expect(firstEnabledPlatformPath({ skland: true })).toBe("/skland");
    expect(firstEnabledPlatformPath({ steam: true, skland: true })).toBe(
      "/steam",
    );
    expect(firstEnabledPlatformPath({ "guides.tarkov": true })).toBe(
      "/guides/tarkov",
    );
  });
});
