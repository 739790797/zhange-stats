import {
  articleToEditorHtml,
  composerHtmlToBody,
  composerImageHtml,
  isComposerEmptyHtml,
  markdownToArticleHtml,
} from "./articleComposer";
import { describe, expect, it } from "vitest";

describe("articleComposer", () => {
  it("converts markdown headings lists and images", () => {
    const html = markdownToArticleHtml(
      "## 标题\n\n一段 **粗** 和 *斜*\n\n- 甲\n- 乙\n\n见 ![图](/uploads/articles/a.png)",
    );
    expect(html).toContain("<h2>");
    expect(html).toContain("<strong>");
    expect(html).toContain("<em>");
    expect(html).toContain("<ul>");
    expect(html).toContain("/uploads/articles/a.png");
  });

  it("keeps html bodies as-is and upgrades markdown", () => {
    expect(articleToEditorHtml("<p>raw</p>", "html")).toBe("<p>raw</p>");
    expect(articleToEditorHtml("**hi**", "markdown")).toContain("<strong>");
    expect(articleToEditorHtml("", "markdown")).toBe("");
  });

  it("builds a figure fragment and drops unsafe src", () => {
    expect(composerImageHtml("/uploads/articles/a.png", "图")).toBe(
      '<figure><img src="/uploads/articles/a.png" alt="图"></figure>',
    );
    expect(composerImageHtml("javascript:alert(1)")).toBe("");
  });

  it("treats placeholder html as empty", () => {
    expect(isComposerEmptyHtml("")).toBe(true);
    expect(isComposerEmptyHtml("<br>")).toBe(true);
    expect(isComposerEmptyHtml("<p></p>")).toBe(true);
    expect(isComposerEmptyHtml("<div><br></div>")).toBe(true);
    expect(isComposerEmptyHtml("<p>字</p>")).toBe(false);
    expect(composerHtmlToBody("<p></p>")).toBe("");
    expect(composerHtmlToBody("<p>字</p>")).toBe("<p>字</p>");
  });
});
