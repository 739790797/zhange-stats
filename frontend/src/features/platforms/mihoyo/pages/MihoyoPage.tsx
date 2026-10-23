import { useQuery } from "@tanstack/react-query";
import { lazy, useMemo, type ReactNode } from "react";
import { fetchMihoyoStatus, triggerMihoyoCheckin, updateMihoyoRolePref } from "@/features/platforms/mihoyo/api/mihoyoApi";
import { fetchPlatformFeaturesEffective } from "@/features/platforms/shared/api/platformFeaturesApi";
import { CheckinPageTemplate } from "@/features/daily/components/CheckinPageTemplate";
import { MihoyoAttendanceCalendarButton } from "@/features/platforms/mihoyo/components/MihoyoAttendanceCalendar";
import { MihoyoBindPanel } from "@/features/platforms/mihoyo/components/MihoyoBindPanel";
import { PlatformFeatureTabsPage } from "@/features/platforms/shared/components/PlatformFeatureTabsPage";
import { useRoleMembershipPicker } from "@/features/profile/hooks/useRoleMembershipPicker";
import { hasMihoyoAttendanceCalendar } from "@/features/platforms/mihoyo/model/mihoyoAttendance";
import { isFeatureOn } from "@/features/platforms/shared/model/platformFeatures";
import { LOCAL_QUERY_STALE_MS } from "@/shared/lib/queryCache";

const MihoyoExchangePanel = lazy(() =>
  import("@/features/platforms/mihoyo/components/MihoyoExchangePanel").then((m) => ({
    default: m.MihoyoExchangePanel,
  })),
);

type TabKey = "checkin" | "exchange";

export default function MihoyoPage() {
  const { openPicker, modal: rolePickerModal } = useRoleMembershipPicker("mihoyo");

  const featuresQuery = useQuery({
    queryKey: ["platform-features-effective"],
    queryFn: fetchPlatformFeaturesEffective,
    staleTime: LOCAL_QUERY_STALE_MS,
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
            onSelectRoles={() => openPicker()}
            renderResultExtra={(row) => {
              const gameCode = row.game_code;
              if (
                !gameCode ||
                !row.role_uid ||
                !hasMihoyoAttendanceCalendar(gameCode)
              ) {
                return null;
              }
              return (
                <MihoyoAttendanceCalendarButton
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
        children: <MihoyoExchangePanel />,
      });
    }
    return items;
  }, [showCheckin, showExchange, openPicker]);

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
            window.setTimeout(() => openPicker(), 0);
          }}
        />
      }
      rolePickerModal={rolePickerModal}
      featuresReady={featuresReady}
      tabItems={tabItems}
      emptyFeaturesMessage="米游社子功能均未启用"
      emptyFeaturesDescription="请联系管理员在「任务配置」中开启签到或兑换。"
    />
  );
}
