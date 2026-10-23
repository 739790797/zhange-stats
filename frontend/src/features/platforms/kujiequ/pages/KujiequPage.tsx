import { useQuery } from "@tanstack/react-query";
import { lazy, useMemo, type ReactNode } from "react";
import { fetchKujiequStatus, triggerKujiequCheckin, updateKujiequRolePref } from "@/features/platforms/kujiequ/api/kujiequApi";
import { fetchPlatformFeaturesEffective } from "@/features/platforms/shared/api/platformFeaturesApi";
import { CheckinPageTemplate } from "@/features/daily/components/CheckinPageTemplate";
import { KujiequAttendanceCalendarButton } from "@/features/platforms/kujiequ/components/KujiequAttendanceCalendar";
import { KujiequBindPanel } from "@/features/platforms/kujiequ/components/KujiequBindPanel";
import { PlatformFeatureTabsPage } from "@/features/platforms/shared/components/PlatformFeatureTabsPage";
import { useRoleMembershipPicker } from "@/features/profile/hooks/useRoleMembershipPicker";
import { hasKujiequAttendanceCalendar } from "@/features/platforms/kujiequ/model/kujiequAttendance";
import { isFeatureOn } from "@/features/platforms/shared/model/platformFeatures";
import { LOCAL_QUERY_STALE_MS } from "@/shared/lib/queryCache";

const KujiequExchangePanel = lazy(() =>
  import("@/features/platforms/kujiequ/components/KujiequExchangePanel").then((m) => ({
    default: m.KujiequExchangePanel,
  })),
);

const WwBoxPanel = lazy(() =>
  import("@/features/platforms/kujiequ/components/WwBoxPanel").then((m) => ({
    default: m.WwBoxPanel,
  })),
);

type TabKey = "checkin" | "exchange" | "ww";

export default function KujiequPage() {
  // 角色树挂在页面级：绑定成功后会卸载 BindPanel，弹窗不能跟它一起卸掉
  const { openPicker, modal: rolePickerModal } = useRoleMembershipPicker("kujiequ");

  const featuresQuery = useQuery({
    queryKey: ["platform-features-effective"],
    queryFn: fetchPlatformFeaturesEffective,
    staleTime: LOCAL_QUERY_STALE_MS,
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
            onSelectRoles={() => openPicker()}
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
  }, [showCheckin, showExchange, showWw, statusQuery.data, openPicker]);

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
            window.setTimeout(() => openPicker(), 0);
          }}
        />
      }
      rolePickerModal={rolePickerModal}
      featuresReady={featuresReady}
      tabItems={tabItems}
      emptyFeaturesMessage="库街区子功能均未启用"
      emptyFeaturesDescription="请联系管理员在「任务配置」中开启签到、兑换或鸣潮。"
    />
  );
}
