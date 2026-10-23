import { describe, expect, it } from "vitest";
import { secretPayloadValue, secretPlaceholder } from "./secretInput";

describe("secretPlaceholder", () => {
  it("shows the hint tail when the secret is stored", () => {
    expect(secretPlaceholder({ set: true, hint: "a1b2", empty: "请输入" })).toBe(
      "已设置（…a1b2），留空不修改",
    );
  });

  it("falls back to a hint-less copy for short secrets", () => {
    expect(secretPlaceholder({ set: true, hint: "", empty: "请输入" })).toBe(
      "已设置，留空不修改",
    );
    expect(secretPlaceholder({ set: true, empty: "请输入" })).toBe("已设置，留空不修改");
  });

  it("uses the empty copy when nothing is stored", () => {
    expect(secretPlaceholder({ set: false, hint: "zzzz", empty: "请输入 Key" })).toBe(
      "请输入 Key",
    );
  });

  it("says the secret will be cleared while a clear is pending", () => {
    expect(
      secretPlaceholder({ set: true, hint: "a1b2", clearing: true, empty: "请输入" }),
    ).toBe("保存后清除");
  });
});

describe("secretPayloadValue", () => {
  it("sends null for blank input so the stored secret is kept", () => {
    expect(secretPayloadValue("", false)).toBeNull();
    expect(secretPayloadValue("   ", false)).toBeNull();
    expect(secretPayloadValue(undefined, false)).toBeNull();
  });

  it("sends the trimmed new value", () => {
    expect(secretPayloadValue("  key-123 ", false)).toBe("key-123");
  });

  it("never sends a new value alongside a clear", () => {
    expect(secretPayloadValue("key-123", true)).toBeNull();
  });
});
