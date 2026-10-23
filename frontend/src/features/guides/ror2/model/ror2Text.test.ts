import { describe, expect, it } from "vitest";
import { ror2ResolvedText, ror2TextContent, toRor2ResolvedText } from "./ror2Text";

describe("ror2 token text fallback", () => {
  it("preserves approved text, original source, and exact Weblate context", () => {
    const value = { text: "已审译文", original: "Wiki source", token: "items.ITEM_X.name" };

    expect(toRor2ResolvedText(value)).toEqual(value);
    expect(ror2TextContent(value)).toBe("已审译文");
  });

  it("does not create token metadata for plain local text", () => {
    expect(toRor2ResolvedText("本站提示")).toEqual({
      text: "本站提示",
      original: "本站提示",
      token: null,
    });
  });
  it("prefers a non-empty approved translation", () => {
    expect(ror2ResolvedText("已审核译文", "Wiki source")).toBe("已审核译文");
  });

  it("falls back to the source when no translation is available", () => {
    expect(ror2ResolvedText(undefined, "Wiki source")).toBe("Wiki source");
    expect(ror2ResolvedText(null, "Wiki source")).toBe("Wiki source");
    expect(ror2ResolvedText("", "Wiki source")).toBe("Wiki source");
    expect(ror2ResolvedText("   ", "Wiki source")).toBe("Wiki source");
  });

  it("returns an empty string when neither translation nor source exists", () => {
    expect(ror2ResolvedText(undefined, undefined)).toBe("");
  });
});
