import type { ReactNode } from "react";
import { ConfigProvider } from "antd";
import { TARKOV_ANTD_DARK } from "@/lib/tarkovAntdDark";

/** 塔科夫攻略暗色主题。套在 GuideShell 上，详情页不要再包一层。 */
export function TarkovThemed({ children }: { children: ReactNode }) {
  return <ConfigProvider theme={TARKOV_ANTD_DARK}>{children}</ConfigProvider>;
}
