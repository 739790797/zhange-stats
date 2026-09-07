import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import remarkRehype from "remark-rehype";
import rehypeStringify from "rehype-stringify";
import { isSafeArticleImageSrc, type ArticleBodyFormat } from "./articleImages";

function escapeAttr(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function isComposerEmptyHtml(html: string): boolean {
  const compact = (html || "")
    .replace(/<br\s*\/?>/gi, "")
    .replace(/&nbsp;/g, "")
    .replace(/<[^>]+>/g, "")
    .trim();
  return !compact;
}

export function composerImageHtml(url: string, alt = ""): string {
  if (!url || !isSafeArticleImageSrc(url)) return "";
  return `<figure><img src="${escapeAttr(url)}" alt="${escapeAttr(alt)}"></figure>`;
}

export function markdownToArticleHtml(markdown: string): string {
  const text = markdown || "";
  if (!text.trim()) return "";
  const file = unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(remarkRehype)
    .use(rehypeStringify)
    .processSync(text);
  return String(file);
}

export function articleToEditorHtml(
  body: string,
  format: ArticleBodyFormat,
): string {
  const text = body || "";
  if (format === "html") return text;
  return markdownToArticleHtml(text);
}

export function composerHtmlToBody(html: string): string {
  return isComposerEmptyHtml(html) ? "" : html || "";
}
