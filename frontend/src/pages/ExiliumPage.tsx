import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Tabs, message } from "antd";
import { useState } from "react";
import {
  fetchExiliumStatus,
  triggerExiliumCheckin,
  updateExiliumBind,
} from "@/api/client";
import { CheckinPageTemplate } from "@/components/CheckinPageTemplate";
import { ExiliumBindPanel } from "@/components/ExiliumBindPanel";
import { ExiliumExchangePanel } from "@/components/ExiliumExchangePanel";
import { PageHeader } from "@/components/PageHeader";
import { isCheckinSuccess } from "@/lib/checkinStatus";

type TabKey = "checkin" | "exchange";

function apiError(e: unknown, fallback: string) {
  const detail =
    e &&
    typeof e === "object" &&
    "response" in e &&
    (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
  return String(detail || (e as Error)?.message || fallback);
}

export default function ExiliumPage() {
  const [tab, setTab] = useState<TabKey>("checkin");
  const queryClient = useQueryClient();

  const statusQuery = useQuery({
    queryKey: ["exilium-status"],
    queryFn: () => fetchExiliumStatus(true),
    retry: false,
  });

  const checkin = useMutation({
    mutationFn: triggerExiliumCheckin,
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
        message.warning("签到未成功，可再次尝试");
      } else {
        message.success("签到完成");
      }
      queryClient.invalidateQueries({ queryKey: ["exilium-status"] });
      queryClient.invalidateQueries({ queryKey: ["exilium-exchange"] });
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
        title="追放"
        subtitle="少女前线2：追放官方社区签到与积分兑换"
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
          message="尚未绑定追放社区"
          description="使用社区账号密码或手机验证码绑定后，可自动签到并兑换积分物品。"
        />
      ) : null}

      {tokenBroken ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="追放凭证可能已失效"
          description={statusQuery.data?.token_error || "请重新绑定后再试。"}
        />
      ) : null}

      {(!bound || tokenBroken) && !statusQuery.isLoading ? (
        <Card style={{ marginBottom: 24 }}>
          <ExiliumBindPanel title="绑定追放社区账号" />
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
                title="追放"
                subtitle=""
                bindName="追放社区"
                bindDescription=""
                statusQueryKey={["exilium-status"]}
                fetchStatus={fetchExiliumStatus}
                triggerCheckin={triggerExiliumCheckin}
                updateBind={updateExiliumBind}
                showPhoneMask
              />
            ),
          },
          {
            key: "exchange",
            label: "积分兑换",
            children: <ExiliumExchangePanel />,
          },
        ]}
      />
    </div>
  );
}
