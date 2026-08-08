import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiError } from "@/lib/apiError";
import { Modal, Select, Space, Tabs, Typography, message } from "antd";
import { useState } from "react";
import {
  exchangeKujiequItem,
  fetchKujiequExchange,
  fetchKujiequStatus,
} from "@/api/client";
import type { KujiequExchangeItem, KujiequExchangeRole } from "@/api/types";
import { ExchangeGoodsCard } from "@/components/ExchangeGoodsCard";
import { ExchangePageTemplate } from "@/components/ExchangePageTemplate";
import { KujiequBindPanel } from "@/components/KujiequBindPanel";
import { useRoleMembershipPicker } from "@/hooks/useRoleMembershipPicker";

type GameFilter = "all" | "2" | "3" | "0";

const GAME_TABS: { key: GameFilter; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "2", label: "战双帕弥什" },
  { key: "3", label: "鸣潮" },
  { key: "0", label: "库街区" },
];

function needsRole(gameId: number) {
  return gameId === 2 || gameId === 3;
}

function statusLabel(item: KujiequExchangeItem) {
  if (item.commodity_type === 2) return "实物·请用 App";
  // 与后端一致：仅有总库存跟踪时 surplus==0 才是售罄
  if (
    item.is_sellout ||
    (item.total_surplus_stock === 0 && item.total_stock > 0)
  ) {
    return "已兑完";
  }
  if (item.commodity_status === 2) return "未开兑";
  if (item.commodity_status === 3 || item.commodity_status === 4)
    return "已下架";
  if (item.commodity_limit > 0 && item.current_user_limit_buy <= 0)
    return "已达上限";
  return null;
}

type Shop = Awaited<ReturnType<typeof fetchKujiequExchange>>;

