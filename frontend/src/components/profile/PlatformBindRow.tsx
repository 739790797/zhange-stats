import { Button, Popconfirm } from "antd";
import { BindActionSlots } from "@/components/profile/BindActionSlots";
import { BindStatusTitle } from "@/components/profile/BindStatusTitle";

type PlatformBindRowProps = {
  name: string;
  bound: boolean;
  /** 已绑定时凭证是否可用；false = 失效 */
  credentialOk?: boolean | null;
  errMsg: string | null;
  borderTop?: boolean;
  unbindConfirmTitle: string;
  unbindPending: boolean;
  onOpenModal: () => void;
  onUnbind: () => void;
  /** 已绑定时：打开该平台角色选用 */
  onOpenRoles?: () => void;
};

export function PlatformBindRow({
  name,
  bound,
  credentialOk,
  errMsg,
  borderTop = false,
  unbindConfirmTitle,
  unbindPending,
  onOpenModal,
  onUnbind,
  onOpenRoles,
}: PlatformBindRowProps) {
  const invalid = bound && credentialOk === false;

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
        <BindStatusTitle
          name={name}
          bound={bound}
          credentialOk={credentialOk}
        />
      </div>
      <BindActionSlots
        roles={
          bound && onOpenRoles ? (
            <Button
              block
              disabled={!!errMsg || invalid}
              onClick={onOpenRoles}
            >
              角色
            </Button>
          ) : undefined
        }
        primary={
          <Button
            block
            type={bound ? (invalid ? "primary" : "default") : "primary"}
            disabled={!!errMsg}
            onClick={onOpenModal}
          >
            {bound ? (invalid ? "重新绑定" : "换绑") : "绑定"}
          </Button>
        }
        danger={
          bound ? (
            <Popconfirm
              title={unbindConfirmTitle}
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
