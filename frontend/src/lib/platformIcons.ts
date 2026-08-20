export const PLATFORM_ICON_SRC = {
  steam: "/platform-icons/steam.png",
  skland: "/platform-icons/skland.png",
  taygedo: "/platform-icons/taygedo.png",
  exilium: "/platform-icons/exilium.png",
  kujiequ: "/platform-icons/kujiequ.png",
  // 游戏：App Store / 官网应用图标
  arknights: "/platform-icons/arknights.png",
  endfield: "/platform-icons/endfield.png",
  exastris: "/platform-icons/exastris.png",
  tower: "/platform-icons/tower.png",
  ww: "/platform-icons/ww.png",
  pgr: "/platform-icons/pgr.png",
  tarkov: "/platform-icons/tarkov.png",
  minecraft: "/platform-icons/minecraft.png",
} as const;

export type PlatformIconName = keyof typeof PLATFORM_ICON_SRC;

/** 功能树节点 id → 图标（平台用根 id，游戏用独立图标） */
const FEATURE_ICON_BY_ID: Record<string, PlatformIconName> = {
  steam: "steam",
  skland: "skland",
  taygedo: "taygedo",
  exilium: "exilium",
  kujiequ: "kujiequ",
  "skland.arknights": "arknights",
  "skland.endfield": "endfield",
  "taygedo.exastris": "exastris",
  "taygedo.tower": "tower",
  "kujiequ.ww": "ww",
  "kujiequ.pgr": "pgr",
  "guides.minecraft": "minecraft",
};

export function featureIconName(featureId: string): PlatformIconName | null {
  if (featureId in FEATURE_ICON_BY_ID) {
    return FEATURE_ICON_BY_ID[featureId];
  }
  const root = featureId.split(".")[0];
  return FEATURE_ICON_BY_ID[root] ?? null;
}

/** 签到结果 game_code → 游戏 / 社区 App 图标 */
const CHECKIN_GAME_ICON: Record<string, PlatformIconName> = {
  arknights: "arknights",
  endfield: "endfield",
  // 塔吉多
  "1289": "exastris", // 异环
  "1256": "tower", // 幻塔
  app: "taygedo", // 塔吉多 APP 社区
  // 库街区
  kujiequ: "kujiequ", // 社区
  game_2: "pgr", // 战双
  game_3: "ww", // 鸣潮
  // 追放社区
  exilium_bbs: "exilium",
};

export function checkinGameIcon(
  gameCode: string | null | undefined,
  fallback?: PlatformIconName | null,
): PlatformIconName | null {
  const key = (gameCode || "").trim();
  if (key && key in CHECKIN_GAME_ICON) return CHECKIN_GAME_ICON[key];
  return fallback ?? null;
}
