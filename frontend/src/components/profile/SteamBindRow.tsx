import { Avatar, Button, Popconfirm, Typography } from "antd";
import { Link } from "react-router-dom";
import type { MemberProfile } from "@/api/types";
import { BindActionSlots } from "@/components/profile/BindActionSlots";
import { BindStatusTitle } from "@/components/profile/BindStatusTitle";

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
            steamBound ? (
              <Avatar size={28} src={data?.steam_avatar_url || undefined}>
                S
              </Avatar>
            ) : null
          }
        />
        {steamBound ? (
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 13 }}>
              {`${data?.steam_persona_name || "已绑定"} · SteamID：${data?.steam_id}${
                data?.steam_friends_public === false
                  ? " · 好友列表未公开（日历只能看自己）"
                  : data?.steam_friends_public
                    ? " · 好友列表已同步"
                    : ""
              }`}
            </Typography.Text>
          </div>
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
