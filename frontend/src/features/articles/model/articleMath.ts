import katex from "katex";

export const ARTICLE_MATH_INLINE_CLASS = "article-math";
export const ARTICLE_MATH_BLOCK_CLASS = "article-math-block";
export const ARTICLE_MATH_MAX = 2000;

const MATH_TAG = /<(span|div)\s+class=(["'])([^"']*)\2\s*>([\s\S]*?)<\/\1>/gi;

export function normalizeArticleMath(src: string): string {
  let text = src || "";
  if (text.includes("\0")) text = text.split("\0").join("");
  return text.trim().slice(0, ARTICLE_MATH_MAX);
}

export function isArticleMathClass(name: string): boolean {
  return (
    name === ARTICLE_MATH_INLINE_CLASS || name === ARTICLE_MATH_BLOCK_CLASS
  );
}

export function decodeArticleMathText(html: string): string {
  return (html || "")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/gi, " ")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/&amp;/gi, "&");
}

export function escapeArticleMathText(text: string): string {
  return (text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function renderArticleMathHtml(
  src: string,
  display: boolean,
): { html: string; error: string | null } {
  const latex = normalizeArticleMath(src);
  if (!latex) return { html: "", error: "请输入公式" };
  try {
    return {
      html: katex.renderToString(latex, {
        displayMode: display,
        throwOnError: true,
        trust: false,
        strict: "ignore",
        maxSize: 20,
        maxExpand: 200,
        output: "html",
      }),
      error: null,
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : "公式无效";
    return { html: "", error: message };
  }
}

export function renderArticleMathInHtml(html: string): string {
  if (!html || !html.includes("article-math")) return html;
  return html.replace(MATH_TAG, (full, tag, _q, className, inner) => {
    const tokens = String(className || "").split(/\s+/);
    const display = tokens.includes(ARTICLE_MATH_BLOCK_CLASS);
    const inline = tokens.includes(ARTICLE_MATH_INLINE_CLASS);
    if (!display && !inline) return full;
    const latex = normalizeArticleMath(decodeArticleMathText(inner));
    const { html: math, error } = renderArticleMathHtml(latex, display);
    const cls = display ? ARTICLE_MATH_BLOCK_CLASS : ARTICLE_MATH_INLINE_CLASS;
    if (error) {
      return `<${tag} class="${cls} article-math-error" title="${escapeArticleMathText(error)}">${escapeArticleMathText(latex)}</${tag}>`;
    }
    return `<${tag} class="${cls}">${math}</${tag}>`;
  });
}
