import { Card, Typography } from "antd";
import type { ReactNode } from "react";
import { AppVersion } from "@/components/AppVersion";
import { BrandLogo } from "@/components/BrandLogo";

type Props = {
  /** 默认 420；安装向导 440 */
  width?: number;
  /** 战鸽 Logo + 主标题 */
  brand?: boolean;
  brandTitleSize?: number;
  /** 品牌头与表单间距；登录 32、安装 28 */
  headerMarginBottom?: number;
  title?: string;
  subtitle?: ReactNode;
  showVersion?: boolean;
  children: ReactNode;
};

/** 未登录页视觉壳：居中 Card + 可选品牌头 + 版本号。QQ 回调等逻辑仍在各页。 */
export function AuthGuestShell({
  width = 420,
  brand = false,
  brandTitleSize = 36,
  headerMarginBottom,
  title,
  subtitle,
  showVersion = true,
  children,
}: Props) {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background:
          "radial-gradient(ellipse at top left, #2c3e50 0%, #1a2332 45%, #0f1419 100%)",
        padding: 24,
      }}
    >
      <Card
        style={{
          width,
          maxWidth: "100%",
          boxShadow: "0 16px 48px rgba(0,0,0,0.35)",
          border: "1px solid rgba(232,184,109,0.25)",
        }}
        styles={{ body: { padding: "40px 36px" } }}
      >
        <div
          style={{
            textAlign: "center",
            marginBottom: headerMarginBottom ?? (brand ? 32 : 24),
          }}
        >
          {brand ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 12,
                marginBottom: 8,
              }}
            >
              <BrandLogo size={48} color="#1a2332" />
              <Typography.Title
                level={1}
                style={{
                  margin: 0,
                  fontSize: brandTitleSize,
                  color: "#1a2332",
                  letterSpacing: 2,
                }}
              >
                战鸽数据
              </Typography.Title>
            </div>
          ) : title ? (
            <Typography.Title level={2} style={{ margin: 0, color: "#1a2332" }}>
              {title}
            </Typography.Title>
          ) : null}
          {subtitle ? (
            <Typography.Paragraph
              type="secondary"
              style={{ marginTop: 8, marginBottom: 0 }}
            >
              {subtitle}
            </Typography.Paragraph>
          ) : null}
        </div>
        {children}
      </Card>
      {showVersion ? (
        <div style={{ position: "fixed", left: 0, right: 0, bottom: 8 }}>
          <AppVersion light />
        </div>
      ) : null}
    </div>
  );
}
