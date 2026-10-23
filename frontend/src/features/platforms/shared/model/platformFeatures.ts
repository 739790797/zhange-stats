/** 平台功能开关（与后端 FEATURE_TREE id 对齐） */

import { flattenGuideLeaves } from "@/features/guides/shared/model/guideNav";
import type { PlatformIconName } from "@/features/platforms/shared/model/platformIcons";

export type PlatformFeatureMap = Record<string, boolean>;

export type PlatformFeatureNavItem = {
  key: string;
  featureId: string;
  label: string;
  icon?: PlatformIconName | "exchange";
};

export type PlatformNavItem = {
  path: string;
  featureId: string;
  label: string;
  icon: PlatformIconName;
  children?: PlatformFeatureNavItem[];
};

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

/** 平台首页保持为签到页；其它平台功能从平台子菜单进入。 */
export const PLATFORM_NAV: PlatformNavItem[] = [
  { path: "/steam", featureId: "steam", label: "Steam", icon: "steam" },
  {
    path: "/skland",
    featureId: "skland",
    label: "森空岛",
    icon: "skland",
    children: [
      {
        key: "arknights",
        featureId: "skland.arknights",
        label: "明日方舟",
        icon: "arknights",
      },
      {
        key: "endfield",
        featureId: "skland.endfield",
        label: "明日方舟：终末地",
        icon: "endfield",
      },
    ],
  },
  {
    path: "/taygedo",
    featureId: "taygedo",
    label: "塔吉多",
    icon: "taygedo",
    children: [
      { key: "exchange", featureId: "taygedo.exchange", label: "兑换", icon: "exchange" },
      {
        key: "exastris",
        featureId: "taygedo.exastris",
        label: "异环",
        icon: "exastris",
      },
    ],
  },
  {
    path: "/kujiequ",
    featureId: "kujiequ",
    label: "库街区",
    icon: "kujiequ",
    children: [
      { key: "exchange", featureId: "kujiequ.exchange", label: "兑换", icon: "exchange" },
      { key: "ww", featureId: "kujiequ.ww", label: "鸣潮", icon: "ww" },
    ],
  },
  {
    path: "/mihoyo",
    featureId: "mihoyo",
    label: "米游社",
    icon: "mihoyo",
    children: [
      { key: "exchange", featureId: "mihoyo.exchange", label: "兑换", icon: "exchange" },
    ],
  },
  {
    path: "/exilium",
    featureId: "exilium",
    label: "追放",
    icon: "exilium",
    children: [
      { key: "exchange", featureId: "exilium.exchange", label: "兑换", icon: "exchange" },
    ],
  },
];

export function platformFeatureMenuKey(path: string, tabKey: string): string {
  return path + "?tab=" + encodeURIComponent(tabKey);
}

/** Pick the requested submenu page; keep the platform landing page on check-in. */
export function resolvePlatformFeaturePageTitle(
  platformTitle: string,
  selectedItem: { key: string; label: string } | undefined,
  landingKey = "checkin",
): string {
  return selectedItem && selectedItem.key !== landingKey
    ? selectedItem.label
    : platformTitle;
}

export function resolvePlatformFeatureTabKey<T extends { key: string }>(
  items: readonly T[],
  requestedKey: string | null,
  defaultKey?: string,
): string {
  if (requestedKey && items.some((item) => item.key === requestedKey)) {
    return requestedKey;
  }
  if (defaultKey) {
    return items.some((item) => item.key === defaultKey) ? defaultKey : "";
  }
  return items[0]?.key ?? "";
}

export function firstEnabledPlatformPath(
  features: PlatformFeatureMap | undefined | null,
): string {
  if (!features) return "/profile";
  for (const item of PLATFORM_NAV) {
    if (isFeatureOn(features, item.featureId)) return item.path;
  }
  for (const item of flattenGuideLeaves()) {
    if (isFeatureOn(features, item.featureId)) return item.path;
  }
  return "/profile";
}
