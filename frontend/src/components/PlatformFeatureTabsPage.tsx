import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Spin } from "antd";
import { Suspense, useEffect, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { PageHeader } from "@/components/PageHeader";
import { MotionIn } from "@/components/PageMotion";
import { PanelFallback } from "@/components/RouteFallback";
import type { ExchangeBindStatus } from "@/components/ExchangePageTemplate";
import {
  bindTokenErrorMessage,
  isBindTokenBroken,
} from "@/lib/checkinStatus";
import { isInitialQueryPending } from "@/lib/queryCache";
import {
  resolvePlatformFeaturePageTitle,
  resolvePlatformFeatureTabKey,
} from "@/lib/platformFeatures";
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
  /** 平台根路径默认只显示签到；非签到功能由侧栏子菜单选择。 */
  defaultTab?: string;
};

/**
 * 平台页外壳：根路径显示签到；其它功能由平台侧栏子菜单通过 ?tab= 选择。
 * 当前未选中的功能卸载，避免签到页同时请求盒子 / 兑换上游。
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
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTab = searchParams.get("tab");
  const activeTab = resolvePlatformFeatureTabKey(
    tabItems,
    requestedTab,
    defaultTab ?? "checkin",
  );
  const activeItem = tabItems.find((item) => item.key === activeTab);
  const pageTitle = resolvePlatformFeaturePageTitle(
    title,
    activeItem,
    defaultTab ?? "checkin",
  );

  const statusQuery = useQuery({
    queryKey: statusQueryKey,
    queryFn: fetchStatus,
    retry: false,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (
      !featuresReady ||
      !requestedTab ||
      tabItems.some((item) => item.key === requestedTab)
    ) {
      return;
    }
    const next = new URLSearchParams(searchParams);
    next.delete("tab");
    setSearchParams(next, { replace: true });
  }, [featuresReady, requestedTab, searchParams, setSearchParams, tabItems]);

  const bound = Boolean(statusQuery.data?.bound);
  const tokenBroken = isBindTokenBroken(statusQuery.data);
  const needsBind =
    (!bound || tokenBroken) && !isInitialQueryPending(statusQuery);

  return (
    <div>
      <PageHeader title={pageTitle} />

      {needsBind ? (
        <MotionIn>
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
        </MotionIn>
      ) : !featuresReady ? (
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin />
        </div>
      ) : activeItem ? (
        <Suspense key={activeItem.key} fallback={<PanelFallback />}>
          {activeItem.children}
        </Suspense>
      ) : tabItems.length ? (
        <MotionIn>
          <Alert
            type="info"
            showIcon
            message="当前平台的签到功能未启用"
            description="请联系管理员在「任务配置」中开启签到；其他已启用功能可从左侧平台子菜单进入。"
          />
        </MotionIn>
      ) : (
        <MotionIn>
          <Alert
            type="info"
            showIcon
            message={emptyFeaturesMessage}
            description={emptyFeaturesDescription}
          />
        </MotionIn>
      )}
      {rolePickerModal}
    </div>
  );
}
