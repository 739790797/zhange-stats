import { useEffect, type ReactNode } from "react";
import { ConfigProvider } from "antd";
import { TARKOV_ANTD_DARK } from "@/lib/tarkovAntdDark";
import { TARKOV_UI_ROOT_CLASS } from "@/lib/tarkovUi";
import "./tarkovScrollbar.css";

/** 塔科夫攻略暗色主题。套在 GuideShell 上，详情页不要再包一层。 */
export function TarkovThemed({ children }: { children: ReactNode }) {
  useEffect(() => {
    const root = document.documentElement;
    root.classList.add(TARKOV_UI_ROOT_CLASS);
    return () => {
      root.classList.remove(TARKOV_UI_ROOT_CLASS);
    };
  }, []);

  return <ConfigProvider theme={TARKOV_ANTD_DARK}>{children}</ConfigProvider>;
}
