import { describe, expect, it } from "vitest";
import { overlayBoxColor, overlayBoxLabel } from "./tarkovKeyOcrOverlay";

describe("overlayBoxColor", () => {
  it("uses hit / fuzzy / miss colors", () => {
    expect(overlayBoxColor("hit")).toBe("#22c55e");
    expect(overlayBoxColor("fuzzy")).toBe("#eab308");
    expect(overlayBoxColor("miss")).toBe("#9ca3af");
    expect(overlayBoxColor()).toBe("#9ca3af");
  });
});

describe("overlayBoxLabel", () => {
  it("keeps short names and trims long OCR text", () => {
    expect(overlayBoxLabel({ x: 0, y: 0, width: 1, height: 1, label: "西203" })).toBe(
      "西203",
    );
    expect(
      overlayBoxLabel({
        x: 0,
        y: 0,
        width: 1,
        height: 1,
        label: "abcdefghijklmnopq",
      }),
    ).toBe("abcdefghijklmno…");
  });
});
