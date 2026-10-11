import { describe, expect, it } from "vitest";
import { isSameDocumentSvgRef, TARKOV_MAP_SVG_PURIFY } from "./tarkovMapSvg";

describe("TARKOV_MAP_SVG_PURIFY", () => {
  it("uses the SVG profiles and keeps <use>, which the maps rely on", () => {
    expect(TARKOV_MAP_SVG_PURIFY.USE_PROFILES).toEqual({
      svg: true,
      svgFilters: true,
    });
    expect(TARKOV_MAP_SVG_PURIFY.ADD_TAGS).toContain("use");
    expect(TARKOV_MAP_SVG_PURIFY.ALLOWED_TAGS).toBeUndefined();
    expect(TARKOV_MAP_SVG_PURIFY.ADD_ATTR).toBeUndefined();
  });
});

describe("isSameDocumentSvgRef", () => {
  it("only accepts in-document fragment references", () => {
    expect(isSameDocumentSvgRef("#ladder-1")).toBe(true);
    expect(isSameDocumentSvgRef(" #a")).toBe(true);
    expect(isSameDocumentSvgRef("https://evil.example/x.svg#a")).toBe(false);
    expect(isSameDocumentSvgRef("data:image/svg+xml,<svg/>")).toBe(false);
    expect(isSameDocumentSvgRef("")).toBe(false);
  });
});
