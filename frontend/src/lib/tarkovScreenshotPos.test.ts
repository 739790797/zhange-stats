import { describe, expect, it } from "vitest";
import {
  parseTarkovScreenshotName,
  quaternionToYawDeg,
  screenshotYawToMapDeg,
} from "./tarkovScreenshotPos";

describe("parseTarkovScreenshotName", () => {
  it("reads raid coordinates and facing from the in-game filename", () => {
    const parsed = parseTarkovScreenshotName(
      "2025-03-30[21-04]_175.30, 1.37, 150.68_-0.01464, 0.98439, -0.14329, -0.10113_9.53 (0).png",
    );
    expect(parsed).toMatchObject({
      x: 175.3,
      y: 1.37,
      z: 150.68,
    });
    expect(parsed?.yaw).toEqual(expect.any(Number));
  });

  it("accepts another raid filename from TarkovMonitor reports", () => {
    const parsed = parseTarkovScreenshotName(
      "2025-04-14[20-42]_14.31, 2.55, 57.88_0.17434, 0.81716, -0.31801, 0.44802_15.47 (0).png",
    );
    expect(parsed).toMatchObject({
      x: 14.31,
      y: 2.55,
      z: 57.88,
    });
  });

  it("ignores lobby screenshots that only have raid time", () => {
    expect(
      parseTarkovScreenshotName("2026-08-30[21-35]_19.91 (0).png"),
    ).toBeNull();
  });

  it("returns null for unrelated names", () => {
    expect(parseTarkovScreenshotName("old.png")).toBeNull();
    expect(parseTarkovScreenshotName("")).toBeNull();
  });
});

describe("quaternionToYawDeg", () => {
  it("maps identity to about 0", () => {
    expect(quaternionToYawDeg(0, 0, 0, 1)).toBeCloseTo(0, 5);
  });
});

describe("screenshotYawToMapDeg", () => {
  it("adds 180 so an up-pointing CSS arrow matches raid heading", () => {
    expect(screenshotYawToMapDeg(0, 180)).toBe(360);
    expect(screenshotYawToMapDeg(-12.4, 180)).toBeCloseTo(347.6, 5);
  });

  it("matches tarkov.dev extra flip on 90 and 270 maps", () => {
    expect(screenshotYawToMapDeg(0, 90)).toBe(270);
    expect(screenshotYawToMapDeg(0, 270)).toBe(450);
  });
});
