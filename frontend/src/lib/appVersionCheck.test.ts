import { describe, expect, it } from "vitest";
import { appBundleOutdated, normalizeAppVersion } from "./appVersionCheck";

describe("normalizeAppVersion", () => {
  it("strips the v prefix and whitespace", () => {
    expect(normalizeAppVersion(" v0.5.16\n")).toBe("0.5.16");
    expect(normalizeAppVersion("V1.0.0")).toBe("1.0.0");
    expect(normalizeAppVersion("0.5.16")).toBe("0.5.16");
  });

  it("treats a missing version as empty", () => {
    expect(normalizeAppVersion(undefined)).toBe("");
    expect(normalizeAppVersion(null)).toBe("");
    expect(normalizeAppVersion("  ")).toBe("");
  });
});

describe("appBundleOutdated", () => {
  it("flags any mismatch, upgrade or rollback", () => {
    expect(appBundleOutdated("0.5.16", "v0.5.17")).toBe(true);
    expect(appBundleOutdated("0.5.17", "0.5.16")).toBe(true);
  });

  it("keeps quiet when the versions match after normalizing", () => {
    expect(appBundleOutdated("0.5.16", "v0.5.16")).toBe(false);
  });

  it("does not compare when either side has no version, or for dev builds", () => {
    expect(appBundleOutdated("0.5.16", "")).toBe(false);
    expect(appBundleOutdated("0.5.16", undefined)).toBe(false);
    expect(appBundleOutdated("", "0.5.16")).toBe(false);
    expect(appBundleOutdated("dev", "0.5.16")).toBe(false);
  });
});
