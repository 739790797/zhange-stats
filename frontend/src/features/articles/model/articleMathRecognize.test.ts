import {
  isNearWhiteCanvas,
  MATH_RECOGNIZE_MAX_BYTES,
  rejectMathRecognizeFile,
} from "./articleMathRecognize";
import { describe, expect, it } from "vitest";

describe("articleMathRecognize", () => {
  it("rejects empty oversized and non-image files", () => {
    expect(rejectMathRecognizeFile({ size: 0, type: "image/png" })).toBe(
      "文件为空",
    );
    expect(
      rejectMathRecognizeFile({
        size: MATH_RECOGNIZE_MAX_BYTES + 1,
        type: "image/png",
      }),
    ).toBe("识别图片不能超过 2MB");
    expect(rejectMathRecognizeFile({ size: 12, type: "application/pdf" })).toBe(
      "请上传公式图片",
    );
    expect(rejectMathRecognizeFile({ size: 12, type: "image/png" })).toBeNull();
    expect(rejectMathRecognizeFile({ size: 12 })).toBeNull();
  });

  it("treats near-white pixels as a blank pad", () => {
    expect(isNearWhiteCanvas([])).toBe(true);
    expect(isNearWhiteCanvas([255, 255, 255, 255, 254, 254, 254, 255])).toBe(
      true,
    );
    expect(isNearWhiteCanvas([255, 255, 255, 255, 10, 10, 10, 255])).toBe(
      false,
    );
    expect(isNearWhiteCanvas([10, 10, 10, 0, 255, 255, 255, 255])).toBe(true);
  });
});
