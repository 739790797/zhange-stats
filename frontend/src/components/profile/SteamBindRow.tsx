import { Avatar, Button, Popconfirm, Typography } from "antd";
import { Link } from "react-router-dom";
import type { MemberProfile } from "@/api/types";
import { PlatformIcon } from "@/components/PlatformIcon";
import { BindActionSlots } from "@/components/profile/BindActionSlots";
import {
  BIND_ROW_ICON_SIZE,
  BindStatusTitle,
} from "@/components/profile/BindStatusTitle";

type SteamBindRowProps = {
  data: MemberProfile | undefined;
  steamBound: boolean;
  errMsg: string | null;
  startBindPending: boolean;
  unbindPending: boolean;
  onStartBind: () => void;
  onUnbind: () => void;
  /** undefined = 加载中；false = 未配置 API Key */
  steamConfigured?: boolean;
  isAdmin?: boolean;
};

export function SteamBindRow({
  data,
  steamBound,
  errMsg,
  startBindPending,
  unbindPending,
  onStartBind,
  onUnbind,
  steamConfigured,
  isAdmin = false,
}: SteamBindRowProps) {
  const notConfigured = steamConfigured === false;
  const bindDisabled = !!errMsg || notConfigured || steamConfigured === undefined;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 16,
        padding: "16px 4px",
        borderBottom: "1px solid rgba(0,0,0,0.06)",
      }}
    >
      <div style={{ minWidth: 0 }}>
        <BindStatusTitle
          name="Steam"
          bound={steamBound}
          leading={
            steamBound && data?.steam_avatar_url ? (
              <Avatar size={BIND_ROW_ICON_SIZE} src={data.steam_avatar_url}>
                S
              </Avatar>
            ) : (
              <PlatformIcon name="steam" size={BIND_ROW_ICON_SIZE} />
            )
          }
        >
          {steamBound ? (
            <Typography.Text type="secondary" style={{ fontSize: 13 }}>
              {`${data?.steam_persona_name || "已绑定"} · SteamID：${data?.steam_id}`}
            </Typography.Text>
          ) : null}
          {notConfigured ? (
            <div>
              <Typography.Text type="warning" style={{ fontSize: 13 }}>
                {isAdmin ? (
                  <>
                    尚未配置 API Key，请先在{" "}
                    <Link to="/settings/integrations">集成密钥</Link> 填写后才能
                    {steamBound ? "换绑" : "绑定"}
                  </>
                ) : (
                  `管理员尚未配置 Steam API Key，暂无法${steamBound ? "换绑" : "绑定"}`
                )}
              </Typography.Text>
            </div>
          ) : null}
        </BindStatusTitle>
      </div>
      <BindActionSlots
        primary={
          <Button
            block
            type={steamBound ? "default" : "primary"}
            loading={startBindPending}
            disabled={bindDisabled}
            onClick={onStartBind}
          >
            {steamBound ? "换绑" : "绑定"}
          </Button>
        }
        danger={
          steamBound ? (
            <Popconfirm
              title="确认解除 Steam 绑定？"
              okText="确定"
              cancelText="取消"
              onConfirm={onUnbind}
            >
              <Button block danger loading={unbindPending} disabled={!!errMsg}>
                解绑
              </Button>
            </Popconfirm>
          ) : undefined
        }
      />
    </div>
  );
}
