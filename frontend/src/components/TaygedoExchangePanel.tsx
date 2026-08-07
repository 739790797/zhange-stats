import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiError } from "@/lib/apiError";
import {
  Alert,
  Modal,
  Select,
  Space,
  Tabs,
  Typography,
  message,
} from "antd";
import { useEffect, useState } from "react";
import {
  exchangeTaygedoItem,
  fetchTaygedoExchange,
  fetchTaygedoStatus,
} from "@/api/client";
import type { TaygedoExchangeItem, TaygedoExchangeRole } from "@/api/types";
import { ExchangeGoodsCard } from "@/components/ExchangeGoodsCard";
import { ExchangePageTemplate } from "@/components/ExchangePageTemplate";
import { TaygedoBindPanel } from "@/components/TaygedoBindPanel";
import { useRoleMembershipPicker } from "@/hooks/useRoleMembershipPicker";

const CYCLE_LABEL: Record<number, string> = {
  1: "每月限购",
};

const GAME_LABEL: Record<string, string> = {
  "1256": "幻塔",
  "1289": "异环",
};

function statusLabel(item: TaygedoExchangeItem) {
  if (!item.can_exchange) {
    if (item.stock_limited && item.stock === 0) return "已兑完";
    if (item.cycle_limit > 0 && item.exchange_num >= item.cycle_limit) {
      return "已达上限";
    }
    if (item.state !== 0 && item.state !== 1) return "暂不可兑";
    return "暂不可兑";
  }
  return null;
}

type Shop = Awaited<ReturnType<typeof fetchTaygedoExchange>>;

