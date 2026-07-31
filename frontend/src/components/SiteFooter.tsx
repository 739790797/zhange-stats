import { Typography } from "antd";

const ICP_TEXT = "浙ICP备2025147006号";
const ICP_HREF = "https://beian.miit.gov.cn/";

/** 全站页脚：备案号（合规展示） */
export function SiteFooter({ light = false }: { light?: boolean }) {
  const color = light ? "rgba(255,255,255,0.45)" : "rgba(0,0,0,0.35)";
  return (
    <footer
      style={{
        textAlign: "center",
        padding: "12px 16px 20px",
        flexShrink: 0,
      }}
    >
      <Typography.Link
        href={ICP_HREF}
        target="_blank"
        rel="noreferrer"
        style={{ color, fontSize: 12 }}
      >
        {ICP_TEXT}
      </Typography.Link>
    </footer>
  );
}
