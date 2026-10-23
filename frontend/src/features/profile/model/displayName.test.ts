import { describe, expect, it } from "vitest";
import { DISPLAY_NAME_MARKUP_ERROR, displayNameError, displayNameRules } from "./displayName";

describe("displayNameError", () => {
  it("rejects angle brackets anywhere in the name", () => {
    expect(displayNameError("<b>阿鸽</b>")).toBe(DISPLAY_NAME_MARKUP_ERROR);
    expect(displayNameError("a>b")).toBe(DISPLAY_NAME_MARKUP_ERROR);
    expect(displayNameError("x<")).toBe(DISPLAY_NAME_MARKUP_ERROR);
  });

  it("accepts ordinary names, including other punctuation", () => {
    expect(displayNameError("战鸽 & 朋友 \"测试\"")).toBeNull();
    expect(displayNameError("")).toBeNull();
    expect(displayNameError(undefined)).toBeNull();
  });
});

describe("displayNameRules", () => {
  const validator = displayNameRules[1].validator!;

  it("surfaces the backend wording through the form validator", async () => {
    await expect(validator({}, "<script>")).rejects.toThrow(DISPLAY_NAME_MARKUP_ERROR);
    await expect(validator({}, "阿鸽")).resolves.toBeUndefined();
    await expect(validator({}, undefined)).resolves.toBeUndefined();
  });
});
