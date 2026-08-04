import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Tabs, message } from "antd";
import { useState } from "react";
import {
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

  return (
    <div>
      <PageHeader
        title="森空岛"
        subtitle="签到、明日方舟干员盒子对比与终末地养成"
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
          description="支持扫码、短信验证码或账号密码登录鹰角通行证，用于方舟 / 终末地签到与养成展示。"
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
            children: <ArknightsBoxCompare />,
          },
          {
            key: "endfield",
            label: "明日方舟：终末地",
            children: <EndfieldBoxPanel enabled={canUse} />,
          },
        ]}
      />
    </div>
  );
}
