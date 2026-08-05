import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Tabs, message } from "antd";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { apiError } from "@/lib/apiError";
import {
  fetchExiliumStatus,
  fetchPlatformFeaturesEffective,
  triggerExiliumCheckin,
  updateExiliumBind,
} from "@/api/client";
import { CheckinPageTemplate } from "@/components/CheckinPageTemplate";
import { ExiliumBindPanel } from "@/components/ExiliumBindPanel";
import { ExiliumExchangePanel } from "@/components/ExiliumExchangePanel";
import { PageHeader } from "@/components/PageHeader";
import { isCheckinSuccess } from "@/lib/checkinStatus";
import { isFeatureOn } from "@/lib/platformFeatures";

type TabKey = "checkin" | "exchange";


export default function ExiliumPage() {
  const [tab, setTab] = useState<TabKey>("checkin");
  const queryClient = useQueryClient();

  const featuresQuery = useQuery({
    queryKey: ["platform-features-effective"],
    queryFn: fetchPlatformFeaturesEffective,
    staleTime: 30_000,
  });

  const statusQuery = useQuery({
    queryKey: ["exilium-status"],
    queryFn: () => fetchExiliumStatus(true),
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
            updateBind={updateExiliumBind}
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

  const checkin = useMutation({
    mutationFn: triggerExiliumCheckin,
    onSuccess: (data) => {
      const allDone =
        Boolean(data.results?.length) &&
        data.results.every((r) => isCheckinSuccess(r.status));
      if (
        data.skipped ||
        (allDone && data.results.every((r) => r.status === "already"))
      ) {
        message.info("今日已签到");
      } else if (data.ok === false) {
        message.warning("签到未成功，可再次尝试");
      } else {
        message.success("签到完成");
      }
      queryClient.invalidateQueries({ queryKey: ["exilium-status"] });
      queryClient.invalidateQueries({ queryKey: ["exilium-exchange"] });
      queryClient.invalidateQueries({ queryKey: ["profile-me"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "签到失败")),
  });

  const bound = Boolean(statusQuery.data?.bound);
  const tokenBroken = bound && statusQuery.data?.token_ok === false;
  const canUse = bound && !tokenBroken;
  const needsBind = (!bound || tokenBroken) && !statusQuery.isLoading;

  return (
    <div>
      <PageHeader
        title="追放"
        extra={
          tab === "checkin" && showCheckin && canUse ? (
            <Button
              type="primary"
              loading={checkin.isPending}
              onClick={() => checkin.mutate()}
            >
              立即签到
            </Button>
          ) : null
        }
      />

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
