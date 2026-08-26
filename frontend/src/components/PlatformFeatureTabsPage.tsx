import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Spin, Tabs } from "antd";
import { Suspense, useEffect, useState, type ReactNode } from "react";
import { PageHeader } from "@/components/PageHeader";
import { PanelFallback } from "@/components/RouteFallback";
import type { ExchangeBindStatus } from "@/components/ExchangePageTemplate";
import {
  bindTokenErrorMessage,
  isBindTokenBroken,
} from "@/lib/checkinStatus";
import { isInitialQueryPending } from "@/lib/queryCache";
import { SKLAND_APP_LOGOUT_HINT } from "@/lib/sklandCredentialCopy";

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
 * 未激活 Tab 会卸载，避免默认签到页同时打盒子/日历/兑换上游。
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
    staleTime: 30_000,
  });

  useEffect(() => {
    if (!tabItems.length) return;
    if (!tabItems.some((item) => item.key === tab)) {
      setTab(tabItems[0].key);
    }
  }, [tab, tabItems]);

  const bound = Boolean(statusQuery.data?.bound);
  const tokenBroken = isBindTokenBroken(statusQuery.data);
  const needsBind =
    (!bound || tokenBroken) && !isInitialQueryPending(statusQuery);

  const tabNodes = tabItems.map((item) => ({
    ...item,
    children: (
      <Suspense fallback={<PanelFallback />}>{item.children}</Suspense>
    ),
  }));

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
                ? [
                    bindTokenErrorMessage(statusQuery.data) ||
                      "请重新绑定后再试。",
                    bindName === "森空岛" ? SKLAND_APP_LOGOUT_HINT : "",
                  ]
                    .filter(Boolean)
                    .join(" ")
                : bindName === "森空岛"
                  ? SKLAND_APP_LOGOUT_HINT
                  : undefined
            }
          />
          <Card>{bindPanel}</Card>
        </div>
      ) : !featuresReady ? (
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin />
        </div>
      ) : tabItems.length ? (
        <Tabs
          activeKey={tab}
          onChange={setTab}
          items={tabNodes}
          destroyInactiveTabPane
        />
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
