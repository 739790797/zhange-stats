import { Button, Typography } from "antd";
import { useState, type ReactNode } from "react";

export type ExchangeGoodsCardProps = {
  imageUrl?: string | null;
  title: ReactNode;
  subtitle?: ReactNode;
  /** 右上角角标，如「每日限购 1/3」 */
  badge?: ReactNode;
  buttonLabel: ReactNode;
  disabled?: boolean;
  loading?: boolean;
  /** 可兑时按钮底色；禁用时走 Ant Design 默认灰 */
  buttonColor?: string;
  onClick: () => void;
};

/** 兑换商城商品卡：图 + 标题 + 底栏价格/状态按钮 */
export function ExchangeGoodsCard({
  imageUrl,
  title,
  subtitle,
  badge,
  buttonLabel,
  disabled = false,
  loading = false,
  buttonColor,
  onClick,
}: ExchangeGoodsCardProps) {
  const [imgFailed, setImgFailed] = useState(false);
  const faded = disabled && !loading;

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
        opacity: faded ? 0.72 : 1,
      }}
    >
      {badge ? (
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
          {badge}
        </div>
      ) : null}

      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "28px 12px 8px",
          gap: 8,
        }}
      >
        {!imgFailed && imageUrl ? (
          <img
            src={imageUrl}
            alt={typeof title === "string" ? title : ""}
            width={96}
            height={96}
            style={{ objectFit: "contain" }}
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={() => setImgFailed(true)}
          />
        ) : (
          <div
            style={{
              width: 96,
              height: 96,
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
          {title}
        </Typography.Text>
        {subtitle ? (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {subtitle}
          </Typography.Text>
        ) : null}
      </div>

      <Button
        type="primary"
        disabled={disabled}
        loading={loading}
        onClick={onClick}
        style={{
          borderRadius: 0,
          height: 40,
          background: disabled ? undefined : buttonColor,
          borderColor: disabled ? undefined : buttonColor,
        }}
        block
      >
        {buttonLabel}
      </Button>
    </div>
  );
}
