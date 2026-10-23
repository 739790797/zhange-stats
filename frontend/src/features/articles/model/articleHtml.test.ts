import {
  articleAlignClass,
  articleColorClass,
  articleIndentClass,
  articleMarkClass,
  classifyArticleColor,
  classifyArticleMark,
  filterArticleClasses,
  findTextRanges,
  isAllowedArticleClass,
  isSafeArticleHref,
  parseArticleAlign,
  parseArticleColor,
  parseArticleIndent,
  parseArticleMark,
  parseCssColor,
} from "./articleHtml";
import { describe, expect, it } from "vitest";

describe("articleHtml", () => {
  it("builds and parses layout classes", () => {
    expect(articleAlignClass("center")).toBe("article-align-center");
    expect(articleAlignClass("wide")).toBe("");
    expect(parseArticleAlign("foo article-align-right")).toBe("right");
    expect(parseArticleAlign("", "center")).toBe("center");
    expect(articleIndentClass(2)).toBe("article-indent-2");
    expect(articleIndentClass(9)).toBe("");
    expect(parseArticleIndent("article-indent-3")).toBe(3);
  });

  it("maps palette colors and marks", () => {
    expect(articleColorClass("red")).toBe("article-color-red");
    expect(articleColorClass("pink")).toBe("");
    expect(parseArticleColor("article-color-blue")).toBe("blue");
    expect(parseArticleColor("", "#1677ff")).toBe("blue");
    expect(parseArticleColor("", "rgb(231, 76, 60)")).toBe("red");
    expect(parseArticleColor("", "#000")).toBeNull();
    expect(articleMarkClass("yellow")).toBe("article-mark-yellow");
    expect(parseArticleMark("article-mark-green")).toBe("green");
    expect(parseArticleMark("", "#ffff00")).toBe("yellow");
    expect(parseCssColor("rgba(22, 119, 255, 1)")).toEqual([22, 119, 255]);
    expect(classifyArticleColor([22, 119, 255])).toBe("blue");
    expect(classifyArticleMark([255, 255, 0])).toBe("yellow");
  });

  it("filters unknown classes", () => {
    expect(isAllowedArticleClass("article-align-center")).toBe(true);
    expect(isAllowedArticleClass("language-js")).toBe(true);
    expect(isAllowedArticleClass("article-math")).toBe(true);
    expect(isAllowedArticleClass("article-math-block")).toBe(true);
    expect(isAllowedArticleClass("onclick")).toBe(false);
    expect(filterArticleClasses("article-color-red evil article-indent-1")).toBe(
      "article-color-red article-indent-1",
    );
  });

  it("accepts safe hrefs only", () => {
    expect(isSafeArticleHref("/tavern/hello")).toBe(true);
    expect(isSafeArticleHref("https://example.com")).toBe(true);
    expect(isSafeArticleHref("mailto:a@b.c")).toBe(true);
    expect(isSafeArticleHref("#sec")).toBe(true);
    expect(isSafeArticleHref("javascript:alert(1)")).toBe(false);
    expect(isSafeArticleHref("//evil.example")).toBe(false);
    expect(isSafeArticleHref("/uploads/../etc/passwd")).toBe(false);
  });

  it("finds text ranges in chunks", () => {
    expect(
      findTextRanges(
        [
          { pos: 1, text: "hello" },
          { pos: 10, text: "hello world hello" },
        ],
        "hello",
      ),
    ).toEqual([
      { from: 1, to: 6 },
      { from: 10, to: 15 },
      { from: 22, to: 27 },
    ]);
    expect(findTextRanges([{ pos: 0, text: "ab" }], "")).toEqual([]);
  });
});
