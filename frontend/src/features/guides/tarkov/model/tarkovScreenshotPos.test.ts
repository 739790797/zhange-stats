import { describe, expect, it } from "vitest";
import {
  gameForwardXZ,
  gameYawToCssDeg,
  normalizeHeadingDeg,
  parseTarkovScreenshotName,
  quaternionToYawDeg,
  screenDeltaToCssDeg,
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

  it("matches TarkovMonitor euler Y for a 180 turn", () => {
    expect(normalizeHeadingDeg(quaternionToYawDeg(0, 1, 0, 0))).toBeCloseTo(
      180,
      5,
    );
  });
});

describe("gameForwardXZ", () => {
  it("faces +Z at yaw 0 and +X at yaw 90", () => {
    expect(gameForwardXZ(0).z).toBeCloseTo(1, 5);
    expect(gameForwardXZ(0).x).toBeCloseTo(0, 5);
    expect(gameForwardXZ(90).x).toBeCloseTo(1, 5);
    expect(gameForwardXZ(90).z).toBeCloseTo(0, 5);
  });
});

describe("gameYawToCssDeg", () => {
  it("points down on 180 maps when facing +Z", () => {
    expect(normalizeHeadingDeg(gameYawToCssDeg(0, 180))).toBeCloseTo(180, 5);
    expect(gameYawToCssDeg(-12.4, 180)).toBeCloseTo(167.6, 5);
  });

  it("treats interchange the same as other 180 maps", () => {
    expect(normalizeHeadingDeg(screenshotYawToMapDeg(0, 180))).toBeCloseTo(
      180,
      5,
    );
  });

  it("includes the 90/270 map flip that tarkov.dev adds", () => {
    expect(normalizeHeadingDeg(gameYawToCssDeg(0, 90))).toBeCloseTo(270, 5);
    expect(normalizeHeadingDeg(gameYawToCssDeg(0, 270))).toBeCloseTo(90, 5);
  });
});

describe("screenDeltaToCssDeg", () => {
  it("maps screen down to 180 and right to 90", () => {
    expect(normalizeHeadingDeg(screenDeltaToCssDeg(0, 1))).toBeCloseTo(180, 5);
    expect(normalizeHeadingDeg(screenDeltaToCssDeg(1, 0))).toBeCloseTo(90, 5);
  });
});
