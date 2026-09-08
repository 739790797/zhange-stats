import { describe, expect, it } from "vitest";
import {
  SITE_DOCUMENT_TITLE,
  formatDocumentTitle,
} from "./documentTitle";

describe("formatDocumentTitle", () => {
  it("falls back to the site title", () => {
    expect(formatDocumentTitle("")).toBe(SITE_DOCUMENT_TITLE);
    expect(formatDocumentTitle("  ")).toBe(SITE_DOCUMENT_TITLE);
  });

  it("suffixes the brand", () => {
    expect(formatDocumentTitle("我的日常")).toBe("我的日常 · 战鸽数据");
    expect(formatDocumentTitle("物品", "逃离塔科夫")).toBe(
      "物品 · 逃离塔科夫",
    );
  });

  it("does not double the brand", () => {
    expect(formatDocumentTitle("逃离塔科夫", "逃离塔科夫")).toBe(
      "逃离塔科夫",
    );
    expect(formatDocumentTitle(SITE_DOCUMENT_TITLE)).toBe(SITE_DOCUMENT_TITLE);
  });
});
