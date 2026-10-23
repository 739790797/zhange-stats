import {
  decodeArticleMathText,
  normalizeArticleMath,
  renderArticleMathHtml,
  renderArticleMathInHtml,
} from "./articleMath";
import { describe, expect, it } from "vitest";

describe("articleMath", () => {
  it("trims and caps latex", () => {
    expect(normalizeArticleMath("  E=mc^2  ")).toBe("E=mc^2");
    expect(normalizeArticleMath("x".repeat(3000)).length).toBe(2000);
  });

  it("renders a simple formula and rejects empty", () => {
    const ok = renderArticleMathHtml("E=mc^2", false);
    expect(ok.error).toBeNull();
    expect(ok.html).toContain("katex");
    expect(renderArticleMathHtml("   ", false).error).toBe("请输入公式");
  });

  it("hydrates stored math tags after sanitize", () => {
    const html = renderArticleMathInHtml(
      '<p>见 <span class="article-math">a^2+b^2=c^2</span></p><div class="article-math-block">\\frac{1}{2}</div>',
    );
    expect(html).toContain("katex");
    expect(html).toContain("article-math-block");
    expect(decodeArticleMathText("a &lt; b")).toBe("a < b");
  });
});
