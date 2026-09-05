const CDN_SUFFIX_RE =
  /-(?:icon|grid-image|base-image|512|8x|image)\.webp(\?.*)?$/i;
const ITEM_ID_RE = /^[a-f0-9]{24}$/i;
const TARKOV_ITEM_CDN = "https://assets.tarkov.dev";

/**
 * 背包格小图：物品铺满格子。
 * base-image / 512 多为黑底 3D 渲染，缩到 28px 会像一块黑。
 * GraphQL 常漏任务物品 iconLink，有 24 位物品 id 时回退 CDN。
 */
export function inventoryThumbUrl(
  src?: string | null,
  itemId?: string | null,
): string {
  const url = (src || "").trim();
  if (url) return url.replace(CDN_SUFFIX_RE, "-icon.webp$1");
  const id = (itemId || "").trim();
  if (!ITEM_ID_RE.test(id)) return "";
  return `${TARKOV_ITEM_CDN}/${id}-icon.webp`;
}

/** 尝试换成 base-image。CDN 上不少仍是不透明黑底，小图标请用 inventoryThumbUrl。 */
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

/**
 * 收藏家格子：用 512 再缩小。-icon 只有几十像素，铺到 2×2 / 高分屏会糊。
 */
export function collectionItemImageUrl(
  src?: string | null,
  itemId?: string | null,
): string {
  const url = (src || "").trim();
  if (url) return hdPreviewUrl(url);
  const id = (itemId || "").trim();
  if (!ITEM_ID_RE.test(id)) return "";
  return `${TARKOV_ITEM_CDN}/${id}-512.webp`;
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
