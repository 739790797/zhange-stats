import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiError } from "@/lib/apiError";
import { Modal, Select, Space, Tabs, Typography, message } from "antd";
import { useState } from "react";
import {
  exchangeMihoyoItem,
  fetchMihoyoExchange,
  fetchMihoyoStatus,
} from "@/api/client";
import type { MihoyoExchangeItem, MihoyoExchangeRole } from "@/api/types";
import { MihoyoBindPanel } from "@/components/MihoyoBindPanel";
import { ExchangeGoodsCard } from "@/components/ExchangeGoodsCard";
import { ExchangePageTemplate } from "@/components/ExchangePageTemplate";
import { PlatformIcon } from "@/components/PlatformIcon";
import { useRoleMembershipPicker } from "@/hooks/useRoleMembershipPicker";
import type { PlatformIconName } from "@/lib/platformIcons";

type Shop = Awaited<ReturnType<typeof fetchMihoyoExchange>>;
type GameFilter =
  | "all"
  | "community"
  | "genshin"
  | "bh3"
  | "starrail"
  | "zzz"
  | "bh2";

const GAME_TABS: {
  key: GameFilter;
  label: string;
  icon: PlatformIconName | null;
}[] = [
  { key: "all", label: "全部", icon: null },
  { key: "community", label: "米游社", icon: "mihoyo" },
  { key: "genshin", label: "原神", icon: "genshin" },
  { key: "bh3", label: "崩坏3", icon: "bh3" },
  { key: "starrail", label: "星穹铁道", icon: "starrail" },
  { key: "zzz", label: "绝区零", icon: "zzz" },
  { key: "bh2", label: "崩坏2", icon: "bh2" },
];

function itemGameKey(item: MihoyoExchangeItem): Exclude<GameFilter, "all"> {
  const code = String(item.game_code || "").trim();
  if (
    code === "genshin" ||
    code === "bh3" ||
    code === "starrail" ||
    code === "zzz" ||
    code === "bh2"
  ) {
    return code;
  }
  return "community";
}

function needsRole(item: MihoyoExchangeItem) {
  return Boolean((item.game_biz || "").trim());
}

function notYetOpen(item: MihoyoExchangeItem) {
  const next = Date.parse(String(item.next_exchange_time || ""));
  return Number.isFinite(next) && next > Date.now();
}

function itemStatus(item: MihoyoExchangeItem, points: number) {
  if (notYetOpen(item)) return "未开兑";
  if (item.exchange_limit > 0 && item.exchanged_count >= item.exchange_limit) {
    return "已兑完";
  }
  if (points < item.price) return `米游币不足 · ${item.price}`;
  return null;
}

