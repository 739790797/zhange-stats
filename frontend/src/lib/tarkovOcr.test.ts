import { describe, expect, it } from "vitest";
import {
  formatOcrProgress,
  mergeOcrSelection,
  newOcrIds,
  ocrFuzzyScore,
  ocrOutputScale,
} from "./tarkovOcr";

describe("formatOcrProgress", () => {
  it("maps tesseract status", () => {
    expect(formatOcrProgress("loading tesseract core")).toBe(
      "正在加载识别引擎…",
    );
    expect(formatOcrProgress("loading language traineddata")).toBe(
      "正在加载识别模型…",
    );
    expect(formatOcrProgress("recognizing text", 0.4)).toBe("正在识别文字… 40%");
    expect(formatOcrProgress("matching icons", 0.2)).toBe("正在比对钥匙图标… 20%");
  });
});

describe("ocrOutputScale", () => {
  it("keeps requested scale when under cap", () => {
    expect(ocrOutputScale(800, 600, 2, 1920)).toBe(2);
  });

  it("caps longest edge", () => {
    expect(ocrOutputScale(1920, 1080, 2, 1920)).toBe(1);
    expect(ocrOutputScale(2560, 1440, 2, 1920)).toBeCloseTo(1920 / 2560);
  });
});

describe("ocrFuzzyScore", () => {
  it("treats one-edit short codes as close", () => {
    expect(ocrFuzzyScore("rbst", "rb5t")).toBeGreaterThanOrEqual(0.82);
  });
});

describe("selection helpers", () => {
  it("merges and reports new ids", () => {
    expect(mergeOcrSelection(["a", "b"], ["b", "c"], 40)).toEqual([
      "a",
      "b",
      "c",
    ]);
    expect(newOcrIds(["a", "b"], ["b", "c", "a"])).toEqual(["c"]);
  });
});
