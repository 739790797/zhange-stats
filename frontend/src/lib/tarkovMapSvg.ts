import DOMPurify, { type Config } from "dompurify";

/** 底图里大量 `<use xlink:href="#…">` 复用图形；DOMPurify 默认按危险标签剔除，须显式放行。 */
export const TARKOV_MAP_SVG_PURIFY: Config = {
  USE_PROFILES: { svg: true, svgFilters: true },
  ADD_TAGS: ["use"],
};

export function isSameDocumentSvgRef(value: string): boolean {
  return value.trim().startsWith("#");
}

type Purifier = ReturnType<typeof DOMPurify>;

let mapSvgPurifier: Purifier | null = null;

/** 独立实例：文章正文在默认实例上挂了按白名单删 class 的钩子，会剥掉底图样式。 */
function purifier(): Purifier {
  if (mapSvgPurifier) return mapSvgPurifier;
  const next = DOMPurify(window);
  next.addHook("uponSanitizeAttribute", (node, event) => {
    if (node.nodeName.toLowerCase() !== "use") return;
    if (event.attrName !== "href" && event.attrName !== "xlink:href") return;
    if (!isSameDocumentSvgRef(event.attrValue)) event.keepAttr = false;
  });
  mapSvgPurifier = next;
  return next;
}

/** assets.tarkov.dev / GitHub 的地图 SVG 是第三方内容，写进 innerHTML 前先净化。 */
export function sanitizeTarkovMapSvg(text: string): string {
  return purifier().sanitize(text, TARKOV_MAP_SVG_PURIFY);
}
