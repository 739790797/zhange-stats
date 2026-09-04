import type { CSSProperties } from "react";
import icpBeianIcon from "@/assets/icp-beian.png";
import { ICP_BEIAN_HREF, ICP_BEIAN_NO } from "@/lib/legalDocs";

type Props = {
  /** 深色底（登录页脚、侧栏） */
  light?: boolean;
  className?: string;
  style?: CSSProperties;
};

const ICON_SIZE = 16;

/** 工信部要求的页脚备案号，点进查询页。 */
export function IcpBeianLink({ light = false, className, style }: Props) {
  return (
    <a
      className={className}
      href={ICP_BEIAN_HREF}
      target="_blank"
      rel="noreferrer"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        textDecoration: "none",
        ...(light
          ? { color: "rgba(255,255,255,0.45)", fontSize: 12 }
          : {}),
        ...style,
      }}
    >
      <img
        src={icpBeianIcon}
        alt=""
        width={ICON_SIZE}
        height={ICON_SIZE}
        draggable={false}
        aria-hidden
        style={{
          display: "block",
          width: ICON_SIZE,
          height: ICON_SIZE,
          flexShrink: 0,
        }}
      />
      {ICP_BEIAN_NO}
    </a>
  );
}