export function TaygedoExchangePanel() {
  const queryClient = useQueryClient();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [tab, setTab] = useState<string>("all");
  /** 各游戏上次选过的接收角色，仅作弹窗默认值 */
  const [lastRoleByGame, setLastRoleByGame] = useState<Record<string, string>>(
    {},
  );
  const [exchangeItem, setExchangeItem] = useState<TaygedoExchangeItem | null>(
    null,
  );
  const [pickedRoleId, setPickedRoleId] = useState<string>("");
  const rolePicker = useRoleMembershipPicker("taygedo");

  const exchangeMut = useMutation({
    mutationFn: (payload: {
      goods_id: string;
      game_id: string;
      role_id: string;
    }) => exchangeTaygedoItem(payload),
    onMutate: (payload) => setPendingId(payload.goods_id),
    onSettled: () => setPendingId(null),
    onSuccess: (data) => {
      message.success(data.message || "兑换成功");
      setExchangeItem(null);
      queryClient.invalidateQueries({ queryKey: ["taygedo-exchange"] });
      queryClient.invalidateQueries({ queryKey: ["taygedo-status"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "兑换失败")),
  });

  const openExchange = (
    item: TaygedoExchangeItem,
    roles: TaygedoExchangeRole[],
  ) => {
    if (!roles.length) {
      message.error("未找到游戏角色，请先在塔吉多绑定后再兑换");
      return;
    }
    const gameId = String(item.game_id || "").trim();
    const gameRoles = gameId
      ? roles.filter((r) => r.game_id === gameId)
      : roles;
    if (!gameRoles.length) {
      message.error("未找到该游戏角色，请先在塔吉多绑定后再兑换");
      return;
    }
    const memoryKey = gameId || "_any";
    const preferred = lastRoleByGame[memoryKey];
    const initial =
      preferred && gameRoles.some((r) => r.role_id === preferred)
        ? preferred
        : gameRoles[0].role_id;
    setPickedRoleId(initial);
    setExchangeItem(item);
  };

  const submitExchange = async (roles: TaygedoExchangeRole[]) => {
    if (!exchangeItem) return;
    if (!pickedRoleId) {
      message.error("请选择接收角色");
      return;
    }
    const picked = roles.find((r) => r.role_id === pickedRoleId);
    const gameId =
      String(exchangeItem.game_id || "").trim() ||
      String(picked?.game_id || "").trim();
    if (!gameId) {
      message.error("请选择接收角色所属游戏");
      return;
    }
    const memoryKey = String(exchangeItem.game_id || "").trim() || "_any";
    setLastRoleByGame((prev) => ({ ...prev, [memoryKey]: pickedRoleId }));
    await exchangeMut.mutateAsync({
      goods_id: exchangeItem.goods_id,
      game_id: gameId,
      role_id: pickedRoleId,
    });
  };

  return (
    <ExchangePageTemplate<Shop>
      bindName="塔吉多"
      statusQueryKey={["taygedo-status"]}
      fetchStatus={() => fetchTaygedoStatus(false, true)}
      bindPanel={
        <TaygedoBindPanel
          title="绑定塔吉多账号"
          openRolePickerOnBind={false}
          onSuccess={() => {
            window.setTimeout(() => rolePicker.openPicker(), 0);
          }}
        />
      }
      bindFooter={rolePicker.modal}
      shopQueryKey={["taygedo-exchange", tab]}
      fetchShop={() => fetchTaygedoExchange(tab)}
      balanceLabel="塔塔币"
      balanceValue={(shop) => shop.gold ?? 0}
      balanceExtra={(shop) => {
        const todayGet = shop.today_get ?? 0;
        const todayTotal = shop.today_total ?? 0;
        if (todayTotal <= 0) return null;
        return (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            今日 {todayGet}/{todayTotal}
          </Typography.Text>
        );
      }}
      description="与官方塔吉多同步；完成签到与社区每日任务可获取塔塔币。兑换时再选择发放角色。"
      toolbar={(shop) => {
        const roles = shop.roles || [];
        const tabs = shop.tabs || [];
        const tabItems = tabs.length
          ? tabs.map((t) => ({ key: t.tab, label: t.name || t.tab }))
          : [{ key: "all", label: "全部" }];
        return (
          <>
            {!roles.length ? (
              <Alert
                type="warning"
                showIcon
                message="未找到游戏角色"
                description="请先在塔吉多绑定异环或幻塔角色后再兑换。"
              />
            ) : null}
            <Tabs
              activeKey={tab}
              onChange={setTab}
              items={tabItems}
              size="small"
            />
          </>
        );
      }}
      isEmpty={(shop) => !(shop.items || []).length}
      footer={(shop) => {
        const gold = shop.gold ?? 0;
        const roles = shop.roles || [];
        const gameId = String(exchangeItem?.game_id || "").trim();
        const rolesForItem = !exchangeItem
          ? []
          : gameId
            ? roles.filter((r) => r.game_id === gameId)
            : roles;
        const pickedRole = rolesForItem.find((r) => r.role_id === pickedRoleId);
        return (
          <>
            <TabSync tabs={shop.tabs || []} tab={tab} setTab={setTab} />
            <Modal
              open={Boolean(exchangeItem)}
              title="确认兑换"
              okText="兑换"
              cancelText="取消"
              confirmLoading={Boolean(pendingId)}
              onCancel={() => setExchangeItem(null)}
              onOk={() => submitExchange(roles)}
              destroyOnClose
            >
              {exchangeItem ? (
                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                  <div>
                    <Typography.Text strong>{exchangeItem.name}</Typography.Text>
                    <div style={{ marginTop: 6, color: "#666" }}>
                      消耗塔塔币 {exchangeItem.price}（当前 {gold}）
                    </div>
                  </div>
                  <div>
                    <Typography.Text type="secondary">发放角色</Typography.Text>
                    <Select
                      style={{ width: "100%", marginTop: 6 }}
                      value={pickedRoleId || undefined}
                      onChange={setPickedRoleId}
                      options={rolesForItem.map((r) => ({
                        value: r.role_id,
                        label: `${r.role_name || r.role_id}（${r.game_name || GAME_LABEL[r.game_id] || r.game_id}）`,
                      }))}
                      placeholder="请选择接收角色"
                    />
                    {pickedRole ? (
                      <Typography.Text
                        type="secondary"
                        style={{
                          display: "block",
                          marginTop: 6,
                          fontSize: 12,
                        }}
                      >
                        兑换成功后请到游戏或社区查看。
                      </Typography.Text>
                    ) : null}
                  </div>
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
        return (shop.items || []).map((item) => {
          const label = statusLabel(item);
          const notEnough = gold < item.price;
          const disabled =
            !item.can_exchange ||
            notEnough ||
            pendingId === item.goods_id ||
            Boolean(label);
          const cycleLabel = CYCLE_LABEL[item.cycle_type] || "限购";
          return (
            <ExchangeGoodsCard
              key={item.goods_id}
              imageUrl={item.cover}
              title={item.name}
              subtitle={`${
                item.game_id
                  ? GAME_LABEL[item.game_id] || `游戏 ${item.game_id}`
                  : "塔吉多"
              }${
                item.stock_limited && item.stock > 0
                  ? ` · 库存 ${item.stock}`
                  : ""
              }`}
              badge={
                item.cycle_limit > 0
                  ? `${cycleLabel} ${item.exchange_num}/${item.cycle_limit}`
                  : undefined
              }
              disabled={disabled}
              loading={pendingId === item.goods_id}
              buttonColor="#1677ff"
              buttonLabel={
                label
                  ? label
                  : notEnough
                    ? `塔塔币不足 · ${item.price}`
                    : item.price
              }
              onClick={() => openExchange(item, shop.roles || [])}
            />
          );
        });
      }}
    </ExchangePageTemplate>
  );
}

/** 上游 tabs 变化时校正当前 tab（副作用组件，避免污染 toolbar 返回值语义） */
function TabSync({
  tabs,
  tab,
  setTab,
}: {
  tabs: Shop["tabs"];
  tab: string;
  setTab: (t: string) => void;
}) {
  useEffect(() => {
    if (tabs?.length && !tabs.some((t) => t.tab === tab)) {
      setTab(tabs[0].tab);
    }
  }, [tabs, tab, setTab]);
  return null;
}
