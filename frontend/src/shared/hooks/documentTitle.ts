import { useEffect } from "react";

/** 与 `index.html` 默认 `<title>` 一致。 */
export const SITE_DOCUMENT_TITLE = "战鸽数据 · Zhange Stats";
export const SITE_DOCUMENT_BRAND = "战鸽数据";

export function formatDocumentTitle(
  page: string,
  brand = SITE_DOCUMENT_BRAND,
): string {
  const next = page.trim();
  if (!next) return SITE_DOCUMENT_TITLE;
  if (next === SITE_DOCUMENT_TITLE) return next;
  if (next.includes(brand)) return next;
  return `${next} · ${brand}`;
}

export function useDocumentTitle(
  page: string,
  brand = SITE_DOCUMENT_BRAND,
) {
  useEffect(() => {
    const prev = document.title;
    document.title = formatDocumentTitle(page, brand);
    return () => {
      document.title = prev;
    };
  }, [page, brand]);
}
