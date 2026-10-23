const SLUG_ALIASES: Record<string, string> = {
  lab: "the-lab",
  streets: "streets-of-tarkov",
  labyrinth: "the-labyrinth",
};

/** assets.tarkov.dev：svgPath 优先，无 SVG 时用互动图 0/0/0 瓦片。 */
const MAP_THUMB_ASSETS: Record<string, string> = {
  customs: "https://assets.tarkov.dev/maps/svg/Customs.svg",
  factory: "https://assets.tarkov.dev/maps/svg/Factory.svg",
  "ground-zero": "https://assets.tarkov.dev/maps/svg/GroundZero.svg",
  interchange: "https://assets.tarkov.dev/maps/svg/Interchange.svg",
  lighthouse: "https://assets.tarkov.dev/maps/svg/Lighthouse.svg",
  reserve: "https://assets.tarkov.dev/maps/svg/Reserve.svg",
  shoreline: "https://assets.tarkov.dev/maps/svg/Shoreline.svg",
  "streets-of-tarkov": "https://assets.tarkov.dev/maps/svg/StreetsOfTarkov.svg",
  terminal: "https://assets.tarkov.dev/maps/svg/Terminal.svg",
  woods: "https://assets.tarkov.dev/maps/svg/Woods.svg",
  "the-lab": "https://assets.tarkov.dev/maps/labs_v4/1st/0/0/0.png",
  "the-labyrinth": "https://assets.tarkov.dev/maps/labyrinth/main/0/0/0.png",
  icebreaker: "https://assets.tarkov.dev/maps/icebreaker/06_infirmary/0/0/0.png",
};

const VARIANT_PARENT: Record<string, string> = {
  "night-factory": "factory",
  "factory-night": "factory",
  "the-lab-dark": "the-lab",
  "ground-zero-21": "ground-zero",
  "ground-zero-tutorial": "ground-zero",
};

const STALE_TARKOV_DEV_THUMB =
  /(?:^https?:\/\/)?(?:www\.)?tarkov\.dev\/maps\/[^/?#]+_thumb\.jpg(?:\?.*)?$/i;

function canonicalMapSlug(slug: string): string {
  const raw = (slug || "").trim().toLowerCase();
  const key = SLUG_ALIASES[raw] || raw;
  return VARIANT_PARENT[key] || key;
}

function pascalSvgUrl(slug: string): string {
  const name = slug
    .split("-")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
  return name ? `https://assets.tarkov.dev/maps/svg/${name}.svg` : "";
}

/** tarkov.dev SPA 会把 /maps/*_thumb.jpg 回成 HTML，不能当缩略图。 */
export function isStaleTarkovDevMapThumb(url: string | null | undefined): boolean {
  return STALE_TARKOV_DEV_THUMB.test((url || "").trim());
}

export function tarkovMapThumbUrl(
  slug: string,
  apiThumb?: string | null,
): string {
  const api = (apiThumb || "").trim();
  if (api && !isStaleTarkovDevMapThumb(api)) return api;
  const key = canonicalMapSlug(slug);
  if (!key) return "";
  return MAP_THUMB_ASSETS[key] || pascalSvgUrl(key);
}
