import { useQuery } from "@tanstack/react-query";
import { lazy, useMemo, type ReactNode } from "react";
import {
  fetchExiliumStatus,
  fetchPlatformFeaturesEffective,
  triggerExiliumCheckin,
  updateExiliumRolePref,
} from "@/api/client";
import { CheckinPageTemplate } from "@/components/CheckinPageTemplate";
import { ExiliumBindPanel } from "@/components/exilium/ExiliumBindPanel";
import { PlatformFeatureTabsPage } from "@/components/PlatformFeatureTabsPage";
import { useRoleMembershipPicker } from "@/hooks/useRoleMembershipPicker";
import { isFeatureOn } from "@/lib/platformFeatures";
import { LOCAL_QUERY_STALE_MS } from "@/lib/queryCache";

const ExiliumExchangePanel = lazy(() =>
  import("@/components/exilium/ExiliumExchangePanel").then((m) => ({
    default: m.ExiliumExchangePanel,
  })),
);

type TabKey = "checkin" | "exchange";

export default function ExiliumPage() {
  // 角色树挂在页面级：绑定成功后会卸载 BindPanel，弹窗不能跟它一起卸掉
  const rolePicker = useRoleMembershipPicker("exilium");

  const featuresQuery = useQuery({
    queryKey: ["platform-features-effective"],
    queryFn: fetchPlatformFeaturesEffective,
    staleTime: LOCAL_QUERY_STALE_MS,
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
            bindName="追放"
            statusQueryKey={["exilium-status"]}
            fetchStatus={fetchExiliumStatus}
            triggerCheckin={triggerExiliumCheckin}
            updateRolePref={updateExiliumRolePref}
            platformIcon="exilium"
            showPhoneMask
            onSelectRoles={() => rolePicker.openPicker()}
          />
        ),
      });
    }
    if (showExchange) {
      items.push({
        key: "exchange",
        label: "兑换",
        children: <ExiliumExchangePanel />,
      });
    }
    return items;
  }, [showCheckin, showExchange, rolePicker.openPicker]);

  return (
    <PlatformFeatureTabsPage
      title="追放"
      bindName="追放"
      unboundMessage="尚未绑定追放"
      statusQueryKey={["exilium-status"]}
      fetchStatus={() => fetchExiliumStatus(true, true)}
      bindPanel={
        <ExiliumBindPanel
          title="绑定追放账号"
          openRolePickerOnBind={false}
          onSuccess={() => {
            window.setTimeout(() => rolePicker.openPicker(), 0);
          }}
        />
      }
      rolePickerModal={rolePicker.modal}
      featuresReady={featuresReady}
      tabItems={tabItems}
      emptyFeaturesMessage="追放子功能均未启用"
      emptyFeaturesDescription="请联系管理员在「任务配置」中开启签到或兑换。"
    />
  );
}
