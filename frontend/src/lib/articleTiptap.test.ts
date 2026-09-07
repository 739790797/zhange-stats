import { generateHTML, generateJSON } from "@tiptap/html/server";
import {
  articleSchemaExtensions,
  articleSlashItems,
  filterArticleSlashItems,
} from "./articleTiptap";
import { describe, expect, it } from "vitest";

const extensions = articleSchemaExtensions();

function roundtrip(html: string): string {
  const json = generateJSON(html, extensions);
  return generateHTML(json, extensions);
}

describe("articleTiptap", () => {
  it("keeps headings lists quotes and code", () => {
    const html = roundtrip(
      "<h2>标题</h2><p>一段 <strong>粗</strong><em>斜</em><u>下划</u><s>删</s></p><ul><li>甲</li></ul><blockquote><p>引</p></blockquote><pre><code>code</code></pre><hr>",
    );
    expect(html).toContain("<h2>");
    expect(html).toContain("<strong>");
    expect(html).toContain("<em>");
    expect(html).toContain("<u>");
    expect(html).toContain("<s>");
    expect(html).toContain("<ul>");
    expect(html).toContain("<blockquote>");
    expect(html).toContain("<code>");
    expect(html).toMatch(/<hr\b/);
  });

  it("keeps halo figure captions and drops javascript images", () => {
    const html = roundtrip(
      '<figure><img src="/uploads/articles/halo/a.png" alt="图"><figcaption>图注</figcaption></figure><p><img src="javascript:alert(1)" alt="x"></p>',
    );
    expect(html).toContain("<figure>");
    expect(html).toContain("/uploads/articles/halo/a.png");
    expect(html).toContain("<figcaption>");
    expect(html).toContain("图注");
    expect(html).not.toContain("javascript:");
  });

  it("keeps tables with merged cells and links", () => {
    const html = roundtrip(
      '<table><thead><tr><th colspan="2">头</th></tr></thead><tbody><tr><td rowspan="1"><a href="https://example.com" title="站" target="_blank">链</a></td><td>B</td></tr></tbody></table>',
    );
    expect(html).toMatch(/<table\b/);
    expect(html).toContain("colspan");
    expect(html).toContain("https://example.com");
    expect(html).toContain("title");
  });

  it("roundtrips latex math source tags", () => {
    const html = roundtrip(
      '<p>见 <span class="article-math">E=mc^2</span></p><div class="article-math-block">\\frac{1}{2}</div>',
    );
    expect(html).toContain("article-math");
    expect(html).toContain("E=mc^2");
    expect(html).toContain("article-math-block");
    expect(html).toContain("\\frac{1}{2}");
  });

  it("keeps uploaded attachment links", () => {
    const html = roundtrip(
      '<p><a href="/uploads/articles/2026/09/a.pdf">说明.pdf</a></p>',
    );
    expect(html).toContain("/uploads/articles/2026/09/a.pdf");
    expect(html).toMatch(/<a\b/);
    expect(html).toContain("说明.pdf");
  });

  it("roundtrips align indent color and highlight classes", () => {
    const html = roundtrip(
      '<p class="article-align-center article-indent-2"><span class="article-color-red">红</span><mark class="article-mark-yellow">亮</mark></p>',
    );
    expect(html).toContain("article-align-center");
    expect(html).toContain("article-indent-2");
    expect(html).toContain("article-color-red");
    expect(html).toContain("article-mark-yellow");
  });

  it("promotes inline color and highlight styles to classes", () => {
    const html = roundtrip(
      '<p><span style="color: rgb(22, 119, 255)">蓝</span><mark style="background-color: #ffff00">亮</mark><font color="#cf1322">红</font></p>',
    );
    expect(html).toContain("article-color-blue");
    expect(html).toContain("article-color-red");
    expect(html).toContain("article-mark-yellow");
    expect(html).not.toContain("style=");
  });

  it("filters slash items by query", () => {
    const items = articleSlashItems();
    expect(filterArticleSlashItems(items, "表").map((row) => row.id)).toContain(
      "table",
    );
    expect(items.map((row) => row.id)).toEqual(
      expect.arrayContaining(["h2", "h4", "quote", "table", "hr"]),
    );
    expect(filterArticleSlashItems(items, "xyz")).toEqual([]);
    expect(filterArticleSlashItems(items, "").length).toBe(items.length);
  });
});
