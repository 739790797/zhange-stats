import { Tag, Typography } from "antd";
import { Children, type ReactNode } from "react";

/** 绑定行左侧图标槽：与 Steam/QQ 头像同尺寸，保证跨行名称与状态标签对齐 */
export const BIND_ROW_ICON_SIZE = 28;
const BIND_ROW_ICON_GAP = 8;

/** 绑定行标题：图标定宽、名称定宽，状态标签纵向对齐 */
export function BindStatusTitle({
  name,
  bound,
  /** 已绑定时：false 表示凭证探测失败（失效） */
  credentialOk,
  leading,
  children,
}: {
  name: string;
  bound: boolean;
  credentialOk?: boolean | null;
  leading?: ReactNode;
  children?: ReactNode;
}) {
  let statusTag: ReactNode;
  if (!bound) {
    statusTag = <Tag>未绑定</Tag>;
  } else if (credentialOk === false) {
    statusTag = <Tag color="error">凭证失效</Tag>;
  } else {
    statusTag = <Tag color="success">已绑定</Tag>;
  }

  return (
    <div>
      <div
        style={{ display: "flex", alignItems: "center", gap: BIND_ROW_ICON_GAP }}
      >
        <span
          style={{
            width: BIND_ROW_ICON_SIZE,
            height: BIND_ROW_ICON_SIZE,
            flex: `0 0 ${BIND_ROW_ICON_SIZE}px`,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {leading}
        </span>
        <Typography.Text
          strong
          style={{ width: "3.75em", flex: "0 0 3.75em", lineHeight: "22px" }}
        >
          {name}
        </Typography.Text>
        {statusTag}
      </div>
      {Children.toArray(children).some(Boolean) ? (
        <div style={{ marginLeft: BIND_ROW_ICON_SIZE + BIND_ROW_ICON_GAP }}>
          {children}
        </div>
      ) : null}
    </div>
  );
}
