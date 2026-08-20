import rawMaps from "@/data/tarkov-dev-maps.json";

export type TarkovDevFloorLayer = {
  name: string;
  svgLayer?: string;
  tilePath?: string;
  show?: boolean;
  extents?: Array<{
    height: number[];
    bounds?: unknown[];
  }>;
};

export type TarkovDevLabel = {
  position: number[];
  text: string;
  rotation?: number;
  size?: number;
  top?: number;
  bottom?: number;
};

export type TarkovDevMapLayer = {
  key: string;
  projection: string;
  altMaps?: string[];
  tileSize?: number;
  minZoom?: number;
  maxZoom?: number;
  transform?: number[];
  coordinateRotation?: number;
  bounds?: number[][];
  svgBounds?: number[][];
  author?: string;
  authorLink?: string;
  svgPath?: string;
  svgLayer?: string;
  tilePath?: string;
  heightRange?: number[];
  layers?: TarkovDevFloorLayer[];
  labels?: TarkovDevLabel[];
  normalizedName?: string;
};

export type TarkovDevMapGroup = {
  normalizedName: string;
  primaryPath?: string;
  maps: TarkovDevMapLayer[];
};

const MAP_GROUPS = rawMaps as TarkovDevMapGroup[];

const SLUG_ALIASES: Record<string, string> = {
  lab: "the-lab",
  streets: "streets-of-tarkov",
  labyrinth: "the-labyrinth",
};

function resolveSlug(slug: string): string {
  const key = slug.trim().toLowerCase();
  return SLUG_ALIASES[key] || key;
}

const FLOOR_ZH: Record<string, string> = {
  "2nd Floor": "2 层",
  "3rd Floor": "3 层",
  "4th Floor": "4 层",
  "5th Floor": "5 层",
  Underground: "地下",
  "Second Level": "2 层",
  "Technical Level": "技术层",
  Garage: "车库",
  Tunnels: "隧道",
  Bunkers: "地堡",
};

export function floorLabel(name: string): string {
  return FLOOR_ZH[name] || name;
}

export function findMapGroup(slug: string): TarkovDevMapGroup | undefined {
  const key = slug.trim().toLowerCase();
  if (!key) return undefined;
  return MAP_GROUPS.find(
    (group) =>
      group.normalizedName === key ||
      group.maps.some(
        (layer) => layer.key === key || layer.altMaps?.includes(key),
      ),
  );
}

function withGroupName(
  layer: TarkovDevMapLayer,
  group: TarkovDevMapGroup,
): TarkovDevMapLayer {
  return { ...layer, normalizedName: group.normalizedName };
}

export function findInteractiveMap(
  slug: string,
  parentSlug?: string,
): TarkovDevMapLayer | undefined {
  const keys = [slug, parentSlug || "", resolveSlug(slug), resolveSlug(parentSlug || "")]
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
  const seen = new Set<string>();
  for (const key of keys) {
    if (seen.has(key)) continue;
    seen.add(key);
    const group = findMapGroup(key);
    if (!group) continue;
    const exact = group.maps.find(
      (layer) =>
        layer.projection === "interactive" &&
        (layer.key === key || layer.altMaps?.includes(key)),
    );
    if (exact) return withGroupName(exact, group);
    const any = group.maps.find((layer) => layer.projection === "interactive");
    if (any) return withGroupName(any, group);
  }
  return undefined;
}

export function findRasterMap(
  slug: string,
  parentSlug?: string,
): { key: string; url: string; projection: string } | undefined {
  const keys = [slug, parentSlug || "", resolveSlug(slug), resolveSlug(parentSlug || "")]
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
  for (const key of keys) {
    const group = findMapGroup(key);
    if (!group) continue;
    const layer =
      group.maps.find((item) => item.projection === "2D") ||
      group.maps.find((item) => item.projection === "3D");
    if (!layer) continue;
    return {
      key: layer.key,
      url: `https://tarkov.dev/maps/${layer.key}.jpg`,
      projection: layer.projection,
    };
  }
  return undefined;
}

export function svgFallbackUrl(svgPath: string): string {
  const file = svgPath.split("/").pop() || "";
  if (!file) return svgPath;
  return `https://raw.githubusercontent.com/the-hideout/tarkov-dev-svg-maps/refs/heads/main/${file}`;
}