export function MihoyoExchangePanel() {
  const queryClient = useQueryClient();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [gameFilter, setGameFilter] = useState<GameFilter>("all");
  const [lastRoleByGame, setLastRoleByGame] = useState<Record<string, string>>(
    {},
  );
  const [exchangeItem, setExchangeItem] = useState<MihoyoExchangeItem | null>(
    null,
  );
  const [pickedRoleUid, setPickedRoleUid] = useState<string>("");
  const [pickedRegion, setPickedRegion] = useState<string>("");
  const rolePicker = useRoleMembershipPicker("mihoyo");

  const exchangeMut = useMutation({
    mutationFn: (payload: {
      goods_id: string;
      game_biz?: string;
      region?: string;
      role_uid?: string;
    }) => exchangeMihoyoItem(payload),
    onMutate: (payload) => setPendingId(payload.goods_id),
    onSettled: () => setPendingId(null),
    onSuccess: (data) => {
      message.success(data.message || "兑换成功");
      setExchangeItem(null);
      queryClient.invalidateQueries({ queryKey: ["mihoyo-exchange"] });
      queryClient.invalidateQueries({ queryKey: ["mihoyo-status"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "兑换失败")),
  });

  const openExchange = (
    item: MihoyoExchangeItem,
    roles: MihoyoExchangeRole[],
  ) => {
    if (needsRole(item)) {
      const matched = roles.filter(
        (r) =>
          (item.game_biz && r.game_biz === item.game_biz) ||
          (item.game_code && r.game_code === item.game_code),
      );
      const key = itemGameKey(item);
      const last = lastRoleByGame[key];
      const preferredRole =
        matched.find((r) => r.role_uid === last) || matched[0] || null;
      setPickedRoleUid(preferredRole?.role_uid || "");
      setPickedRegion(preferredRole?.region || "");
      setExchangeItem(item);
      return;
    }
    setPickedRoleUid("");
    setPickedRegion("");
    setExchangeItem(item);
  };

  const submitExchange = async () => {
    if (!exchangeItem) return;
    if (needsRole(exchangeItem) && !pickedRoleUid) {
      message.error("请选择接收角色");
      return;
    }
    const key = itemGameKey(exchangeItem);
    if (needsRole(exchangeItem)) {
      setLastRoleByGame((prev) => ({ ...prev, [key]: pickedRoleUid }));
    }
    await exchangeMut.mutateAsync({
      goods_id: exchangeItem.goods_id,
      game_biz: exchangeItem.game_biz || undefined,
      region: pickedRegion || undefined,
      role_uid: pickedRoleUid || undefined,
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
      description="与米游社米游币商城同步；兑换游戏道具时选择发放角色，实物使用米游社默认收货地址。"
      toolbar={() => (
        <Tabs
          activeKey={gameFilter}
          onChange={(k) => setGameFilter(k as GameFilter)}
          items={GAME_TABS.map((t) => ({
            key: t.key,
            label: (
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                {t.icon ? <PlatformIcon name={t.icon} size={16} /> : null}
                {t.label}
              </span>
            ),
          }))}
          size="small"
        />
      )}
      isEmpty={(shop) => {
        const items = shop.items || [];
        if (gameFilter === "all") return items.length === 0;
        return !items.some((it) => itemGameKey(it) === gameFilter);
      }}
      footer={(shop) => {
        const points = shop.points ?? 0;
        const roles = shop.roles || [];
        const roleOptions = !exchangeItem
          ? []
          : needsRole(exchangeItem)
            ? roles.filter(
                (r) =>
                  (exchangeItem.game_biz &&
                    r.game_biz === exchangeItem.game_biz) ||
                  (exchangeItem.game_code &&
                    r.game_code === exchangeItem.game_code),
              )
            : [];
        return (
          <>
            <Modal
              open={Boolean(exchangeItem)}
              title="确认兑换"
              okText="兑换"
              cancelText="取消"
              confirmLoading={Boolean(pendingId)}
              onCancel={() => setExchangeItem(null)}
              onOk={submitExchange}
              destroyOnClose
            >
              {exchangeItem ? (
                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                  <div>
                    <Typography.Text strong>
                      {exchangeItem.goods_name}×{exchangeItem.goods_num}
                    </Typography.Text>
                    <div style={{ marginTop: 6, color: "#666" }}>
                      消耗米游币 {exchangeItem.price}（当前 {points}）
                    </div>
                  </div>
                  {needsRole(exchangeItem) ? (
                    <div>
                      <Typography.Text type="secondary">发放角色</Typography.Text>
                      <Select
                        style={{ width: "100%", marginTop: 6 }}
                        value={pickedRoleUid || undefined}
                        onChange={(uid) => {
                          setPickedRoleUid(uid);
                          const hit = roleOptions.find((r) => r.role_uid === uid);
                          setPickedRegion(hit?.region || "");
                        }}
                        options={roleOptions.map((r) => ({
                          value: r.role_uid,
                          label: `${r.role_name || r.role_uid}${
                            r.channel_name ? ` · ${r.channel_name}` : ""
                          }`,
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
        const points = shop.points ?? 0;
        const items = shop.items || [];
        const filtered =
          gameFilter === "all"
            ? items
            : items.filter((it) => itemGameKey(it) === gameFilter);
        return filtered.map((item) => {
          const label = itemStatus(item, points);
          const disabled = Boolean(label);
          const remain =
            item.exchange_limit > 0
              ? Math.max(item.exchange_limit - item.exchanged_count, 0)
              : null;
          return (
            <ExchangeGoodsCard
              key={item.goods_id}
              imageUrl={item.goods_img || undefined}
              title={`${item.goods_name}×${item.goods_num}`}
              subtitle={item.game_name || "米游社"}
              badge={
                remain != null ? `限兑 ${item.exchanged_count}/${item.exchange_limit}` : null
              }
              disabled={disabled}
              loading={pendingId === item.goods_id}
              buttonLabel={label || item.price}
              onClick={() => openExchange(item, shop.roles || [])}
            />
          );
        });
      }}
    </ExchangePageTemplate>
  );
}
