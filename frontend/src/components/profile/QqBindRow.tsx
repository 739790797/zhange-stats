import { Avatar, Button, Popconfirm, Space, Typography } from "antd";
import type { MemberProfile } from "@/api/types";
import { BindStatusTitle } from "@/components/profile/BindStatusTitle";

type QqBindRowProps = {
  data: MemberProfile | undefined;
  qqBound: boolean;
  errMsg: string | null;
  startBindPending: boolean;
  unbindPending: boolean;
  onStartBind: () => void;
  onUnbind: () => void;
};

export function QqBindRow({
  data,
  qqBound,
  errMsg,
  startBindPending,
  unbindPending,
  onStartBind,
  onUnbind,
}: QqBindRowProps) {
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
          name="QQ"
          bound={qqBound}
          leading={
            qqBound && data?.qq_avatar_url ? (
              <Avatar size={28} src={data.qq_avatar_url}>
                Q
              </Avatar>
            ) : null
          }
        />
        {qqBound ? (
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 13 }}>
              {`昵称：${data?.qq_nickname || "已绑定"}`}
            </Typography.Text>
          </div>
        ) : null}
      </div>
      <Space>
        {qqBound ? (
          <>
            <Button
              loading={startBindPending}
              disabled={!!errMsg}
              onClick={onStartBind}
            >
              换绑
            </Button>
            <Popconfirm
              title="确认解除 QQ 绑定？"
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
