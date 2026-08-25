import { describe, expect, it } from "vitest";
import {
  parseModToolExpandedMap,
  resolveModToolExpanded,
} from "./minecraftModToolCollapse";

describe("minecraft mod tool collapse", () => {
  it("parses a saved expanded map", () => {
    expect(parseModToolExpandedMap('{"chunky":false,"other":true}')).toEqual({
      chunky: false,
      other: true,
    });
  });

  it("ignores junk storage", () => {
    expect(parseModToolExpandedMap("nope")).toEqual({});
    expect(parseModToolExpandedMap("[1]")).toEqual({});
    expect(parseModToolExpandedMap('{"chunky":"yes"}')).toEqual({});
  });

  it("defaults installed tools to expanded", () => {
    expect(resolveModToolExpanded(true, undefined)).toBe(true);
  });

  it("remembers a collapsed installed tool", () => {
    expect(resolveModToolExpanded(true, false)).toBe(false);
  });

  it("keeps uninstalled tools collapsed even if saved expanded", () => {
    expect(resolveModToolExpanded(false, true)).toBe(false);
    expect(resolveModToolExpanded(false, undefined)).toBe(false);
  });
});
