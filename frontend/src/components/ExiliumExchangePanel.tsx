import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Empty,
  Modal,
  Space,
  Typography,
  message,
} from "antd";
import { useMemo, useState } from "react";
import {
  exchangeExiliumItem,
  fetchExiliumExchange,
  fetchExiliumStatus,
} from "@/api/client";
import type { ExiliumExchangeItem } from "@/api/types";
import { ExiliumBindPanel } from "@/components/ExiliumBindPanel";

const CYCLE_LABEL: Record<string, string> = {
  day: "每日限购",
  month: "每月限购",
  life: "终生限购",
};

function apiError(e: unknown, fallback: string) {
  const detail =
    e &&
    typeof e === "object" &&
    "response" in e &&
    (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
  return String(detail || (e as Error)?.message || fallback);
}

function formatRemain(seconds: number | null | undefined) {
  if (seconds == null || seconds < 0) return null;
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const parts: string[] = [];
  if (d > 0) parts.push(`${d}天`);
  if (h > 0 || d > 0) parts.push(`${h}小时`);
  parts.push(`${m}分钟`);
  return `剩余: ${parts.join("")}`;
}

function ExchangeCard({
  item,
  score,
  exchanging,
  onExchange,
}: {
  item: ExiliumExchangeItem;
  score: number;
  exchanging: boolean;
  onExchange: (item: ExiliumExchangeItem) => void;
}) {
  const [imgFailed, setImgFailed] = useState(false);
  const soldOut =
    item.max_exchange_count > 0 &&
    item.exchange_count >= item.max_exchange_count;
  const notEnough = score < item.use_score;
  const disabled = soldOut || notEnough || exchanging;
  const cycleLabel = CYCLE_LABEL[item.cycle] || "限购";
  const remain = formatRemain(item.remain_seconds);

  return (
    <div
      style={{
        position: "relative",
        border: "1px solid rgba(0,0,0,0.08)",
        borderRadius: 10,
        background: "#fff",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        minHeight: 220,
        opacity: soldOut ? 0.72 : 1,
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 10,
          right: 10,
          zIndex: 1,
          background: "#f5a623",
          color: "#fff",
          fontSize: 12,
          lineHeight: 1.2,
          padding: "4px 8px",
          borderRadius: 4,
          fontWeight: 600,
        }}
      >
        {cycleLabel} {item.exchange_count}/{item.max_exchange_count || "∞"}
      </div>

      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "28px 16px 12px",
          gap: 8,
        }}
      >
        {!imgFailed && item.item_pic ? (
          <img
            src={item.item_pic}
            alt={item.item_name}
            width={88}
            height={88}
            style={{ objectFit: "contain" }}
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={() => setImgFailed(true)}
          />
        ) : (
          <div
            style={{
              width: 88,
              height: 88,
              borderRadius: 8,
              background: "#f0f0f0",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#999",
              fontSize: 12,
            }}
          >
            无图
          </div>
        )}
        <Typography.Text strong style={{ textAlign: "center" }}>
          {item.item_name}*{item.item_count}
        </Typography.Text>
        {remain ? (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {remain}
          </Typography.Text>
        ) : null}
      </div>

      <Button
        type="primary"
        disabled={disabled}
        loading={exchanging}
        onClick={() => onExchange(item)}
        style={{
          borderRadius: 0,
          height: 40,
          background: disabled ? undefined : "#4a4a4a",
          borderColor: disabled ? undefined : "#4a4a4a",
        }}
        block
      >
        {soldOut
          ? "已兑完"
          : notEnough
            ? `积分不足 · ${item.use_score}`
            : item.use_score}
      </Button>
    </div>
  );
}

