import { Avatar, Button, Popconfirm, Space, Typography } from "antd";
import type { MemberProfile } from "@/api/types";
import { BindStatusTitle } from "@/components/profile/BindStatusTitle";

type SteamBindRowProps = {
  data: MemberProfile | undefined;
  steamBound: boolean;
  errMsg: string | null;
  startBindPending: boolean;
  unbindPending: boolean;
  onStartBind: () => void;
  onUnbind: () => void;
};

export function SteamBindRow({
  data,
  steamBound,
  errMsg,
  startBindPending,
  unbindPending,
  onStartBind,
  onUnbind,
}: SteamBindRowProps) {
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
      </div>
      <Space>
        {steamBound ? (
          <>
            <Button
              loading={startBindPending}
              disabled={!!errMsg}
              onClick={onStartBind}
            >
              换绑
            </Button>
            <Popconfirm
              title="确认解除 Steam 绑定？"
              okText="确定"
              cancelText="取消"
              onConfirm={onUnbind}
            >
              <Button danger loading={unbindPending} disabled={!!errMsg}>
                解绑
              </Button>
            </Popconfirm>
          </>
        ) : (
          <Button
            type="primary"
            loading={startBindPending}
            disabled={!!errMsg}
            onClick={onStartBind}
          >
            绑定
          </Button>
        )}
      </Space>
    </div>
  );
}