export function KujiequExchangePanel() {
  const queryClient = useQueryClient();
  const [pendingCode, setPendingCode] = useState<string | null>(null);
  const [gameFilter, setGameFilter] = useState<GameFilter>("all");
  const [lastRoleByGame, setLastRoleByGame] = useState<Record<string, string>>(
    {},
  );
  const [exchangeItem, setExchangeItem] = useState<KujiequExchangeItem | null>(
    null,
  );
  const [pickedRoleId, setPickedRoleId] = useState<string>("");
  const rolePicker = useRoleMembershipPicker("kujiequ");

  const exchangeMut = useMutation({
    mutationFn: (payload: {
      commodity_code: string;
      game_id: number;
      role_id?: string | null;
    }) => exchangeKujiequItem(payload),
    onMutate: (payload) => setPendingCode(payload.commodity_code),
    onSettled: () => setPendingCode(null),
    onSuccess: (data) => {
      message.success(data.message || "兑换成功");
      setExchangeItem(null);
      queryClient.invalidateQueries({ queryKey: ["kujiequ-exchange"] });
      queryClient.invalidateQueries({ queryKey: ["kujiequ-status"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "兑换失败")),
  });

  const openExchange = (item: KujiequExchangeItem, roles: KujiequExchangeRole[]) => {
    const gameId = Number(item.game_id || 0);
    if (needsRole(gameId)) {
      const gameRoles = roles.filter((r) => Number(r.game_id) === gameId);
      if (!gameRoles.length) {
        message.error("未找到该游戏角色，请先在库街区绑定后再兑换");
        return;
      }
      const preferred = lastRoleByGame[String(gameId)];
      const initial =
        preferred && gameRoles.some((r) => r.role_id === preferred)
          ? preferred
          : gameRoles[0].role_id;
      setPickedRoleId(initial);
    } else {
      setPickedRoleId("");
    }
    setExchangeItem(item);
  };

  const submitExchange = async () => {
    if (!exchangeItem) return;
    const gameId = Number(exchangeItem.game_id || 0);
    if (needsRole(gameId) && !pickedRoleId) {
      message.error("请选择接收角色");
      return;
    }
    if (needsRole(gameId)) {
      setLastRoleByGame((prev) => ({
        ...prev,
        [String(gameId)]: pickedRoleId,
      }));
    }
    await exchangeMut.mutateAsync({
      commodity_code: exchangeItem.commodity_code,
      game_id: gameId,
      role_id: pickedRoleId || null,
    });
  };

  return (
    <ExchangePageTemplate<Shop>
      bindName="库街区"
      statusQueryKey={["kujiequ-status"]}
      fetchStatus={() => fetchKujiequStatus(true, true)}
      bindPanel={
        <KujiequBindPanel
          title="绑定库街区账号"
          openRolePickerOnBind={false}
          onSuccess={() => {
            window.setTimeout(() => rolePicker.openPicker(), 0);
          }}
        />
      }
      bindFooter={rolePicker.modal}
      shopQueryKey={["kujiequ-exchange"]}
      fetchShop={() => fetchKujiequExchange()}
      balanceLabel="库洛币"
      balanceValue={(shop) => shop.gold ?? 0}
      description="与官方库街区同步；完成签到与每日任务可获取库洛币。兑换战双/鸣潮道具时选择发放角色；实物请在 App 内兑换。"
      toolbar={() => (
        <Tabs
          activeKey={gameFilter}
          onChange={(k) => setGameFilter(k as GameFilter)}
          items={GAME_TABS.map((t) => ({ key: t.key, label: t.label }))}
          size="small"
        />
      )}
      isEmpty={(shop) => {
        const items = shop.items || [];
        if (gameFilter === "all") return items.length === 0;
        const gid = Number(gameFilter);
        return !items.some((it) => it.game_id === gid);
      }}
      footer={(shop) => {
        const gold = shop.gold ?? 0;
        const roles = shop.roles || [];
        const gameId = Number(exchangeItem?.game_id || 0);
        const roleOptions = !exchangeItem
          ? []
          : needsRole(gameId)
            ? roles.filter((r) => Number(r.game_id) === gameId)
            : roles;
        return (
          <>
            <Modal
              open={Boolean(exchangeItem)}
              title="确认兑换"
              okText="兑换"
              cancelText="取消"
              confirmLoading={Boolean(pendingCode)}
              onCancel={() => setExchangeItem(null)}
              onOk={submitExchange}
              destroyOnClose
            >
              {exchangeItem ? (
                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                  <div>
                    <Typography.Text strong>
                      {exchangeItem.commodity_name}
                    </Typography.Text>
                    <div style={{ marginTop: 6, color: "#666" }}>
                      消耗库洛币 {exchangeItem.commodity_price}（当前 {gold}）
                    </div>
                  </div>
                  {needsRole(gameId) ? (
                    <div>
                      <Typography.Text type="secondary">发放角色</Typography.Text>
                      <Select
                        style={{ width: "100%", marginTop: 6 }}
                        value={pickedRoleId || undefined}
                        onChange={setPickedRoleId}
                        options={roleOptions.map((r) => ({
                          value: r.role_id,
                          label: `${r.role_name || r.role_id}（${r.game_name || r.game_id}）`,
                        }))}
                        placeholder="请选择接收角色"
                      />
                      <Typography.Text
                        type="secondary"
                        style={{ display: "block", marginTop: 6, fontSize: 12 }}
                      >
                        兑换成功后请到游戏或社区查看。
                      </Typography.Text>
                    </div>
                  ) : (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      兑换成功后请到游戏或社区查看。
                    </Typography.Text>
                  )}
                </Space>
              ) : null}
            </Modal>
            {rolePicker.modal}
          </>
        );
      }}
    >
      {(shop) => {
        const gold = shop.gold ?? 0;
        const items = shop.items || [];
        const filtered =
          gameFilter === "all"
            ? items
            : items.filter((it) => it.game_id === Number(gameFilter));
        return filtered.map((item) => {
          const label = statusLabel(item);
          const notEnough = gold < item.commodity_price;
          const disabled =
            !item.can_exchange ||
            notEnough ||
            pendingCode === item.commodity_code ||
            Boolean(label);
          return (
            <ExchangeGoodsCard
              key={item.commodity_code}
              imageUrl={item.picture_url}
              title={item.commodity_name}
              subtitle={`${item.game_name || "库街区"}${
                item.total_surplus_stock > 0
                  ? ` · 库存 ${item.total_surplus_stock}`
                  : ""
              }`}
              disabled={disabled}
              loading={pendingCode === item.commodity_code}
              buttonColor="#13c2c2"
              buttonLabel={
                label
                  ? label
                  : notEnough
                    ? `库洛币不足 · ${item.commodity_price}`
                    : item.commodity_price
              }
              onClick={() => openExchange(item, shop.roles || [])}
            />
          );
        });
      }}
    </ExchangePageTemplate>
  );
}
