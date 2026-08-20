import { Tabs } from "antd";
import { useEffect, useState, type ReactNode } from "react";
import { PageHeader } from "@/components/PageHeader";

export type GuideTabItem = {
  key: string;
  label: ReactNode;
  children: ReactNode;
};

export type GuideTabsPageProps = {
  title: string;
  subtitle?: ReactNode;
  tabItems: GuideTabItem[];
  /** 非受控默认选中；缺省取 tabItems[0] */
  defaultTab?: string;
  /** 受控选中 key（与 onTabChange 一起用） */
  activeTab?: string;
  onTabChange?: (key: string) => void;
  destroyInactiveTabPane?: boolean;
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
  activeTab,
  onTabChange,
  destroyInactiveTabPane,
}: GuideTabsPageProps) {
  const controlled = activeTab !== undefined;
  const [innerTab, setInnerTab] = useState(
    defaultTab || tabItems[0]?.key || "",
  );
  const tab = controlled ? activeTab : innerTab;

  useEffect(() => {
    if (!tabItems.length) return;
    if (!tabItems.some((item) => item.key === tab)) {
      const fallback = tabItems[0].key;
      if (controlled) onTabChange?.(fallback);
      else setInnerTab(fallback);
    }
  }, [tab, tabItems, controlled, onTabChange]);

  const handleChange = (key: string) => {
    if (controlled) onTabChange?.(key);
    else setInnerTab(key);
  };

  return (
    <div>
      <PageHeader title={title} subtitle={subtitle} />
      {tabItems.length ? (
        <Tabs
          activeKey={tab}
          onChange={handleChange}
          items={tabItems}
          destroyInactiveTabPane={destroyInactiveTabPane}
        />
      ) : null}
    </div>
  );
}
