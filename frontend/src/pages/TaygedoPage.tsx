import { useQuery } from "@tanstack/react-query";
import { useMemo, type ReactNode } from "react";
import {
  fetchPlatformFeaturesEffective,
  fetchTaygedoStatus,
  triggerTaygedoCheckin,
  updateTaygedoRolePref,
} from "@/api/client";
import { CheckinPageTemplate } from "@/components/CheckinPageTemplate";
import { ExastrisBoxPanel } from "@/components/ExastrisBoxPanel";
import { PlatformFeatureTabsPage } from "@/components/PlatformFeatureTabsPage";
import { TaygedoAttendanceCalendarButton } from "@/components/TaygedoAttendanceCalendar";
import { TaygedoBindPanel } from "@/components/TaygedoBindPanel";
import { TaygedoExchangePanel } from "@/components/TaygedoExchangePanel";
import { useRoleMembershipPicker } from "@/hooks/useRoleMembershipPicker";
import { isFeatureOn } from "@/lib/platformFeatures";
import { hasTaygedoAttendanceCalendar } from "@/lib/taygedoAttendance";

type TabKey = "checkin" | "exchange" | "exastris";

export default function TaygedoPage() {
  // 角色树挂在页面级：绑定成功后会卸载 BindPanel，弹窗不能跟它一起卸掉
  const rolePicker = useRoleMembershipPicker("taygedo");

  const featuresQuery = useQuery({
    queryKey: ["platform-features-effective"],
    queryFn: fetchPlatformFeaturesEffective,
    staleTime: 30_000,
  });

  const statusQuery = useQuery({
    // 与 CheckinPageTemplate / PlatformFeatureTabsPage 共用 queryKey
    queryKey: ["taygedo-status"],
    queryFn: () => fetchTaygedoStatus(true, true),
    retry: false,
    staleTime: 30_000,
  });

  const featuresReady =
    featuresQuery.isSuccess && Boolean(featuresQuery.data);
  const showCheckin =
    featuresReady && isFeatureOn(featuresQuery.data, "taygedo.checkin");
  const showExchange =
    featuresReady && isFeatureOn(featuresQuery.data, "taygedo.exchange");
  const showExastris =
    featuresReady && isFeatureOn(featuresQuery.data, "taygedo.exastris");

  const tabItems = useMemo(() => {
    const items: { key: TabKey; label: string; children: ReactNode }[] = [];
    if (showCheckin) {
      items.push({
        key: "checkin",
        label: "签到",
        children: (
          <CheckinPageTemplate
            contentOnly
            title="塔吉多"
            bindName="塔吉多"
            statusQueryKey={["taygedo-status"]}
            fetchStatus={fetchTaygedoStatus}
            triggerCheckin={triggerTaygedoCheckin}
            updateRolePref={updateTaygedoRolePref}
            platformIcon="taygedo"
            renderResultExtra={(row) => {
              const gameCode = row.game_code;
              const roleUid = row.role_uid;
              if (
                !gameCode ||
                !roleUid ||
                !hasTaygedoAttendanceCalendar(gameCode)
              ) {
                return null;
              }
              return (
                <TaygedoAttendanceCalendarButton
                  gameCode={gameCode}
                  roleUid={roleUid}
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
        children: <TaygedoExchangePanel />,
      });
    }
    if (showExastris) {
      items.push({
        key: "exastris",
        label: "异环",
        children: (
          <ExastrisBoxPanel
            enabled={Boolean(
              statusQuery.data?.bound && statusQuery.data?.token_ok !== false,
            )}
          />
        ),
      });
    }
    return items;
  }, [showCheckin, showExchange, showExastris, statusQuery.data]);

  return (
    <PlatformFeatureTabsPage
      title="塔吉多"
      bindName="塔吉多"
      statusQueryKey={["taygedo-status"]}
      fetchStatus={() => fetchTaygedoStatus(true, true)}
      bindPanel={
        <TaygedoBindPanel
          title="绑定塔吉多账号"
          openRolePickerOnBind={false}
          onSuccess={() => {
            window.setTimeout(() => rolePicker.openPicker(), 0);
          }}
        />
      }
      rolePickerModal={rolePicker.modal}
      featuresReady={featuresReady}
      tabItems={tabItems}
      emptyFeaturesMessage="塔吉多子功能均未启用"
      emptyFeaturesDescription="请联系管理员在「任务配置」中开启签到、兑换或异环相关功能。"
    />
  );
}
