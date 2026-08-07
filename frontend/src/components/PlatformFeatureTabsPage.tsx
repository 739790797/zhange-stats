import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Tabs } from "antd";
import { useEffect, useState, type ReactNode } from "react";
import { PageHeader } from "@/components/PageHeader";
import type { ExchangeBindStatus } from "@/components/ExchangePageTemplate";

export type PlatformFeatureTabItem = {
  key: string;
  label: string;
  children: ReactNode;
};

export type PlatformFeatureTabsPageProps = {
  title: string;
  bindName: string;
  /** 未绑定 Alert 主文案；默认「尚未绑定{bindName}」 */
  unboundMessage?: string;
  statusQueryKey: unknown[];
  /** 页级 status：与签到模板共用 key 时须 force 回源 */
  fetchStatus: () => Promise<ExchangeBindStatus>;
  bindPanel: ReactNode;
  rolePickerModal: ReactNode;
  featuresReady: boolean;
  tabItems: PlatformFeatureTabItem[];
  emptyFeaturesMessage: string;
  emptyFeaturesDescription: string;
  /** 默认选中的 tab key；缺省取 tabItems[0] */
  defaultTab?: string;
};

/**
 * 平台页外壳：PageHeader + 绑定门禁 + feature 开关驱动的 Tabs。
 * 签到 / 兑换等子内容由 tabItems 注入（签到用 CheckinPageTemplate contentOnly）。
 */
export function PlatformFeatureTabsPage({
  title,
  bindName,
  unboundMessage,
  statusQueryKey,
  fetchStatus,
  bindPanel,
  rolePickerModal,
  featuresReady,
  tabItems,
  emptyFeaturesMessage,
  emptyFeaturesDescription,
  defaultTab,
}: PlatformFeatureTabsPageProps) {
  const [tab, setTab] = useState(defaultTab || tabItems[0]?.key || "");

  const statusQuery = useQuery({
    queryKey: statusQueryKey,
    queryFn: fetchStatus,
    retry: false,
  });

  useEffect(() => {
    if (!tabItems.length) return;
    if (!tabItems.some((item) => item.key === tab)) {
      setTab(tabItems[0].key);
    }
  }, [tab, tabItems]);

  const bound = Boolean(statusQuery.data?.bound);
  const tokenBroken = bound && statusQuery.data?.token_ok === false;
  const needsBind = (!bound || tokenBroken) && !statusQuery.isLoading;

  return (
    <div>
      <PageHeader title={title} />

      {needsBind ? (
        <div
          style={{
            maxWidth: 560,
            margin: "0 auto",
            padding: "8px 0 48px",
          }}
        >
          <Alert
            type={tokenBroken ? "warning" : "info"}
            showIcon
            style={{ marginBottom: 16 }}
            message={
              tokenBroken
                ? `${bindName}凭证可能已失效`
                : unboundMessage || `尚未绑定${bindName}`
            }
            description={
              tokenBroken
                ? statusQuery.data?.token_error || "请重新绑定后再试。"
                : undefined
            }
          />
          <Card>{bindPanel}</Card>
        </div>
      ) : !featuresReady ? null : tabItems.length ? (
        <Tabs activeKey={tab} onChange={setTab} items={tabItems} />
      ) : (
        <Alert
          type="info"
          showIcon
          message={emptyFeaturesMessage}
          description={emptyFeaturesDescription}
        />
      )}
      {rolePickerModal}
    </div>
  );
}
