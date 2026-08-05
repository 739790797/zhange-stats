import { Button, Popconfirm, Space } from "antd";
import { BindStatusTitle } from "@/components/profile/BindStatusTitle";

type PlatformBindRowProps = {
  name: string;
  bound: boolean;
  errMsg: string | null;
  borderTop?: boolean;
  unbindConfirmTitle: string;
  unbindPending: boolean;
  onOpenModal: () => void;
  onUnbind: () => void;
};

export function PlatformBindRow({
  name,
  bound,
  errMsg,
  borderTop = false,
  unbindConfirmTitle,
  unbindPending,
  onOpenModal,
  onUnbind,
}: PlatformBindRowProps) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 16,
        padding: "16px 4px",
        borderTop: borderTop ? "1px solid rgba(0,0,0,0.06)" : undefined,
      }}
    >
      <div style={{ minWidth: 0 }}>
        <BindStatusTitle name={name} bound={bound} />
      </div>
      <Space>
        {bound ? (
          <>
            <Button disabled={!!errMsg} onClick={onOpenModal}>
              换绑
            </Button>
            <Popconfirm
              title={unbindConfirmTitle}
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
          <Button type="primary" disabled={!!errMsg} onClick={onOpenModal}>
            绑定
          </Button>
        )}
      </Space>
    </div>
  );
}
