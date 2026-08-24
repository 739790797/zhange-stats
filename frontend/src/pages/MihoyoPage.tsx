import { useQuery } from "@tanstack/react-query";
import { useMemo, type ReactNode } from "react";
import {
  fetchMihoyoStatus,
  fetchPlatformFeaturesEffective,
  triggerMihoyoCheckin,
  updateMihoyoRolePref,
} from "@/api/client";
import { CheckinPageTemplate } from "@/components/CheckinPageTemplate";
import { MihoyoBindPanel } from "@/components/MihoyoBindPanel";
import { MihoyoExchangePanel } from "@/components/MihoyoExchangePanel";
import { PlatformFeatureTabsPage } from "@/components/PlatformFeatureTabsPage";
import { useRoleMembershipPicker } from "@/hooks/useRoleMembershipPicker";
import { isFeatureOn } from "@/lib/platformFeatures";

type TabKey = "checkin" | "exchange";

export default function MihoyoPage() {
  const rolePicker = useRoleMembershipPicker("mihoyo");

  const featuresQuery = useQuery({
    queryKey: ["platform-features-effective"],
    queryFn: fetchPlatformFeaturesEffective,
    staleTime: 30_000,
  });

  const featuresReady =
    featuresQuery.isSuccess && Boolean(featuresQuery.data);
  const showCheckin =
    featuresReady && isFeatureOn(featuresQuery.data, "mihoyo.checkin");
  const showExchange =
    featuresReady && isFeatureOn(featuresQuery.data, "mihoyo.exchange");

  const tabItems = useMemo(() => {
    const items: { key: TabKey; label: string; children: ReactNode }[] = [];
    if (showCheckin) {
      items.push({
        key: "checkin",
        label: "签到",
        children: (
          <CheckinPageTemplate
            contentOnly
            title="米游社"
            bindName="米游社"
            statusQueryKey={["mihoyo-status"]}
            fetchStatus={fetchMihoyoStatus}
            triggerCheckin={triggerMihoyoCheckin}
            updateRolePref={updateMihoyoRolePref}
            platformIcon="mihoyo"
            showPhoneMask
          />
        ),
      });
    }
    if (showExchange) {
      items.push({
        key: "exchange",
        label: "兑换",
        children: <MihoyoExchangePanel />,
      });
    }
    return items;
  }, [showCheckin, showExchange]);

  return (
    <PlatformFeatureTabsPage
      title="米游社"
      bindName="米游社"
      unboundMessage="尚未绑定米游社"
      statusQueryKey={["mihoyo-status"]}
      fetchStatus={() => fetchMihoyoStatus(true, true)}
      bindPanel={
        <MihoyoBindPanel
          title="绑定米游社账号"
          openRolePickerOnBind={false}
          onSuccess={() => {
            window.setTimeout(() => rolePicker.openPicker(), 0);
          }}
        />
      }
      rolePickerModal={rolePicker.modal}
      featuresReady={featuresReady}
      tabItems={tabItems}
      emptyFeaturesMessage="米游社子功能均未启用"
      emptyFeaturesDescription="请联系管理员在「任务配置」中开启签到或兑换。"
    />
  );
}
