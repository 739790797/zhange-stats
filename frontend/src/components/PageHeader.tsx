import { Typography } from "antd";
import type { ReactNode } from "react";
import { useDocumentTitle } from "@/lib/documentTitle";

interface PageHeaderProps {
  title: string;
  subtitle?: ReactNode;
  extra?: React.ReactNode;
}

export function PageHeader({ title, subtitle, extra }: PageHeaderProps) {
  useDocumentTitle(title);
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
