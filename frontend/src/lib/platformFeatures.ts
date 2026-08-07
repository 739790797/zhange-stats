/** 平台功能开关（与后端 FEATURE_TREE id 对齐） */

export type PlatformFeatureMap = Record<string, boolean>;

/**
 * 是否视为开启。未加载 / 失败时 fail-closed（false），与后端缺省拒绝一致。
 */
export function isFeatureOn(
  features: PlatformFeatureMap | undefined | null,
  featureId: string,
): boolean {
  if (!features) return false;
  return features[featureId] === true;
}

export const PLATFORM_NAV: {
  path: string;
  featureId: string;
  label: string;
  icon: "steam" | "skland" | "taygedo" | "exilium" | "kujiequ";
}[] = [
  { path: "/steam", featureId: "steam", label: "Steam", icon: "steam" },
  { path: "/skland", featureId: "skland", label: "森空岛", icon: "skland" },
  { path: "/taygedo", featureId: "taygedo", label: "塔吉多", icon: "taygedo" },
  { path: "/kujiequ", featureId: "kujiequ", label: "库街区", icon: "kujiequ" },
  { path: "/exilium", featureId: "exilium", label: "追放", icon: "exilium" },
];

export function firstEnabledPlatformPath(
  features: PlatformFeatureMap | undefined | null,
): string {
  if (!features) return "/profile";
  for (const item of PLATFORM_NAV) {
    if (isFeatureOn(features, item.featureId)) return item.path;
  }
  return "/profile";
}
