import type { CSSProperties } from "react";
import icpBeianIcon from "@/assets/icp-beian.png";
import { useSitePublic } from "@/hooks/useSitePublic";
import { ICP_BEIAN_HREF, siteIcpBeianNo } from "@/lib/legalDocs";

type Props = {
  /** 深色底（登录页脚） */
  light?: boolean;
  className?: string;
  style?: CSSProperties;
};

const ICON_SIZE = 16;

/** 工信部要求的页脚备案号，点进查询页。未配置则不渲染。 */
export function IcpBeianLink({ light = false, className, style }: Props) {
  const { data } = useSitePublic();
  const no = siteIcpBeianNo(data?.icp_beian_no);
  if (!no) return null;
  const href = data?.icp_beian_href || ICP_BEIAN_HREF;

  return (
    <a
      className={className}
      href={href}
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
      {no}
    </a>
  );
}

type FooterProps = {
  /** 塔科夫攻略正文末尾 */
  variant?: "default" | "tarkov";
};

/** 跟在页面内容后面，随主栏滚动；未配置备案号则不渲染。 */
export function IcpBeianFooter({ variant = "default" }: FooterProps) {
  const { data } = useSitePublic();
  if (!siteIcpBeianNo(data?.icp_beian_no)) return null;
  return (
    <div
      className={[
        "app-icp-footer",
        variant === "tarkov" ? "app-icp-footer--tarkov" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <IcpBeianLink />
    </div>
  );
}
