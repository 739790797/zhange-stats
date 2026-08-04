const SRC = {
  steam: "/platform-icons/steam.png",
  skland: "/platform-icons/skland.png",
  taygedo: "/platform-icons/taygedo.png",
  exilium: "/platform-icons/exilium.png",
} as const;

export type PlatformIconName = keyof typeof SRC;

type PlatformIconProps = {
  name: PlatformIconName;
  size?: number;
};

/** 侧栏 / 标签用的平台品牌图标（本地静态资源） */
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
