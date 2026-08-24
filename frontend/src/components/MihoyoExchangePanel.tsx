import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiError } from "@/lib/apiError";
import { Modal, message } from "antd";
import { useState } from "react";
import {
  exchangeMihoyoItem,
  fetchMihoyoExchange,
  fetchMihoyoStatus,
} from "@/api/client";
import type { MihoyoExchangeItem } from "@/api/types";
import { MihoyoBindPanel } from "@/components/MihoyoBindPanel";
import { ExchangeGoodsCard } from "@/components/ExchangeGoodsCard";
import { ExchangePageTemplate } from "@/components/ExchangePageTemplate";
import { useRoleMembershipPicker } from "@/hooks/useRoleMembershipPicker";

type Shop = Awaited<ReturnType<typeof fetchMihoyoExchange>>;

export function MihoyoExchangePanel() {
  const queryClient = useQueryClient();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const rolePicker = useRoleMembershipPicker("mihoyo");

  const exchangeMut = useMutation({
    mutationFn: (item: MihoyoExchangeItem) =>
      exchangeMihoyoItem({
        goods_id: item.goods_id,
        game_biz: item.game_biz || undefined,
      }),
    onMutate: (item) => setPendingId(item.goods_id),
    onSettled: () => setPendingId(null),
    onSuccess: (data) => {
      message.success(data.message || "兑换成功");
      queryClient.invalidateQueries({ queryKey: ["mihoyo-exchange"] });
      queryClient.invalidateQueries({ queryKey: ["mihoyo-status"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "兑换失败")),
  });

  const confirmExchange = (item: MihoyoExchangeItem, points: number) => {
    Modal.confirm({
      title: "确认兑换",
      content: (
        <div>
          <div>
            {item.goods_name}×{item.goods_num}
          </div>
          <div style={{ marginTop: 8, color: "#666" }}>
            消耗米游币 {item.price}（当前 {points}）
          </div>
        </div>
      ),
      okText: "兑换",
      cancelText: "取消",
      onOk: () => exchangeMut.mutateAsync(item),
    });
  };

  return (
    <ExchangePageTemplate<Shop>
      bindName="米游社"
      unboundMessage="尚未绑定米游社"
      statusQueryKey={["mihoyo-status"]}
      fetchStatus={() => fetchMihoyoStatus(true, true)}
      bindPanel={
        <MihoyoBindPanel
          openRolePickerOnBind={false}
          onSuccess={() => {
            window.setTimeout(() => rolePicker.openPicker(), 0);
          }}
        />
      }
      bindFooter={rolePicker.modal}
      shopQueryKey={["mihoyo-exchange"]}
      fetchShop={fetchMihoyoExchange}
      balanceLabel="当前米游币"
      balanceValue={(shop) => shop.points ?? 0}
      description="与米游社商城同步；部分商品需选择游戏角色领取。"
      isEmpty={(shop) => !(shop.items || []).length}
      footer={() => rolePicker.modal}
    >
      {(shop) => {
        const points = shop.points ?? 0;
        return (shop.items || []).map((item) => {
          const soldOut =
            item.exchange_limit > 0 &&
            item.exchanged_count >= item.exchange_limit;
          const notEnough = points < item.price;
          return (
            <ExchangeGoodsCard
              key={item.goods_id}
              imageUrl={item.goods_img || undefined}
              title={`${item.goods_name}×${item.goods_num}`}
              subtitle={item.game_name || undefined}
              disabled={soldOut || notEnough}
              loading={pendingId === item.goods_id}
              buttonLabel={
                soldOut
                  ? "已兑完"
                  : notEnough
                    ? `米游币不足 · ${item.price}`
                    : item.price
              }
              onClick={() => confirmExchange(item, points)}
            />
          );
        });
      }}
    </ExchangePageTemplate>
  );
}
