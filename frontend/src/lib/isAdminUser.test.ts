import { describe, expect, it } from "vitest";
import { isAdminUser } from "./isAdminUser";
import {
  firstEnabledPlatformPath,
  isFeatureOn,
} from "./platformFeatures";

describe("isAdminUser", () => {
  it("returns false for nullish", () => {
    expect(isAdminUser(null)).toBe(false);
    expect(isAdminUser(undefined)).toBe(false);
  });

  it("accepts role admin", () => {
    expect(isAdminUser({ role: "admin" })).toBe(true);
  });

  it("accepts derived is_admin", () => {
    expect(isAdminUser({ role: "user", is_admin: true })).toBe(true);
  });

  it("rejects plain user", () => {
    expect(isAdminUser({ role: "user", is_admin: false })).toBe(false);
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
  });
});
