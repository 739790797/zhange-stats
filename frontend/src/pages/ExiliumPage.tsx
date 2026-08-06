import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Tabs } from "antd";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  fetchExiliumStatus,
  fetchPlatformFeaturesEffective,
  triggerExiliumCheckin,
  updateExiliumRolePref,
} from "@/api/client";
import { CheckinPageTemplate } from "@/components/CheckinPageTemplate";
import { ExiliumBindPanel } from "@/components/ExiliumBindPanel";
import { ExiliumExchangePanel } from "@/components/ExiliumExchangePanel";
import { PageHeader } from "@/components/PageHeader";
import { isFeatureOn } from "@/lib/platformFeatures";

type TabKey = "checkin" | "exchange";


export default function ExiliumPage() {
  const [tab, setTab] = useState<TabKey>("checkin");

  const featuresQuery = useQuery({
    queryKey: ["platform-features-effective"],
    queryFn: fetchPlatformFeaturesEffective,
    staleTime: 30_000,
  });

  const statusQuery = useQuery({
    queryKey: ["exilium-status"],
    queryFn: () => fetchExiliumStatus(true, true),
    retry: false,
  });

  const featuresReady =
    featuresQuery.isSuccess && Boolean(featuresQuery.data);
  const showCheckin =
    featuresReady && isFeatureOn(featuresQuery.data, "exilium.checkin");
  const showExchange =
    featuresReady && isFeatureOn(featuresQuery.data, "exilium.exchange");

  const tabItems = useMemo(() => {
    const items: { key: TabKey; label: string; children: ReactNode }[] = [];
    if (showCheckin) {
      items.push({
        key: "checkin",
        label: "签到",
        children: (
          <CheckinPageTemplate
            contentOnly
            title="追放"
            bindName="追放社区"
            statusQueryKey={["exilium-status"]}
            fetchStatus={fetchExiliumStatus}
            triggerCheckin={triggerExiliumCheckin}
            updateRolePref={updateExiliumRolePref}
            platformIcon="exilium"
            showPhoneMask
          />
        ),
      });
    }
    if (showExchange) {
      items.push({
        key: "exchange",
        label: "积分兑换",
        children: <ExiliumExchangePanel />,
      });
    }
    return items;
  }, [showCheckin, showExchange]);

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
      <PageHeader title="追放" />

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
              tokenBroken ? "追放凭证可能已失效" : "尚未绑定追放社区"
            }
            description={
              tokenBroken
                ? statusQuery.data?.token_error || "请重新绑定后再试。"
                : undefined
            }
          />
          <Card>
            <ExiliumBindPanel title="绑定追放社区账号" />
          </Card>
        </div>
      ) : !featuresReady ? null : tabItems.length ? (
        <Tabs
          activeKey={tab}
          onChange={(k) => setTab(k as TabKey)}
          items={tabItems}
        />
      ) : (
        <Alert
          type="info"
          showIcon
          message="追放子功能均未启用"
          description="请联系管理员在「任务配置」中开启签到或积分兑换。"
        />
      )}
    </div>
  );
}
