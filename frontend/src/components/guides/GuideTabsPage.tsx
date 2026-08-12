import { Tabs } from "antd";
import { useEffect, useState, type ReactNode } from "react";
import { PageHeader } from "@/components/PageHeader";

export type GuideTabItem = {
  key: string;
  label: string;
  children: ReactNode;
};

export type GuideTabsPageProps = {
  title: string;
  subtitle?: ReactNode;
  tabItems: GuideTabItem[];
  /** 默认选中的 tab key；缺省取 tabItems[0] */
  defaultTab?: string;
};

/**
 * 攻略页外壳：PageHeader + Tabs。
 * 无绑定门禁 / feature 开关（与 PlatformFeatureTabsPage 分离）。
 */
export function GuideTabsPage({
  title,
  subtitle,
  tabItems,
  defaultTab,
}: GuideTabsPageProps) {
  const [tab, setTab] = useState(defaultTab || tabItems[0]?.key || "");

  useEffect(() => {
    if (!tabItems.length) return;
    if (!tabItems.some((item) => item.key === tab)) {
      setTab(tabItems[0].key);
    }
  }, [tab, tabItems]);

  return (
    <div>
      <PageHeader title={title} subtitle={subtitle} />
      {tabItems.length ? (
        <Tabs activeKey={tab} onChange={setTab} items={tabItems} />
      ) : null}
    </div>
  );
}
