import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiError } from "@/lib/apiError";
import { Modal, message } from "antd";
import { useState } from "react";
import {
  exchangeExiliumItem,
  fetchExiliumExchange,
  fetchExiliumStatus,
} from "@/api/client";
import type { ExiliumExchangeItem } from "@/api/types";
import { ExiliumBindPanel } from "@/components/ExiliumBindPanel";
import { ExchangeGoodsCard } from "@/components/ExchangeGoodsCard";
import { ExchangePageTemplate } from "@/components/ExchangePageTemplate";
import { useRoleMembershipPicker } from "@/hooks/useRoleMembershipPicker";

const CYCLE_LABEL: Record<string, string> = {
  day: "每日限购",
  month: "每月限购",
  life: "终生限购",
};

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

type Shop = Awaited<ReturnType<typeof fetchExiliumExchange>>;

export function ExiliumExchangePanel() {
  const queryClient = useQueryClient();
  const [pendingId, setPendingId] = useState<number | null>(null);
  // 角色树挂在面板级：绑定成功后会切到商店视图并卸载 BindPanel
  const rolePicker = useRoleMembershipPicker("exilium");

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

  const confirmExchange = (item: ExiliumExchangeItem, score: number) => {
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

  return (
    <ExchangePageTemplate<Shop>
      bindName="追放"
      unboundMessage="尚未绑定追放社区"
      statusQueryKey={["exilium-status"]}
      fetchStatus={() => fetchExiliumStatus(false)}
      bindPanel={
        <ExiliumBindPanel
          title="绑定追放社区账号"
          openRolePickerOnBind={false}
          onSuccess={() => {
            window.setTimeout(() => rolePicker.openPicker(), 0);
          }}
        />
      }
      bindFooter={rolePicker.modal}
      shopQueryKey={["exilium-exchange"]}
      fetchShop={fetchExiliumExchange}
      balanceLabel="当前积分"
      balanceValue={(shop) => shop.score ?? 0}
      description="与官方社区同步；兑换物品发送至游戏邮箱。每日签到与社区任务可获得积分。"
      isEmpty={(shop) => !(shop.items || []).length}
      footer={() => rolePicker.modal}
    >
      {(shop) => {
        const score = shop.score ?? 0;
        const order = { day: 0, month: 1, life: 2 };
        const sorted = [...(shop.items || [])].sort((a, b) => {
          const ca = order[a.cycle as keyof typeof order] ?? 9;
          const cb = order[b.cycle as keyof typeof order] ?? 9;
          if (ca !== cb) return ca - cb;
          return a.exchange_id - b.exchange_id;
        });
        return sorted.map((item) => {
          const soldOut =
            item.max_exchange_count > 0 &&
            item.exchange_count >= item.max_exchange_count;
          const notEnough = score < item.use_score;
          const cycleLabel = CYCLE_LABEL[item.cycle] || "限购";
          const remain = formatRemain(item.remain_seconds);
          return (
            <ExchangeGoodsCard
              key={item.exchange_id}
              imageUrl={item.item_pic}
              title={`${item.item_name}*${item.item_count}`}
              subtitle={remain || undefined}
              badge={`${cycleLabel} ${item.exchange_count}/${item.max_exchange_count || "∞"}`}
              disabled={soldOut || notEnough}
              loading={pendingId === item.exchange_id}
              buttonColor="#4a4a4a"
              buttonLabel={
                soldOut
                  ? "已兑完"
                  : notEnough
                    ? `积分不足 · ${item.use_score}`
                    : item.use_score
              }
              onClick={() => confirmExchange(item, score)}
            />
          );
        });
      }}
    </ExchangePageTemplate>
  );
}
