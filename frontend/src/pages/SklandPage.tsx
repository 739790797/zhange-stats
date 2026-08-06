import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Tabs } from "antd";
import { CalendarOutlined } from "@ant-design/icons";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  fetchPlatformFeaturesEffective,
  fetchSklandStatus,
  triggerSklandCheckin,
  updateSklandRolePref,
} from "@/api/client";
import {
  ArknightsAttendanceCalendarButton,
  isOfficialArknightsChannel,
} from "@/components/ArknightsAttendanceCalendar";
import { ArknightsBoxCompare } from "@/components/ArknightsBoxCompare";
import { CheckinPageTemplate } from "@/components/CheckinPageTemplate";
import { EndfieldBoxPanel } from "@/components/EndfieldBoxPanel";
import { PageHeader } from "@/components/PageHeader";
import { SklandBindPanel } from "@/components/SklandBindPanel";
import { isFeatureOn } from "@/lib/platformFeatures";

type TabKey = "checkin" | "arknights" | "endfield";


export default function SklandPage() {
  const [tab, setTab] = useState<TabKey>("checkin");

  const featuresQuery = useQuery({
    queryKey: ["platform-features-effective"],
    queryFn: fetchPlatformFeaturesEffective,
    staleTime: 30_000,
  });

  const statusQuery = useQuery({
    queryKey: ["skland-status"],
    queryFn: () => fetchSklandStatus(true, true),
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
            updateRolePref={updateSklandRolePref}
            platformIcon="skland"
            renderResultExtra={(row) => {
              if (row.game_code !== "arknights") return null;
              if (!row.role_uid) return null;
              if (isOfficialArknightsChannel(row.channel_name)) {
                return (
                  <ArknightsAttendanceCalendarButton
                    uid={row.role_uid}
                    roleName={row.role_name}
                    channelName={row.channel_name}
                  />
                );
              }
              // B 服等：上游不返回签到进度，置灰提示
              return (
                <Button
                  type="link"
                  size="small"
                  disabled
                  icon={<CalendarOutlined />}
                  style={{ paddingInline: 4, height: "auto" }}
                  title="该渠道森空岛未返回签到进度，暂不支持日历"
                >
                  签到日历（暂不支持）
                </Button>
              );
            }}
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

  const bound = Boolean(statusQuery.data?.bound);
  const tokenBroken = bound && statusQuery.data?.token_ok === false;
  const needsBind = (!bound || tokenBroken) && !statusQuery.isLoading;

  return (
    <div>
      <PageHeader title="森空岛" />

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