export function ExiliumExchangePanel() {
  const queryClient = useQueryClient();
  const [pendingId, setPendingId] = useState<number | null>(null);

  const statusQuery = useQuery({
    queryKey: ["exilium-status"],
    queryFn: () => fetchExiliumStatus(false),
    retry: false,
  });

  const bound = Boolean(statusQuery.data?.bound);
  const tokenBroken = bound && statusQuery.data?.token_ok === false;
  const canUse = bound && !tokenBroken;

  const shopQuery = useQuery({
    queryKey: ["exilium-exchange"],
    queryFn: fetchExiliumExchange,
    enabled: canUse,
    retry: false,
  });

  const exchangeMut = useMutation({
    mutationFn: (exchangeId: number) => exchangeExiliumItem(exchangeId),
    onMutate: (exchangeId) => setPendingId(exchangeId),
    onSettled: () => setPendingId(null),
    onSuccess: (data) => {
      message.success(data.message || "兑换成功");
      queryClient.invalidateQueries({ queryKey: ["exilium-exchange"] });
      queryClient.invalidateQueries({ queryKey: ["exilium-status"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "兑换失败")),
  });

  const items = shopQuery.data?.items || [];
  const score = shopQuery.data?.score ?? 0;

  const sortedItems = useMemo(() => {
    const order = { day: 0, month: 1, life: 2 };
    return [...items].sort((a, b) => {
      const ca = order[a.cycle as keyof typeof order] ?? 9;
      const cb = order[b.cycle as keyof typeof order] ?? 9;
      if (ca !== cb) return ca - cb;
      return a.exchange_id - b.exchange_id;
    });
  }, [items]);

  const confirmExchange = (item: ExiliumExchangeItem) => {
    Modal.confirm({
      title: "确认兑换",
      content: (
        <div>
          <div>
            {item.item_name}*{item.item_count}
          </div>
          <div style={{ marginTop: 8, color: "#666" }}>
            消耗积分 {item.use_score}（当前 {score}）
          </div>
          <div style={{ marginTop: 4, color: "#999", fontSize: 12 }}>
            兑换成功后请到游戏邮箱领取
          </div>
        </div>
      ),
      okText: "兑换",
      cancelText: "取消",
      onOk: () => exchangeMut.mutateAsync(item.exchange_id),
    });
  };

  if (statusQuery.isLoading) {
    return <Card loading />;
  }

  if (!bound || tokenBroken) {
    return (
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Alert
          type={tokenBroken ? "warning" : "info"}
          showIcon
          message={tokenBroken ? "追放凭证可能已失效" : "尚未绑定追放社区"}
          description={
            tokenBroken
              ? statusQuery.data?.token_error || "请重新绑定后再兑换。"
              : undefined
          }
        />
        <Card>
          <ExiliumBindPanel title="绑定追放社区账号" />
        </Card>
      </Space>
    );
  }

  if (shopQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="加载积分中心失败"
        description={apiError(shopQuery.error, "请稍后重试")}
      />
    );
  }

  if (shopQuery.isLoading) {
    return <Card loading />;
  }

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <div
        style={{
          display: "flex",
          gap: 12,
          flexWrap: "wrap",
          alignItems: "stretch",
        }}
      >
        <Card size="small" style={{ minWidth: 140 }}>
          <Typography.Text type="secondary" style={{ display: "block" }}>
            当前积分
          </Typography.Text>
          <Typography.Text
            strong
            style={{ fontSize: 28, color: "#d48806", lineHeight: 1.2 }}
          >
            {score}
          </Typography.Text>
        </Card>
        <Card size="small" style={{ flex: 1, minWidth: 180 }}>
          <Typography.Text strong style={{ fontSize: 16 }}>
            积分中心
          </Typography.Text>
          <Typography.Paragraph
            type="secondary"
            style={{ margin: "6px 0 0", fontSize: 13 }}
          >
            与官方社区同步；兑换物品发送至游戏邮箱。每日签到与社区任务可获得积分。
          </Typography.Paragraph>
        </Card>
      </div>

      {sortedItems.length === 0 ? (
        <Empty description="暂无可兑换物品" />
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: 16,
          }}
        >
          {sortedItems.map((item) => (
            <ExchangeCard
              key={item.exchange_id}
              item={item}
              score={score}
              exchanging={pendingId === item.exchange_id}
              onExchange={confirmExchange}
            />
          ))}
        </div>
      )}
    </Space>
  );
}
