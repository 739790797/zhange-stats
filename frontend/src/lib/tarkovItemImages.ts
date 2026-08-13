const CDN_SUFFIX_RE =
  /-(?:icon|grid-image|base-image|512|8x|image)\.webp(\?.*)?$/i;

/** icon 为灰黑底；base-image 为透明小图 */
export function transparentThumbUrl(src: string | null | undefined): string {
  const url = (src || "").trim();
  if (!url) return "";
  return url.replace(CDN_SUFFIX_RE, "-base-image.webp$1");
}

/** CDN 透明高清：image512pxLink → -512.webp */
export function hdPreviewUrl(src: string | null | undefined): string {
  const url = (src || "").trim();
  if (!url) return "";
  return url.replace(CDN_SUFFIX_RE, "-512.webp$1");
}

/** 详情大图：优先 512，再 grid / inspect / base */
export function inspectImageUrl(
  item: Record<string, unknown> | undefined,
): string {
  if (!item) return "";
  const keys = [
    "image512pxLink",
    "inspectImageLink",
    "gridImageLink",
    "baseImageLink",
    "iconLink",
  ];
  for (const key of keys) {
    const url = String(item[key] || "").trim();
    if (url) return hdPreviewUrl(url) || url;
  }
  return "";
}
