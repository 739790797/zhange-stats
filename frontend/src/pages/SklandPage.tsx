import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Tabs, message } from "antd";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { apiError } from "@/lib/apiError";
import {
  fetchPlatformFeaturesEffective,
  fetchSklandStatus,
  triggerSklandCheckin,
  updateSklandBind,
} from "@/api/client";
import { ArknightsBoxCompare } from "@/components/ArknightsBoxCompare";
import { CheckinPageTemplate } from "@/components/CheckinPageTemplate";
import { EndfieldBoxPanel } from "@/components/EndfieldBoxPanel";
import { PageHeader } from "@/components/PageHeader";
import { SklandBindPanel } from "@/components/SklandBindPanel";
import { isCheckinSuccess } from "@/lib/checkinStatus";
import { isFeatureOn } from "@/lib/platformFeatures";

type TabKey = "checkin" | "arknights" | "endfield";


export default function SklandPage() {
  const [tab, setTab] = useState<TabKey>("checkin");
  const queryClient = useQueryClient();

  const featuresQuery = useQuery({
    queryKey: ["platform-features-effective"],
    queryFn: fetchPlatformFeaturesEffective,
    staleTime: 30_000,
  });

  const statusQuery = useQuery({
    queryKey: ["skland-status"],
    queryFn: () => fetchSklandStatus(true),
    retry: false,
  });

  const featuresReady =
    featuresQuery.isSuccess && Boolean(featuresQuery.data);
  const showCheckin =
    featuresReady && isFeatureOn(featuresQuery.data, "skland.checkin");
  const showArknights =
    featuresReady && isFeatureOn(featuresQuery.data, "skland.arknights");
  const showEndfield =
    featuresReady && isFeatureOn(featuresQuery.data, "skland.endfield");

  const tabItems = useMemo(() => {
    const items: { key: TabKey; label: string; children: ReactNode }[] = [];
    if (showCheckin) {
      items.push({
        key: "checkin",
        label: "签到",
        children: (
          <CheckinPageTemplate
            contentOnly
            title="森空岛"
            bindName="森空岛"
            statusQueryKey={["skland-status"]}
            fetchStatus={fetchSklandStatus}
            triggerCheckin={triggerSklandCheckin}
            updateBind={updateSklandBind}
          />
        ),
      });
    }
    if (showArknights) {
      items.push({
        key: "arknights",
        label: "明日方舟",
        children: <ArknightsBoxCompare />,
      });
    }
    if (showEndfield) {
      items.push({
        key: "endfield",
        label: "明日方舟：终末地",
        children: (
          <EndfieldBoxPanel
            enabled={Boolean(
              statusQuery.data?.bound && statusQuery.data?.token_ok !== false,
            )}
          />
        ),
      });
    }
    return items;
  }, [showArknights, showCheckin, showEndfield, statusQuery.data]);

  useEffect(() => {
    if (!tabItems.length) return;
    if (!tabItems.some((item) => item.key === tab)) {
      setTab(tabItems[0].key);
    }
  }, [tab, tabItems]);

  const checkin = useMutation({
    mutationFn: triggerSklandCheckin,
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
        message.warning("签到未全部成功，失败角色可再次尝试");
      } else {
        message.success("签到完成");
      }
      queryClient.invalidateQueries({ queryKey: ["skland-status"] });
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
        title="森空岛"
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
              tokenBroken ? "森空岛凭证可能已失效" : "尚未绑定森空岛"
            }
            description={
              tokenBroken
                ? statusQuery.data?.token_error || "请重新绑定后再试。"
                : undefined
            }
          />
          <Card>
            <SklandBindPanel title="绑定森空岛账号" />
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
          message="森空岛子功能均未启用"
          description="请联系管理员在「任务配置」中开启签到或养成相关功能。"
        />
      )}
    </div>
  );
}
