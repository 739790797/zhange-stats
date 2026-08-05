const SRC = {
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
} as const;

export type PlatformIconName = keyof typeof SRC;

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
};

export function featureIconName(featureId: string): PlatformIconName | null {
  if (featureId in FEATURE_ICON_BY_ID) {
    return FEATURE_ICON_BY_ID[featureId];
  }
  const root = featureId.split(".")[0];
  return FEATURE_ICON_BY_ID[root] ?? null;
}

type PlatformIconProps = {
  name: PlatformIconName;
  size?: number;
};

/** 侧栏 / 任务配置用的平台与游戏品牌图标（本地静态资源） */
export function PlatformIcon({ name, size = 16 }: PlatformIconProps) {
  return (
    // 使用 anticon 类，与 Ant Menu「系统管理」等图标间距规则一致
    <span
      className="anticon"
      role="img"
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: size,
        height: size,
        fontSize: size,
        verticalAlign: "-0.125em",
        flexShrink: 0,
      }}
    >
      <img
        src={SRC[name]}
        alt=""
        width={size}
        height={size}
        draggable={false}
        style={{
          display: "block",
          width: size,
          height: size,
          borderRadius: Math.max(2, Math.round(size * 0.22)),
          objectFit: "cover",
        }}
      />
    </span>
  );
}
