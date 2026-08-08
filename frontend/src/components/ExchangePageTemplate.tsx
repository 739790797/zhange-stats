import { useQuery } from "@tanstack/react-query";
import { apiError } from "@/lib/apiError";
import { Alert, Card, Empty, Space, Typography } from "antd";
import type { ReactNode } from "react";

/** 兑换页绑定门禁所需的最小 status 面 */
export type ExchangeBindStatus = {
  bound: boolean;
  token_ok?: boolean | null;
  token_error?: string | null;
};

export type ExchangePageTemplateProps<TShop> = {
  /** 绑定源名称，如「追放社区」「库街区」「塔吉多」 */
  bindName: string;
  /** 未绑定 Alert 主文案；默认「尚未绑定{bindName}」 */
  unboundMessage?: string;
  statusQueryKey: unknown[];
  fetchStatus: () => Promise<ExchangeBindStatus>;
  bindPanel: ReactNode;
  /** 未绑定视图底部（通常是 rolePicker.modal） */
  bindFooter?: ReactNode;

  shopQueryKey: unknown[];
  fetchShop: () => Promise<TShop>;

  balanceLabel: string;
  balanceValue: (shop: TShop) => number;
  balanceExtra?: (shop: TShop) => ReactNode;
  /** 「兑换商城」副文案 */
  description: string;

  /** 余额卡下方、商品网格上方（Tabs / 提示等） */
  toolbar?: (shop: TShop) => ReactNode;
  /** 商品网格内容（通常 map → ExchangeGoodsCard） */
  children: (shop: TShop) => ReactNode;
  isEmpty: (shop: TShop) => boolean;
  emptyDescription?: string;
  /** 网格下方（确认 Modal、rolePicker.modal 等） */
  footer?: (shop: TShop) => ReactNode;
};

/**
 * 平台兑换页骨架：绑定门禁 → 加载商城 → 余额卡 + 说明 → toolbar → 商品网格。
 * 商品字段 / 确认兑换流由调用方通过 children / footer 注入。
 */
export function ExchangePageTemplate<TShop>({
  bindName,
  unboundMessage,
  statusQueryKey,
  fetchStatus,
  bindPanel,
  bindFooter,
  shopQueryKey,
  fetchShop,
  balanceLabel,
  balanceValue,
  balanceExtra,
  description,
  toolbar,
  children,
  isEmpty,
  emptyDescription = "暂无可兑换物品",
  footer,
}: ExchangePageTemplateProps<TShop>) {
  const statusQuery = useQuery({
    queryKey: statusQueryKey,
    queryFn: fetchStatus,
    retry: false,
    staleTime: 30_000,
  });

  const bound = Boolean(statusQuery.data?.bound);
  const tokenBroken = bound && statusQuery.data?.token_ok === false;
  const canUse = bound && !tokenBroken;

  const shopQuery = useQuery({
    queryKey: shopQueryKey,
    queryFn: fetchShop,
    enabled: canUse,
    retry: false,
  });

  if (statusQuery.isLoading) {
    return <Card loading />;
  }

  if (!bound || tokenBroken) {
    return (
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Alert
          type={tokenBroken ? "warning" : "info"}
          showIcon
          message={
            tokenBroken
              ? `${bindName}凭证可能已失效`
              : unboundMessage || `尚未绑定${bindName}`
          }
          description={
            tokenBroken
              ? statusQuery.data?.token_error || "请重新绑定后再兑换。"
              : undefined
          }
        />
        <Card>{bindPanel}</Card>
        {bindFooter}
      </Space>
    );
  }

  if (shopQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="加载兑换商城失败"
        description={apiError(shopQuery.error, "请稍后重试")}
      />
    );
  }

  if (shopQuery.isLoading || !shopQuery.data) {
    return <Card loading />;
  }

  const shop = shopQuery.data;

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
            {balanceLabel}
          </Typography.Text>
          <Typography.Text
            strong
            style={{ fontSize: 28, color: "#d48806", lineHeight: 1.2 }}
          >
            {balanceValue(shop)}
          </Typography.Text>
          {balanceExtra?.(shop)}
        </Card>
        <Card size="small" style={{ flex: 1, minWidth: 180 }}>
          <Typography.Text strong style={{ fontSize: 16 }}>
            兑换商城
          </Typography.Text>
          <Typography.Paragraph
            type="secondary"
            style={{ margin: "6px 0 0", fontSize: 13 }}
          >
            {description}
          </Typography.Paragraph>
        </Card>
      </div>

      {toolbar?.(shop)}

      {isEmpty(shop) ? (
        <Empty description={emptyDescription} />
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: 16,
          }}
        >
          {children(shop)}
        </div>
      )}

      {footer?.(shop)}
    </Space>
  );
}
