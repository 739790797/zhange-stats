import { QqOutlined } from "@ant-design/icons";
import { Avatar, Button, Popconfirm, Typography } from "antd";
import type { MemberProfile } from "@/api/types";
import { BindActionSlots } from "@/components/profile/BindActionSlots";
import {
  BIND_ROW_ICON_SIZE,
  BindStatusTitle,
} from "@/components/profile/BindStatusTitle";

function QqBindMark() {
  return (
    <span
      className="anticon"
      role="img"
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: BIND_ROW_ICON_SIZE,
        height: BIND_ROW_ICON_SIZE,
        borderRadius: Math.max(2, Math.round(BIND_ROW_ICON_SIZE * 0.22)),
        background: "#12b7f5",
        color: "#fff",
        fontSize: Math.round(BIND_ROW_ICON_SIZE * 0.62),
        flexShrink: 0,
      }}
    >
      <QqOutlined />
    </span>
  );
}

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
              <Avatar size={BIND_ROW_ICON_SIZE} src={data.qq_avatar_url}>
                Q
              </Avatar>
            ) : (
              <QqBindMark />
            )
          }
        >
          {qqBound ? (
            <Typography.Text type="secondary" style={{ fontSize: 13 }}>
              {`昵称：${data?.qq_nickname || "已绑定"}`}
            </Typography.Text>
          ) : null}
        </BindStatusTitle>
      </div>
      <BindActionSlots
        primary={
          <Button
            block
            type={qqBound ? "default" : "primary"}
            loading={startBindPending}
            disabled={!!errMsg}
            onClick={onStartBind}
          >
            {qqBound ? "换绑" : "绑定"}
          </Button>
        }
        danger={
          qqBound ? (
            <Popconfirm
              title="确认解除 QQ 绑定？"
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
