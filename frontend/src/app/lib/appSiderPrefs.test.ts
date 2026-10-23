import { describe, expect, it } from "vitest";
import { parseAppSiderCollapsed } from "./appSiderPrefs";

describe("parseAppSiderCollapsed", () => {
  it("defaults to expanded", () => {
    expect(parseAppSiderCollapsed(null)).toBe(false);
    expect(parseAppSiderCollapsed("")).toBe(false);
    expect(parseAppSiderCollapsed("nope")).toBe(false);
    expect(parseAppSiderCollapsed("[]")).toBe(false);
  });

  it("reads boolean, 0/1, and { collapsed }", () => {
    expect(parseAppSiderCollapsed("true")).toBe(true);
    expect(parseAppSiderCollapsed("1")).toBe(true);
    expect(parseAppSiderCollapsed("false")).toBe(false);
    expect(parseAppSiderCollapsed("0")).toBe(false);
    expect(parseAppSiderCollapsed(JSON.stringify({ collapsed: true }))).toBe(
      true,
    );
    expect(parseAppSiderCollapsed(JSON.stringify({ collapsed: false }))).toBe(
      false,
    );
  });
});
