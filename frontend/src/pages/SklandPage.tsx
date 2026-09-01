import { useQuery } from "@tanstack/react-query";
import { lazy, useMemo, type ReactNode } from "react";
import {
  fetchPlatformFeaturesEffective,
  fetchSklandStatus,
  triggerSklandCheckin,
  updateSklandRolePref,
} from "@/api/client";
import { ArknightsAttendanceCalendarButton } from "@/components/arknights/ArknightsAttendanceCalendar";
import { EndfieldAttendanceCalendarButton } from "@/components/endfield/EndfieldAttendanceCalendar";
import { CheckinPageTemplate } from "@/components/CheckinPageTemplate";
import { PlatformFeatureTabsPage } from "@/components/PlatformFeatureTabsPage";
import { SklandBindPanel } from "@/components/skland/SklandBindPanel";
import { useRoleMembershipPicker } from "@/hooks/useRoleMembershipPicker";
import { isFeatureOn } from "@/lib/platformFeatures";
import { LOCAL_QUERY_STALE_MS } from "@/lib/queryCache";

const ArknightsTabPanel = lazy(() =>
  import("@/components/arknights/ArknightsTabPanel").then((m) => ({
    default: m.ArknightsTabPanel,
  })),
);

const EndfieldBoxPanel = lazy(() =>
  import("@/components/endfield/EndfieldBoxPanel").then((m) => ({
    default: m.EndfieldBoxPanel,
  })),
);

type TabKey = "checkin" | "arknights" | "endfield";

export default function SklandPage() {
  // 角色树挂在页面级：绑定成功后会卸载 BindPanel，弹窗不能跟它一起卸掉
  const { openPicker, modal: rolePickerModal } = useRoleMembershipPicker("skland");

  const featuresQuery = useQuery({
    queryKey: ["platform-features-effective"],
    queryFn: fetchPlatformFeaturesEffective,
    staleTime: LOCAL_QUERY_STALE_MS,
  });

  const statusQuery = useQuery({
    // 与 CheckinPageTemplate / PlatformFeatureTabsPage 共用 queryKey
    queryKey: ["skland-status"],
    queryFn: () => fetchSklandStatus(true, true),
    retry: false,
    staleTime: 30_000,
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
              updateRolePref={updateSklandRolePref}
              platformIcon="skland"
              onSelectRoles={() => openPicker()}
              renderResultExtra={(row) => {
                if (!row.role_uid) return null;
                if (row.game_code === "arknights") {
                  return (
                    <ArknightsAttendanceCalendarButton
                      uid={row.role_uid}
                      roleName={row.role_name}
                      channelName={row.channel_name}
                    />
                  );
                }
                if (row.game_code === "endfield") {
                  return (
                    <EndfieldAttendanceCalendarButton
                      uid={row.role_uid}
                      roleName={row.role_name}
                      channelName={row.channel_name}
                    />
                  );
                }
                return null;
            }}
          />
        ),
      });
    }
    if (showArknights) {
      items.push({
        key: "arknights",
        label: "明日方舟",
        children: (
          <ArknightsTabPanel
            rogueEnabled={Boolean(
              statusQuery.data?.bound && statusQuery.data?.token_ok !== false,
            )}
          />
        ),
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
  }, [showArknights, showCheckin, showEndfield, statusQuery.data, openPicker]);

  return (
    <PlatformFeatureTabsPage
      title="森空岛"
      bindName="森空岛"
      statusQueryKey={["skland-status"]}
      fetchStatus={() => fetchSklandStatus(true, true)}
      bindPanel={
        <SklandBindPanel
          title="绑定森空岛账号"
          openRolePickerOnBind={false}
          onSuccess={() => {
            window.setTimeout(() => openPicker(), 0);
          }}
        />
      }
      rolePickerModal={rolePickerModal}
      featuresReady={featuresReady}
      tabItems={tabItems}
      emptyFeaturesMessage="森空岛子功能均未启用"
      emptyFeaturesDescription="请联系管理员在「任务配置」中开启签到或养成相关功能。"
    />
  );
}
