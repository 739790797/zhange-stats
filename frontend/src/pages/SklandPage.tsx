import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Empty, Tabs, message } from "antd";
import { useMemo, useState } from "react";
import {
  fetchSklandStatus,
  triggerSklandCheckin,
  updateSklandBind,
} from "@/api/client";
import { ArknightsBoxPanel } from "@/components/ArknightsBoxPanel";
import { CheckinPageTemplate } from "@/components/CheckinPageTemplate";
import { PageHeader } from "@/components/PageHeader";
import { SklandBindPanel } from "@/components/SklandBindPanel";
import { isCheckinSuccess } from "@/lib/checkinStatus";

type TabKey = "checkin" | "arknights" | "endfield";

function apiError(e: unknown, fallback: string) {
  const detail =
    e &&
    typeof e === "object" &&
    "response" in e &&
    (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
  return String(detail || (e as Error)?.message || fallback);
}

export default function SklandPage() {
  const [tab, setTab] = useState<TabKey>("checkin");
  const queryClient = useQueryClient();

  const statusQuery = useQuery({
    queryKey: ["skland-status"],
    queryFn: () => fetchSklandStatus(true),
    retry: false,
  });

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

  const endfieldRoles = useMemo(
    () =>
      (statusQuery.data?.roles || []).filter((r) => r.game_code === "endfield"),
    [statusQuery.data?.roles],
  );

  return (
    <div>
      <PageHeader
        title="森空岛"
        subtitle="签到、明日方舟干员盒子与终末地（建设中）"
        extra={
          tab === "checkin" && canUse ? (
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

      {!bound && !statusQuery.isLoading ? (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="尚未绑定森空岛"
          description="支持扫码、短信验证码或账号密码登录鹰角通行证，用于方舟 / 终末地签到与干员盒子。"
        />
      ) : null}

      {tokenBroken ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="森空岛凭证可能已失效"
          description={statusQuery.data?.token_error || "请重新绑定后再试。"}
        />
      ) : null}

      {(!bound || tokenBroken) && !statusQuery.isLoading ? (
        <Card style={{ marginBottom: 24 }}>
          <SklandBindPanel title="绑定森空岛账号" />
        </Card>
      ) : null}

      <Tabs
        activeKey={tab}
        onChange={(k) => setTab(k as TabKey)}
        items={[
          {
            key: "checkin",
            label: "签到",
            children: (
              <CheckinPageTemplate
                contentOnly
                title="森空岛"
                subtitle=""
                bindName="森空岛"
                bindDescription=""
                statusQueryKey={["skland-status"]}
                fetchStatus={fetchSklandStatus}
                triggerCheckin={triggerSklandCheckin}
                updateBind={updateSklandBind}
              />
            ),
          },
          {
            key: "arknights",
            label: "明日方舟",
            children: (
              <ArknightsBoxPanel
                enabled={canUse}
                fallbackRoles={statusQuery.data?.roles || []}
              />
            ),
          },
          {
            key: "endfield",
            label: "明日方舟：终末地",
            children: canUse ? (
              endfieldRoles.length ? (
                <Card title="绑定角色">
                  {endfieldRoles.map((r) => (
                    <div key={r.uid} style={{ marginBottom: 8 }}>
                      {r.role_name}
                      <span style={{ color: "#888" }}> · {r.channel_name}</span>
                      <span style={{ color: "#888" }}> · UID {r.uid}</span>
                    </div>
                  ))}
                  <Empty
                    style={{ marginTop: 24 }}
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="终末地角色卡片 / 养成展示开发中"
                  />
                </Card>
              ) : (
                <Empty description="未绑定终末地角色" />
              )
            ) : (
              <Empty description="绑定森空岛后可查看终末地角色" />
            ),
          },
        ]}
      />
    </div>
  );
}
