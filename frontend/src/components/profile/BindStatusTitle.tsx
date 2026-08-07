import { Tag, Typography } from "antd";
import type { ReactNode } from "react";

/** 绑定行标题：名称定宽，状态标签纵向对齐 */
export function BindStatusTitle({
  name,
  bound,
  /** 已绑定时：false 表示凭证探测失败（失效） */
  credentialOk,
  leading,
}: {
  name: string;
  bound: boolean;
  credentialOk?: boolean | null;
  leading?: ReactNode;
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
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      {leading}
      <Typography.Text
        strong
        style={{ width: "3.75em", flex: "0 0 3.75em", lineHeight: "22px" }}
      >
        {name}
      </Typography.Text>
      {statusTag}
    </div>
  );
}
