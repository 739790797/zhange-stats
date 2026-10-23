import { Typography } from "antd";
import type { ReactNode } from "react";
import { useDocumentTitle } from "@/shared/hooks/documentTitle";

export interface PageHeaderProps {
  title: string;
  subtitle?: ReactNode;
  extra?: ReactNode;
  /** 仅提供标题栏视觉的紧凑内容；上下文语义由所属 feature 决定。 */
  compact?: boolean;
}

export function PageHeader({
  title,
  subtitle,
  extra,
  compact = false,
}: PageHeaderProps) {
  useDocumentTitle(title);
  if (compact) {
    if (!subtitle && !extra) return null;
    return (
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 24,
          gap: 16,
        }}
      >
        <div>
          {subtitle ? (
            <Typography.Text type="secondary">{subtitle}</Typography.Text>
          ) : null}
        </div>
        {extra}
      </div>
    );
  }
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        marginBottom: 24,
        gap: 16,
      }}
    >
      <div>
        <Typography.Title level={3} style={{ margin: 0 }}>
          {title}
        </Typography.Title>
        {subtitle ? (
          <Typography.Text type="secondary">{subtitle}</Typography.Text>
        ) : null}
      </div>
      {extra}
    </div>
  );
}
