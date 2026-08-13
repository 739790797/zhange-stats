import { useQuery } from "@tanstack/react-query";
import { useMemo, type ReactNode } from "react";
import {
  fetchKujiequStatus,
  fetchPlatformFeaturesEffective,
  triggerKujiequCheckin,
  updateKujiequRolePref,
} from "@/api/client";
import { CheckinPageTemplate } from "@/components/CheckinPageTemplate";
import { KujiequAttendanceCalendarButton } from "@/components/KujiequAttendanceCalendar";
import { KujiequBindPanel } from "@/components/KujiequBindPanel";
import { KujiequExchangePanel } from "@/components/KujiequExchangePanel";
import { PlatformFeatureTabsPage } from "@/components/PlatformFeatureTabsPage";
import { WwBoxPanel } from "@/components/WwBoxPanel";
import { useRoleMembershipPicker } from "@/hooks/useRoleMembershipPicker";
import { hasKujiequAttendanceCalendar } from "@/lib/kujiequAttendance";
import { isFeatureOn } from "@/lib/platformFeatures";

type TabKey = "checkin" | "exchange" | "ww";

export default function KujiequPage() {
  // 角色树挂在页面级：绑定成功后会卸载 BindPanel，弹窗不能跟它一起卸掉
  const rolePicker = useRoleMembershipPicker("kujiequ");

  const featuresQuery = useQuery({
    queryKey: ["platform-features-effective"],
    queryFn: fetchPlatformFeaturesEffective,
    staleTime: 30_000,
  });

  const statusQuery = useQuery({
    queryKey: ["kujiequ-status"],
    queryFn: () => fetchKujiequStatus(true, true),
    retry: false,
    staleTime: 30_000,
  });

  const featuresReady =
    featuresQuery.isSuccess && Boolean(featuresQuery.data);
  const showCheckin =
    featuresReady && isFeatureOn(featuresQuery.data, "kujiequ.checkin");
  const showExchange =
    featuresReady && isFeatureOn(featuresQuery.data, "kujiequ.exchange");
  const showWw =
    featuresReady && isFeatureOn(featuresQuery.data, "kujiequ.ww");

  const tabItems = useMemo(() => {
    const items: { key: TabKey; label: string; children: ReactNode }[] = [];
    if (showCheckin) {
      items.push({
        key: "checkin",
        label: "签到",
        children: (
          <CheckinPageTemplate
            contentOnly
            title="库街区"
            bindName="库街区"
            statusQueryKey={["kujiequ-status"]}
            fetchStatus={fetchKujiequStatus}
            triggerCheckin={triggerKujiequCheckin}
            updateRolePref={updateKujiequRolePref}
            platformIcon="kujiequ"
            renderResultExtra={(row) => {
              const gameCode = row.game_code;
              if (
                !gameCode ||
                !row.role_uid ||
                !hasKujiequAttendanceCalendar(gameCode)
              ) {
                return null;
              }
              return (
                <KujiequAttendanceCalendarButton
                  gameCode={gameCode}
                  roleUid={row.role_uid}
                  roleName={row.role_name}
                  gameName={row.game_name}
                />
              );
            }}
          />
        ),
      });
    }
    if (showExchange) {
      items.push({
        key: "exchange",
        label: "兑换",
        children: <KujiequExchangePanel />,
      });
    }
    if (showWw) {
      items.push({
        key: "ww",
        label: "鸣潮",
        children: (
          <WwBoxPanel
            enabled={Boolean(
              statusQuery.data?.bound && statusQuery.data?.token_ok !== false,
            )}
          />
        ),
      });
    }
    return items;
  }, [showCheckin, showExchange, showWw, statusQuery.data]);

  return (
    <PlatformFeatureTabsPage
      title="库街区"
      bindName="库街区"
      statusQueryKey={["kujiequ-status"]}
      fetchStatus={() => fetchKujiequStatus(true, true)}
      bindPanel={
        <KujiequBindPanel
          title="绑定库街区账号"
          openRolePickerOnBind={false}
          onSuccess={() => {
            window.setTimeout(() => rolePicker.openPicker(), 0);
          }}
        />
      }
      rolePickerModal={rolePicker.modal}
      featuresReady={featuresReady}
      tabItems={tabItems}
      emptyFeaturesMessage="库街区子功能均未启用"
      emptyFeaturesDescription="请联系管理员在「任务配置」中开启签到、兑换或鸣潮。"
    />
  );
}
